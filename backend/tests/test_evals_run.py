"""End-to-end eval runs with a scripted fake LLM (no API calls)."""

import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

import evals.cases
import evals.run
import evals.scenarios
from evals import report as report_cli
from evals.cases import load_cases
from evals.judge import Judge, fact_ids
from evals.run import SKIPPED_ERROR, build_results, combine_runs, is_fatal, run_case, run_cases, write_results
from fynn import config
from fynn.bots import build_bots
from fynn.llm import Generation, LLMError, Usage
from fynn.personas import load_personas
from fynn.skills import SkillLibrary
from tests.conftest import AGENT_USAGE, ROUTER_USAGE, FakeLLM

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
        self.router_systems: list[str] = []

    def generate_json(
        self, *, schema: dict[str, Any], messages: list[dict[str, str]], system: str = "", **_: Any
    ):
        prompt = messages[-1]["content"]
        props = schema["properties"]
        with self.lock:
            self.calls.append("judge" if "facts" in props else "router")
            if "skills" in props:
                self.router_systems.append(system)
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


class FlakyLLM(ScriptedLLM):
    """ScriptedLLM whose judge grades the n-th call for a message ABSENT.

    `fail_on` maps a text unique to one case's judge prompt to the call numbers (1-based) that
    fail. Calls are counted per case, so how many runs of a case fail is fixed even though the
    repeats run in parallel.
    """

    def __init__(self, fail_on: dict[str, set[int]], error_on: dict[str, set[int]] | None = None):
        super().__init__()
        self.fail_on = fail_on
        self.error_on = error_on or {}  # the same, for answer calls that raise
        self.seen: dict[str, int] = {}
        self.answers: dict[str, int] = {}

    def generate(self, *, model: str, messages: list[dict[str, str]], **kwargs: Any) -> Generation:
        prompt = messages[-1]["content"]
        for key, calls in self.error_on.items():
            if key in prompt:
                with self.lock:
                    self.answers[key] = self.answers.get(key, 0) + 1
                    n = self.answers[key]
                if n in calls:
                    raise LLMError(f"answer call {n} failed", Usage(input_tokens=3))
        return super().generate(model=model, messages=messages, **kwargs)

    def generate_json(self, *, schema: dict[str, Any], messages: list[dict[str, str]], **kwargs: Any):
        prompt = messages[-1]["content"]
        if "facts" in schema["properties"]:
            for key, calls in self.fail_on.items():
                if key not in prompt:
                    continue
                with self.lock:
                    self.seen[key] = self.seen.get(key, 0) + 1
                    n = self.seen[key]
                    if n in calls:
                        self.calls.append("judge")
                if n in calls:
                    ids = schema["properties"]["facts"]["items"]["properties"]["id"]["enum"]
                    facts = [{"id": i, "status": "ABSENT", "note": "n"} for i in ids]
                    return {"facts": facts, "reason": f"dropped on call {n}"}, ROUTER_USAGE
        return super().generate_json(schema=schema, messages=messages, **kwargs)


ST001 = "<message>\nWhy did my score drop last month?\n</message>"  # mi-001 starts with the same question
ST002 = "rent showing up"
MI001 = "secured card arrived"
SB001 = "deleted from my report"


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
        "usage": asdict(ROUTER_USAGE),
    }
    assert first["checks"] == {"passed": True, "failures": []}
    assert [f["status"] for f in first["judge"]["facts"]] == ["PRESENT", "PRESENT"]
    assert first["usage"] == asdict(AGENT_USAGE)  # the answering model's call only
    multi = results[2]
    assert multi["routing"]["selected"] == ["score-changes", "secured-card"]

    out = tmp_path / "results" / "after.json"
    results_json = build_results(name="after", bot="after", library=mini_library, case_results=results)
    write_results(out, results_json)
    saved = json.loads(out.read_text(encoding="utf-8"))

    assert set(saved) == {
        "name", "bot", "scenario", "repeats", "skill_cap", "created_at", "models", "skill_fingerprint",
        "setup_fingerprint", "selection", "cases", "summary",
    }
    assert set(saved["setup_fingerprint"]) == {"bot_code", "judge_code", "settings"}
    assert saved["repeats"] == 1
    assert saved["skill_cap"] == config.MAX_NEW_SKILLS_PER_TURN
    assert (first["repeats"], first["passes"], first["pass_fraction"]) == (1, 1, 1.0) and "runs" not in first
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


