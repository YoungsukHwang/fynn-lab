"""Regression report: compare a candidate results JSON with its baseline.

    python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s1.json \
        --out ../results/reports/s1 --scenario s1

Only case ids present in the candidate are compared, so a selected (dependent-only) run is
compared on exactly the cases it reran. Writes report.json (for the site) and report.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from evals.cases import DATASETS
from evals.scenarios import Scenario, load_scenario

TRANSITIONS = ("improved", "regressed", "unchanged_pass", "unchanged_fail")


def _rate(passed: int, total: int) -> float | None:
    return round(passed / total, 4) if total else None


def _transition(base_passed: bool, cand_passed: bool) -> str:
    if base_passed and cand_passed:
        return "unchanged_pass"
    if base_passed:
        return "regressed"
    if cand_passed:
        return "improved"
    return "unchanged_fail"


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


def _failure(base: Mapping[str, Any], cand: Mapping[str, Any]) -> dict[str, Any]:
    judge = cand.get("judge") or {}
    checks = cand.get("checks") or {}
    return {
        "id": cand["id"],
        "dataset": cand["dataset"],
        "persona": cand["persona"],
        "intents": cand.get("intents"),
        "message": cand["message"],
        "skills": cand.get("skills", []),
        "baseline_routing": (base.get("routing") or {}).get("selected"),
        "candidate_routing": (cand.get("routing") or {}).get("selected"),
        "baseline_reply": base.get("reply"),
        "candidate_reply": cand.get("reply"),
        "judge_facts": judge.get("facts", []),
        "judge_reason": judge.get("reason", ""),
        "check_failures": checks.get("failures", []),
        "status": cand.get("status"),
        "error": cand.get("error"),
    }


def _run_info(results: Mapping[str, Any]) -> dict[str, Any]:
    return {key: results.get(key) for key in ("name", "bot", "scenario", "created_at", "models")}


def compare(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any], scenario: Scenario | None = None
) -> dict[str, Any]:
    base_cases = {c["id"]: c for c in baseline.get("cases", [])}
    cand_cases = list(candidate.get("cases", []))

    warnings: list[str] = []
    if baseline.get("bot") != candidate.get("bot"):
        warnings.append(f"bots differ: baseline {baseline.get('bot')}, candidate {candidate.get('bot')}")
    if baseline.get("models") != candidate.get("models"):
        warnings.append(f"models differ: baseline {baseline.get('models')}, candidate {candidate.get('models')}")

    transitions: dict[str, list[str]] = {name: [] for name in TRANSITIONS}
    compared: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    missing: list[str] = []
    for cand in cand_cases:
        base = base_cases.get(cand["id"])
        if base is None:
            missing.append(cand["id"])
            continue
        compared.append((base, cand))
        transitions[_transition(bool(base.get("passed")), bool(cand.get("passed")))].append(cand["id"])
    if missing:
        warnings.append(f"not in the baseline, so not compared: {', '.join(missing)}")

    by_dataset: dict[str, dict[str, Any]] = {}
    for name in DATASETS:
        pairs = [(b, c) for b, c in compared if c["dataset"] == name]
        if not pairs:
            continue
        base_passed = sum(1 for b, _ in pairs if b.get("passed"))
        cand_passed = sum(1 for _, c in pairs if c.get("passed"))
        base_rate, cand_rate = _rate(base_passed, len(pairs)), _rate(cand_passed, len(pairs))
        by_dataset[name] = {
            "total": len(pairs),
            "baseline": {"passed": base_passed, "rate": base_rate},
            "candidate": {"passed": cand_passed, "rate": cand_rate},
            "delta": round(cand_rate - base_rate, 4) if base_rate is not None and cand_rate is not None else None,
        }
    total = len(compared)
    base_total = sum(1 for b, _ in compared if b.get("passed"))
    cand_total = sum(1 for _, c in compared if c.get("passed"))

    counts = {name: len(ids) for name, ids in transitions.items()}
    improved, regressed = counts["improved"], counts["regressed"]
    regressed_ids = set(transitions["regressed"])
    failures = [_failure(b, c) for b, c in compared if c["id"] in regressed_ids]

    selection = candidate.get("selection")
    scenario_id = scenario.id if scenario else candidate.get("scenario")
    hypothesis_result = None
    if scenario is not None:
        expected = scenario.hypothesis.expected
        hypothesis_result = {
            "expected": expected,
            "observed": observed_direction(improved, regressed),
            "matches": hypothesis_matches(expected, improved, regressed),
        }

    return {
        "scenario": scenario.model_dump(mode="json") if scenario else ({"id": scenario_id} if scenario_id else None),
        "baseline": _run_info(baseline),
        "candidate": _run_info(candidate),
        "selection": {
            "rule": selection["rule"] if selection else "no selection: the candidate ran every case it lists",
            "case_count": total,
        },
        "pass_rates": {
            "overall": {
                "total": total,
                "baseline": {"passed": base_total, "rate": _rate(base_total, total)},
                "candidate": {"passed": cand_total, "rate": _rate(cand_total, total)},
            },
            "by_dataset": by_dataset,
        },
        "transitions": transitions,
        "transition_counts": counts,
        "errors": [c["id"] for _, c in compared if c.get("status") == "error"],
        "failures": failures,
        "verdict": "Passed" if regressed == 0 else "Not passed",
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


def render_markdown(report: Mapping[str, Any]) -> str:
    scenario = report.get("scenario")
    title = "Regression report"
    if scenario:
        title += f": {scenario['id']}" + (f" ({scenario['title']})" if scenario.get("title") else "")
    lines = [f"# {title}", ""]

    counts = report["transition_counts"]
    lines.append(f"**Verdict: {report['verdict']}.** {counts['regressed']} regressed, {counts['improved']} improved.")
    hyp = report.get("hypothesis_result")
    if hyp:
        verdict = "matches" if hyp["matches"] else "does not match"
        lines.append(f"Hypothesis: expected {hyp['expected']}, observed {hyp['observed']} ({verdict}).")
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
        "## Transitions",
        "",
    ]
    labels = {
        "improved": "Improved",
        "regressed": "Regressed",
        "unchanged_pass": "Unchanged (pass)",
        "unchanged_fail": "Unchanged (fail)",
    }
    for name in TRANSITIONS:
        ids = report["transitions"][name]
        lines.append(f"- {labels[name]} ({len(ids)}): {', '.join(ids) if ids else 'none'}")
    if report.get("errors"):
        lines.append(f"- Candidate errors: {', '.join(report['errors'])}")
    lines.append("")

    lines += ["## Failures overview", ""]
    if not report["failures"]:
        lines += ["No case regressed.", ""]
    for failure in report["failures"]:
        lines += [
            f"### {failure['id']} ({failure['dataset']}, {failure['persona']})",
            "",
            f"**Message.** {failure['message'].strip()}",
            "",
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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    scenario_id = args.scenario or candidate.get("scenario")
    scenario = load_scenario(scenario_id) if scenario_id else None
    report = compare(baseline, candidate, scenario)
    json_path, md_path = write_report(args.out, report)
    counts = report["transition_counts"]
    print(f"{report['verdict']}: {counts['improved']} improved, {counts['regressed']} regressed")
    hyp = report["hypothesis_result"]
    if hyp:
        print(f"hypothesis {hyp['expected']}: observed {hyp['observed']} ({'match' if hyp['matches'] else 'no match'})")
    print(f"wrote {json_path} and {md_path}")
    return report


if __name__ == "__main__":
    main(sys.argv[1:])
