"""Statistics for regression reports: separating real changes from LLM run-to-run noise (SPEC section 3).

A results file holds K runs per case (`run.py --repeats K`). A report pairs each case with its
baseline and adds:

- a flag rule: a case regresses only when it fails at least m of its K runs and passed every
  baseline run (and improves when it passes at least m and failed every baseline run);
- a paired test of the net change: an exact McNemar test on the cases that flipped when both
  sides ran once, otherwise an exact permutation test that shuffles run labels within each case.
  Both test whether the overall pass rate moved, so a balanced tradeoff can read as no change;
- a persona-cluster bootstrap interval for the mean per-case change, as a description only (with
  at most 6 personas it is too coarse to test with);
- Holm's correction across the per-dataset tests;
- an A/A noise floor: how many cases flip between two runs of the baseline with nothing changed.

Errored runs are left out of a case's counts on either side when that side has other runs: an
infrastructure error says nothing about the bot. For the flag rule, a side whose every run errored
counts as failing, as a single errored run always has. The paired test and the noise floor leave
such a case out instead, since its "failures" are not runs of the bot at all.
P-values are computed exactly (as fractions), so p equal to alpha is significant.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

ALPHA = 0.05
CONFIDENCE = 0.95
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0
MIN_CI_CLUSTERS = 3  # below this the bootstrap interval is just the spread of one or two personas
# Sums of fractions like 1/3 leave float residue; anything this close to zero is zero.
_ZERO = 1e-9

METHODS = ("mcnemar_exact", "run_permutation")

Pair = tuple[Mapping[str, Any], Mapping[str, Any]]  # (baseline case, candidate case)


def case_runs(case: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Every run of a case: the `runs` list of a repeated run, or the case itself for a single run."""
    runs = case.get("runs")
    return list(runs) if runs else [case]


def pass_counts(case: Mapping[str, Any]) -> tuple[int, int]:
    """(runs passed, runs) for one case. An errored run counts as not passed."""
    runs = case_runs(case)
    return sum(1 for run in runs if run.get("passed")), len(runs)


def error_count(case: Mapping[str, Any]) -> int:
    return sum(1 for run in case_runs(case) if run.get("status") == "error")


def ok_runs(case: Mapping[str, Any]) -> int:
    """Runs that did not error."""
    return len(case_runs(case)) - error_count(case)


def valid_counts(case: Mapping[str, Any]) -> tuple[int, int]:
    """(runs passed, runs) leaving out errored runs when the case has other runs.

    A case whose every run errored keeps them as failures, as a single errored run always did.
    """
    valid = [run for run in case_runs(case) if run.get("status") != "error"]
    if not valid:
        return pass_counts(case)
    return sum(1 for run in valid if run.get("passed")), len(valid)


def pair_counts(base: Mapping[str, Any], cand: Mapping[str, Any]) -> tuple[tuple[int, int], tuple[int, int]]:
    """The (passed, runs) counts the flag rule, the tests and the rates use for one pair."""
    return valid_counts(base), valid_counts(cand)


def run_repeats(results: Mapping[str, Any]) -> int:
    """K for a results file. Files written before --repeats existed ran every case once."""
    declared = results.get("repeats")
    if isinstance(declared, int) and declared >= 1:
        return declared
    return max((len(case_runs(case)) for case in results.get("cases", [])), default=1)


# Every After run before results recorded `skill_cap` used a cap of 3 (config.py has had 3 since the
# first commit). Fixed here, not read from config, so raising the configured cap cannot relabel old files.
LEGACY_SKILL_CAP = 3


def run_skill_cap(results: Mapping[str, Any]) -> int | None:
    """The After bot's cap on new skills per message in a results file; None for the Before bot."""
    if results.get("bot") != "after":
        return None
    declared = results.get("skill_cap")
    return declared if isinstance(declared, int) and declared >= 1 else LEGACY_SKILL_CAP


