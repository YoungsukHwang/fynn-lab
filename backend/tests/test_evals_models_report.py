"""Answer model and judge report, from results files only. No API calls."""

import json
from pathlib import Path
from typing import Any

import pytest

import evals.cases
import evals.models_report as mr
from evals.judge_validation import _sha
from fynn.skills import SkillLibrary

FIXTURE_CASES = Path(__file__).parent / "fixtures" / "eval_cases"
U = {"input_tokens": 1000, "output_tokens": 100, "cache_read_input_tokens": 2000, "cache_creation_input_tokens": 0}
# Large enough that a judge run costs whole cents, so cost_per_run is checked, not rounded away.
JUDGE_USAGE = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
ROUTER = {"input_tokens": 400, "output_tokens": 40, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}


def _case(case_id: str, skills: list[str], passed: bool, words: int = 100, routing_usage: dict | None = None) -> dict[str, Any]:
    routing: dict[str, Any] = {"strategy": "skills", "selected": skills, "carried": []}
    if routing_usage is not None:
        routing["usage"] = routing_usage
    return {
        "id": case_id, "skills": skills, "status": "ok", "passed": passed, "reply": " ".join(["w"] * words),
        "agent_model": "claude-sonnet-5-5", "usage": dict(U), "routing": routing,
        "judge": {"passed": passed, "facts": [{"fact": "f1", "status": "PRESENT" if passed else "ABSENT"}]},
    }


def _run(agent: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {"created_at": "2026-10-23T00:00:00+00:00",
            "models": {"router": "claude-haiku-5-5", "agent": agent, "judge": "claude-opus-5-5"}, "cases": cases}


def test_cost_uses_list_prices_and_the_cache_write_premium() -> None:
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_input_tokens": 1_000_000,
             "cache_creation_input_tokens": 1_000_000}
    assert mr.cost(usage, "claude-sonnet-5-5") == pytest.approx(2 + 1 + 0.2 + 2.5)
    assert mr.cost(usage, "some-other-model") is None


def test_split_takes_the_router_off_an_old_style_answer() -> None:
    old = _case("st-001", ["score-changes"], True)
    answer, router, estimated = mr._split(old, {"st-001": ROUTER})
    assert answer["input_tokens"] == 600 and answer["output_tokens"] == 60 and router == ROUTER and estimated
    new = _case("st-001", ["score-changes"], True, routing_usage=ROUTER)
    assert mr._split(new, {}) == (U, ROUTER, False)  # already split by the runner
    assert mr._split(old, {})[2] is True  # no router record to split with: still an estimate


def test_model_row_counts_groups_facts_lengths_and_cost(mini_library: SkillLibrary) -> None:
    results = _run("claude-sonnet-5-5", [
        _case("st-001", ["score-changes"], True, words=120),
        _case("mi-001", ["score-changes", "secured-card"], True, words=320),  # passes, but over 300 words
        _case("st-002", ["rent-reporting"], False),
    ])
    row = mr.model_row("after-sonnet", results, {}, mini_library)
    assert (row["passed"], row["cases"], row["errors"]) == (2, 3, 0)
    assert row["by_group"] == {"cross": {"cases": 1, "passed": 1}, "single": {"cases": 2, "passed": 1}}
    assert row["facts"] == {"present": 2, "graded": 3}
    assert row["passed_if_over_300_fails"] == 1
    assert row["lengths"]["over_limit"] == 1
    per_case = (1000 * 2 + 100 * 10 + 2000 * 0.2) / 1e6
    assert row["cost_per_1000"] == {"answer": round(per_case * 1000, 2), "router": 0.0, "total": round(per_case * 1000, 2),
                                    "estimated_split": True}


def test_paired_counts_flips_with_and_without_the_length_cap() -> None:
    a = _run("m1", [_case("c1", [], True), _case("c2", [], False), _case("c3", [], True, words=400)])
    b = _run("m2", [_case("c1", [], True), _case("c2", [], True), _case("c3", [], True)])
    assert mr.paired(a, b) == {"cases": 3, "up": 1, "down": 0, "p": 1.0}
    assert mr.paired(a, b, cap=True)["up"] == 2  # c3 fails on a once its 400 words count


def _regrade(label: str, model: str, source: str, rows: list[tuple[str, bool]]) -> dict[str, Any]:
    return {
        "kind": "judge_regrade", "label": label, "source": source, "complete": True,
        "models": {"answer": "m", "judge": model},
        "cases": [{"id": cid, "status": "ok", "reply_sha": _sha(" ".join(["w"] * 100)),
                   "judge": {"passed": ok, "facts": [{"fact": "f1", "status": "PRESENT" if ok else "ABSENT"}],
                             "usage": dict(JUDGE_USAGE)}}
                  for cid, ok in rows],
    }


def test_judge_rows_sum_flips_and_agreement_over_runs() -> None:
    runs = {
        "after-a": _run("m", [_case("c1", [], True), _case("c2", [], False)]),
        "after-b": _run("m", [_case("c1", [], True), _case("c2", [], True)]),
    }
    regrades = [
        _regrade("cheap", "claude-haiku-5-5", "after-a", [("c1", True), ("c2", True)]),  # one verdict changes
        _regrade("cheap", "claude-haiku-5-5", "after-b", [("c1", True), ("c2", True)]),
    ]
    [row] = mr.judge_rows(runs, regrades, [])
    assert (row["label"], row["replies"], row["facts"], row["facts_agree"], row["verdict_flips"]) == ("cheap", 4, 4, 3, 1)
    assert row["fact_agreement"] == 0.75
    assert row["by_source"]["after-a"]["lenient"] == 1
    # Two replies per run at $0.15 each (Haiku: $0.10 input + $0.05 output), over two runs.
    assert row["cost_per_run"] == 0.30


def test_build_report_orders_by_cost_and_compares_neighbours(mini_library: SkillLibrary) -> None:
    runs = {
        "after-opus": _run("claude-opus-5-5", [_case("c1", [], True)]),
        "after-haiku": _run("claude-haiku-5-5", [_case("c1", [], False)]),
        "after-sonnet": _run("claude-sonnet-5-5", [_case("c1", [], True)]),
    }
    report = mr.build_report(runs, None, [], [], mini_library)
    assert [r["source"] for r in report["models"]] == ["after-haiku", "after-sonnet", "after-opus"]
    assert [(p["a"], p["b"]) for p in report["paired"]] == [
        ("after-haiku", "after-sonnet"), ("after-sonnet", "after-opus"), ("after-haiku", "after-opus")]
    assert report["router_usage_from"] is None
    assert mr.render_markdown(report).startswith("# Answer model and judge")


def test_cli_writes_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    paths = []
    for name, agent in (("after-haiku", "claude-haiku-5-5"), ("after-sonnet", "claude-sonnet-5-5")):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(_run(agent, [_case("st-001", ["score-changes"], True)])), encoding="utf-8")
        paths.append(str(path))
    router = tmp_path / "after.json"
    router.write_text(json.dumps({**_run("claude-sonnet-5-5", [_case("st-001", ["score-changes"], True, routing_usage=ROUTER)]),
                                  "name": "after"}), encoding="utf-8")
    report = mr.main(["--runs", *paths, "--router-from", str(router), "--out", str(tmp_path / "models")])
    assert report["router_usage_from"]["name"] == "after"
    assert all(r["cost_per_1000"]["router"] > 0 for r in report["models"])
    assert (tmp_path / "models" / "report.md").exists()