def _graded(case: evals.cases.EvalCase) -> dict[str, Any]:
    return {"facts": [{"id": i, "status": "PRESENT", "note": "n"} for i in fact_ids(case)], "reason": "graded"}


@pytest.mark.parametrize(
    ("bot_name", "route"),
    [
        ("after", {"reason": "r", "skills": ["score-changes"]}),
        ("before", {"reason": "r", "agent": "score-and-reports"}),
    ],
)
def test_run_case_records_router_usage_apart_from_the_answer(
    mini_library: SkillLibrary, personas, bot_name: str, route: dict[str, Any]
) -> None:
    # The router and the answering model are priced differently, so a result keeps their tokens apart.
    case = next(c for c in load_cases(FIXTURE_CASES) if c.id == "st-001")
    llm = FakeLLM([route, _graded(case)])
    result = run_case(case, personas[case.persona], build_bots(llm, mini_library)[bot_name], Judge(llm))

    assert result["status"] == "ok"
    assert result["routing"]["usage"] == asdict(ROUTER_USAGE)
    assert result["usage"] == asdict(AGENT_USAGE)
    assert result["judge"]["usage"] == asdict(ROUTER_USAGE)  # FakeLLM bills every structured call the same


def test_run_case_keeps_a_failed_router_calls_tokens_under_routing(mini_library: SkillLibrary, personas) -> None:
    case = next(c for c in load_cases(FIXTURE_CASES) if c.id == "st-001")
    failed = Usage(input_tokens=9, output_tokens=4)
    llm = FakeLLM([LLMError("router stopped with max_tokens", failed), _graded(case)])
    result = run_case(case, personas[case.persona], build_bots(llm, mini_library)["after"], Judge(llm))

    assert result["status"] == "ok" and result["routing"]["selected"] == []
    assert result["routing"]["error"] == "router stopped with max_tokens"
    assert result["routing"]["usage"] == asdict(failed)
    assert result["usage"] == asdict(AGENT_USAGE)


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
    assert errored["usage"]["input_tokens"] == 3  # the failed answer call's tokens

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


def test_cli_skill_cap_reruns_every_case_and_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    bot_llm = ScriptedLLM()
    monkeypatch.setattr(evals.run, "make_llms", lambda: (bot_llm, ScriptedLLM()))
    baseline_path = tmp_path / "after.json"
    evals.run.main(["--bot", "after", "--out", str(baseline_path)])

    cap = config.MAX_NEW_SKILLS_PER_TURN + 1
    candidate_path = tmp_path / "cap.json"
    bot_llm.router_systems.clear()
    candidate = evals.run.main(
        ["--bot", "after", "--max-skills", str(cap), "--baseline", str(baseline_path), "--out", str(candidate_path)]
    )
    # The cap reaches the router, not only the results file.
    assert bot_llm.router_systems and all(f"Choose at most {cap}," in s for s in bot_llm.router_systems)
    # Skills did not change, but the cap can change routing for any message, so every case reruns.
    assert candidate["skill_cap"] == cap
    assert len(candidate["cases"]) == 4
    assert candidate["selection"]["rule"] == f"all cases: the skill cap changed from {config.MAX_NEW_SKILLS_PER_TURN} to {cap}"

    report = report_cli.main(
        ["--baseline", str(baseline_path), "--candidate", str(candidate_path), "--out", str(tmp_path / "report")]
    )
    assert report["kind"] == "change"
    assert report["candidate"]["skill_cap"] == cap
    assert f"skill caps differ: baseline {config.MAX_NEW_SKILLS_PER_TURN}, candidate {cap}" in report["warnings"]

    # Back to the default cap against the higher-cap baseline: also a cap change, so every case reruns.
    back = evals.run.main(["--bot", "after", "--baseline", str(candidate_path), "--out", str(tmp_path / "back.json")])
    assert back["skill_cap"] == config.MAX_NEW_SKILLS_PER_TURN
    assert len(back["cases"]) == 4
    assert back["selection"]["rule"] == f"all cases: the skill cap changed from {cap} to {config.MAX_NEW_SKILLS_PER_TURN}"


