import json
from pathlib import Path

import pytest

from evals.report import _p, compare, decision_line, hypothesis_matches, main, observed_direction, render_markdown
from evals.scenarios import Scenario
from evals.stats import permutation_test
from fynn import config


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
        "unstable": [],  # always empty with one run per side
    }
    assert report["transition_counts"] == {
        "improved": 1, "regressed": 1, "unchanged_pass": 1, "unchanged_fail": 1, "unstable": 0,
    }
    assert report["verdict"] == "Not passed"
    assert report["hypothesis_result"] == {"expected": "tradeoff", "observed": "tradeoff", "matches": True}
    assert report["selection"] == {"rule": CANDIDATE["selection"]["rule"], "case_count": 4}
    assert report["scenario"]["hypothesis"]["expected"] == "tradeoff"


def test_pass_rates_cover_only_compared_cases() -> None:
    report = compare(BASELINE, CANDIDATE)
    rates = report["pass_rates"]
    assert set(rates["by_dataset"]) == {"single_topic", "multi_intent"}  # sb-001 is not in the candidate
    single = rates["by_dataset"]["single_topic"]
    assert single["baseline"] == {"passed": 1, "runs": 2, "rate": 0.5}
    assert single["candidate"] == {"passed": 2, "runs": 2, "rate": 1.0}
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
    assert "observed tradeoff (matches; from the flagged counts, not a significance test)" in text
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


def test_cli_refuses_to_replace_a_report_of_other_runs_without_force(tmp_path: Path) -> None:
    paths = {name: tmp_path / f"{name}.json" for name in ("a", "b", "c")}
    paths["a"].write_text(json.dumps(BASELINE), encoding="utf-8")
    paths["b"].write_text(json.dumps({**CANDIDATE, "scenario": None}), encoding="utf-8")
    paths["c"].write_text(json.dumps({**CANDIDATE, "scenario": None, "created_at": "2026-10-22T00:00:00+00:00"}), encoding="utf-8")
    out = tmp_path / "r"
    args = lambda cand: ["--baseline", str(paths["a"]), "--candidate", str(paths[cand]), "--out", str(out)]  # noqa: E731
    main(args("b"))
    main(args("b"))  # the same runs again: allowed
    with pytest.raises(SystemExit, match="compares other runs"):
        main(args("c"))
    assert main([*args("c"), "--force"])["candidate"]["created_at"] == "2026-10-22T00:00:00+00:00"
    for broken in ("{not json", '{"baseline": "x", "candidate": "y"}', "[]"):
        (out / "report.json").write_text(broken, encoding="utf-8")
        with pytest.raises(SystemExit, match="is not a readable report"):
            main(args("c"))


def test_cli_refuses_a_baseline_that_does_not_fit_the_scenario(tmp_path: Path) -> None:
    # scenarios/s4 on disk edits the body of credit-builder-account.
    fp = {"credit-builder-account": {"description": "d", "body": "b", "meta": "m"}, "tone": {"description": "t", "body": "t", "meta": "m"}}
    edited = {**fp, "credit-builder-account": {**fp["credit-builder-account"], "body": "b2"}, "tone": {**fp["tone"], "body": "t2"}}
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({**BASELINE, "skill_fingerprint": fp}), encoding="utf-8")
    b.write_text(json.dumps({**CANDIDATE, "scenario": "s4", "skill_fingerprint": edited}), encoding="utf-8")
    args = ["--baseline", str(a), "--candidate", str(b), "--out", str(tmp_path / "r")]
    with pytest.raises(SystemExit, match="also differ in tone"):
        main(args)
    assert main([*args, "--force"])["scenario"]["id"] == "s4"


# ---- Noise and significance ------------------------------------------------------------------


def test_single_run_report_has_mcnemar_and_no_noise_floor() -> None:
    report = compare(BASELINE, CANDIDATE, SCENARIO)
    assert report["flag_rule"] == {
        "min_fails": 1,
        "baseline_repeats": 1,
        "candidate_repeats": 1,
        "text": "a case regresses when it passed in the baseline and fails in the candidate (one run each)",
    }
    test = report["paired_test"]
    assert test["method"] == "mcnemar_exact"
    assert (test["overall"]["improved"], test["overall"]["regressed"]) == (1, 1)
    assert test["overall"]["p_value"] == 1.0 and test["overall"]["significant"] is False
    assert set(test["by_dataset"]) == {"single_topic", "multi_intent"}
    assert report["noise_floor"] is None
    assert report["noise_floor_note"] == "the baseline ran each case once and no A/A run was given"
    assert report["kind"] == "change"
    assert report["verdict_note"].startswith("The verdict is Not passed, but the net change is not significant")
    text = render_markdown(report)
    assert (
        "Paired test of the net change (exact McNemar on the 2 cases that flipped): p = 1.000, "
        "not significant at 0.05."
    ) in text
    assert "A/A noise floor: not measured (the baseline ran each case once and no A/A run was given)." in text
    assert "| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |" in text
    assert "a balanced tradeoff (as many cases fixed as broken) can read as not significant" in text
    assert "Unstable" not in text  # only shown when a side ran more than once


def _repeated(
    case_id: str, outcomes: list[bool | None], dataset: str = "single_topic", persona: str = "rebuilder"
) -> dict:
    """A repeated case; None in `outcomes` is an errored run."""
    runs = []
    for i, outcome in enumerate(outcomes):
        run = _case(case_id, bool(outcome), dataset, reply=f"{case_id} run {i + 1}")
        run = {k: v for k, v in run.items() if k not in ("id", "dataset", "persona", "intents", "message", "skills")}
        if outcome is None:
            run.update(status="error", error="bot: LLMError: boom", judge=None)
        runs.append(run)
    passes = sum(1 for o in outcomes if o)
    shown = next(r for r in runs if r["passed"] == (passes * 2 > len(outcomes)))
    return {
        **_case(case_id, shown["passed"], dataset),
        **shown,
        "persona": persona,
        "repeats": len(outcomes),
        "passes": passes,
        "runs": runs,
    }


