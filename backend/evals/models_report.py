"""Answer model and judge report: the After bot answering with different models, and other judge
models regrading the same replies. Reads results files only.

    python -m evals.models_report --runs ../results/models/k3/after-haiku.json ../results/after.json \
        ../results/models/k3/after-opus.json --regraded-runs ../results/models/after-*.json \
        --regrades ../results/validation/regrades --out ../results/reports/models

Cost is per 1,000 replies at list prices. Results files written before
routing.usage existed add the router's tokens to the answer's; for those, --router-from gives a run
that records the router's tokens per case, and they are taken off the answer and priced at the
router's model. That split is an estimate (the router prompt changes a little with the skills).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.judge_validation import judge_vs_judge, load_regrades, source_name
from evals.quality import reply_lengths
from evals.run import write_results
from evals.stats import case_runs, expected_flips, mcnemar_exact, ok_runs, permutation_test, valid_counts
from fynn.skills import SkillLibrary

# Per million tokens: input, output, cache read (list prices, 2026-10). A 5-minute cache write is 1.25x input.
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
}
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
# Word cutoffs for the length sensitivity. The response rules say "under about 250 words"; nothing grades it,
# and which model comes out ahead depends on where the line is drawn, so the report shows several.
LENGTH_CUTOFFS = (200, 250, 300, 350)


def cost(usage: Mapping[str, int], model: str) -> float | None:
    if model not in PRICES:
        return None
    i, o, cr = PRICES[model]
    return (
        usage.get("input_tokens", 0) * i
        + usage.get("output_tokens", 0) * o
        + usage.get("cache_read_input_tokens", 0) * cr
        + usage.get("cache_creation_input_tokens", 0) * i * 1.25
    ) / 1e6


def _split(
    run: Mapping[str, Any], case_id: str, router: Mapping[str, Mapping[str, int]]
) -> tuple[dict[str, int], dict[str, int], bool]:
    """(answer usage, router usage, estimated) for one run of a case."""
    usage = run.get("usage") or {}
    recorded = (run.get("routing") or {}).get("usage")
    if recorded is not None:
        return dict(usage), dict(recorded), False
    other = router.get(case_id)
    if other is None:
        return dict(usage), {}, True
    answer = {k: max(0, usage.get(k, 0) - other.get(k, 0)) for k in TOKEN_FIELDS}
    return answer, {k: other.get(k, 0) for k in TOKEN_FIELDS}, True


def cost_per_1000(results: Mapping[str, Any]) -> dict[str, Any] | None:
    """Answer and router cost per 1,000 replies at list prices, averaged over the runs that replied, with a
    warm cache as in the eval. None when a run records no router tokens apart (files written before
    routing.usage) or a model has no price."""
    models = results.get("models") or {}
    runs = [run for case in results.get("cases", []) for run in case_runs(case) if run.get("status") != "error"]
    if not runs or any((run.get("routing") or {}).get("usage") is None for run in runs):
        return None
    if models.get("agent") not in PRICES or models.get("router") not in PRICES:
        return None
    answer = sum(cost(run.get("usage") or {}, models["agent"]) or 0.0 for run in runs)
    router = sum(cost((run.get("routing") or {}).get("usage") or {}, models["router"]) or 0.0 for run in runs)
    scale = 1000 / len(runs)
    return {"answer": round(answer * scale, 2), "router": round(router * scale, 2), "total": round((answer + router) * scale, 2)}


def _words(run: Mapping[str, Any]) -> int:
    return len((run.get("reply") or "").split())


def model_row(source: str, results: Mapping[str, Any], router: Mapping[str, Mapping[str, int]], library: SkillLibrary) -> dict[str, Any]:
    """One answer model's results. Every run of every case counts: with K runs per case, passes are
    out of K times the cases, and cost is the mean over the runs that replied."""
    domains = {s.name: s.domain for s in library.topics}
    cases = results["cases"]
    models = results.get("models") or {}
    groups = {"cross": {"runs": 0, "passed": 0}, "single": {"runs": 0, "passed": 0}}
    answer_cost = router_cost = 0.0
    estimated = False
    runs = passed = errors = 0
    facts_present = facts_graded = 0
    served: set[str] = set()
    flips: list[float] = []
    for case in cases:
        group = "cross" if len({domains[s] for s in case.get("skills", []) if s in domains}) > 1 else "single"
        for run in case_runs(case):
            ok = bool(run.get("passed"))
            runs += 1
            passed += ok
            errors += run.get("status") == "error"
            groups[group]["runs"] += 1
            groups[group]["passed"] += ok
            facts = (run.get("judge") or {}).get("facts", [])
            facts_graded += len(facts)
            facts_present += sum(1 for f in facts if f.get("status") == "PRESENT")
            if run.get("agent_model"):
                served.add(run["agent_model"])
            if run.get("status") == "error":
                continue  # no reply to price: cost is per reply, as in cost_per_1000
            answer, routed, guessed = _split(run, case["id"], router)
            estimated |= guessed
            answer_cost += cost(answer, models.get("agent", "")) or 0.0
            router_cost += cost(routed, models.get("router", "")) or 0.0
        # Only runs that did not error say anything about the model's noise.
        flip = expected_flips(*valid_counts(case)) if ok_runs(case) >= 2 else None
        if flip is not None:
            flips.append(flip)
    # Per reply: errored runs are left out of both the cost and the count, though some record tokens.
    per_1000 = 1000 / (runs - errors) if runs > errors else 0
    return {
        "source": source,
        "model": models.get("agent"),
        "served": sorted(served),
        "created_at": results.get("created_at"),
        "cases": len(cases),
        "repeats": max((len(case_runs(c)) for c in cases), default=1),
        "runs": runs,
        "passed": passed,  # passing runs
        "errors": errors,
        "by_group": groups,
        "facts": {"present": facts_present, "graded": facts_graded},
        "lengths": reply_lengths(results),
        # With K >= 2: the chance that two single runs of a case disagree, averaged over cases.
        "flip_rate": round(sum(flips) / len(flips), 4) if flips else None,
        "unstable_cases": sum(1 for c in cases if ok_runs(c) and 0 < valid_counts(c)[0] < valid_counts(c)[1]),
        "cost_per_1000": {
            "answer": round(answer_cost * per_1000, 2),
            "router": round(router_cost * per_1000, 2),
            "total": round((answer_cost + router_cost) * per_1000, 2),
            "estimated_split": estimated,
        },
    }


def _counts(case: Mapping[str, Any], cutoff: int | None) -> tuple[int, int]:
    """(runs passed, runs that did not error); with a cutoff, a reply longer than it fails."""
    runs = [r for r in case_runs(case) if r.get("status") != "error"]
    return sum(1 for r in runs if r.get("passed") and (cutoff is None or _words(r) <= cutoff)), len(runs)


def paired(a: Mapping[str, Any], b: Mapping[str, Any], *, cutoff: int | None = None) -> dict[str, Any]:
    """Cases where `b` passes more often than `a` (up) and less often (down). One run per case on
    both sides gives the exact McNemar test; more runs give the run-permutation test, as in report.py."""
    ca = {c["id"]: _counts(c, cutoff) for c in a["cases"]}
    cb = {c["id"]: _counts(c, cutoff) for c in b["cases"]}
    # A case with no run that did not error on one side says nothing about either model (stats.testable).
    ids = sorted(i for i in set(ca) & set(cb) if ca[i][1] and cb[i][1])
    share = {i: (ca[i][0] / ca[i][1], cb[i][0] / cb[i][1]) for i in ids}
    up = sum(1 for i in ids if share[i][1] > share[i][0])
    down = sum(1 for i in ids if share[i][1] < share[i][0])
    single = all(ca[i][1] == 1 and cb[i][1] == 1 for i in ids)
    if not ids:
        method, p = "mcnemar_exact", 1.0
    elif single:
        method, p = "mcnemar_exact", mcnemar_exact(up, down)
    else:
        method, p = "run_permutation", permutation_test([(*ca[i], *cb[i]) for i in ids])
    mean = sum(s[1] - s[0] for s in share.values()) / len(ids) if ids else None
    return {
        "cases": len(ids),
        "left_out": len(set(ca) & set(cb)) - len(ids),
        "method": method,
        "up": up,
        "down": down,
        "mean_diff": None if mean is None else round(mean, 4),
        "p": round(p, 4),
    }


def judge_rows(runs: Mapping[str, Mapping[str, Any]], regrades: Sequence[Mapping[str, Any]], cases: Sequence[Any]) -> list[dict[str, Any]]:
    """Each judge model's regrades against the run's own judge, summed over the runs it regraded."""
    warnings: list[str] = []
    pairs = judge_vs_judge(runs, regrades, cases, warnings)
    by_label: dict[str, dict[str, Any]] = {}
    for regrade_file, pair in zip([r for r in regrades if r["source"] in runs], pairs, strict=True):
        row = by_label.setdefault(
            pair["label"],
            {"label": pair["label"], "model": regrade_file["models"]["judge"], "replies": 0, "facts": 0,
             "facts_agree": 0, "verdict_flips": 0, "cost": 0.0, "by_source": {}},
        )
        passes = pair["passes"]
        flips = passes["original"] + passes["regrade"] - 2 * passes["both"]
        graded = [r for r in regrade_file["cases"] if r.get("judge")]
        row["replies"] += pair["replies"]
        row["facts"] += pair["facts"]
        row["facts_agree"] += pair["agree_binary"]
        row["verdict_flips"] += flips
        row["cost"] += sum(cost(r["judge"].get("usage") or {}, row["model"]) or 0.0 for r in graded)
        row["by_source"][pair["source"]] = {
            "replies": pair["replies"],
            "fact_agreement": pair["rate_binary"],
            "verdict_flips": flips,
            "passes": passes,
            "stricter": pair["stricter"],
            "lenient": pair["lenient"],
        }
    out = []
    for row in by_label.values():
        runs_graded = len(row["by_source"]) or 1
        out.append(
            {
                **{k: v for k, v in row.items() if k != "cost"},
                "fact_agreement": round(row["facts_agree"] / row["facts"], 4) if row["facts"] else None,
                "cost_per_run": round(row["cost"] / runs_graded, 2),
            }
        )
    return out


def build_report(
    runs: Mapping[str, Mapping[str, Any]],
    router_from: Mapping[str, Any] | None,
    regrades: Sequence[Mapping[str, Any]],
    cases: Sequence[Any],
    library: SkillLibrary,
    regraded_runs: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """`regraded_runs` are the results files the regrades graded, when they are not `runs` (for
    example, single runs regraded before a repeated rerun replaced them in the comparison)."""
    router = {
        c["id"]: (c.get("routing") or {}).get("usage")
        for c in (router_from or {}).get("cases", [])
        if (c.get("routing") or {}).get("usage")
    }
    rows = sorted(
        (model_row(source, results, router, library) for source, results in runs.items()),
        key=lambda r: r["cost_per_1000"]["total"],
    )
    names = [r["source"] for r in rows]
    comparisons = [(names[i], names[i + 1]) for i in range(len(names) - 1)]
    if len(names) > 2:
        comparisons.append((names[0], names[-1]))
    return {
        "kind": "models",
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "router_usage_from": None
        if router_from is None
        else {"name": router_from.get("name"), "created_at": router_from.get("created_at")},
        "prices": {m: {"input": p[0], "output": p[1], "cache_read": p[2], "cache_write": round(p[0] * 1.25, 4)} for m, p in PRICES.items()},
        "models": rows,
        "paired": [{"a": a, "b": b, **paired(runs[a], runs[b])} for a, b in comparisons],
        # If replies over a cutoff counted as failures: passing runs per model and the same paired tests.
        "length_sensitivity": [
            {
                "cutoff": cutoff,
                "passed": {
                    name: sum(_counts(c, cutoff)[0] for c in runs[name]["cases"]) for name in names
                },
                "paired": [{"a": a, "b": b, **paired(runs[a], runs[b], cutoff=cutoff)} for a, b in comparisons],
            }
            for cutoff in LENGTH_CUTOFFS
        ],
        "judges": judge_rows(regraded_runs if regraded_runs is not None else runs, regrades, cases),
        "regraded_runs": sorted(regraded_runs if regraded_runs is not None else runs),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = ["# Answer model and judge", "", "## Answer models", ""]
    lines += [
        "| Answer model | Passing runs | Needs a second domain | One domain | Facts present | Same-prompt flip rate | "
        "Median words | Over 250 | Cost per 1,000 replies, warm cache (answer + router) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report["models"]:
        g, c = r["by_group"], r["cost_per_1000"]
        flip = "n/a" if r["flip_rate"] is None else f"{r['flip_rate'] * 100:.0f}%"
        lines.append(
            f"| {r['model']} | {r['passed']} of {r['runs']} | {g['cross']['passed']} of {g['cross']['runs']} | "
            f"{g['single']['passed']} of {g['single']['runs']} | {r['facts']['present']} of {r['facts']['graded']} | {flip} | "
            f"{r['lengths']['median_words']} | {r['lengths']['over_limit']} | ${c['total']:.2f} (${c['answer']:.2f} + ${c['router']:.2f}) |"
        )
    def pval(p: float) -> str:
        return "p < 0.001" if p < 0.001 else f"p = {p}"

    lines += ["", "Paired by case (up: the second passes more often):", ""]
    for p in report["paired"]:
        lines.append(f"- {p['a']} to {p['b']} ({p['method']}): {p['up']} up, {p['down']} down, {pval(p['p'])}")
    names = [r["source"] for r in report["models"]]
    lines += [
        "",
        "Passing runs if replies over a cutoff counted as failures (the rules say about 250 words; nothing grades it):",
        "",
        "| Cutoff | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    for row in report["length_sensitivity"]:
        lines.append(f"| {row['cutoff']} words | " + " | ".join(str(row["passed"][n]) for n in names) + " |")
    if report["judges"]:
        lines += ["", "## Judges regrading the same replies", ""]
        lines += ["| Judge | Replies | Fact agreement with the run's judge | Verdicts changed | Cost per 64-reply run |", "|---|---|---|---|---|"]
        for j in report["judges"]:
            agree = "n/a" if j["fact_agreement"] is None else f"{j['fact_agreement'] * 100:.1f}%"
            lines.append(f"| {j['label']} | {j['replies']} | {agree} | {j['verdict_flips']} | ${j['cost_per_run']:.2f} |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    from evals.cases import load_cases

    parser = argparse.ArgumentParser(prog="python -m evals.models_report", description=__doc__.splitlines()[0])
    parser.add_argument("--runs", nargs="+", required=True, type=Path, help="After-bot results files, one per answer model")
    parser.add_argument("--router-from", type=Path, help="a results file that records routing.usage per case")
    parser.add_argument("--regrades", nargs="*", default=[], type=Path, help="regrade files or directories")
    parser.add_argument("--regraded-runs", nargs="*", type=Path, help="the results files the regrades graded (default: --runs)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    runs = {source_name(p): json.loads(p.read_text(encoding="utf-8")) for p in args.runs}
    regraded = (
        {source_name(p): json.loads(p.read_text(encoding="utf-8")) for p in args.regraded_runs}
        if args.regraded_runs
        else None
    )
    router_from = json.loads(args.router_from.read_text(encoding="utf-8")) if args.router_from else None
    warnings: list[str] = []
    regrades = [r for r in load_regrades(args.regrades, warnings) if r["source"] in (regraded or runs)]
    report = build_report(runs, router_from, regrades, load_cases(), SkillLibrary.load(), regraded)
    args.out.mkdir(parents=True, exist_ok=True)
    write_results(args.out / "report.json", report)
    (args.out / "report.md").write_text(render_markdown(report), encoding="utf-8")
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"wrote {args.out / 'report.md'}")
    return report


if __name__ == "__main__":
    main()