def test_cli_a_model_or_code_change_reruns_every_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(), ScriptedLLM()))
    baseline_path = tmp_path / "after.json"
    baseline = evals.run.main(["--bot", "after", "--out", str(baseline_path)])

    def rerun(edit: dict) -> dict:
        edited = tmp_path / "edited.json"
        edited.write_text(json.dumps({**baseline, **edit}), encoding="utf-8")
        return evals.run.main(["--bot", "after", "--baseline", str(edited), "--out", str(tmp_path / "again.json")])

    # Nothing changed: nothing reruns, and a report on the empty run passes nothing.
    unchanged = rerun({})
    assert unchanged["cases"] == [] and unchanged["selection"]["rule"].startswith("no skill changed")
    report = report_cli.main(
        ["--baseline", str(baseline_path), "--candidate", str(tmp_path / "again.json"), "--out", str(tmp_path / "r")]
    )
    assert report["verdict"] == "No cases compared"

    models = rerun({"models": {**baseline["models"], "agent": "claude-old"}})
    assert len(models["cases"]) == 4
    assert models["selection"]["rule"] == f"all cases: the models (agent claude-old to {config.AGENT_MODEL}) changed"

    code = rerun({"setup_fingerprint": {**baseline["setup_fingerprint"], "bot_code": "000000000000"}})
    assert len(code["cases"]) == 4 and code["selection"]["rule"] == "all cases: the bot code changed"

    # A baseline from before setup fingerprints can only be checked for models.
    legacy = {k: v for k, v in baseline.items() if k != "setup_fingerprint"}
    (tmp_path / "legacy.json").write_text(json.dumps(legacy), encoding="utf-8")
    old = evals.run.main(["--bot", "after", "--baseline", str(tmp_path / "legacy.json"), "--out", str(tmp_path / "o.json")])
    assert old["cases"] == []


