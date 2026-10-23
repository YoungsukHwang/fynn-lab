"""Regression report: compare a candidate results JSON with its baseline.

    python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s1.json \
        --out ../results/reports/s1 --scenario s1 [--aa ../results/aa/after.json] [--min-fails 2]

Only case ids present in the candidate are compared, so a selected (dependent-only) run is
compared on exactly the cases it reran. Next to the verdict the report gives the flag rule, a
paired test of the net change with Holm's correction across datasets, the A/A noise floor, and a
note when the verdict and the test disagree (see evals/stats.py). Writes report.json (for the
site) and report.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evals.cases import DATASETS
from evals.scenarios import Scenario, load_scenario
from evals.setup import PART_LABELS
from evals.stats import (
    ALPHA,
    case_runs,
    classify,
    default_min_fails,
    error_count,
    flag_rule_text,
    noise_from_aa,
    noise_from_repeats,
    ok_runs,
    pair_counts,
    paired_tests,
    run_repeats,
    run_skill_cap,
    sharp_changes,
    valid_counts,
)

# "unstable" is empty with one run per side: there every case either flips or stays put.
TRANSITIONS = ("improved", "regressed", "unchanged_pass", "unchanged_fail", "unstable")
# The verdict when no case could be compared: nothing passed or failed, so neither Passed nor Not passed.
NO_CASES = "No cases compared"


def _rate(passed: int, total: int) -> float | None:
    return round(passed / total, 4) if total else None


def _n(count: int | float, word: str, plural: str | None = None) -> str:
    """'1 run', '3 runs'."""
    return f"{count} {word if count == 1 else (plural or word + 's')}"


def observed_direction(improved: int, regressed: int) -> str:
    if improved and regressed:
        return "tradeoff"
    if improved:
        return "improve"
    if regressed:
        return "regress"
    return "no change"


def hypothesis_matches(expected: str, improved: int, regressed: int) -> bool:
    if expected == "improve":
        return improved > 0 and regressed == 0
    if expected == "regress":
        return regressed > 0
    if expected == "tradeoff":
        return improved > 0 and regressed > 0
    raise ValueError(f"unknown hypothesis {expected!r}")


def _pick(case: Mapping[str, Any], passed: bool) -> Mapping[str, Any]:
    """The first run with this outcome, preferring runs that did not error."""
    runs = [run for run in case_runs(case) if bool(run.get("passed")) == passed]
    return next((run for run in runs if run.get("status") != "error"), runs[0] if runs else case)


def _failure(base: Mapping[str, Any], cand: Mapping[str, Any], *, regressed: bool = True) -> dict[str, Any]:
    """A flagged case with one run from each side that shows the change: for a regression a failing
    candidate run next to a passing baseline run, for an improvement the other way round."""
    cand_run = _pick(cand, passed=not regressed)
    base_run = _pick(base, passed=regressed)
    judge = cand_run.get("judge") or {}
    checks = cand_run.get("checks") or {}
    (base_passed, base_runs), (cand_passed, cand_runs) = valid_counts(base), valid_counts(cand)
    return {
        "id": cand["id"],
        "dataset": cand["dataset"],
        "persona": cand["persona"],
        "intents": cand.get("intents"),
        "message": cand["message"],
        "skills": cand.get("skills", []),
        "baseline_routing": (base_run.get("routing") or {}).get("selected"),
        "candidate_routing": (cand_run.get("routing") or {}).get("selected"),
        "baseline_reply": base_run.get("reply"),
        "candidate_reply": cand_run.get("reply"),
        "judge_facts": judge.get("facts", []),
        "judge_reason": judge.get("reason", ""),
        "check_failures": checks.get("failures", []),
        "status": cand_run.get("status"),
        "error": cand_run.get("error"),
        "baseline_passed": base_passed,
        "baseline_runs": base_runs,
        "candidate_passed": cand_passed,
        "candidate_runs": cand_runs,
        "baseline_errored": error_count(base),
        "candidate_errored": error_count(cand),
        "baseline_all_errored": not ok_runs(base),
        "candidate_all_errored": not ok_runs(cand),
        "baseline_status": base_run.get("status"),
        "baseline_error": base_run.get("error"),
    }


def _run_info(results: Mapping[str, Any]) -> dict[str, Any]:
    info = {key: results.get(key) for key in ("name", "bot", "scenario", "created_at", "models")}
    return {**info, "repeats": run_repeats(results), "skill_cap": run_skill_cap(results)}


def _same_setup(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    """Same bot, skills, models, skill cap, scenario and setup fingerprint (bot code, judge code and
    settings). A file without a setup fingerprint matches only another file without one. Cases are not
    fingerprinted beyond the facts the judge graded, so two such runs differ only by noise if nothing
    else changed between them."""
    keys = ("bot", "scenario", "models", "skill_fingerprint", "setup_fingerprint")
    return (
        all(a.get(key) == b.get(key) for key in keys)
        and a.get("skill_fingerprint") is not None
        and run_skill_cap(a) == run_skill_cap(b)
    )


def _graded_facts(case: Mapping[str, Any]) -> list[str]:
    """The expected facts the judge graded for a case, in order; empty if no run reached the judge."""
    for run in case_runs(case):
        facts = [str(fact.get("fact", "")) for fact in (run.get("judge") or {}).get("facts") or []]
        if facts:
            return facts
    return []


def _noise_floor(
    baseline: Mapping[str, Any],
    compared: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    aa: Mapping[str, Any] | None,
    min_fails: int,
    cand_repeats: int,
    warnings: list[str],
) -> tuple[dict[str, Any] | None, str | None]:
    """(noise floor, why it is missing). From a second baseline run when given (`--aa`),
    otherwise, or when it shares no compared case, from the baseline's own repeats."""
    if not compared:
        return None, "no cases were compared"
    aa_unusable = False
    if aa is not None:
        if not _same_setup(baseline, aa):
            warnings.append("the A/A run differs from the baseline in bot, scenario, models, skills, skill cap or setup fingerprint")
        aa_cases = {c["id"]: c for c in aa.get("cases", [])}
        pairs = [(base, aa_cases[base["id"]]) for base, _ in compared if base["id"] in aa_cases]
        missing = [base["id"] for base, _ in compared if base["id"] not in aa_cases]
        if pairs and missing:
            warnings.append(f"not in the A/A run, so left out of the noise floor: {', '.join(missing)}")
        aa_repeats = run_repeats(aa)
        used = min(min_fails, aa_repeats)
        noise = noise_from_aa(pairs, DATASETS, used)
        if noise is not None:
            same = aa_repeats == cand_repeats
            if not same:
                warnings.append(
                    f"the A/A run has {_n(aa_repeats, 'run')} per case and the candidate {cand_repeats}, so its noise "
                    f"floor flags a case at {used} of {aa_repeats} failing runs instead of the candidate's {min_fails} "
                    f"of {cand_repeats}; rerun the A/A with --repeats {cand_repeats} for a like-for-like floor"
                )
            if partly := [c["id"] for _, c in pairs if error_count(c) and ok_runs(c)]:
                warnings.append(f"A/A runs errored for {', '.join(partly)}; those runs are left out")
            if noise["left_out"]:
                warnings.append(
                    f"every run errored on one side for {', '.join(noise['left_out'])}, so the noise floor leaves "
                    "those cases out"
                )
            noise.update(run=_run_info(aa), repeats=aa_repeats, same_rule=same)
            return noise, None
        warnings.append("none of the compared cases are in the A/A run, so it was not used")
        aa_unusable = True
    noise = noise_from_repeats([base for base, _ in compared], DATASETS)
    if noise is not None:
        noise["repeats"] = run_repeats(baseline)
        if noise["unmeasured"]:
            warnings.append(
                f"fewer than 2 baseline runs are left once errored runs are taken out for "
                f"{', '.join(noise['unmeasured'])}, so the noise floor leaves them out"
            )
        return noise, None
    given = "no usable A/A run was given" if aa_unusable else "no A/A run was given"
    if any(len(case_runs(base)) >= 2 for base, _ in compared):
        return None, f"no compared baseline case has two runs that did not error, and {given}"
    return None, f"the baseline ran each case once and {given}"