def _repeated_results(cases: list[dict], repeats: int = 3, **extra) -> dict:
    return {**_results(cases), "repeats": repeats, **extra}


T, F, E = True, False, None
REPEATED_BASELINE = _repeated_results(
    [
        _repeated("st-001", [T, T, T], persona="rebuilder"),
        _repeated("st-002", [T, T, T], persona="renter"),
        _repeated("st-003", [T, F, T], persona="high-util"),  # unstable in the baseline
        _repeated("st-004", [F, F, F], persona="collections"),
        _repeated("mi-001", [T, T, T], "multi_intent", persona="rebuilder"),
        _repeated("mi-002", [T, T, T], "multi_intent", persona="renter"),
    ]
)
REPEATED_CANDIDATE = _repeated_results(
    [
        _repeated("st-001", [F, T, F], persona="rebuilder"),  # fails 2 of 3 after 3 of 3: regressed
        _repeated("st-002", [T, F, T], persona="renter"),  # fails 1 of 3: unstable, not flagged
        _repeated("st-003", [F, F, F], persona="high-util"),  # baseline was unstable: not flagged
        _repeated("st-004", [T, T, F], persona="collections"),  # passes 2 of 3 after 0 of 3: improved
        _repeated("mi-001", [T, T, T], "multi_intent", persona="rebuilder"),
        _repeated("mi-002", [F, F, F], "multi_intent", persona="renter"),
    ]
)


def test_flag_rule_with_repeats() -> None:
    report = compare(REPEATED_BASELINE, REPEATED_CANDIDATE)
    assert report["transitions"] == {
        "improved": ["st-004"],
        "regressed": ["st-001", "mi-002"],
        "unchanged_pass": ["mi-001"],
        "unchanged_fail": [],
        "unstable": ["st-002", "st-003"],
    }
    assert report["verdict"] == "Not passed"
    assert report["flag_rule"]["min_fails"] == 2
    assert "fails at least 2 of its 3 runs and passed every one of its 3 baseline runs that did not error" in (
        report["flag_rule"]["text"]
    )
    assert report["baseline"]["repeats"] == 3 and report["candidate"]["repeats"] == 3
    assert report["sharp_changes"] == {"dropped": ["st-003"], "rose": []}  # 2/3 to 0/3, never flagged

    stricter = compare(REPEATED_BASELINE, REPEATED_CANDIDATE, min_fails=1)
    assert stricter["transitions"]["regressed"] == ["st-001", "st-002", "mi-002"]
    lenient = compare(REPEATED_BASELINE, REPEATED_CANDIDATE, min_fails=3)
    assert lenient["transitions"]["regressed"] == ["mi-002"]
    with pytest.raises(ValueError, match="min_fails"):
        compare(REPEATED_BASELINE, REPEATED_CANDIDATE, min_fails=4)


def test_pass_rates_count_runs_with_repeats() -> None:
    rates = compare(REPEATED_BASELINE, REPEATED_CANDIDATE)["pass_rates"]
    single = rates["by_dataset"]["single_topic"]
    assert single["total"] == 4  # cases
    assert single["baseline"] == {"passed": 8, "runs": 12, "rate": 0.6667}
    assert single["candidate"] == {"passed": 5, "runs": 12, "rate": 0.4167}  # 1 + 2 + 0 + 2
    assert single["delta"] == round(0.4167 - 0.6667, 4)
    assert rates["overall"]["candidate"] == {"passed": 8, "runs": 18, "rate": 0.4444}


def test_repeated_report_uses_the_permutation_test_and_baseline_noise() -> None:
    report = compare(REPEATED_BASELINE, REPEATED_CANDIDATE)
    test = report["paired_test"]
    assert test["method"] == "run_permutation"
    overall = test["overall"]
    assert overall["clusters"] == 4 and overall["cases"] == 6 and overall["informative"] == 5
    cells = [(3, 3, 1, 3), (3, 3, 2, 3), (2, 3, 0, 3), (0, 3, 2, 3), (3, 3, 3, 3), (3, 3, 0, 3)]
    assert overall["p_value"] == round(permutation_test(cells), 6)
    assert overall["ci_low"] <= overall["mean_diff"] <= overall["ci_high"]
    for row in test["by_dataset"].values():
        assert row["p_holm"] >= row["p_value"]

    noise = report["noise_floor"]
    assert noise["source"] == "baseline_repeats" and noise["unit"] == "single_run_flips" and noise["repeats"] == 3
    assert noise["overall"]["flips"] == round(2 / 3, 4)  # st-003 passed 2 of 3: 2*2*1/(3*2)
    assert noise["overall"]["regressed"] is None  # single-run flips are not split into chance regressions
    assert noise["unstable"] == ["st-003"]

    text = render_markdown(report)
    assert "**Verdict: Not passed.** 2 regressed, 1 improved, 2 unstable." in text
    assert "Paired test of the net change (exact run-permutation test; 5 of 6 cases had runs that disagreed)" in text
    assert "(descriptive only)" in text
    assert "A/A noise floor (single runs): about 0.7 of 6 cases flip between two single runs" in text
    assert "for a like-for-like floor, rerun the baseline with the same --repeats and pass it with --aa" in text
    assert (
        "| Dataset | Cases | Runs disagreed | Personas | Mean change | Persona interval | p | p (Holm) "
        "| A/A single-run flips (expected) |"
    ) in text
    assert "- Unstable (not flagged: varied across runs, or too few runs that did not error) (2): st-002, st-003" in text
    assert "- Unstable but dropped sharply, not counted: st-003" in text
    assert "Counts are passing runs; rates are the mean pass fraction per case." in text
    assert "Unstable in the baseline: st-003." in text
    assert "-0.0" not in text and "—" not in text