@pytest.mark.parametrize(
    ("argv", "message"),
    [(["--bot", "before", "--max-skills", "4"], "only to the after bot"), (["--bot", "after", "--max-skills", "0"], "at least 1")],
)
def test_cli_rejects_a_bad_skill_cap(
    argv: list[str], message: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        evals.run.parse_args([*argv, "--out", str(tmp_path / "x.json")])
    assert message in capsys.readouterr().err


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


def test_run_cases_with_repeats(mini_library: SkillLibrary, personas) -> None:
    cases = load_cases(FIXTURE_CASES)  # st-001, st-002, mi-001, sb-001
    llm = FlakyLLM({ST002: {2}, SB001: {1, 2, 3}})
    lines: list[str] = []
    results = run_cases(
        cases, bot=build_bots(llm, mini_library)["after"], judge=Judge(llm), personas=personas,
        repeats=3, workers=4, progress=lines.append,
    )

    assert [r["id"] for r in results] == [c.id for c in cases]
    assert len(lines) == 12 and all(" run " in line for line in lines)
    assert llm.calls.count("judge") == 12

    st001, st002, mi001, sb001 = results
    assert (st001["repeats"], st001["passes"], st001["pass_fraction"], st001["passed"]) == (3, 3, 1.0, True)
    assert (st002["passes"], st002["pass_fraction"], st002["passed"]) == (2, 0.6667, True)  # majority passed
    assert st002["judge"]["passed"] is True  # the shown run has the majority outcome
    assert [run["passed"] for run in st002["runs"]].count(False) == 1
    assert (sb001["passes"], sb001["passed"]) == (0, False)
    assert sb001["judge"]["reason"].startswith("dropped on call")
    assert mi001["passes"] == 3 and mi001["errors"] == 0

    run = st002["runs"][0]
    assert "id" not in run and "message" not in run  # case fields are kept once, at the top
    assert {"routing", "reply", "checks", "judge", "passed", "status", "error", "usage"} <= set(run)

    summary = build_results(name="after", bot="after", library=mini_library, case_results=results, repeats=3)
    assert summary["repeats"] == 3
    # Buckets count runs: 3 + 2 + 3 + 0 of 12.
    assert summary["summary"]["overall"] == {"passed": 8, "total": 12, "rate": 0.6667, "errors": 0}
    assert summary["summary"]["by_dataset"]["single_topic"] == {"passed": 5, "total": 6, "rate": 0.8333, "errors": 0}


def test_run_cases_rejects_zero_repeats(mini_library: SkillLibrary, personas) -> None:
    llm = ScriptedLLM()
    with pytest.raises(ValueError, match="repeats"):
        run_cases([], bot=build_bots(llm, mini_library)["after"], judge=Judge(llm), personas=personas, repeats=0)


def test_cli_repeated_runs_then_flagged_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    # One LLM pair per run: the baseline, then the scenario.
    llms = iter(
        [
            (FlakyLLM({ST002: {2}}), FlakyLLM({ST002: {2}})),
            (FlakyLLM({ST001: {1, 2, 3}, MI001: {1}}), FlakyLLM({ST001: {1, 2, 3}, MI001: {1}})),
        ]
    )
    monkeypatch.setattr(evals.run, "make_llms", lambda: next(llms))

    baseline_path = tmp_path / "after.json"
    baseline = evals.run.main(["--bot", "after", "--repeats", "3", "--out", str(baseline_path), "--workers", "4"])
    assert baseline["repeats"] == 3
    assert baseline["summary"]["overall"]["total"] == 12
    st002 = next(c for c in baseline["cases"] if c["id"] == "st-002")
    assert st002["passes"] == 2

    scenarios = tmp_path / "scenarios"
    (scenarios / "s9" / "skills").mkdir(parents=True)
    (scenarios / "s9" / "scenario.yaml").write_text(
        "id: s9\ntitle: Test\nkind: body\nskill: score-changes\nchange: c\nmotivation: m\n"
        "hypothesis: {expected: regress, detail: d}\n",
        encoding="utf-8",
    )
    original = (config.SKILLS_DIR / "score-changes.md").read_text(encoding="utf-8")
    (scenarios / "s9" / "skills" / "score-changes.md").write_text(original.rstrip() + "\n- Extra.\n", encoding="utf-8")
    monkeypatch.setattr(evals.scenarios, "SCENARIOS_DIR", scenarios)

    candidate_path = tmp_path / "s9.json"
    candidate = evals.run.main(
        ["--bot", "after", "--repeats", "3", "--scenario", "s9", "--baseline", str(baseline_path),
         "--out", str(candidate_path)]
    )
    # Selection runs on a repeated baseline. Both cases are picked by their labels; the routing union
    # over runs is tested in test_evals_selection.py.
    assert candidate["selection"]["case_ids"] == ["st-001", "mi-001"]

    report = report_cli.main(
        ["--baseline", str(baseline_path), "--candidate", str(candidate_path), "--out", str(tmp_path / "report")]
    )
    assert report["transitions"]["regressed"] == ["st-001"]  # failed 3 of 3 after passing 3 of 3
    assert report["transitions"]["unstable"] == ["mi-001"]  # failed 1 of 3: below m = 2
    assert report["verdict"] == "Not passed"
    assert report["hypothesis_result"]["matches"] is True
    assert report["paired_test"]["method"] == "run_permutation"
    # Both selected cases belong to one persona: the test still runs, but there is no persona interval.
    overall = report["paired_test"]["overall"]
    assert overall["clusters"] == 1 and overall["ci_low"] is None
    assert overall["informative"] == 2 and overall["p_value"] is not None
    assert report["noise_floor"]["source"] == "baseline_repeats"
    assert report["noise_floor"]["overall"]["flips"] == 0.0  # both selected cases were stable in the baseline
    assert "## Noise and significance" in (tmp_path / "report" / "report.md").read_text(encoding="utf-8")


def test_cli_rejects_zero_repeats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_clients():
        raise AssertionError("must stop before building API clients")

    monkeypatch.setattr(evals.run, "make_llms", no_clients)
    with pytest.raises(SystemExit) as exc:
        evals.run.main(["--bot", "after", "--repeats", "0", "--out", str(tmp_path / "x.json")])
    assert exc.value.code == 2
    assert "--repeats must be at least 1" in capsys.readouterr().err


def _run(passed: bool | None, reply: str) -> dict[str, Any]:
    """One run as run_case returns it; None is an errored run."""
    return {
        "id": "st-001", "dataset": "single_topic", "persona": "rebuilder", "intents": 1, "message": "m",
        "skills": [], "routing": None, "reply": reply, "checks": None, "judge": None, "passed": bool(passed),
        "status": "error" if passed is None else "ok", "error": "boom" if passed is None else None,
        "usage": {},
    }


@pytest.mark.parametrize(
    ("outcomes", "passed", "shown", "errors"),
    [
        ([False, True, True], True, "r2", 0),  # the majority passed; the first passing run is shown
        ([True, False, False], False, "r2", 0),
        ([True, False], False, "r2", 0),  # a tie is not a majority
        ([True, None, True], True, "r1", 1),
        ([None, None, None], False, "r1", 3),
    ],
)
def test_combine_runs(outcomes: list[bool | None], passed: bool, shown: str, errors: int) -> None:
    combined = combine_runs([_run(o, f"r{i + 1}") for i, o in enumerate(outcomes)])
    assert combined["passed"] is passed
    assert combined["reply"] == shown
    assert combined["errors"] == errors
    assert combined["repeats"] == len(outcomes)
    assert combined["passes"] == sum(1 for o in outcomes if o)
    assert [run["reply"] for run in combined["runs"]] == [f"r{i + 1}" for i in range(len(outcomes))]
    assert all("id" not in run for run in combined["runs"])


def test_combine_runs_keeps_a_single_run_as_is() -> None:
    combined = combine_runs([_run(True, "only")])
    assert "runs" not in combined and "errors" not in combined
    assert (combined["repeats"], combined["passes"], combined["pass_fraction"]) == (1, 1, 1.0)


def test_errored_runs_inside_repeats(mini_library: SkillLibrary, personas) -> None:
    cases = load_cases(FIXTURE_CASES)
    llm = FlakyLLM({}, error_on={ST002: {2}})
    results = run_cases(
        cases, bot=build_bots(llm, mini_library)["after"], judge=Judge(llm), personas=personas,
        repeats=3, workers=1, progress=None,
    )
    st002 = results[1]
    assert (st002["passes"], st002["errors"], st002["passed"]) == (2, 1, True)
    assert [run["status"] for run in st002["runs"]].count("error") == 1
    report = report_cli.compare(
        build_results(name="a", bot="after", library=mini_library, case_results=results, repeats=3),
        build_results(name="b", bot="after", library=mini_library, case_results=results, repeats=3),
    )
    assert report["errors"] == ["st-002"] and report["baseline_errors"] == ["st-002"]


# --- Fatal errors and --rerun-errors ----------------------------------------------------------


class AuthenticationError(Exception):
    """Named like the SDK's, so the runner treats it as fatal."""


class OutOfCreditLLM(ScriptedLLM):
    """ScriptedLLM whose answer calls fail with a fatal error after the first `ok` of them.
    With a `gate`, the answer calls after the first failing one wait for it before failing too."""

    def __init__(self, ok: int, gate: threading.Event | None = None):
        super().__init__()
        self.ok, self.gate, self.answers = ok, gate, 0

    def generate(self, **kwargs: Any) -> Generation:
        with self.lock:
            self.answers += 1
            n = self.answers
        if self.gate is not None and n > self.ok + 1:
            self.gate.wait(timeout=5)
        if n > self.ok:
            raise AuthenticationError("Error code: 401 - invalid x-api-key")
        return super().generate(**kwargs)


@pytest.mark.parametrize(
    ("error", "fatal"),
    [
        ("bot: AuthenticationError: Error code: 401", True),
        ("judge: PermissionDeniedError: Error code: 403", True),
        ("bot: NotFoundError: Error code: 404 - model: claude-typo", True),
        ("bot: BadRequestError: Error code: 400 - Your credit balance is too low to access the Anthropic API.", True),
        ("bot: LLMError: answer call failed", False),
        ("judge: BadRequestError: Error code: 400 - prompt is too long", False),
        (None, False),
    ],
)
def test_is_fatal(error: str | None, fatal: bool) -> None:
    assert is_fatal(error) is fatal


def test_a_fatal_error_cancels_the_runs_not_started(mini_library: SkillLibrary, personas) -> None:
    gate = threading.Event()
    llm = OutOfCreditLLM(ok=1, gate=gate)
    results = run_cases(
        load_cases(FIXTURE_CASES), bot=build_bots(llm, mini_library)["after"], judge=Judge(ScriptedLLM()),
        personas=personas, workers=1, progress=lambda line: gate.set() if line.startswith("stopping") else None,
    )
    assert results[0]["status"] == "ok"
    assert results[1]["error"].startswith("bot: AuthenticationError:")
    # The third case may already have started when the run stopped; the fourth never does.
    assert results[2]["status"] == "error" and results[3]["error"] == SKIPPED_ERROR
    assert llm.answers in (2, 3)


def test_cli_fatal_stop_writes_a_partial_file_then_rerun_errors_completes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    out = tmp_path / "after.json"
    out.write_text("{}", encoding="utf-8")  # an earlier complete file must survive the failed run
    monkeypatch.setattr(evals.run, "make_llms", lambda: (OutOfCreditLLM(ok=1), ScriptedLLM()))
    with pytest.raises(SystemExit, match="--rerun-errors"):
        evals.run.main(["--bot", "after", "--out", str(out)])
    assert out.read_text(encoding="utf-8") == "{}"
    partial = json.loads((tmp_path / "after.partial.json").read_text(encoding="utf-8"))
    assert partial["complete"] is False and partial["name"] == "after"
    kept = next(c for c in partial["cases"] if c["status"] == "ok")
    assert sum(c["status"] == "error" for c in partial["cases"]) == 3

    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(reply="Rerun reply, 47%."), ScriptedLLM()))
    merged = evals.run.main(
        ["--bot", "after", "--rerun-errors", str(tmp_path / "after.partial.json"), "--out", str(out)]
    )
    assert json.loads(out.read_text(encoding="utf-8"))["created_at"] == merged["created_at"]
    assert "complete" not in merged and merged["rerun_errors"]["runs"] == 3
    assert all(c["status"] == "ok" for c in merged["cases"])
    by_id = {c["id"]: c for c in merged["cases"]}
    assert by_id[kept["id"]]["reply"] == kept["reply"]  # the run that finished is kept, not rerun
    assert sum(c["reply"] == "Rerun reply, 47%." for c in merged["cases"]) == 3