def default_min_fails(repeats: int) -> int:
    """A strict majority of K runs: 1 of 1, 2 of 2, 2 of 3, 3 of 5."""
    return repeats // 2 + 1


def classify(base: tuple[int, int], cand: tuple[int, int], min_fails: int) -> str:
    """Transition of one case from its (passed, runs) counts under the flag rule.

    With one run per side this is the plain flip: pass to fail regresses, fail to pass improves.
    """
    base_passed, base_runs = base
    cand_passed, cand_runs = cand
    base_stable_pass, base_stable_fail = base_passed == base_runs, base_passed == 0
    if base_stable_pass and cand_runs - cand_passed >= min_fails:
        return "regressed"
    if base_stable_fail and cand_passed >= min_fails:
        return "improved"
    if base_stable_pass and cand_passed == cand_runs:
        return "unchanged_pass"
    if base_stable_fail and cand_passed == 0:
        return "unchanged_fail"
    return "unstable"


def flag_rule_text(min_fails: int, cand_repeats: int, base_repeats: int) -> str:
    if cand_repeats == 1 and base_repeats == 1:
        return "a case regresses when it passed in the baseline and fails in the candidate (one run each)"
    base_runs = "its baseline run" if base_repeats == 1 else f"every one of its {base_repeats} baseline runs that did not error"
    if cand_repeats == 1:
        fails, passes = "fails its one run", "passes its one run"
    else:
        fails = f"fails at least {min_fails} of its {cand_repeats} runs"
        passes = f"passes at least {min_fails} of {cand_repeats}"
    return f"a case regresses when it {fails} and passed {base_runs}; it improves when it {passes} and failed {base_runs}"


def _mcnemar(improved: int, regressed: int) -> Fraction:
    n = improved + regressed
    if n == 0:
        return Fraction(1)
    tail = Fraction(sum(math.comb(n, i) for i in range(min(improved, regressed) + 1)), 2**n)
    return min(Fraction(1), 2 * tail)


def mcnemar_exact(improved: int, regressed: int) -> float:
    """Two-sided exact McNemar p-value: a binomial test of the discordant pairs against 1/2."""
    return float(_mcnemar(improved, regressed))


Cell = tuple[int, int, int, int]  # (baseline passed, baseline runs, candidate passed, candidate runs)