def test_repeated_failure_shows_a_failing_run() -> None:
    report = compare(REPEATED_BASELINE, REPEATED_CANDIDATE)
    st001 = next(f for f in report["failures"] if f["id"] == "st-001")
    assert st001["candidate_reply"] == "st-001 run 1"  # the first failing run, though run 2 passed
    assert st001["baseline_reply"] == "st-001 run 1"
    assert (st001["baseline_passed"], st001["baseline_runs"]) == (3, 3)
    assert (st001["candidate_passed"], st001["candidate_runs"]) == (1, 3)
    assert "Passed 3 of 3 baseline runs and 1 of 3 candidate runs" in render_markdown(report)


def test_failure_detail_with_a_lenient_flag_rule_still_shows_a_failing_run() -> None:
    # st-002 went 3/3 to 2/3 ([T, F, T]): its top-level fields are a passing run.
    [st002] = [f for f in compare(REPEATED_BASELINE, REPEATED_CANDIDATE, min_fails=1)["failures"] if f["id"] == "st-002"]
    assert st002["candidate_reply"] == "st-002 run 2"
    assert [fact["status"] for fact in st002["judge_facts"]] == ["ABSENT"]


def test_improvements_show_a_passing_candidate_run() -> None:
    base = _repeated_results([_repeated("st-001", [F, F, F])])
    cand = _repeated_results([_repeated("st-001", [F, T, F])])  # majority fails, but flagged with m=1
    report = compare(base, cand, min_fails=1)
    assert report["transitions"]["improved"] == ["st-001"]
    [improvement] = report["improvements"]
    assert improvement["candidate_reply"] == "st-001 run 2"
    assert improvement["judge_facts"][0]["status"] == "PRESENT"
    assert improvement["baseline_reply"] == "st-001 run 1"


def test_mixed_repeats() -> None:
    single = _results([_case("st-001", True), _case("st-002", True), _case("st-003", False)])
    report = compare(single, REPEATED_CANDIDATE)
    assert report["flag_rule"]["min_fails"] == 2  # from the candidate's K
    assert report["transitions"]["regressed"] == ["st-001"]
    assert report["transitions"]["unstable"] == ["st-002"]  # fails 1 of 3
    assert report["paired_test"]["method"] == "run_permutation"
    assert "runs per case differ: baseline 1, candidate 3" in report["warnings"]

    reverse = compare(REPEATED_BASELINE, _results([_case("st-001", False), _case("st-003", False)]))
    assert reverse["flag_rule"]["min_fails"] == 1
    assert reverse["transitions"]["regressed"] == ["st-001"]
    assert reverse["transitions"]["unstable"] == ["st-003"]  # the baseline was unstable
    assert reverse["paired_test"]["method"] == "run_permutation"
    assert "runs per case differ: baseline 3, candidate 1" in reverse["warnings"]


def test_errored_baseline_run_does_not_hide_a_regression() -> None:
    base = _repeated_results([_repeated("st-001", [T, E, T]), _repeated("st-002", [E, E, E], persona="renter")])
    cand = _repeated_results([_repeated("st-001", [F, F, F]), _repeated("st-002", [F, F, F], persona="renter")])
    report = compare(base, cand)
    assert report["transitions"]["regressed"] == ["st-001"]  # the errored run is left out of the baseline
    assert report["transitions"]["unchanged_fail"] == ["st-002"]  # every run errored: counted as failing
    assert report["baseline_errors"] == ["st-001", "st-002"]
    assert any("baseline runs errored for st-001" in w for w in report["warnings"])
    assert any("every baseline run errored for st-002" in w for w in report["warnings"])
    assert "- Baseline errors: st-001, st-002" in render_markdown(report)


def test_errored_candidate_runs_are_left_out_unless_every_run_errored() -> None:
    base = _repeated_results([_repeated("st-001", [T, T, T]), _repeated("st-002", [T, T, T], persona="renter")])
    cand = _repeated_results([_repeated("st-001", [T, E, E]), _repeated("st-002", [E, E, E], persona="renter")])
    report = compare(base, cand)
    assert report["errors"] == ["st-001", "st-002"]
    assert report["transitions"]["unchanged_pass"] == ["st-001"]  # its one valid run passed
    assert report["transitions"]["regressed"] == ["st-002"]  # nothing but errors: counted as failing
    assert any("candidate runs errored for st-001" in w for w in report["warnings"])
    assert any("every candidate run errored for st-002" in w for w in report["warnings"])
    assert report["pass_rates"]["overall"]["candidate"] == {"passed": 1, "runs": 4, "rate": 0.25}


def test_errored_baseline_runs_in_the_failure_detail() -> None:
    base = _repeated_results([_repeated("st-001", [E, E, T])])
    cand = _repeated_results([_repeated("st-001", [F, F, T])])
    report = compare(base, cand)
    [failure] = report["failures"]
    assert (failure["baseline_passed"], failure["baseline_runs"], failure["baseline_errored"]) == (1, 1, 2)
    assert failure["baseline_reply"] == "st-001 run 3"  # the passing run, not an errored one
    assert (
        "Passed 1 of 1 baseline run and 1 of 3 candidate runs (2 errored baseline runs left out)"
        in render_markdown(report)
    )


def test_an_all_errored_side_counts_as_failing_but_is_left_out_of_the_test() -> None:
    base = _results([_case("st-001", True), _case("st-002", True)])
    errored = {**_case("st-001", False), "status": "error", "error": "bot: APIError: boom", "judge": None}
    report = compare(base, _results([errored, _case("st-002", True)]))
    assert report["transitions"]["regressed"] == ["st-001"]  # the flag rule still counts it, as before
    overall = report["paired_test"]["overall"]
    assert (overall["cases"], overall["left_out"], overall["regressed"]) == (1, 1, 0)
    [failure] = report["failures"]
    assert failure["candidate_all_errored"] is True
    text = render_markdown(report)
    assert "(every candidate run errored and counts as failing)" in text
    assert "1 case with only errored runs on one side was left out." in text