def test_cli_rerun_errors_reruns_only_the_errored_repeats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    first = tmp_path / "first.json"
    monkeypatch.setattr(evals.run, "make_llms", lambda: (FlakyLLM({}, error_on={ST002: {2}}), ScriptedLLM()))
    before = evals.run.main(["--bot", "after", "--repeats", "3", "--out", str(first), "--workers", "1"])
    runs_before = next(c for c in before["cases"] if c["id"] == "st-002")["runs"]
    errored = [i for i, run in enumerate(runs_before) if run["status"] == "error"]
    assert len(errored) == 1

    rerun_llm = ScriptedLLM(reply="Rerun reply, 47%.")
    monkeypatch.setattr(evals.run, "make_llms", lambda: (rerun_llm, ScriptedLLM()))
    merged = evals.run.main(["--bot", "after", "--rerun-errors", str(first), "--out", str(tmp_path / "m.json")])
    st002 = next(c for c in merged["cases"] if c["id"] == "st-002")
    assert merged["repeats"] == 3 and (st002["repeats"], st002["errors"], st002["passes"]) == (3, 0, 3)
    assert rerun_llm.calls.count("router") == 1  # one errored run of one case, nothing else
    # The rerun lands at the index that errored; the other runs are kept as they were.
    for i, run in enumerate(st002["runs"]):
        assert run["reply"] == ("Rerun reply, 47%." if i in errored else runs_before[i]["reply"])


