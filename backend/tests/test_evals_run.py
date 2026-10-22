"""End-to-end eval runs with a scripted fake LLM (no API calls)."""

import json
import threading
from pathlib import Path
from typing import Any

import pytest

import evals.cases
import evals.run
import evals.scenarios
from evals import report as report_cli
from evals.cases import load_cases
from evals.judge import Judge
from evals.run import build_results, run_cases, write_results
from fynn import config
from fynn.bots import build_bots
from fynn.llm import Generation, LLMError, Usage
from fynn.personas import load_personas
from fynn.skills import SkillLibrary
from tests.conftest import AGENT_USAGE, ROUTER_USAGE

FIXTURE_CASES = Path(__file__).parent / "fixtures" / "eval_cases"

ROUTES = {
    "score": "score-changes",
    "secured card": "secured-card",
    "rent": "rent-reporting",
    "collection": "collections",
}


class ScriptedLLM:
    """Thread-safe fake that answers by content, since cases run in parallel.

    Router calls pick skills by keyword; the reply always quotes 47%; the judge marks every
    fact PRESENT unless the reply contains "MISSING". "BOOM" in a message makes the answer
    call fail, and "JUDGE-FAIL" in a reply makes the judge fail.
    """

    def __init__(self, reply: str = "Your utilization is 47%. Next step: pay down the store card."):
        self.reply = reply
        self.lock = threading.Lock()
        self.calls: list[str] = []

    def generate_json(self, *, schema: dict[str, Any], messages: list[dict[str, str]], **_: Any):
        prompt = messages[-1]["content"]
        props = schema["properties"]
        with self.lock:
            self.calls.append("judge" if "facts" in props else "router")
        if "facts" in props:
            if "JUDGE-FAIL" in prompt:
                raise LLMError("judge stopped with max_tokens", Usage(input_tokens=7))
            status = "ABSENT" if "MISSING" in prompt else "PRESENT"
            ids = props["facts"]["items"]["properties"]["id"]["enum"]
            return {"facts": [{"id": i, "status": status, "note": "n"} for i in ids], "reason": "graded"}, ROUTER_USAGE
        transcript = prompt.split("Conversation (latest message last):")[-1].lower()
        if "agent" in props:
            return {"reason": "r", "agent": "score-and-reports"}, ROUTER_USAGE
        skills = [skill for key, skill in ROUTES.items() if key in transcript]
        return {"reason": "r", "skills": skills}, ROUTER_USAGE

    def generate(self, *, model: str, messages: list[dict[str, str]], **_: Any) -> Generation:
        if "BOOM" in messages[-1]["content"]:
            raise LLMError("answer call failed", Usage(input_tokens=3))
        return Generation(text=self.reply, model=model, stop_reason="end_turn", usage=AGENT_USAGE)


@pytest.fixture
def personas():
    return load_personas()


def test_run_cases_after_bot(mini_library: SkillLibrary, personas, tmp_path: Path) -> None:
    cases = load_cases(FIXTURE_CASES)
    llm = ScriptedLLM()
    bot = build_bots(llm, mini_library)["after"]
    lines: list[str] = []
    results = run_cases(cases, bot=bot, judge=Judge(llm), personas=personas, workers=3, progress=lines.append)

    assert [r["id"] for r in results] == [c.id for c in cases]  # case order, not completion order
    assert len(lines) == len(cases) and all(line.startswith("[") for line in lines)

    first = results[0]
    assert first["status"] == "ok" and first["passed"]
    assert first["routing"] == {
        "strategy": "skills",
        "selected": ["score-changes"],
        "carried": [],
        "reason": "r",
        "error": None,
    }
    assert first["checks"] == {"passed": True, "failures": []}
    assert [f["status"] for f in first["judge"]["facts"]] == ["PRESENT", "PRESENT"]
    assert first["usage"] == {
        "input_tokens": 110,
        "output_tokens": 55,
        "cache_read_input_tokens": 3001,
        "cache_creation_input_tokens": 42,
    }
    multi = results[2]
    assert multi["routing"]["selected"] == ["score-changes", "secured-card"]

    out = tmp_path / "results" / "after.json"
    results_json = build_results(name="after", bot="after", library=mini_library, case_results=results)
    write_results(out, results_json)
    saved = json.loads(out.read_text(encoding="utf-8"))

    assert set(saved) == {
        "name", "bot", "scenario", "created_at", "models", "skill_fingerprint", "selection", "cases", "summary",
    }
    assert saved["models"] == {"router": config.ROUTER_MODEL, "agent": config.AGENT_MODEL, "judge": config.JUDGE_MODEL}
    assert saved["skill_fingerprint"]["score-changes"] == {
        "description": mini_library.get("score-changes").hashes.description,
        "body": mini_library.get("score-changes").hashes.body,
        "meta": mini_library.get("score-changes").hashes.meta,
    }
    assert saved["scenario"] is None and saved["selection"] is None
    summary = saved["summary"]
    assert summary["overall"] == {"passed": 4, "total": 4, "rate": 1.0, "errors": 0}
    assert summary["by_dataset"]["multi_intent"]["total"] == 1
    assert summary["by_dataset"]["context_use"] == {"passed": 0, "total": 0, "rate": None, "errors": 0}
    assert summary["by_intents"]["2"]["total"] == 1 and summary["by_intents"]["1"]["total"] == 3


