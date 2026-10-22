import json
from pathlib import Path

import pytest

from evals.report import compare, hypothesis_matches, main, observed_direction, render_markdown
from evals.scenarios import Scenario


def _case(case_id: str, passed: bool, dataset: str = "single_topic", reply: str = "reply") -> dict:
    return {
        "id": case_id,
        "dataset": dataset,
        "persona": "rebuilder",
        "intents": 1,
        "message": f"message {case_id}",
        "skills": ["score-changes"],
        "routing": {"strategy": "skills", "selected": ["score-changes"], "carried": [], "error": None},
        "reply": reply,
        "checks": {"passed": True, "failures": []},
        "judge": {
            "facts": [{"fact": "Names 47%", "status": "PRESENT" if passed else "ABSENT", "note": "n"}],
            "reason": "ok" if passed else "missing 47%",
            "passed": passed,
        },
        "passed": passed,
        "status": "ok",
        "error": None,
    }


def _results(cases: list[dict], scenario: str | None = None, selection: dict | None = None) -> dict:
    return {
        "name": "run",
        "bot": "after",
        "scenario": scenario,
        "created_at": "2026-10-21T00:00:00+00:00",
        "models": {"router": "r", "agent": "a", "judge": "j"},
        "selection": selection,
        "cases": cases,
    }


BASELINE = _results(
    [
        _case("st-001", True, reply="old 1"),
        _case("st-002", False),
        _case("mi-001", True, "multi_intent", reply="old answer"),
        _case("mi-002", False, "multi_intent"),
        _case("sb-001", True, "safety_basic"),  # not in the candidate, so not compared
    ]
)
CANDIDATE = _results(
    [
        _case("st-001", True),
        _case("st-002", True),
        _case("mi-001", False, "multi_intent", reply="new answer"),
        _case("mi-002", False, "multi_intent"),
    ],
    scenario="s3",
    selection={"rule": "all cases: description of topic skill utilization changed", "case_ids": []},
)

SCENARIO = Scenario(
    id="s3",
    title="Wider utilization description",
    kind="description",
    skill="utilization",
    change="Widen the description.",
    motivation="Route score drops to utilization.",
    hypothesis={"expected": "tradeoff", "detail": "Singles improve, triples lose a skill."},
)


def test_transitions_and_verdict() -> None:
    report = compare(BASELINE, CANDIDATE, SCENARIO)

    assert report["transitions"] == {
        "improved": ["st-002"],
        "regressed": ["mi-001"],
        "unchanged_pass": ["st-001"],
        "unchanged_fail": ["mi-002"],
    }
    assert report["transition_counts"] == {"improved": 1, "regressed": 1, "unchanged_pass": 1, "unchanged_fail": 1}
    assert report["verdict"] == "Not passed"
    assert report["hypothesis_result"] == {"expected": "tradeoff", "observed": "tradeoff", "matches": True}
    assert report["selection"] == {"rule": CANDIDATE["selection"]["rule"], "case_count": 4}
    assert report["scenario"]["hypothesis"]["expected"] == "tradeoff"


def test_pass_rates_cover_only_compared_cases() -> None:
    report = compare(BASELINE, CANDIDATE)
    rates = report["pass_rates"]
    assert set(rates["by_dataset"]) == {"single_topic", "multi_intent"}  # sb-001 is not in the candidate
    single = rates["by_dataset"]["single_topic"]
    assert single["baseline"] == {"passed": 1, "rate": 0.5}
    assert single["candidate"] == {"passed": 2, "rate": 1.0}
    assert single["delta"] == 0.5
    assert rates["overall"]["baseline"]["passed"] == 2 and rates["overall"]["candidate"]["passed"] == 2
    assert report["hypothesis_result"] is None  # no scenario object given
    assert report["scenario"] == {"id": "s3"}


def test_failures_overview_shows_both_replies_and_judge() -> None:
    [failure] = compare(BASELINE, CANDIDATE)["failures"]
    assert failure["id"] == "mi-001"
    assert failure["baseline_reply"] == "old answer"
    assert failure["candidate_reply"] == "new answer"
    assert failure["judge_facts"][0]["status"] == "ABSENT"
    assert failure["judge_reason"] == "missing 47%"
    assert failure["message"] == "message mi-001"


def test_no_regression_passes_and_new_cases_are_flagged() -> None:
    candidate = _results([_case("st-001", True), _case("st-009", False)])
    report = compare(BASELINE, candidate)
    assert report["verdict"] == "Passed"
    assert report["transitions"]["unchanged_pass"] == ["st-001"]
    assert any("st-009" in w for w in report["warnings"])
    assert report["selection"]["rule"].startswith("no selection")


def test_candidate_error_counts_as_not_passed() -> None:
    errored = {**_case("st-001", False), "status": "error", "error": "bot: APIError: boom", "judge": None}
    report = compare(BASELINE, _results([errored]))
    assert report["transitions"]["regressed"] == ["st-001"]
    assert report["errors"] == ["st-001"]
    assert "boom" in render_markdown(report)


@pytest.mark.parametrize(
    ("expected", "improved", "regressed", "matches"),
    [
        ("improve", 2, 0, True),
        ("improve", 2, 1, False),
        ("improve", 0, 0, False),
        ("regress", 0, 3, True),
        ("regress", 1, 3, True),
        ("regress", 1, 0, False),
        ("tradeoff", 1, 1, True),
        ("tradeoff", 2, 0, False),
        ("tradeoff", 0, 2, False),
    ],
)
def test_hypothesis_matches(expected: str, improved: int, regressed: int, matches: bool) -> None:
    assert hypothesis_matches(expected, improved, regressed) is matches


def test_observed_direction() -> None:
    assert [observed_direction(*pair) for pair in [(1, 0), (0, 1), (1, 1), (0, 0)]] == [
        "improve",
        "regress",
        "tradeoff",
        "no change",
    ]


def test_markdown_sections() -> None:
    text = render_markdown(compare(BASELINE, CANDIDATE, SCENARIO))
    assert text.startswith("# Regression report: s3 (Wider utilization description)")
    assert "**Verdict: Not passed.**" in text
    assert "observed tradeoff (matches)" in text
    for heading in ("## Scenario", "## Pass rates", "## Transitions", "## Failures overview", "### mi-001"):
        assert heading in text
    assert "> new answer" in text and "> old answer" in text
    assert "| Names 47% | ABSENT | n |" in text
    assert "—" not in text  # no em dashes


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    baseline_path, candidate_path = tmp_path / "a.json", tmp_path / "b.json"
    baseline_path.write_text(json.dumps(BASELINE), encoding="utf-8")
    candidate_path.write_text(json.dumps({**CANDIDATE, "scenario": None}), encoding="utf-8")

    report = main(["--baseline", str(baseline_path), "--candidate", str(candidate_path), "--out", str(tmp_path / "r")])

    saved = json.loads((tmp_path / "r" / "report.json").read_text(encoding="utf-8"))
    assert saved == json.loads(json.dumps(report))
    assert saved["verdict"] == "Not passed"
    assert (tmp_path / "r" / "report.md").read_text(encoding="utf-8").startswith("# Regression report")