def test_cli_rerun_errors_refuses_another_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(), ScriptedLLM()))
    done = tmp_path / "after.json"
    results = evals.run.main(["--bot", "after", "--out", str(done)])
    with pytest.raises(SystemExit, match="it was run on the after bot, not before"):
        evals.run.main(["--bot", "before", "--rerun-errors", str(done), "--out", str(tmp_path / "x.json")])
    done.write_text(json.dumps({**results, "models": {**results["models"], "judge": "claude-old"}}), encoding="utf-8")
    with pytest.raises(SystemExit, match="the models .* changed since then"):
        evals.run.main(["--bot", "after", "--rerun-errors", str(done), "--out", str(tmp_path / "x.json")])
    with pytest.raises(SystemExit):
        evals.run.parse_args(["--bot", "after", "--rerun-errors", str(done), "--limit", "2", "--out", "x.json"])


def test_cli_a_second_fatal_stop_keeps_the_runs_already_done(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    out, partial = tmp_path / "after.json", tmp_path / "after.partial.json"
    monkeypatch.setattr(evals.run, "make_llms", lambda: (OutOfCreditLLM(ok=1), ScriptedLLM()))
    with pytest.raises(SystemExit):
        evals.run.main(["--bot", "after", "--out", str(out), "--workers", "1"])
    kept = next(c for c in json.loads(partial.read_text(encoding="utf-8"))["cases"] if c["status"] == "ok")

    # Still no credit: the rerun stops again, and the rewritten partial keeps the run done the first time.
    monkeypatch.setattr(evals.run, "make_llms", lambda: (OutOfCreditLLM(ok=0), ScriptedLLM()))
    with pytest.raises(SystemExit):
        evals.run.main(["--bot", "after", "--rerun-errors", str(partial), "--out", str(out)])
    again = json.loads(partial.read_text(encoding="utf-8"))
    assert not out.exists() and again["complete"] is False and again["rerun_errors"]["runs"] == 3
    assert next(c for c in again["cases"] if c["id"] == kept["id"])["reply"] == kept["reply"]


def test_cli_every_run_erroring_writes_a_partial_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(), ScriptedLLM()))
    monkeypatch.setattr(evals.run, "run_case", lambda case, *a: {**evals.run._skipped(case), "error": "bot: LLMError: down"})
    with pytest.raises(SystemExit, match="every run errored"):
        evals.run.main(["--bot", "after", "--out", str(tmp_path / "after.json")])
    assert (tmp_path / "after.partial.json").exists() and not (tmp_path / "after.json").exists()