def test_failures_and_errors_do_not_crash_the_run(mini_library: SkillLibrary, personas) -> None:
    base = load_cases(FIXTURE_CASES)
    boom = base[1].model_copy(update={"message": "BOOM rent question"})
    cases = [base[0], boom, base[2]]

    llm = ScriptedLLM(reply="MISSING the figure")
    results = run_cases(cases, bot=build_bots(llm, mini_library)["before"], judge=Judge(llm), personas=personas,
                        workers=2, progress=None)

    failed, errored, _ = results
    assert failed["status"] == "ok" and not failed["passed"]
    assert failed["checks"]["passed"] is False  # 47% missing from the reply
    assert failed["judge"]["passed"] is False
    assert failed["routing"]["strategy"] == "single_agent"

    assert errored["status"] == "error" and not errored["passed"]
    assert errored["error"].startswith("bot: LLMError: answer call failed")
    assert errored["reply"] is None
    assert errored["usage"]["input_tokens"] == 3

    judge_fail = run_cases([base[0]], bot=build_bots(ScriptedLLM("47% JUDGE-FAIL"), mini_library)["after"],
                           judge=Judge(ScriptedLLM()), personas=personas, progress=None)[0]
    assert judge_fail["status"] == "error" and judge_fail["error"].startswith("judge: LLMError")
    assert judge_fail["reply"] == "47% JUDGE-FAIL"  # the bot's answer is kept for inspection
    assert judge_fail["judge"]["usage"]["input_tokens"] == 7


def test_cli_full_run_then_scenario_with_selection_then_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(), ScriptedLLM()))

    baseline_path = tmp_path / "after.json"
    baseline = evals.run.main(["--bot", "after", "--out", str(baseline_path), "--workers", "2"])
    assert baseline_path.exists()
    assert baseline["summary"]["overall"]["total"] == 4

    # A body-only scenario on score-changes, overlaid on the real skills/ directory.
    scenarios = tmp_path / "scenarios"
    (scenarios / "s9" / "skills").mkdir(parents=True)
    (scenarios / "s9" / "scenario.yaml").write_text(
        "id: s9\ntitle: Test\nkind: body\nskill: score-changes\nchange: c\nmotivation: m\n"
        "hypothesis: {expected: improve, detail: d}\n",
        encoding="utf-8",
    )
    original = (config.SKILLS_DIR / "score-changes.md").read_text(encoding="utf-8")
    (scenarios / "s9" / "skills" / "score-changes.md").write_text(
        original.rstrip() + "\n- Compute utilization for each card.\n", encoding="utf-8"
    )
    monkeypatch.setattr(evals.scenarios, "SCENARIOS_DIR", scenarios)

    candidate_path = tmp_path / "after-s9.json"
    candidate = evals.run.main(
        ["--bot", "after", "--scenario", "s9", "--baseline", str(baseline_path), "--out", str(candidate_path)]
    )
    assert candidate["scenario"] == "s9"
    # st-001 and mi-001 are labeled score-changes; st-002 (rent) and sb-001 (collections) are not routed to it.
    assert candidate["selection"]["case_ids"] == ["st-001", "mi-001"]
    assert [c["id"] for c in candidate["cases"]] == ["st-001", "mi-001"]
    assert candidate["skill_fingerprint"]["score-changes"]["body"] != baseline["skill_fingerprint"]["score-changes"]["body"]
    assert (config.SKILLS_DIR / "score-changes.md").read_text(encoding="utf-8") == original

    report = report_cli.main(
        ["--baseline", str(baseline_path), "--candidate", str(candidate_path), "--out", str(tmp_path / "report")]
    )
    assert report["verdict"] == "Passed"
    assert report["selection"]["case_count"] == 2
    assert report["hypothesis_result"] == {"expected": "improve", "observed": "no change", "matches": False}
    assert (tmp_path / "report" / "report.md").exists()


def test_cli_rejects_a_baseline_from_the_other_bot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    baseline = tmp_path / "before.json"
    baseline.write_text(json.dumps({"bot": "before", "cases": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="before"):
        evals.run.main(["--bot", "after", "--baseline", str(baseline), "--out", str(tmp_path / "x.json")])


def test_cli_without_credentials_stops_before_any_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # conftest removed every credential source, so the real make_llms refuses to build clients.
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    with pytest.raises(SystemExit, match="No Anthropic credentials"):
        evals.run.main(["--bot", "after", "--out", str(tmp_path / "x.json"), "--limit", "1"])
    assert not (tmp_path / "x.json").exists()
