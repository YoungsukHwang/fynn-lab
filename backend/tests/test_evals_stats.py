import itertools
import math
import random

import pytest

from evals.stats import (
    BOOTSTRAP_RESAMPLES,
    MIN_CI_CLUSTERS,
    _quantile,
    _r,
    case_runs,
    classify,
    cluster_bootstrap,
    default_min_fails,
    error_count,
    expected_flips,
    holm,
    mcnemar_exact,
    noise_from_aa,
    noise_from_repeats,
    paired_tests,
    pass_counts,
    permutation_test,
    run_repeats,
    sharp_changes,
    valid_counts,
)


def _case(
    case_id: str, outcomes: list[bool | None], dataset: str = "single_topic", persona: str = "rebuilder"
) -> dict:
    """A case with one run per outcome; None is an errored run. One outcome is a plain single-run case."""
    runs = [{"passed": bool(o), "status": "error" if o is None else "ok"} for o in outcomes]
    base = {"id": case_id, "dataset": dataset, "persona": persona, **runs[0]}
    return base if len(runs) == 1 else {**base, "runs": runs}


def test_case_runs_and_pass_counts() -> None:
    single = _case("st-001", [True])
    repeated = _case("st-002", [True, False, True])
    assert case_runs(single) == [single]
    assert pass_counts(single) == (1, 1)
    assert pass_counts(repeated) == (2, 3)
    assert pass_counts(_case("st-003", [True, None])) == (1, 2)  # an errored run counts as not passed


def test_valid_counts_leave_out_errored_runs() -> None:
    assert valid_counts(_case("st-001", [True, None, True])) == (2, 2)
    assert valid_counts(_case("st-001", [False, None, None])) == (0, 1)
    assert valid_counts(_case("st-001", [None, None, None])) == (0, 3)  # nothing else to go on
    assert valid_counts(_case("st-001", [None])) == (0, 1)  # one errored run is a failure, as before
    assert error_count(_case("st-001", [True, None, None])) == 2


def test_run_repeats() -> None:
    assert run_repeats({"repeats": 3, "cases": []}) == 3
    assert run_repeats({"cases": [_case("st-001", [True, True])]}) == 2  # older file without the key
    assert run_repeats({"cases": [_case("st-001", [True])]}) == 1
    assert run_repeats({"cases": []}) == 1


@pytest.mark.parametrize(("repeats", "m"), [(1, 1), (2, 2), (3, 2), (4, 3), (5, 3)])
def test_default_min_fails_is_a_strict_majority(repeats: int, m: int) -> None:
    assert default_min_fails(repeats) == m


@pytest.mark.parametrize(
    ("base", "cand", "m", "expected"),
    [
        # one run per side: the plain flip
        ((1, 1), (0, 1), 1, "regressed"),
        ((0, 1), (1, 1), 1, "improved"),
        ((1, 1), (1, 1), 1, "unchanged_pass"),
        ((0, 1), (0, 1), 1, "unchanged_fail"),
        # three runs, m = 2
        ((3, 3), (1, 3), 2, "regressed"),
        ((3, 3), (0, 3), 2, "regressed"),
        ((3, 3), (2, 3), 2, "unstable"),  # one failing run is not enough
        ((2, 3), (0, 3), 2, "unstable"),  # the baseline was not stable, so it is never flagged
        ((0, 3), (2, 3), 2, "improved"),
        ((1, 3), (3, 3), 2, "unstable"),
        ((3, 3), (3, 3), 2, "unchanged_pass"),
        ((0, 3), (0, 3), 2, "unchanged_fail"),
        ((3, 3), (2, 3), 1, "regressed"),  # a stricter m flags a single failing run
        # a single-run baseline against a repeated candidate
        ((1, 1), (1, 3), 2, "regressed"),
    ],
)
def test_classify(base: tuple[int, int], cand: tuple[int, int], m: int, expected: str) -> None:
    assert classify(base, cand, m) == expected