def test_cli_rerun_errors_refuses_legacy_files_and_edited_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(), ScriptedLLM()))
    done = tmp_path / "after.json"
    results = evals.run.main(["--bot", "after", "--out", str(done)])

    legacy = tmp_path / "legacy.json"
    legacy.write_text(json.dumps({k: v for k, v in results.items() if k != "setup_fingerprint"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="predates setup fingerprints"):
        evals.run.main(["--bot", "after", "--rerun-errors", str(legacy), "--out", str(tmp_path / "x.json")])

    edited = json.loads(done.read_text(encoding="utf-8"))
    edited["cases"][0]["message"] += " (old wording)"
    edited["cases"][1]["judge"]["facts"][0]["fact"] = "An older fact"
    (tmp_path / "edited.json").write_text(json.dumps(edited), encoding="utf-8")
    first, second = edited["cases"][0]["id"], edited["cases"][1]["id"]
    with pytest.raises(SystemExit, match=f"these cases were edited since then: {first}, {second}"):
        evals.run.main(["--bot", "after", "--rerun-errors", str(tmp_path / "edited.json"), "--out", str(tmp_path / "x.json")])



def test_cli_an_empty_selection_keeps_the_results_file_already_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(), ScriptedLLM()))
    baseline = tmp_path / "after.json"
    evals.run.main(["--bot", "after", "--out", str(baseline)])

    # Nothing changed since the baseline, so nothing reruns; an existing --out must not be emptied.
    out = tmp_path / "cap.json"
    out.write_text('{"kept": true}', encoding="utf-8")
    results = evals.run.main(["--bot", "after", "--baseline", str(baseline), "--out", str(out)])
    assert results["cases"] == []
    assert json.loads(out.read_text(encoding="utf-8")) == {"kept": True}


def test_cli_runs_another_case_set_and_records_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evals.cases, "CASES_DIR", FIXTURE_CASES)
    monkeypatch.setattr(evals.run, "make_llms", lambda: (ScriptedLLM(), ScriptedLLM()))
    holdout = tmp_path / "holdout"
    holdout.mkdir()
    (holdout / "single_topic.yaml").write_text((FIXTURE_CASES / "single_topic.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    main_path, other_path = tmp_path / "after.json", tmp_path / "after-holdout.json"
    main_run = evals.run.main(["--bot", "after", "--out", str(main_path)])
    assert "cases_dir" not in main_run  # the main set is not named, so existing files stay as they were
    other = evals.run.main(["--bot", "after", "--cases", str(holdout), "--out", str(other_path)])
    assert other["cases_dir"] == str(holdout.resolve())
    assert [c["id"] for c in other["cases"]] == ["st-001", "st-002"]
    # A baseline from the other case set cannot pick the cases to rerun.
    with pytest.raises(SystemExit, match="case set"):
        evals.run.main(["--bot", "after", "--baseline", str(main_path), "--cases", str(holdout), "--out", str(tmp_path / "x.json")])
    # Rerunning errors keeps the file's own case set, and refuses another.
    again = evals.run.main(["--bot", "after", "--rerun-errors", str(other_path), "--out", str(tmp_path / "again.json")])
    assert again["cases_dir"] == other["cases_dir"] and len(again["cases"]) == 2
    with pytest.raises(SystemExit, match="case set"):
        evals.run.main(["--bot", "after", "--rerun-errors", str(other_path), "--cases", str(FIXTURE_CASES), "--out", str(tmp_path / "y.json")])