def test_aa_cases_with_only_errored_runs_are_left_out_of_the_floor() -> None:
    aa_error = {**_case("st-001", False), "status": "error", "error": "boom", "judge": None}
    report = compare(BASELINE, CANDIDATE, aa=_results([aa_error, _case("st-002", False)]))
    noise = report["noise_floor"]
    assert noise["left_out"] == ["st-001"]
    assert noise["overall"] == {"cases": 1, "flips": 0, "regressed": 0, "improved": 0}
    assert any("every run errored on one side for st-001" in w for w in report["warnings"])


def test_p_value_wording() -> None:
    assert _p(0.0625) == "0.063"  # ties round up, as the site's toFixed does
    from evals.report import _p_eq

    assert _p_eq(0.0004) == "p < 0.001" and _p_eq(0.07) == "p = 0.070" and _p_eq(None) == "p = n/a"
    one = compare(_repeated_results([_repeated("st-001", [T, T, T])]), _repeated_results([_repeated("st-001", [F, F, T])]))
    assert "1 of 1 case had runs that disagreed" in render_markdown(one)


def test_verdict_notes() -> None:
    # Passed, but a significant net regression hides in the unstable cases.
    personas = ["rebuilder", "renter", "high-util", "collections", "new-to-credit", "multi-product"]
    base = _repeated_results([_repeated(f"st-0{i:02}", [T, T, F], persona=personas[i % 6]) for i in range(12)])
    cand = _repeated_results([_repeated(f"st-0{i:02}", [F, F, F], persona=personas[i % 6]) for i in range(12)])
    report = compare(base, cand)
    assert report["verdict"] == "Passed" and report["transition_counts"]["unstable"] == 12
    assert report["paired_test"]["overall"]["significant"] is True
    assert report["verdict_note"].startswith("The verdict is Passed, but the paired test finds a significant net regression")
    assert report["sharp_changes"]["dropped"] == [f"st-0{i:02}" for i in range(12)]

    # Not passed, but the net change is a significant improvement.
    base = _results([_case("st-001", True)] + [_case(f"st-1{i:02}", False) for i in range(10)])
    cand = _results([_case("st-001", False)] + [_case(f"st-1{i:02}", True) for i in range(10)])
    note = compare(base, cand)["verdict_note"]
    assert note.startswith("The verdict is Not passed because 1 case regressed, although the net change")

    # Agreement leaves no note.
    assert compare(BASELINE, _results([_case("st-001", True), _case("st-002", True)]))["verdict_note"] is None


def test_aa_run_sets_the_noise_floor() -> None:
    aa = _results(
        [
            _case("st-001", True),
            _case("st-002", True),  # flipped
            _case("mi-001", False, "multi_intent"),  # flipped
            # mi-002 missing
        ]
    )
    report = compare(BASELINE, CANDIDATE, aa={**aa, "name": "after-aa"})
    noise = report["noise_floor"]
    assert noise["source"] == "aa_run" and noise["repeats"] == 1 and noise["same_rule"] is True
    assert noise["overall"] == {"cases": 3, "flips": 2, "regressed": 1, "improved": 1}
    assert noise["by_dataset"]["multi_intent"] == {"cases": 1, "flips": 1, "regressed": 1, "improved": 0}
    assert noise["run"]["name"] == "after-aa"
    assert any("mi-002" in w and "A/A" in w for w in report["warnings"])
    text = render_markdown(report)
    assert "A/A noise floor: 2 of 3 cases were flagged (1 regressed, 1 improved)" in text
    assert "under the same flag rule" in text
    assert "| A/A flags (same rule) |" in text
    assert "Flipped or varied in the A/A run: st-002, mi-001." in text


def test_aa_run_with_fewer_repeats_names_the_rule_it_used() -> None:
    aa = _results([_case("st-001", False), _case("st-002", True), _case("mi-001", True, "multi_intent")])
    report = compare(REPEATED_BASELINE, REPEATED_CANDIDATE, aa=aa)
    noise = report["noise_floor"]
    assert noise["same_rule"] is False and noise["min_fails"] == 1 and noise["repeats"] == 1
    assert noise["overall"]["flips"] == 1  # st-001 failed its one run after 3 of 3
    assert any("the A/A run has 1 run per case and the candidate 3" in w for w in report["warnings"])
    text = render_markdown(report)
    assert "under a different rule (1 of 1 failing runs instead of 2 of 3), since the A/A run has 1 run per case" in text
    assert "under the same flag rule" not in text and "looser" not in text
    assert "| A/A flags (1 of 1 fails) |" in text


def test_aa_run_from_a_different_setup_is_flagged() -> None:
    aa = {**_results([_case("st-001", True)]), "models": {"router": "x", "agent": "y", "judge": "z"}}
    report = compare(BASELINE, CANDIDATE, aa=aa)
    assert "the A/A run differs from the baseline in bot, scenario, models, skills, skill cap or setup fingerprint" in report["warnings"]


def test_aa_run_with_no_shared_cases_falls_back_to_the_baseline_repeats() -> None:
    aa = _repeated_results([_repeated("zz-001", [T, T, T])])
    report = compare(REPEATED_BASELINE, REPEATED_CANDIDATE, aa=aa)
    assert report["noise_floor"]["source"] == "baseline_repeats"
    assert "none of the compared cases are in the A/A run, so it was not used" in report["warnings"]

    single = compare(BASELINE, CANDIDATE, aa=_results([_case("zz-001", True)]))
    assert single["noise_floor"] is None
    assert single["noise_floor_note"] == "the baseline ran each case once and no usable A/A run was given"


def test_noise_floor_notes() -> None:
    empty = compare(REPEATED_BASELINE, _repeated_results([]))
    assert empty["noise_floor"] is None and empty["noise_floor_note"] == "no cases were compared"
    assert "A/A noise floor: not measured (no cases were compared)." in render_markdown(empty)