def verdict_note(
    verdict: str, test: Mapping[str, Any] | None, kind: str, regressed: int, alpha: float = ALPHA
) -> str | None:
    """A sentence when the verdict (a per-case gate) and the paired test (the net change) tell
    different stories, or when the comparison is an A/A one."""
    if verdict == NO_CASES:
        return "No case was in both runs (or every shared case was left out), so there is nothing to pass or fail."
    if kind == "aa":
        return (
            "This is an A/A comparison: both runs share the bot, skills, models, skill cap and setup, so if "
            "nothing else changed (the cases or personas, or code and judge when a run has no setup fingerprint) "
            "every flip is run-to-run noise, and the verdict is counting noise."
        )
    if test is None:
        return None
    row = test["overall"]
    p = _p_eq(row["p_value"], alpha)
    worse = (row["mean_diff"] or 0) < 0
    if verdict == "Passed" and row["significant"] and worse:
        return (
            f"The verdict is Passed, but the paired test finds a significant net regression ({p}). "
            "The flag rule does not count unstable cases; look at those."
        )
    if verdict == "Not passed" and row["significant"] is False:
        return (
            f"The verdict is Not passed, but the net change is not significant ({p}): the flagged "
            "regressions could be run-to-run noise, or be offset by improvements."
        )
    if verdict == "Not passed" and row["significant"] and not worse:
        return (
            f"The verdict is Not passed because {_n(regressed, 'case')} regressed, "
            f"although the net change is a significant improvement ({p})."
        )
    return None


