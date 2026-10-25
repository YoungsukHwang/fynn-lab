"""Recorded demo exchanges for the static site, from results files only. No API calls."""

import json
from pathlib import Path

import pytest

from evals.demo_snapshot import build_snapshot, main
from fynn.skills import SkillLibrary

U = {"input_tokens": 1000, "output_tokens": 300, "cache_read_input_tokens": 2000, "cache_creation_input_tokens": 0}
R = {"input_tokens": 400, "output_tokens": 40, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


def _case(passed: bool, selected: list[str], strategy: str = "skills") -> dict:
    return {
        "id": "mi-001", "dataset": "multi_intent", "persona": "rebuilder", "message": "Why did my score drop?",
        "routing": {"strategy": strategy, "selected": selected, "carried": [], "reason": "r", "error": None, "usage": R},
        "reply": "reply", "checks": {"passed": True, "failures": []},
        "judge": {"facts": [{"fact": "f1", "status": "PRESENT" if passed else "ABSENT", "note": "n"}], "passed": passed},
        "passed": passed, "status": "ok", "usage": U, "agent_model": "claude-sonnet-5-5",
        "repeats": 3, "passes": 3 if passed else 0,
    }


def _run(bot: str, case: dict) -> dict:
    return {"name": bot, "bot": bot, "created_at": "2026-10-23T00:00:00+00:00",
            "models": {"router": "r", "agent": "claude-sonnet-5-5", "judge": "j"}, "cases": [case]}


def test_snapshot_keeps_both_replies_with_routing_tokens_and_facts() -> None:
    before = _run("before", _case(False, ["score-and-reports"], "single_agent"))
    after = _run("after", _case(True, ["score-changes", "secured-card"]))
    snap = build_snapshot(before, after, SkillLibrary.load(), cases=(("mi-001", "Example"),))
    (ex,) = snap["exchanges"]
    assert (ex["id"], ex["label"], ex["persona"]) == ("mi-001", "Example", "rebuilder")
    assert ex["before"]["routing"]["selected"] == ["score-and-reports"] and "usage" not in ex["before"]["routing"]
    assert ex["after"]["usage"] == {"input_tokens": 1400, "output_tokens": 340, "cache_read_input_tokens": 2000,
                                    "cache_creation_input_tokens": 0}  # router plus answer, as the API reports
    assert (ex["before"]["passes"], ex["after"]["passes"], ex["after"]["repeats"]) == (0, 3, 3)
    assert ex["after"]["facts"] == [{"fact": "f1", "status": "PRESENT"}]
    assert {d["id"] for d in snap["architecture"]["domains"]} >= {"score-and-reports"}
    assert any(p["id"] == "rebuilder" for p in snap["personas"])
    assert snap["sources"]["after"] == {"name": "after", "created_at": "2026-10-23T00:00:00+00:00"}


def test_snapshot_refuses_mismatched_files() -> None:
    after = _run("after", _case(True, ["score-changes"]))
    with pytest.raises(ValueError, match="Before bot run"):
        build_snapshot(after, after, SkillLibrary.load(), cases=(("mi-001", "x"),))
    other = _run("before", {**_case(False, []), "message": "something else"})
    with pytest.raises(ValueError, match="different message"):
        build_snapshot(other, after, SkillLibrary.load(), cases=(("mi-001", "x"),))
    with pytest.raises(ValueError, match="not in both"):
        build_snapshot(_run("before", _case(False, [])), after, SkillLibrary.load(), cases=(("st-404", "x"),))


def test_cli_writes_the_committed_cases(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    out = tmp_path / "recorded.json"
    snap = main(["--before", str(repo / "results" / "before.json"), "--after", str(repo / "results" / "after.json"),
                 "--out", str(out)])
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(json.dumps(snap))
    assert [e["id"] for e in snap["exchanges"]] == ["mi-001", "mi-010", "mi-015", "st-011"]