def test_a_run_against_its_own_setup_is_an_aa_report() -> None:
    fingerprint = {"score-changes": {"description": "d", "body": "b", "meta": "m"}}
    base = {**BASELINE, "skill_fingerprint": fingerprint}
    again = {**_results([_case("st-001", False), _case("st-002", False)]), "skill_fingerprint": fingerprint}
    report = compare(base, again)
    assert report["kind"] == "aa"
    assert "if nothing else changed (the cases or personas" in report["verdict_note"]
    assert "This is an A/A comparison" in render_markdown(report)
    assert compare(base, {**again, "skill_fingerprint": {}})["kind"] == "change"


def test_a_different_skill_cap_is_a_change_and_old_files_read_as_cap_3(monkeypatch: pytest.MonkeyPatch) -> None:
    # Raising the configured cap must not relabel files written before the cap was recorded.
    monkeypatch.setattr(config, "MAX_NEW_SKILLS_PER_TURN", 4)
    fingerprint = {"score-changes": {"description": "d", "body": "b", "meta": "m"}}
    base = {**BASELINE, "skill_fingerprint": fingerprint}  # written before the cap was recorded
    same = {**base, "skill_cap": 3}
    assert compare(base, same)["kind"] == "aa"
    assert compare(base, same)["baseline"]["skill_cap"] == 3

    wider = {**base, "skill_cap": 4}
    report = compare(base, wider)
    assert report["kind"] == "change"
    assert any(w.startswith("skill caps differ") for w in report["warnings"])
    # The Before bot has no skill cap.
    assert compare({**base, "bot": "before"}, {**wider, "bot": "before"})["candidate"]["skill_cap"] is None


def _routed(case: dict, *skills: str) -> dict:
    return {**case, "routing": {**case["routing"], "selected": list(skills)}}


def test_flips_the_edit_cannot_reach_are_chance() -> None:
    body = Scenario(
        id="s9", title="t", kind="body", skill="utilization", change="c", motivation="m",
        hypothesis={"expected": "improve", "detail": "d"},
    )
    base = _results([
        _routed(_case("st-001", False), "utilization"), _case("st-002", False), _case("mi-001", True, "multi_intent"),
    ])
    cand = _results([
        _routed(_case("st-001", True), "utilization"),  # the edited skill loaded on both sides: the edit can explain it
        _case("st-002", True),  # same prompt as before: chance
        _case("mi-001", False, "multi_intent"),  # same prompt: chance
    ])
    report = compare(base, cand, body)
    assert report["attribution"] == {
        "rule": "a body edit can reach a case only when the edited skill (for the Before bot, its domain) is loaded on both sides",
        "fixed": ["st-001"], "broken": [], "chance_up": ["st-002"], "chance_down": ["mi-001"], "errored": [],
        "decision": "ship", "tested": False, "reached_p": 1.0, "reached_significant": False,
    }
    text = render_markdown(report)
    assert text.splitlines()[2].startswith("**Decision: Ship, as a lead.** The change fixed 1 case and broke none")
    # The skill loaded only on the candidate side came from the router, which never reads bodies: chance.
    newly = compare(_results([_case("st-001", False)]), _results([_routed(_case("st-001", True), "utilization")]), body)
    assert newly["attribution"]["chance_up"] == ["st-001"] and newly["attribution"]["fixed"] == []
    assert "- Flipped by chance (1 up, 1 down): st-002, mi-001" in text

    # A description edit reaches a case only when the edited skill enters or leaves its routing.
    desc = body.model_copy(update={"kind": "description"})
    unrouted = _results([_case("st-001", False), _case("st-002", False), _case("mi-001", True, "multi_intent")])
    routed = compare(unrouted, _results([_routed(_case("st-001", True), "utilization"), _case("st-002", True),
                                     _routed(_case("mi-001", False, "multi_intent"), "rent-reporting")]), desc)
    assert (routed["attribution"]["fixed"], routed["attribution"]["broken"]) == (["st-001"], [])
    assert routed["attribution"]["chance_down"] == ["mi-001"]  # its routing changed, but not utilization

    always = compare(base, cand, body.model_copy(update={"kind": "always_on", "skill": "tone"}))
    assert always["attribution"]["chance_up"] == [] and always["attribution"]["broken"] == ["mi-001"]


def test_before_vs_after_has_no_attribution_and_leads_with_both_rates() -> None:
    report = compare({**BASELINE, "bot": "before"}, CANDIDATE)
    assert report["attribution"] is None
    text = render_markdown(report)
    assert text.splitlines()[2] == "**After passes 2 of 4; before passes 2 of 4.**"
    assert "## Details\n\n**Verdict:" in text


def test_an_aa_comparison_has_no_decision() -> None:
    fingerprint = {"score-changes": {"description": "d", "body": "b", "meta": "m"}}
    base = {**BASELINE, "skill_fingerprint": fingerprint}
    rerun = {**_results([_routed(_case("st-001", False), "utilization"), _case("st-002", True)]), "skill_fingerprint": fingerprint}
    report = compare(base, rerun)
    assert report["kind"] == "aa" and report["attribution"] is None


def test_without_a_scenario_the_change_is_read_from_the_fingerprints(monkeypatch: pytest.MonkeyPatch) -> None:
    import evals.report as report_module

    monkeypatch.setattr(report_module, "_topic_skill", lambda name: True)
    old = {"utilization": {"description": "d", "body": "b", "meta": "m"}}
    base = {**_results([_routed(_case("st-001", False), "utilization"), _case("st-002", False)]), "skill_fingerprint": old}
    cand = _results([_routed(_case("st-001", True), "utilization"), _case("st-002", True)])
    body = compare(base, {**cand, "skill_fingerprint": {"utilization": {**old["utilization"], "body": "b2"}}})
    assert body["attribution"]["rule"].startswith("a body edit") and body["attribution"]["fixed"] == ["st-001"]
    desc = compare(base, {**cand, "skill_fingerprint": {"utilization": {**old["utilization"], "description": "d2"}}})
    assert desc["attribution"]["rule"].startswith("a description edit")
    models = compare(base, {**cand, "skill_fingerprint": old, "models": {"router": "r", "agent": "other", "judge": "j"}})
    assert models["attribution"]["rule"].startswith("the runs differ") and models["attribution"]["chance_up"] == []