def _rate_cell(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Passing runs over runs (with one run per case, passing cases over cases), leaving out
    errored runs the way the flag rule and the test do."""
    counts = [valid_counts(case) for case in cases]
    passed, runs = sum(p for p, _ in counts), sum(r for _, r in counts)
    return {"passed": passed, "runs": runs, "rate": _rate(passed, runs)}


def _delta(base: Mapping[str, Any], cand: Mapping[str, Any]) -> float | None:
    if base["rate"] is None or cand["rate"] is None:
        return None
    return round(cand["rate"] - base["rate"], 4)


def compare(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    scenario: Scenario | None = None,
    *,
    aa: Mapping[str, Any] | None = None,
    min_fails: int | None = None,
) -> dict[str, Any]:
    """Pair the candidate's cases with the baseline's. `aa` is an optional second baseline run
    for the noise floor; `min_fails` is m in the flag rule (default: a majority of the candidate's K)."""
    base_cases = {c["id"]: c for c in baseline.get("cases", [])}
    cand_cases = list(candidate.get("cases", []))
    base_repeats, cand_repeats = run_repeats(baseline), run_repeats(candidate)
    if min_fails is None:
        min_fails = default_min_fails(cand_repeats)
    if not 1 <= min_fails <= cand_repeats:
        raise ValueError(f"min_fails must be between 1 and the candidate's {cand_repeats} runs per case, not {min_fails}")

    warnings: list[str] = []
    kind = "aa" if _same_setup(baseline, candidate) else "change"
    if baseline.get("bot") != candidate.get("bot"):
        warnings.append(f"bots differ: baseline {baseline.get('bot')}, candidate {candidate.get('bot')}")
    if baseline.get("models") != candidate.get("models"):
        warnings.append(f"models differ: baseline {baseline.get('models')}, candidate {candidate.get('models')}")
    if base_repeats != cand_repeats:
        warnings.append(f"runs per case differ: baseline {base_repeats}, candidate {cand_repeats}")
    for side, results in (("baseline", baseline), ("candidate", candidate)):
        if results.get("complete") is False:
            warnings.append(f"the {side} is a partial run that stopped on a fatal error; complete it with --rerun-errors")
    if run_skill_cap(baseline) != run_skill_cap(candidate):
        warnings.append(f"skill caps differ: baseline {run_skill_cap(baseline)}, candidate {run_skill_cap(candidate)}")
    base_setup, cand_setup = baseline.get("setup_fingerprint"), candidate.get("setup_fingerprint")
    if isinstance(base_setup, Mapping) and isinstance(cand_setup, Mapping):
        differ = [PART_LABELS.get(part, part) for part in sorted(set(base_setup) | set(cand_setup)) if base_setup.get(part) != cand_setup.get(part)]
        if differ:
            warnings.append(f"setups differ between the runs: {', '.join(differ)}")
    elif base_setup or cand_setup:
        side = "baseline" if not base_setup else "candidate"
        warnings.append(f"the {side} does not record a setup fingerprint, so prompt, judge and setting changes cannot be checked")

    transitions: dict[str, list[str]] = {name: [] for name in TRANSITIONS}
    compared: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    missing: list[str] = []
    facts_changed: list[str] = []
    for cand in cand_cases:
        base = base_cases.get(cand["id"])
        if base is None:
            missing.append(cand["id"])
            continue
        # A case whose expected facts were edited between the runs was graded against different facts.
        base_facts, cand_facts = _graded_facts(base), _graded_facts(cand)
        if base_facts and cand_facts and base_facts != cand_facts:
            facts_changed.append(cand["id"])
            continue
        compared.append((base, cand))
        transitions[classify(*pair_counts(base, cand), min_fails)].append(cand["id"])
    if missing:
        warnings.append(f"not in the baseline, so not compared: {', '.join(missing)}")
    if facts_changed:
        warnings.append(
            f"expected facts differ between the runs, so not compared: {', '.join(facts_changed)}; "
            "rerun the baseline to compare them"
        )
    for side, cases in (("baseline", [b for b, _ in compared]), ("candidate", [c for _, c in compared])):
        all_errored = [case["id"] for case in cases if error_count(case) == len(case_runs(case))]
        partly = [case["id"] for case in cases if error_count(case) and case["id"] not in all_errored]
        if partly:
            warnings.append(
                f"{side} runs errored for {', '.join(partly)}; the flag rule, the test and the rates leave those runs out"
            )
        if all_errored:
            effect = (
                "they cannot be flagged as regressed, and a passing candidate shows as improved"
                if side == "baseline"
                else "a stable baseline pass shows as regressed"
            )
            warnings.append(
                f"every {side} run errored for {', '.join(all_errored)}, so they count as failing: {effect}; rerun them"
            )
    baseline_errors = [b["id"] for b, _ in compared if error_count(b)]

    by_dataset: dict[str, dict[str, Any]] = {}
    for name in DATASETS:
        pairs = [(b, c) for b, c in compared if c["dataset"] == name]
        if not pairs:
            continue
        base_cell, cand_cell = _rate_cell([b for b, _ in pairs]), _rate_cell([c for _, c in pairs])
        by_dataset[name] = {
            "total": len(pairs),
            "baseline": base_cell,
            "candidate": cand_cell,
            "delta": _delta(base_cell, cand_cell),
        }
    total = len(compared)
    base_overall, cand_overall = _rate_cell([b for b, _ in compared]), _rate_cell([c for _, c in compared])

    counts = {name: len(ids) for name, ids in transitions.items()}
    improved, regressed = counts["improved"], counts["regressed"]
    regressed_ids, improved_ids = set(transitions["regressed"]), set(transitions["improved"])
    failures = [_failure(b, c) for b, c in compared if c["id"] in regressed_ids]
    improvements = [_failure(b, c, regressed=False) for b, c in compared if c["id"] in improved_ids]

    selection = candidate.get("selection")
    scenario_id = scenario.id if scenario else candidate.get("scenario")
    hypothesis_result = None
    if scenario is not None and total:
        expected = scenario.hypothesis.expected
        hypothesis_result = {
            "expected": expected,
            "observed": observed_direction(improved, regressed),
            "matches": hypothesis_matches(expected, improved, regressed),
        }

    noise_floor, noise_note = _noise_floor(baseline, compared, aa, min_fails, cand_repeats, warnings)
    test = paired_tests(compared, DATASETS)
    verdict = NO_CASES if total == 0 else "Passed" if regressed == 0 else "Not passed"
    return {
        "scenario": scenario.model_dump(mode="json") if scenario else ({"id": scenario_id} if scenario_id else None),
        "baseline": _run_info(baseline),
        "candidate": _run_info(candidate),
        "kind": kind,
        "selection": {
            "rule": selection["rule"] if selection else "no selection: the candidate ran every case it lists",
            "case_count": total,
        },
        "pass_rates": {
            "overall": {"total": total, "baseline": base_overall, "candidate": cand_overall},
            "by_dataset": by_dataset,
        },
        "transitions": transitions,
        "transition_counts": counts,
        "sharp_changes": sharp_changes(compared, transitions["unstable"], min_fails, cand_repeats),
        "errors": [c["id"] for _, c in compared if error_count(c)],
        "baseline_errors": baseline_errors,
        "facts_changed": facts_changed,
        "failures": failures,
        "improvements": improvements,
        "verdict": verdict,
        "verdict_note": verdict_note(verdict, test, kind, regressed),
        "flag_rule": {
            "min_fails": min_fails,
            "baseline_repeats": base_repeats,
            "candidate_repeats": cand_repeats,
            "text": flag_rule_text(min_fails, cand_repeats, base_repeats),
        },
        "paired_test": test,
        "noise_floor": noise_floor,
        "noise_floor_note": noise_note,
        "hypothesis_result": hypothesis_result,
        "warnings": warnings,
    }


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate * 100:.0f}%"


def _quote(text: str | None) -> str:
    if not text:
        return "> (no reply)"
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _fixed(value: float, digits: int) -> str:
    """Like JavaScript's toFixed: the exact binary value, ties rounded up, so the site and the report agree."""
    return str(Decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def _p(p: float | None, alpha: float = ALPHA) -> str:
    """Three decimals, with more when three would round onto alpha (0.0502 is not 0.050)."""
    if p is None:
        return "n/a"
    if p < 0.001:
        return "<0.001"
    digits = 3
    while digits < 6 and p != alpha and _fixed(p, digits) == _fixed(alpha, digits):
        digits += 1
    return _fixed(p, digits)


def _p_eq(p: float | None, alpha: float = ALPHA) -> str:
    """'p = 0.070', 'p < 0.001' or 'p = n/a'."""
    text = _p(p, alpha)
    return f"p {text[0]} {text[1:]}" if text.startswith("<") else f"p = {text}"


def _pts(diff: float | None) -> str:
    return "n/a" if diff is None else f"{diff * 100:+.1f} pts"


def _count(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _significance(row: Mapping[str, Any]) -> str:
    if row["significant"] is None:
        return "not tested"
    if not row["significant"]:
        return "not significant"
    return "significant (improvement)" if (row["mean_diff"] or 0) > 0 else "significant (regression)"


def _interval(row: Mapping[str, Any]) -> str:
    return "n/a" if row.get("ci_low") is None else f"[{_pts(row['ci_low'])}, {_pts(row['ci_high'])}]"


def test_summary(test: Mapping[str, Any] | None) -> str:
    """One sentence on the overall paired test of the net change."""
    if test is None:
        return "Paired test: no cases compared."
    row, alpha = test["overall"], test["alpha"]
    result = f"{_p_eq(row['p_value'], alpha)}, {_significance(row)} at {alpha}"
    left_out = (
        f" {_n(row['left_out'], 'case')} with only errored runs on one side {'was' if row['left_out'] == 1 else 'were'} left out."
        if row.get("left_out")
        else ""
    )
    if row["cases"] == 0:
        return f"Paired test of the net change: no case to test.{left_out}"
    if test["method"] == "mcnemar_exact":
        flipped = row["improved"] + row["regressed"]
        return (
            f"Paired test of the net change (exact McNemar on the {_n(flipped, 'case')} that flipped): {result}."
            + left_out
        )
    ci = test["ci"]
    interval = (
        f"Persona bootstrap {int(ci['confidence'] * 100)}% interval {_interval(row)} over "
        f"{_n(row['clusters'], 'persona')} (descriptive only)."
        if row["ci_low"] is not None
        else f"No persona interval: only {_n(row['clusters'], 'persona')} (an interval needs {ci['min_clusters']})."
    )
    return (
        f"Paired test of the net change (exact run-permutation test; {row['informative']} of {_n(row['cases'], 'case')} "
        f"had runs that disagreed): mean pass-fraction change {_pts(row['mean_diff'])}, {result}. {interval}{left_out}"
    )


def _noise_label(noise: Mapping[str, Any]) -> str:
    """Column header for the noise floor, naming what it counts."""
    if noise["source"] != "aa_run":
        return "A/A single-run flips (expected)"
    if noise.get("same_rule", True):
        return "A/A flags (same rule)"
    return f"A/A flags ({noise['min_fails']} of {noise['repeats']} fails)"


def _aa_rule(noise: Mapping[str, Any], rule: Mapping[str, Any] | None) -> str:
    if noise.get("same_rule", True):
        return "under the same flag rule"
    theirs = f" instead of {rule['min_fails']} of {rule['candidate_repeats']}" if rule else ""
    return (
        f"under a different rule ({noise['min_fails']} of {noise['repeats']} failing runs{theirs}), since the A/A "
        f"run has {_n(noise['repeats'], 'run')} per case"
    )


def noise_summary(
    noise: Mapping[str, Any] | None, note: str | None = None, rule: Mapping[str, Any] | None = None
) -> str:
    """One sentence on the A/A noise floor."""
    if noise is None:
        return f"A/A noise floor: not measured ({note or 'no baseline repeats and no A/A run'})."
    row = noise["overall"]
    if noise["source"] == "aa_run":
        return (
            f"A/A noise floor: {row['flips']} of {_n(row['cases'], 'case')} were flagged ({row['regressed']} regressed, "
            f"{row['improved']} improved) in a second run of the baseline with nothing changed, {_aa_rule(noise, rule)}."
        )
    unstable = len(noise["unstable"])
    text = (
        f"A/A noise floor (single runs): about {_count(row['flips'])} of {_n(row['cases'], 'case')} flip between two "
        f"single runs of the baseline with nothing changed (estimated from its {_n(noise['repeats'], 'run')} per case); "
        f"{_n(unstable, 'baseline case')} passed some runs but not all."
    )
    if (row["flips"] or 0) >= 0.5:
        text += (
            " The flag rule needs a stable baseline, so far fewer cases are flagged by chance than this; for a "
            "like-for-like floor, rerun the baseline with the same --repeats and pass it with --aa."
        )
    if noise.get("unmeasured"):
        text += f" Left out for lack of runs: {', '.join(noise['unmeasured'])}."
    return text


def _stats_section(report: Mapping[str, Any]) -> list[str]:
    test, noise, rule = report.get("paired_test"), report.get("noise_floor"), report["flag_rule"]
    lines = [
        "## Noise and significance",
        "",
        f"- Runs per case: baseline {rule['baseline_repeats']}, candidate {rule['candidate_repeats']}.",
        f"- Flag rule: {rule['text']}.",
    ]
    if test is None:
        return lines + [""]
    alpha = test["alpha"]
    if test["method"] == "mcnemar_exact":
        lines.append("- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).")
    else:
        lines.append(
            "- Paired test: exact permutation test of the mean per-case change in pass fraction, shuffling each "
            "case's baseline and candidate runs between the two sides (it reduces to exact McNemar with one run each)."
        )
        ci = test["ci"]
        lines.append(
            f"- Interval: persona-cluster bootstrap ({ci['resamples']} resamples, at least {ci['min_clusters']} "
            "personas), a description of how the change varies between personas; it is not a test."
        )
    lines.append(
        "- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) "
        "can read as not significant."
    )
    if test["family"] == 1:
        lines.append("- Multiplicity: one dataset, so its p-value needs no adjustment.")
    else:
        lines.append(f"- Multiplicity: {test['correction']}.")
    if noise is None:
        lines.append(f"- Noise floor: not measured ({report.get('noise_floor_note') or 'no data'}).")
    elif noise["source"] == "aa_run":
        run = noise["run"]
        lines.append(f"- Noise floor: the A/A run {run.get('name')} ({run.get('created_at')}), {_aa_rule(noise, rule)}.")
    else:
        lines.append(
            "- Noise floor: expected flips between two single runs, from the baseline's own repeats. This is "
            "single-run noise, not comparable one to one with flagged counts."
        )
    lines.append("")

    noise_rows = (noise or {}).get("by_dataset", {})
    noise_header = _noise_label(noise) if noise else "A/A noise floor"
    rows = [(name, row, noise_rows.get(name)) for name, row in test["by_dataset"].items()]
    overall = ("**overall**", test["overall"], (noise or {}).get("overall"))
    if test["method"] == "mcnemar_exact":
        lines += [
            f"| Dataset | Cases | Improved | Regressed | p | p (Holm) | {noise_header} |",
            "|---|---|---|---|---|---|---|",
        ]
        for name, row, aa in [*rows, overall]:
            holm = _p(row["p_holm"], alpha) if "p_holm" in row else "primary"
            lines.append(
                f"| {name} | {row['cases']} | {row['improved']} | {row['regressed']} | {_p(row['p_value'], alpha)} "
                f"| {holm} | {_count(aa['flips']) if aa else 'n/a'} |"
            )
    else:
        lines += [
            f"| Dataset | Cases | Runs disagreed | Personas | Mean change | Persona interval | p | p (Holm) "
            f"| {noise_header} |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for name, row, aa in [*rows, overall]:
            interval = "n/a" if row["ci_low"] is None else f"{_pts(row['ci_low'])} to {_pts(row['ci_high'])}"
            holm = _p(row["p_holm"], alpha) if "p_holm" in row else "primary"
            lines.append(
                f"| {name} | {row['cases']} | {row['informative']} | {row['clusters']} | {_pts(row['mean_diff'])} "
                f"| {interval} | {_p(row['p_value'], alpha)} | {holm} | {_count(aa['flips']) if aa else 'n/a'} |"
            )
    if noise and noise["unstable"]:
        label = "Flipped or varied in the A/A run" if noise["source"] == "aa_run" else "Unstable in the baseline"
        lines += ["", f"{label}: {', '.join(noise['unstable'])}."]
    return lines + [""]


def render_markdown(report: Mapping[str, Any]) -> str:
    scenario = report.get("scenario")
    title = "Regression report"
    if scenario:
        title += f": {scenario['id']}" + (f" ({scenario['title']})" if scenario.get("title") else "")
    lines = [f"# {title}", ""]

    counts = report["transition_counts"]
    unstable = f", {counts['unstable']} unstable" if counts.get("unstable") else ""
    lines.append(
        f"**Verdict: {report['verdict']}.** {counts['regressed']} regressed, {counts['improved']} improved{unstable}."
    )
    if report.get("verdict_note"):
        lines.append(report["verdict_note"])
    if "flag_rule" in report:
        lines.append(test_summary(report.get("paired_test")))
        lines.append(noise_summary(report.get("noise_floor"), report.get("noise_floor_note"), report["flag_rule"]))
    hyp = report.get("hypothesis_result")
    if hyp:
        verdict = "matches" if hyp["matches"] else "does not match"
        lines.append(
            f"Hypothesis: expected {hyp['expected']}, observed {hyp['observed']} ({verdict}; from the flagged counts, "
            "not a significance test)."
        )
    lines.append("")

    if scenario and scenario.get("title"):
        lines += [
            "## Scenario",
            "",
            f"- Skill: `{scenario['skill']}` ({scenario['kind']} change)",
            f"- Change: {scenario['change']}",
            f"- Motivation: {scenario['motivation']}",
            f"- Hypothesis ({scenario['hypothesis']['expected']}): {scenario['hypothesis']['detail']}",
            "",
        ]

    base, cand = report["baseline"], report["candidate"]
    lines += [
        "## Runs",
        "",
        f"- Baseline: {base.get('name')} ({base.get('bot')}, {base.get('created_at')})",
        f"- Candidate: {cand.get('name')} ({cand.get('bot')}, {cand.get('created_at')})",
        f"- Selection: {report['selection']['rule']}",
        f"- Cases compared: {report['selection']['case_count']}",
        "",
    ]
    for warning in report.get("warnings", []):
        lines.append(f"- Warning: {warning}")
    if report.get("warnings"):
        lines.append("")

    rates = report["pass_rates"]
    lines += ["## Pass rates", "", "| Dataset | Cases | Baseline | Candidate | Change |", "|---|---|---|---|---|"]
    for name, row in rates["by_dataset"].items():
        delta = "n/a" if row["delta"] is None else f"{row['delta'] * 100:+.0f} pts"
        lines.append(
            f"| {name} | {row['total']} | {row['baseline']['passed']} ({_pct(row['baseline']['rate'])}) "
            f"| {row['candidate']['passed']} ({_pct(row['candidate']['rate'])}) | {delta} |"
        )
    overall = rates["overall"]
    lines += [
        f"| **overall** | {overall['total']} | {overall['baseline']['passed']} ({_pct(overall['baseline']['rate'])}) "
        f"| {overall['candidate']['passed']} ({_pct(overall['candidate']['rate'])}) | |",
        "",
    ]
    repeated = "flag_rule" in report and max(report["flag_rule"]["baseline_repeats"], report["flag_rule"]["candidate_repeats"]) > 1
    if repeated:
        lines += ["Counts are passing runs; rates are the mean pass fraction per case.", ""]
    if report.get("errors") or report.get("baseline_errors"):
        lines += [
            "Errored runs are left out of these counts when the case has other runs on that side; a side whose every "
            "run errored counts as failing. The counts pool runs, so with errored runs a change here can differ a "
            "little from the paired test's mean per-case change.",
            "",
        ]
    if "flag_rule" in report:
        lines += _stats_section(report)
    lines += ["## Transitions", ""]
    labels = {
        "improved": "Improved",
        "regressed": "Regressed",
        "unchanged_pass": "Unchanged (pass)",
        "unchanged_fail": "Unchanged (fail)",
        "unstable": "Unstable (not flagged: varied across runs, or too few runs that did not error)",
    }
    for name in TRANSITIONS:
        ids = report["transitions"].get(name, [])
        if name == "unstable" and not repeated:
            continue
        lines.append(f"- {labels[name]} ({len(ids)}): {', '.join(ids) if ids else 'none'}")
    sharp = report.get("sharp_changes") or {}
    if sharp.get("dropped"):
        lines.append(f"- Unstable but dropped sharply, not counted: {', '.join(sharp['dropped'])}")
    if sharp.get("rose"):
        lines.append(f"- Unstable but rose sharply, not counted: {', '.join(sharp['rose'])}")
    if report.get("errors"):
        lines.append(f"- Candidate errors: {', '.join(report['errors'])}")
    if report.get("baseline_errors"):
        lines.append(f"- Baseline errors: {', '.join(report['baseline_errors'])}")
    lines.append("")

    lines += ["## Failures overview", ""]
    if not report["failures"]:
        lines += ["No case regressed.", ""]
    for failure in report["failures"]:
        runs = ""
        base_err, cand_err = failure.get("baseline_errored", 0), failure.get("candidate_errored", 0)
        if max(failure.get("baseline_runs", 1), failure.get("candidate_runs", 1)) > 1 or base_err or cand_err:
            notes = []
            for side, errored, all_errored in (
                ("baseline", base_err, failure.get("baseline_all_errored")),
                ("candidate", cand_err, failure.get("candidate_all_errored")),
            ):
                if all_errored:
                    notes.append(f"every {side} run errored and counts as failing")
                elif errored:
                    notes.append(f"{_n(errored, 'errored ' + side + ' run')} left out")
            runs = (
                f"Passed {failure['baseline_passed']} of {_n(failure['baseline_runs'], 'baseline run')} and "
                f"{failure['candidate_passed']} of {_n(failure['candidate_runs'], 'candidate run')}"
                + (f" ({'; '.join(notes)})" if notes else "")
                + "; one failing run is shown."
            )
        lines += [
            f"### {failure['id']} ({failure['dataset']}, {failure['persona']})",
            "",
            f"**Message.** {failure['message'].strip()}",
            "",
            *([runs, ""] if runs else []),
            f"Expected skills: {', '.join(failure['skills']) or 'none'}. "
            f"Routed: baseline {failure['baseline_routing']}, candidate {failure['candidate_routing']}.",
            "",
        ]
        if failure.get("error"):
            lines += [f"**Candidate error.** {failure['error']}", ""]
        lines += ["**Baseline reply.**", "", _quote(failure["baseline_reply"]), ""]
        lines += ["**Candidate reply.**", "", _quote(failure["candidate_reply"]), ""]
        if failure["judge_facts"]:
            lines += ["| Expected fact | Status | Note |", "|---|---|---|"]
            for fact in failure["judge_facts"]:
                lines.append(f"| {_cell(fact['fact'])} | {fact['status']} | {_cell(fact['note'])} |")
            lines.append("")
        if failure["judge_reason"]:
            lines += [f"**Judge reason.** {failure['judge_reason']}", ""]
        if failure["check_failures"]:
            lines += ["**Check failures.**", ""] + [f"- {item}" for item in failure["check_failures"]] + [""]
    return "\n".join(lines).rstrip() + "\n"


def write_report(out_dir: Path, report: Mapping[str, Any]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = out_dir / "report.json", out_dir / "report.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m evals.report", description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="directory for report.json and report.md")
    parser.add_argument("--scenario", help="scenario id (defaults to the candidate's scenario)")
    parser.add_argument(
        "--aa", type=Path, help="a second run of the baseline with nothing changed, for the A/A noise floor"
    )
    parser.add_argument(
        "--min-fails",
        type=int,
        help="m in the flag rule: a case regresses when it fails at least m of its K runs (default: a majority)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    scenario_id = args.scenario or candidate.get("scenario")
    scenario = load_scenario(scenario_id) if scenario_id else None
    aa = json.loads(args.aa.read_text(encoding="utf-8")) if args.aa else None
    try:
        report = compare(baseline, candidate, scenario, aa=aa, min_fails=args.min_fails)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    json_path, md_path = write_report(args.out, report)
    counts = report["transition_counts"]
    unstable = f", {counts['unstable']} unstable" if counts["unstable"] else ""
    print(f"{report['verdict']}: {counts['improved']} improved, {counts['regressed']} regressed{unstable}")
    if report["verdict_note"]:
        print(report["verdict_note"])
    print(test_summary(report["paired_test"]))
    print(noise_summary(report["noise_floor"], report["noise_floor_note"], report["flag_rule"]))
    hyp = report["hypothesis_result"]
    if hyp:
        print(f"hypothesis {hyp['expected']}: observed {hyp['observed']} ({'match' if hyp['matches'] else 'no match'})")
    print(f"wrote {json_path} and {md_path}")
    return report


if __name__ == "__main__":
    main(sys.argv[1:])