def _permutation(cells: Sequence[Cell]) -> Fraction:
    if not cells:
        return Fraction(1)
    scale = math.lcm(*(k for _, base_runs, _, cand_runs in cells for k in (base_runs, cand_runs)))
    observed = 0
    weights: dict[int, int] = {0: 1}  # lattice value -> number of relabellings, out of `total`
    total = 1
    for base_passed, base_runs, cand_passed, cand_runs in cells:
        runs, passes = base_runs + cand_runs, base_passed + cand_passed

        def lattice(x: int) -> int:  # the case's difference, times `scale`, with x candidate passes
            return x * (scale // cand_runs) - (passes - x) * (scale // base_runs)

        observed += lattice(cand_passed)
        if passes in (0, runs):
            continue  # every arrangement gives a difference of zero
        step: dict[int, int] = {}
        for x in range(max(0, cand_runs - (runs - passes)), min(cand_runs, passes) + 1):
            value = lattice(x)
            step[value] = step.get(value, 0) + math.comb(passes, x) * math.comb(runs - passes, cand_runs - x)
        total *= math.comb(runs, cand_runs)
        merged: dict[int, int] = {}
        for value, weight in weights.items():
            for delta, count in step.items():
                merged[value + delta] = merged.get(value + delta, 0) + weight * count
        weights = merged
    hits = sum(weight for value, weight in weights.items() if abs(value) >= abs(observed))
    return min(Fraction(1), Fraction(hits, total))


def permutation_test(cells: Sequence[Cell]) -> float:
    """Exact two-sided p-value for the mean per-case change in pass fraction.

    Under the null hypothesis that the change did nothing, a case's baseline and candidate runs
    are exchangeable, so given the case's total passes its candidate passes are hypergeometric.
    The statistic, the sum of per-case differences, then has the exact null distribution of a
    sum of independent hypergeometrics, counted here in whole numbers on an integer lattice, so
    the p-value is an exact fraction. It is the null probability of a sum at least as far from
    zero as the one observed. It needs no resampling and no minimum number of personas, and with
    one run per side it is exactly the McNemar test. The lattice is scaled by the least common
    multiple of the run counts, so it stays small for K up to about 5 and slows down when errored
    runs leave many different run counts at a large K.
    """
    return float(_permutation(cells))


@dataclass(frozen=True)
class Bootstrap:
    mean: float
    low: float | None  # None when there are fewer than MIN_CI_CLUSTERS clusters
    high: float | None
    clusters: int


def _quantile(ordered: Sequence[float], q: float) -> float:
    """Linear interpolation between order statistics (numpy's default)."""
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _snap(value: float) -> float:
    return 0.0 if abs(value) < _ZERO else value


def cluster_bootstrap(
    diffs: Sequence[tuple[str, float]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    confidence: float = CONFIDENCE,
) -> Bootstrap:
    """Percentile bootstrap interval of the mean per-case difference, resampling clusters.

    `diffs` holds (cluster, difference) per case. Each resample draws as many clusters as there
    are, with replacement, and takes the case-weighted mean over all their cases. This is a
    description of how much the change varies between personas, not a test: with a handful of
    clusters every resample can land on one side of zero, so it says nothing about noise.
    """
    if not diffs:
        raise ValueError("no cases to bootstrap")
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for cluster, diff in diffs:
        sums[cluster] = sums.get(cluster, 0.0) + diff
        counts[cluster] = counts.get(cluster, 0) + 1
    mean = _snap(sum(sums.values()) / len(diffs))
    names = sorted(sums)
    if len(names) < MIN_CI_CLUSTERS:
        return Bootstrap(mean, None, None, len(names))

    cluster_sums = [sums[name] for name in names]
    cluster_counts = [counts[name] for name in names]
    indices = range(len(names))
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        picks = rng.choices(indices, k=len(names))
        means.append(sum(cluster_sums[i] for i in picks) / sum(cluster_counts[i] for i in picks))
    means.sort()
    tail = (1 - confidence) / 2
    return Bootstrap(mean, _snap(_quantile(means, tail)), _snap(_quantile(means, 1 - tail)), len(names))


def holm(p_values: Mapping[str, Any]) -> dict[str, Any]:
    """Holm step-down adjusted p-values. A None p-value is left out of the family and stays None."""
    tested = sorted((p, key) for key, p in p_values.items() if p is not None)
    adjusted: dict[str, Any] = {key: None for key in p_values}
    running: Any = 0
    for rank, (p, key) in enumerate(tested):
        running = max(running, min(1, (len(tested) - rank) * p))  # stays exact for fractions
        adjusted[key] = running
    return adjusted


def expected_flips(passed: int, runs: int) -> float | None:
    """Chance that two single runs of a case disagree, from K >= 2 runs: 2k(K-k) / (K(K-1)).

    This is the share of disagreeing pairs among the K runs, an unbiased estimate of 2p(1-p).
    """
    if runs < 2:
        return None
    return 2 * passed * (runs - passed) / (runs * (runs - 1))


def _r(value: float | Fraction | None, digits: int = 4) -> float | None:
    """Round for the report, with float residue and -0.0 turned into 0.0."""
    return None if value is None else round(_snap(float(value)), digits) + 0.0


def _rp(p: Fraction | None) -> float | None:
    """P-values keep 6 decimals, so the display can tell 0.0502 from 0.05."""
    return _r(p, 6)


def choose_method(pairs: Sequence[Pair]) -> str:
    """Exact McNemar when every case ran once on both sides, otherwise the run-permutation test."""
    single = all(len(case_runs(b)) == 1 and len(case_runs(c)) == 1 for b, c in pairs)
    return "mcnemar_exact" if single else "run_permutation"


def testable(pairs: Sequence[Pair]) -> list[Pair]:
    """Pairs with at least one run that did not error on each side; the others say nothing about the bot."""
    return [(base, cand) for base, cand in pairs if ok_runs(base) and ok_runs(cand)]


def _test(pairs: Sequence[Pair], method: str, seed: int) -> tuple[dict[str, Any], Fraction | None]:
    """One row of the paired test, and its exact p-value (Holm and significance work on that)."""
    tested = testable(pairs)
    left_out = len(pairs) - len(tested)
    if not tested:
        row: dict[str, Any] = {"cases": 0, "left_out": left_out, "mean_diff": None, "p_value": None}
        if method == "mcnemar_exact":
            return {**row, "improved": 0, "regressed": 0}, None
        return {**row, "informative": 0, "clusters": 0, "ci_low": None, "ci_high": None}, None
    pairs = tested
    counts = [pair_counts(base, cand) for base, cand in pairs]
    diffs = [cp / cr - bp / br for (bp, br), (cp, cr) in counts]
    mean = sum(diffs) / len(diffs)
    if method == "mcnemar_exact":
        improved = sum(1 for (bp, _), (cp, _) in counts if not bp and cp)
        regressed = sum(1 for (bp, _), (cp, _) in counts if bp and not cp)
        p = _mcnemar(improved, regressed)
        row = {"cases": len(pairs), "left_out": left_out, "mean_diff": _r(mean), "improved": improved, "regressed": regressed}
        return {**row, "p_value": _rp(p)}, p
    cells = [(bp, br, cp, cr) for (bp, br), (cp, cr) in counts]
    p = _permutation(cells)
    boot = cluster_bootstrap([(cand.get("persona") or cand["id"], d) for (_, cand), d in zip(pairs, diffs)], seed=seed)
    row = {
        "cases": len(pairs),
        "left_out": left_out,
        "mean_diff": _r(mean),
        "informative": sum(1 for bp, br, cp, cr in cells if 0 < bp + cp < br + cr),
        "clusters": boot.clusters,
        "ci_low": _r(boot.low),
        "ci_high": _r(boot.high),
    }
    return {**row, "p_value": _rp(p)}, p


def _significant(p: Fraction | float | None, alpha: float) -> bool | None:
    """Exact comparison: alpha is read as the decimal it is written as (0.05 is 1/20)."""
    return None if p is None else Fraction(p) <= Fraction(str(alpha))


def paired_tests(
    pairs: Sequence[Pair],
    datasets: Sequence[str],
    *,
    alpha: float = ALPHA,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any] | None:
    """The overall test (the primary one, unadjusted) and one test per dataset, Holm-corrected together."""
    if not pairs:
        return None
    method = choose_method(pairs)
    overall, overall_p = _test(pairs, method, seed)
    overall["significant"] = _significant(overall_p, alpha)
    by_dataset: dict[str, dict[str, Any]] = {}
    raw: dict[str, Fraction | None] = {}
    for name in datasets:
        subset = [(b, c) for b, c in pairs if c["dataset"] == name]
        if subset:
            by_dataset[name], raw[name] = _test(subset, method, seed)
    adjusted = holm(raw)
    for name, row in by_dataset.items():
        row["p_holm"] = _rp(adjusted[name])
        row["significant"] = _significant(adjusted[name], alpha)
    ci = None
    if method == "run_permutation":
        ci = {
            "method": "persona_cluster_bootstrap",
            "confidence": CONFIDENCE,
            "resamples": BOOTSTRAP_RESAMPLES,
            "min_clusters": MIN_CI_CLUSTERS,
            "descriptive": True,
        }
    return {
        "method": method,
        "alpha": alpha,
        "ci": ci,
        "family": sum(1 for p in raw.values() if p is not None),
        "correction": (
            "Holm across the per-dataset tests, which controls the chance of any false positive among them; "
            "the overall test is the primary one and is not adjusted, so across every row that chance can "
            "reach twice alpha"
        ),
        "overall": overall,
        "by_dataset": by_dataset,
    }


def noise_from_repeats(cases: Sequence[Mapping[str, Any]], datasets: Sequence[str]) -> dict[str, Any] | None:
    """A/A noise floor from the baseline's own repeats: each pair of its K runs is a run against itself.

    `flips` is the expected number of cases that flip between two single runs of the baseline.
    That is single-run noise: the flag rule needs a stable baseline and m failing runs, so far
    fewer cases get flagged by chance. None when no case ran more than once. A case with fewer
    than two runs that did not error cannot be measured; it is listed as such.
    """
    if not any(len(case_runs(case)) >= 2 for case in cases):
        return None
    measurable = [case for case in cases if ok_runs(case) >= 2]
    if not measurable:
        return None

    def bucket(subset: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        flips = sum(expected_flips(*valid_counts(case)) or 0.0 for case in subset)
        return {"cases": len(subset), "flips": _r(flips), "regressed": None, "improved": None}

    return {
        "source": "baseline_repeats",
        "unit": "single_run_flips",
        "overall": bucket(measurable),
        "by_dataset": {
            name: bucket(subset) for name in datasets if (subset := [c for c in measurable if c["dataset"] == name])
        },
        "unstable": [case["id"] for case in measurable if 0 < valid_counts(case)[0] < valid_counts(case)[1]],
        "unmeasured": [case["id"] for case in cases if ok_runs(case) < 2],
    }


def noise_from_aa(pairs: Sequence[Pair], datasets: Sequence[str], min_fails: int) -> dict[str, Any] | None:
    """A/A noise floor from a second run of the baseline, compared with it under the flag rule with
    `min_fails`. A case with only errored runs on either side is left out and listed: an all-errored
    side would otherwise count as failing, and that is infrastructure, not noise in the bot."""
    left_out = [cand["id"] for base, cand in pairs if not (ok_runs(base) and ok_runs(cand))]
    pairs = testable(pairs)
    if not pairs:
        return None
    labels = {cand["id"]: classify(*pair_counts(base, cand), min_fails) for base, cand in pairs}

    def bucket(subset: Sequence[Pair]) -> dict[str, Any]:
        regressed = sum(1 for _, c in subset if labels[c["id"]] == "regressed")
        improved = sum(1 for _, c in subset if labels[c["id"]] == "improved")
        return {"cases": len(subset), "flips": regressed + improved, "regressed": regressed, "improved": improved}

    return {
        "source": "aa_run",
        "unit": "flag_rule",
        "min_fails": min_fails,
        "overall": bucket(pairs),
        "by_dataset": {
            name: bucket(subset) for name in datasets if (subset := [(b, c) for b, c in pairs if c["dataset"] == name])
        },
        "unstable": [cand["id"] for _, cand in pairs if labels[cand["id"]] in ("regressed", "improved", "unstable")],
        "left_out": left_out,
    }


def sharp_changes(
    pairs: Sequence[Pair], unstable: Sequence[str], min_fails: int, cand_repeats: int | None = None
) -> dict[str, list[str]]:
    """Unstable cases whose pass fraction moved by at least m runs' worth (m / K), which the flag
    rule leaves out: for example 2 of 3 to 0 of 3, or 3 of 3 to a single valid run that failed.
    K is the candidate's runs per case, so errored runs do not raise the bar."""
    wanted = set(unstable)
    dropped: list[str] = []
    rose: list[str] = []
    for base, cand in pairs:
        if cand["id"] not in wanted:
            continue
        (bp, br), (cp, cr) = pair_counts(base, cand)
        change = cp / cr - bp / br
        bar = min_fails / (cand_repeats or cr)
        if change <= -bar + _ZERO:
            dropped.append(cand["id"])
        elif change >= bar - _ZERO:
            rose.append(cand["id"])
    return {"dropped": dropped, "rose": rose}