def test_errored_runs_do_not_decide_the_attribution() -> None:
    base = _results([_case("st-001", True), _routed(_case("st-002", True), "score-changes", "utilization")])
    errored = {**_case("st-001", False), "routing": None, "status": "error", "error": "bot: LLMError: down"}
    cand = _results([errored, _routed(_case("st-002", False), "rent-reporting")])
    a = compare(base, cand)["attribution"]
    assert a["errored"] == ["st-001"] and a["broken"] == ["st-002"]
    assert "errored on one side and is left out" in render_markdown(compare(base, cand))


def test_a_reordered_routing_is_not_a_routing_change() -> None:
    # The router reorders the same picks between identical runs; that is not the change. The baseline
    # filled its cap of 3, so a real routing change would count for the higher cap.
    base = _results([_routed(_case("st-001", False), "score-changes", "utilization", "secured-card")])
    cand = {**_results([_routed(_case("st-001", True), "utilization", "secured-card", "score-changes")]), "skill_cap": 4}
    a = compare(base, cand)["attribution"]
    assert a["rule"].startswith("a skill cap change")
    assert a["fixed"] == [] and a["chance_up"] == ["st-001"]


def test_a_cap_change_reaches_only_cases_where_the_cap_mattered() -> None:
    base = _results([
        _routed(_case("st-001", False), "score-changes", "utilization", "secured-card"),  # filled the cap of 3
        _routed(_case("st-002", False), "rent-reporting"),  # one skill, then two: the cap did not bind
        _routed(_case("st-003", False), "rent-reporting"),  # one skill, then four: only the higher cap allows it
        _routed(_case("st-004", False), "rent-reporting", "collections"),  # two, then three: fits either cap
    ])
    cand = {**_results([
        _routed(_case("st-001", True), "score-changes", "utilization", "secured-card", "collections"),
        _routed(_case("st-002", True), "rent-reporting", "collections"),
        _routed(_case("st-003", True), "rent-reporting", "collections", "utilization", "secured-card"),
        _routed(_case("st-004", True), "rent-reporting", "collections", "utilization"),
    ]), "skill_cap": 4}
    a = compare(base, cand)["attribution"]
    assert a["rule"].startswith("a skill cap change")
    assert (a["fixed"], a["chance_up"]) == (["st-001", "st-003"], ["st-002", "st-004"])
    # Lowering the cap: the run with the higher cap went past the lower one, or the lower cap was filled.
    lower = compare({**cand, "skill_cap": 4}, {**base, "skill_cap": 3})["attribution"]
    assert (lower["broken"], lower["chance_down"]) == (["st-001", "st-003"], ["st-002", "st-004"])
    # The cap limits new picks only: carried skills do not fill it.
    carried = lambda case, *skills: {**case, "routing": {**case["routing"], "carried": list(skills)}}  # noqa: E731
    held = ("score-changes", "utilization", "secured-card")
    a = compare(_results([carried(_routed(_case("st-001", False)), *held)]),
                {**_results([carried(_routed(_case("st-001", True), "collections"), *held)]), "skill_cap": 4})["attribution"]
    assert (a["fixed"], a["chance_up"]) == ([], ["st-001"])


def test_runs_that_record_no_change_count_every_flip() -> None:
    # Same cap, no fingerprints: nothing the files record explains the change, so every case is reached.
    base = _results([_case("st-001", False), _case("st-002", True)])
    cand = _results([_case("st-001", True), _case("st-002", True)])
    a = compare(base, cand)["attribution"]
    assert a["rule"].startswith("the runs differ") and a["fixed"] == ["st-001"]
    before = compare({**base, "bot": "before"}, {**cand, "bot": "before"})["attribution"]
    assert before["rule"].startswith("the runs differ") and before["fixed"] == ["st-001"]


def test_a_description_edit_on_the_before_bot_reaches_through_the_domain() -> None:
    desc = Scenario(
        id="s9", title="t", kind="description", skill="utilization", change="c", motivation="m",
        hypothesis={"expected": "improve", "detail": "d"},
    )
    # Before routes to domains; utilization sits in score-and-reports, so only that domain entering counts.
    base = {**_results([_routed(_case("st-001", False), "credit-products"),
                        _routed(_case("st-002", False), "credit-products")]), "bot": "before"}
    cand = {**_results([_routed(_case("st-001", True), "score-and-reports"),
                        _routed(_case("st-002", True), "rent-and-bills")]), "bot": "before"}
    a = compare(base, cand, desc)["attribution"]
    assert (a["fixed"], a["chance_up"]) == (["st-001"], ["st-002"])


def test_a_description_edit_with_a_cap_change_also_counts_where_the_cap_mattered() -> None:
    desc = Scenario(
        id="s9", title="t", kind="description", skill="utilization", change="c", motivation="m",
        hypothesis={"expected": "improve", "detail": "d"},
    )
    base = _results([_routed(_case("st-001", False), "utilization", "score-changes", "secured-card")])
    cand = {**_results([_routed(_case("st-001", True), "utilization", "score-changes", "secured-card", "collections")]),
            "skill_cap": 4}
    assert compare(base, cand, desc)["attribution"]["fixed"] == ["st-001"]


ALWAYS_ON = Scenario(
    id="s9", title="t", kind="always_on", skill="tone", change="c", motivation="m",
    hypothesis={"expected": "improve", "detail": "d"},
)


def _flips(fixed: int, broken: int, scenario: Scenario = ALWAYS_ON) -> dict:
    """A one-run report where every case is reached: `fixed` cases go from fail to pass, `broken` the other way."""
    ids = [f"st-{i:03d}" for i in range(fixed + broken)]
    base = _results([_case(i, n >= fixed) for n, i in enumerate(ids)])
    cand = _results([_case(i, n < fixed) for n, i in enumerate(ids)])
    return compare(base, cand, scenario)["attribution"]