def test_mcnemar_exact() -> None:
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(1, 7) == pytest.approx(18 / 256)  # 2 * P(X <= 1), X ~ Bin(8, 1/2)
    assert mcnemar_exact(7, 1) == mcnemar_exact(1, 7)
    assert mcnemar_exact(4, 1) == pytest.approx(12 / 32)
    assert mcnemar_exact(0, 10) == pytest.approx(2 / 1024)
    assert mcnemar_exact(3, 3) == 1.0  # capped at 1


# ---- the run-permutation test ----------------------------------------------------------------


def test_permutation_test_is_exact_mcnemar_with_one_run_per_side() -> None:
    for improved, regressed, stable in itertools.product(range(10), range(10), range(3)):
        cells = [(0, 1, 1, 1)] * improved + [(1, 1, 0, 1)] * regressed + [(1, 1, 1, 1), (0, 1, 0, 1)] * stable
        assert permutation_test(cells) == pytest.approx(mcnemar_exact(improved, regressed), abs=1e-12)


def _brute_force(cells: list[tuple[int, int, int, int]]) -> float:
    """Every way of relabelling each case's runs, counted directly."""
    observed = sum(cp / cr - bp / br for bp, br, cp, cr in cells)
    choices = []
    for bp, br, cp, cr in cells:
        runs = [1] * (bp + cp) + [0] * (br + cr - bp - cp)
        choices.append([(sum(runs[i] for i in pick), bp + cp, br, cr) for pick in itertools.combinations(range(br + cr), cr)])
    hits = total = 0
    for combo in itertools.product(*choices):
        stat = sum(x / cr - (s - x) / br for x, s, br, cr in combo)
        total += 1
        hits += abs(stat) >= abs(observed) - 1e-12
    return hits / total


@pytest.mark.parametrize(
    "cells",
    [
        [(3, 3, 1, 3), (2, 3, 3, 3), (3, 3, 2, 3)],
        [(2, 3, 0, 1), (1, 2, 2, 3), (3, 3, 1, 3), (0, 1, 1, 2)],  # mixed run counts
        [(1, 2, 1, 2), (0, 2, 2, 2)],
    ],
)
def test_permutation_test_matches_brute_force(cells: list[tuple[int, int, int, int]]) -> None:
    assert permutation_test(cells) == pytest.approx(_brute_force(cells), abs=1e-9)


def test_permutation_test_edge_cases() -> None:
    assert permutation_test([]) == 1.0
    assert permutation_test([(3, 3, 3, 3), (0, 3, 0, 3)]) == 1.0  # no case's runs disagree
    # Two cases each lose one of three runs. The old persona bootstrap called this p = 0.0002.
    assert permutation_test([(3, 3, 2, 3)] * 2 + [(3, 3, 3, 3)] * 9) == pytest.approx(0.5)
    # Every case drops from 3 of 3 to 0 of 3. Each case puts its 3 passes on the baseline side
    # with probability 1/20; two-sided, so every case rising 0 to 3 counts too.
    assert permutation_test([(3, 3, 0, 3)] * 6) == pytest.approx(2 * (1 / 20) ** 6)


def test_permutation_test_holds_its_size_with_nothing_changed() -> None:
    """A/A simulation on the real layout (40 cases, K=3): at most about 5% significant at 0.05."""
    rng = random.Random(20261021)
    trials, rejections = 600, 0
    for _ in range(trials):
        cells = []
        for i in range(40):
            p = 1.0 if i < 20 else (0.95, 0.8, 0.6, 0.3)[i % 4]
            cells.append((sum(rng.random() < p for _ in range(3)), 3, sum(rng.random() < p for _ in range(3)), 3))
        rejections += permutation_test(cells) <= 0.05
    assert rejections / trials <= 0.06  # exact test: the true rate is at most 0.05


# ---- multiplicity, bootstrap interval, noise ---------------------------------------------------


