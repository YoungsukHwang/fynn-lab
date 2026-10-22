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
from evals.run import build_results, combine_runs, run_cases, write_results
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
        "name", "bot", "scenario", "repeats", "skill_cap", "created_at", "models", "skill_fingerprint", "selection",
        "cases", "summary",
    }
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