def test_the_test_on_reached_flips_backs_a_decision() -> None:
    # With one run per case the test is exact McNemar on fixed against broken. A Ship needs six fixed and
    # none broken (p = 0.031; five gives 0.0625); a Do not ship, six broken and none fixed, or eight against one.
    assert [(a["decision"], a["reached_p"], a["tested"]) for a in (_flips(6, 0), _flips(5, 0))] == [
        ("ship", 0.03125, True), ("ship", 0.0625, False)]
    assert [(a["decision"], a["reached_p"], a["tested"]) for a in (_flips(0, 6), _flips(1, 7), _flips(1, 8))] == [
        ("do not ship", 0.03125, True), ("do not ship", 0.070312, False), ("do not ship", 0.039062, True)]
    # A tradeoff stays a lead even when the test is significant, and the line says why.
    tradeoff = _flips(9, 1)
    assert (tradeoff["decision"], tradeoff["reached_p"], tradeoff["tested"]) == ("tradeoff", 0.021484, False)
    assert decision_line(tradeoff).endswith(
        " A tradeoff stays a lead whatever the test shows, since it broke 1 case it could reach"
        " (the test on the cases it could reach gives p = 0.021).")
    line = decision_line({"decision": "no effect", "fixed": [], "broken": [], "chance_up": ["st-001"],
                          "chance_down": [], "errored": [], "tested": None, "reached_p": None})
    assert line.startswith("**Decision: No effect.**") and "lead" not in line
    lead = decision_line({"decision": "ship", "fixed": ["a"] * 5, "broken": [], "chance_up": ["b"], "chance_down": [],
                          "errored": [], "tested": False, "reached_p": 0.0625, "reached_significant": False})
    assert lead.startswith("**Decision: Ship, as a lead.**") and "gives p = 0.063, so a reached flip may still be chance" in lead


def test_a_reached_p_just_above_alpha_is_not_shown_as_alpha() -> None:
    # Errored runs leave mixed run counts, where the exact p can be 0.050000375: stored as 0.05, not significant.
    pairs = [([T, E, E], [F, E, E]), ([T, F, E], [F, F, F]), ([T, F, F], [T, F, E]), ([F, F, F], [T, F, F]),
             ([F, F, F], [T, T, F]), ([F, F, F], [T, T, T]), ([T, F, F], [T, T, T]), ([T, F, F], [T, T, T])]
    pairs += [([T, T, F], [T, T, T])] * 4
    base = _repeated_results([_repeated(f"st-{i:03d}", b, persona=f"p{i}") for i, (b, _) in enumerate(pairs)])
    cand = _repeated_results([_repeated(f"st-{i:03d}", c, persona=f"p{i}") for i, (_, c) in enumerate(pairs)])
    a = compare(base, cand, ALWAYS_ON)["attribution"]
    assert (a["decision"], a["reached_p"], a["reached_significant"], a["tested"]) == ("ship", 0.05, False, False)
    assert decision_line(a).endswith(
        " The test on the cases it could reach gives p just above 0.05, so a reached flip may still be chance.")


def test_only_reached_flips_decide_not_every_flip() -> None:
    # The S4 shape: five reached fixes and one chance improvement. Counting every flip (6 to 0) would be
    # significant; the five the edit could reach are not.
    body = ALWAYS_ON.model_copy(update={"kind": "body", "skill": "utilization"})
    reached = [f"st-{i:03d}" for i in range(5)]
    base = _results([_routed(_case(i, False), "utilization") for i in reached] + [_case("st-099", False)])
    cand = _results([_routed(_case(i, True), "utilization") for i in reached] + [_case("st-099", True)])
    report = compare(base, cand, body)
    a = report["attribution"]
    assert (a["fixed"], a["chance_up"]) == (reached, ["st-099"])
    assert (a["reached_p"], a["tested"]) == (0.0625, False)
    assert report["paired_test"]["overall"]["p_value"] == 0.03125


def test_with_repeats_the_reached_cases_get_the_run_permutation_test() -> None:
    # One case is fixed (0 of 3, then 3 of 3) and none broken, so the flag rule says Ship. Eight reached
    # cases that were unstable (2 of 3) fall to 0 of 3: the flag rule cannot label them, but the test on the
    # reached cases counts them, so the decision is a lead and the line says the cases moved the other way.
    def run(case_id: str, outcomes: list[bool]) -> dict:
        return _repeated(case_id, outcomes, persona=f"p{case_id}")

    drops = [f"st-{i:03d}" for i in range(1, 9)]
    base = _repeated_results([run("st-000", [F, F, F])] + [run(i, [T, T, F]) for i in drops])
    cand = _repeated_results([run("st-000", [T, T, T])] + [run(i, [F, F, F]) for i in drops])
    report = compare(base, cand, ALWAYS_ON)
    a = report["attribution"]
    assert (a["decision"], a["fixed"], a["broken"]) == ("ship", ["st-000"], [])
    cells = [(0, 3, 3, 3)] + [(2, 3, 0, 3)] * 8
    assert a["reached_p"] == round(permutation_test(cells), 6) and a["reached_p"] <= 0.05
    assert a["tested"] is False and a["reached_significant"] is True
    assert decision_line(a).endswith("but those cases moved the other way on average, so it does not back the decision.")
    # Moving the decision's way, the same test backs it.
    up = compare(base, _repeated_results([run("st-000", [T, T, T])] + [run(i, [T, T, T]) for i in drops]), ALWAYS_ON)
    assert up["attribution"]["decision"] == "ship" and up["attribution"]["tested"] is True