def test_holm() -> None:
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": None})
    # Sorted 0.01, 0.03, 0.04 with multipliers 3, 2, 1; then made monotone.
    assert adjusted == {"a": pytest.approx(0.03), "c": pytest.approx(0.06), "b": pytest.approx(0.06), "d": None}
    assert holm({"a": 0.6, "b": 0.7}) == {"a": 1.0, "b": 1.0}
    assert holm({"a": 0.02, "b": 0.02}) == {"a": pytest.approx(0.04), "b": pytest.approx(0.04)}  # ties
    assert holm({}) == {}


BOOT_DIFFS = [("p1", -1.0), ("p1", -1 / 3), ("p2", 0.0), ("p3", 1 / 3), ("p3", 0.0), ("p3", 0.0), ("p4", -2 / 3), ("p5", 1 / 3)]


def _ideal_bootstrap(diffs: list[tuple[str, float]]) -> list[float]:
    """Every equally likely resample of the clusters, enumerated."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for cluster, diff in diffs:
        sums[cluster] = sums.get(cluster, 0.0) + diff
        counts[cluster] = counts.get(cluster, 0) + 1
    names = sorted(sums)
    return sorted(
        sum(sums[names[i]] for i in picks) / sum(counts[names[i]] for i in picks)
        for picks in itertools.product(range(len(names)), repeat=len(names))
    )


def test_cluster_bootstrap_matches_the_ideal_bootstrap() -> None:
    boot = cluster_bootstrap(BOOT_DIFFS)
    ideal = _ideal_bootstrap(BOOT_DIFFS)
    assert boot.clusters == 5
    assert boot.mean == pytest.approx(-1 / 6)  # weighted by cases, not the mean of the 5 persona means
    assert boot.low == pytest.approx(_quantile(ideal, 0.025)) == pytest.approx(-4 / 7)
    assert boot.high == pytest.approx(_quantile(ideal, 0.975)) == pytest.approx(4 / 27)
    assert boot.low > ideal[0] and boot.high < ideal[-1]  # not the min and max
    narrower = cluster_bootstrap(BOOT_DIFFS, confidence=0.9)
    assert boot.low < narrower.low and narrower.high < boot.high
    assert cluster_bootstrap(BOOT_DIFFS) == boot  # seeded, so reports are reproducible


def test_cluster_bootstrap_with_few_clusters_gives_no_interval() -> None:
    few = cluster_bootstrap([("p1", -1.0), ("p2", -1 / 3)])
    assert few.clusters == 2 < MIN_CI_CLUSTERS
    assert (few.low, few.high) == (None, None)
    assert few.mean == pytest.approx(-2 / 3)
    with pytest.raises(ValueError):
        cluster_bootstrap([])


def test_cluster_bootstrap_snaps_float_residue_to_zero() -> None:
    # A 3/3 to 2/3 case and a 0/3 to 1/3 case in one persona: (2/3 - 1) + 1/3 is -5.55e-17, not 0.
    residue = (2 / 3 - 1.0) + (1 / 3 - 0.0)
    assert residue != 0.0
    boot = cluster_bootstrap([("p1", 2 / 3 - 1.0), ("p1", 1 / 3 - 0.0), ("p2", 0.0), ("p3", 0.0)])
    assert (boot.mean, boot.low, boot.high) == (0.0, 0.0, 0.0)
    assert _r(-4.5e-18) == 0.0 and str(_r(-4.5e-18)) == "0.0"  # never "-0.0" in a report


def test_expected_flips() -> None:
    assert expected_flips(2, 3) == pytest.approx(2 / 3)
    assert expected_flips(3, 3) == 0.0
    assert expected_flips(0, 3) == 0.0
    assert expected_flips(1, 2) == 1.0
    assert expected_flips(1, 1) is None


def test_expected_flips_is_unbiased_for_two_single_runs() -> None:
    rng = random.Random(7)
    for p in (0.5, 0.8, 0.95):
        estimates = [expected_flips(sum(rng.random() < p for _ in range(3)), 3) or 0.0 for _ in range(20_000)]
        assert sum(estimates) / len(estimates) == pytest.approx(2 * p * (1 - p), abs=0.01)


# ---- paired_tests ------------------------------------------------------------------------------


def test_paired_tests_single_run_uses_mcnemar_with_holm() -> None:
    pairs = [(_case(f"st-00{i}", [True]), _case(f"st-00{i}", [False])) for i in range(1, 6)]
    pairs += [(_case("mi-001", [False], "multi_intent"), _case("mi-001", [True], "multi_intent"))]
    test = paired_tests(pairs, ["single_topic", "multi_intent", "context_use"])
    assert test is not None and test["method"] == "mcnemar_exact"
    overall = test["overall"]
    assert (overall["improved"], overall["regressed"], overall["cases"]) == (1, 5, 6)
    assert overall["p_value"] == round(mcnemar_exact(1, 5), 6)
    assert overall["mean_diff"] == round(-4 / 6, 4)
    assert "p_holm" not in overall
    single = test["by_dataset"]["single_topic"]
    assert single["p_value"] == round(mcnemar_exact(0, 5), 6)
    assert single["p_holm"] == round(min(1.0, 2 * mcnemar_exact(0, 5)), 6)  # two datasets in the family
    assert set(test["by_dataset"]) == {"single_topic", "multi_intent"}
    assert test["family"] == 2 and test["ci"] is None
    assert paired_tests([], ["single_topic"]) is None


def test_dataset_significance_comes_from_the_holm_p_value() -> None:
    pairs = [(_case(f"st-0{i:02}", [True]), _case(f"st-0{i:02}", [False])) for i in range(6)]
    pairs += [
        (_case(f"mi-0{i:02}", [True], "multi_intent"), _case(f"mi-0{i:02}", [False], "multi_intent"))
        for i in range(6)
    ]
    test = paired_tests(pairs, ["single_topic", "multi_intent"])
    for row in test["by_dataset"].values():
        assert row["p_value"] == round(2 / 64, 6) and row["p_value"] <= 0.05  # significant on its own
        assert row["p_holm"] == round(4 / 64, 6) and row["significant"] is False  # but not after Holm
    assert test["overall"]["significant"] is True  # the overall test is not adjusted


def test_paired_tests_repeated_runs_use_the_permutation_test() -> None:
    personas = ["rebuilder", "renter", "collections", "high-util"]
    pairs = [
        (_case(f"st-00{i}", [True, True, True], persona=p), _case(f"st-00{i}", [False, False, True], persona=p))
        for i, p in enumerate(personas, start=1)
    ]
    test = paired_tests(pairs, ["single_topic"])
    assert test is not None and test["method"] == "run_permutation"
    overall = test["overall"]
    assert overall["cases"] == 4 and overall["informative"] == 4 and overall["clusters"] == 4
    assert overall["mean_diff"] == round(-2 / 3, 4)
    assert overall["p_value"] == round(permutation_test([(3, 3, 1, 3)] * 4), 6)
    assert overall["ci_low"] == overall["ci_high"] == round(-2 / 3, 4)  # every persona changed the same way
    assert overall["significant"] is (permutation_test([(3, 3, 1, 3)] * 4) <= 0.05)
    assert test["by_dataset"]["single_topic"]["p_holm"] == overall["p_value"]  # a family of one
    assert test["ci"] == {
        "method": "persona_cluster_bootstrap",
        "confidence": 0.95,
        "resamples": BOOTSTRAP_RESAMPLES,
        "min_clusters": MIN_CI_CLUSTERS,
        "descriptive": True,
    }


def test_two_personas_losing_one_run_each_is_not_significant() -> None:
    """The case the persona bootstrap got wrong: a dataset subset with two personas."""
    pairs = [
        (_case("st-001", [True] * 3, persona="rebuilder"), _case("st-001", [True, False, True], persona="rebuilder")),
        (_case("st-002", [True] * 3, persona="high-util"), _case("st-002", [False, True, True], persona="high-util")),
    ]
    row = paired_tests(pairs, ["single_topic"])["by_dataset"]["single_topic"]
    assert row["p_value"] == 0.5 and row["significant"] is False
    assert row["clusters"] == 2 and row["ci_low"] is None  # too few personas for an interval


def test_mixed_repeats_use_the_permutation_test() -> None:
    pairs = [(_case("st-001", [True]), _case("st-001", [False, False, True]))]
    test = paired_tests(pairs, ["single_topic"])
    assert test["method"] == "run_permutation"
    assert test["overall"]["p_value"] == round(permutation_test([(1, 1, 1, 3)]), 6)


def test_errored_runs_are_left_out_on_both_sides() -> None:
    pairs = [(_case("st-001", [True, None, True]), _case("st-001", [True, True, True]))]
    assert paired_tests(pairs, ["single_topic"])["overall"]["mean_diff"] == 0.0
    # The same error rate on both sides is not a regression.
    personas = ["rebuilder", "renter", "high-util", "collections"]
    pairs = [
        (_case(f"st-0{i:02}", [True, None, True], persona=personas[i % 4]),
         _case(f"st-0{i:02}", [None, True, True], persona=personas[i % 4]))
        for i in range(8)
    ]
    overall = paired_tests(pairs, ["single_topic"])["overall"]
    assert (overall["mean_diff"], overall["p_value"], overall["significant"]) == (0.0, 1.0, False)


def test_p_exactly_alpha_is_significant() -> None:
    """Float sums put this p a hair above 0.05; the exact fraction is 1/20."""
    from fractions import Fraction

    from evals.stats import _permutation

    cells = [(0, 3, 3, 3), (1, 3, 2, 3), (2, 3, 3, 3)]
    assert _permutation(cells) == Fraction(1, 20)
    assert _permutation(cells) == pytest.approx(_brute_force(cells))
    pairs = [
        (_case("st-001", [False] * 3), _case("st-001", [True] * 3)),
        (_case("st-002", [True, False, False], persona="renter"), _case("st-002", [True, True, False], persona="renter")),
        (_case("st-003", [True, True, False], persona="high-util"), _case("st-003", [True] * 3, persona="high-util")),
    ]
    overall = paired_tests(pairs, ["single_topic"])["overall"]
    assert overall["p_value"] == 0.05 and overall["significant"] is True


def test_noise_from_repeats() -> None:
    cases = [
        _case("st-001", [True, True, True]),
        _case("st-002", [True, False, True]),
        _case("mi-001", [False, True, False], "multi_intent"),
    ]
    noise = noise_from_repeats(cases, ["single_topic", "multi_intent"])
    assert noise is not None and noise["source"] == "baseline_repeats" and noise["unit"] == "single_run_flips"
    assert noise["overall"] == {"cases": 3, "flips": round(4 / 3, 4), "regressed": None, "improved": None}
    assert noise["by_dataset"]["single_topic"]["flips"] == round(2 / 3, 4)
    assert noise["unstable"] == ["st-002", "mi-001"]
    assert noise["unmeasured"] == []
    assert noise_from_repeats([_case("st-001", [True])], ["single_topic"]) is None


def test_noise_from_repeats_leaves_out_cases_without_two_valid_runs() -> None:
    cases = [_case("st-001", [True, False, True]), _case("st-002", [True, None, None]), _case("st-003", [None] * 3)]
    noise = noise_from_repeats(cases, ["single_topic"])
    assert noise["overall"] == {"cases": 1, "flips": round(2 / 3, 4), "regressed": None, "improved": None}
    assert noise["unmeasured"] == ["st-002", "st-003"]  # an all-errored case is not a stable one
    assert noise_from_repeats([_case("st-002", [True, None, None])], ["single_topic"]) is None
    # A case that simply ran once among repeated ones is unmeasured too.
    mixed = noise_from_repeats([_case("st-001", [True, False, True]), _case("st-002", [True])], ["single_topic"])
    assert mixed["unmeasured"] == ["st-002"]


def test_pairs_with_an_all_errored_side_are_left_out_of_the_test() -> None:
    pairs = [
        (_case("st-001", [True] * 3), _case("st-001", [None] * 3)),
        (_case("st-002", [True] * 3, persona="renter"), _case("st-002", [True] * 3, persona="renter")),
    ]
    overall = paired_tests(pairs, ["single_topic"])["overall"]
    assert (overall["cases"], overall["left_out"], overall["mean_diff"], overall["p_value"]) == (1, 1, 0.0, 1.0)
    only_errors = paired_tests(pairs[:1], ["single_topic"])["overall"]
    assert only_errors["cases"] == 0 and only_errors["p_value"] is None and only_errors["significant"] is None


def test_flag_rule_text() -> None:
    from evals.stats import flag_rule_text

    assert flag_rule_text(1, 1, 1).endswith("(one run each)")
    assert flag_rule_text(1, 1, 2).startswith(
        "a case regresses when it fails its one run and passed every one of its 2 baseline runs that did not error"
    )
    assert "fails at least 2 of its 3 runs" in flag_rule_text(2, 3, 3)


def test_noise_from_aa() -> None:
    pairs = [
        (_case("st-001", [True]), _case("st-001", [False])),
        (_case("st-002", [False]), _case("st-002", [True])),
        (_case("st-003", [True]), _case("st-003", [True])),
    ]
    noise = noise_from_aa(pairs, ["single_topic"], 1)
    assert noise is not None and noise["source"] == "aa_run" and noise["unit"] == "flag_rule"
    assert noise["min_fails"] == 1
    assert noise["overall"] == {"cases": 3, "flips": 2, "regressed": 1, "improved": 1}
    assert noise["unstable"] == ["st-001", "st-002"]
    assert noise_from_aa([], ["single_topic"], 1) is None

    varied = [(_case("st-001", [True] * 3), _case("st-001", [True, False, True]))]
    assert noise_from_aa(varied, ["single_topic"], 2)["unstable"] == ["st-001"]  # unstable, not flagged


def test_sharp_changes() -> None:
    pairs = [
        (_case("st-001", [True, True, False]), _case("st-001", [False, False, False])),  # 2/3 to 0/3
        (_case("st-002", [True, True, False]), _case("st-002", [True, False, False])),  # 2/3 to 1/3
        (_case("st-003", [False, True, False]), _case("st-003", [True, True, True])),  # 1/3 to 3/3
    ]
    assert sharp_changes(pairs, ["st-001", "st-002", "st-003"], 2) == {"dropped": ["st-001"], "rose": ["st-003"]}
    assert sharp_changes(pairs, [], 2) == {"dropped": [], "rose": []}
    # 3 of 3 to a single valid run that failed: unstable (too few runs to flag), but a sharp drop.
    errored = [(_case("st-004", [True] * 3), _case("st-004", [False, None, None]))]
    assert classify((3, 3), (0, 1), 2) == "unstable"
    assert sharp_changes(errored, ["st-004"], 2, 3) == {"dropped": ["st-004"], "rose": []}


def test_sharp_changes_tolerate_float_residue() -> None:
    # 1/2 to 4/6 is a change of 1/6, which floats compute as 0.16666666666666663 < 1/6.
    rose = [(_case("st-001", [True, False]), _case("st-001", [True, True, True, True, False, False]))]
    assert sharp_changes(rose, ["st-001"], 1) == {"dropped": [], "rose": ["st-001"]}
    # 2/3 to 3/6 is a drop of 1/6, just as close.
    dropped = [(_case("st-001", [True, True, False]), _case("st-001", [True, True, True, False, False, False]))]
    assert sharp_changes(dropped, ["st-001"], 1) == {"dropped": ["st-001"], "rose": []}


def test_quantile_interpolation_matches_numpy_default() -> None:
    values = [0.0, 1.0, 2.0, 3.0]
    assert _quantile(values, 0.5) == 1.5
    assert _quantile(values, 0.0) == 0.0 and _quantile(values, 1.0) == 3.0
    assert math.isclose(_quantile(values, 0.25), 0.75)