def test_the_summary_counts_cases_as_well_as_runs() -> None:
    text = render_markdown(compare(REPEATED_BASELINE, REPEATED_CANDIDATE))
    # st-004 is better; st-001, st-002, st-003 and mi-002 are worse; mi-001 is a tie.
    assert "Counting cases instead of runs (sign test): 1 better, 4 worse, p = 0.375." in text


def test_a_decision_the_paired_test_does_not_back_is_a_lead() -> None:
    body = Scenario(
        id="s9", title="t", kind="body", skill="utilization", change="c", motivation="m",
        hypothesis={"expected": "improve", "detail": "d"},
    )
    base = _results([_routed(_case("st-001", False), "utilization"), _case("st-002", True)])
    cand = _results([_routed(_case("st-001", True), "utilization"), _case("st-002", True)])
    report = compare(base, cand, body)
    assert report["attribution"]["decision"] == "ship" and report["attribution"]["tested"] is False
    line = decision_line(report["attribution"])
    assert line.startswith("**Decision: Ship, as a lead.**") and "may still be chance" in line


def test_a_scenario_baseline_must_differ_only_in_the_edited_skill() -> None:
    from evals.report import scenario_baseline_problems

    scenario = Scenario(
        id="s9", title="t", kind="description", skill="utilization", change="c", motivation="m",
        hypothesis={"expected": "improve", "detail": "d"},
    )
    fp = {"utilization": {"description": "d", "body": "b", "meta": "m"}, "tone": {"description": "t", "body": "t", "meta": "m"}}
    edited = {**fp, "utilization": {**fp["utilization"], "description": "d2"}}
    assert scenario_baseline_problems({"skill_fingerprint": fp}, {"skill_fingerprint": edited}, scenario) == []
    other = {**edited, "tone": {**fp["tone"], "body": "t2"}}
    assert "also differ in tone" in scenario_baseline_problems({"skill_fingerprint": fp}, {"skill_fingerprint": other}, scenario)[0]
    assert "already has s9's edit" in scenario_baseline_problems({"skill_fingerprint": edited}, {"skill_fingerprint": edited}, scenario)[0]


def test_failures_are_labeled_with_their_attribution() -> None:
    text = render_markdown(compare(BASELINE, CANDIDATE, SCENARIO))
    assert "### mi-001 (multi_intent, rebuilder) (chance: outside the change's reach)" in text


def test_a_partial_run_is_flagged() -> None:
    report = compare(BASELINE, {**CANDIDATE, "complete": False})
    assert any(w.startswith("the candidate is a partial run") for w in report["warnings"])


def test_no_compared_case_is_neither_passed_nor_not_passed() -> None:
    report = compare(BASELINE, _results([]), SCENARIO)
    assert report["verdict"] == "No cases compared"
    assert report["verdict_note"].startswith("No case was in both runs")
    assert report["hypothesis_result"] is None


def test_setup_fingerprints_that_differ_make_a_change_with_a_warning() -> None:
    fingerprint = {"bot_code": "b", "judge_code": "j", "settings": "s"}
    skills = {"score-changes": {"description": "d", "body": "b", "meta": "m"}}
    base = {**BASELINE, "skill_fingerprint": skills, "setup_fingerprint": fingerprint}
    assert compare(base, {**base})["kind"] == "aa"

    report = compare(base, {**base, "setup_fingerprint": {**fingerprint, "judge_code": "x"}})
    assert report["kind"] == "change"
    assert "setups differ between the runs: the judge code" in report["warnings"]
    legacy = compare({**base, "setup_fingerprint": None}, base)
    assert legacy["kind"] == "change"  # a file without the fingerprint matches only another without one
    assert any("baseline does not record a setup fingerprint" in w for w in legacy["warnings"])


def test_cases_whose_expected_facts_changed_are_not_compared() -> None:
    reworded = _case("st-002", True)
    reworded["judge"]["facts"][0]["fact"] = "Names 47% of the limit"
    candidate = _results([_case("st-001", True), reworded])
    report = compare(BASELINE, candidate)

    assert report["facts_changed"] == ["st-002"]
    assert report["pass_rates"]["overall"]["total"] == 1
    assert "st-002" not in [i for ids in report["transitions"].values() for i in ids]
    assert any(w.startswith("expected facts differ between the runs, so not compared: st-002") for w in report["warnings"])
    # A case that errored before grading has no facts to compare, so it is still paired.
    errored = {**_case("st-002", False), "judge": None, "status": "error", "error": "agent: LLMError"}
    assert compare(BASELINE, _results([errored]))["facts_changed"] == []


def test_p_values_near_alpha_keep_enough_digits() -> None:
    assert _p(0.0502) == "0.0502" and _p(0.05) == "0.050" and _p(0.0498) == "0.0498"
    assert _p(0.0703) == "0.070" and _p(0.0004) == "<0.001" and _p(None) == "n/a"


def test_cli_aa_and_min_fails(tmp_path: Path) -> None:
    paths = {name: tmp_path / f"{name}.json" for name in ("base", "cand", "aa")}
    paths["base"].write_text(json.dumps(REPEATED_BASELINE), encoding="utf-8")
    paths["cand"].write_text(json.dumps(REPEATED_CANDIDATE), encoding="utf-8")
    paths["aa"].write_text(json.dumps(REPEATED_BASELINE), encoding="utf-8")
    args = ["--baseline", str(paths["base"]), "--candidate", str(paths["cand"]), "--out", str(tmp_path / "r")]

    report = main([*args, "--aa", str(paths["aa"]), "--min-fails", "3"])
    assert report["flag_rule"]["min_fails"] == 3
    assert report["noise_floor"]["source"] == "aa_run" and report["noise_floor"]["same_rule"] is True
    assert report["noise_floor"]["overall"]["flips"] == 0  # the same file: nothing flips
    saved = json.loads((tmp_path / "r" / "report.json").read_text(encoding="utf-8"))
    assert saved["paired_test"]["method"] == "run_permutation"

    with pytest.raises(SystemExit, match="min_fails"):
        main([*args, "--min-fails", "0"])
