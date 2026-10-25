"""Recorded demo exchanges for the static site, from committed results files. No API calls.

    python -m evals.demo_snapshot --before ../results/before.json --after ../results/after.json \
        --out ../results/demo/recorded.json

The deployed site has no backend, so its Demo page shows these instead of a live chat. For each chosen
case it keeps both bots' reply as the results file has it (the run that matches the case's majority
result), with its routing, tokens and the judge's verdict on each expected fact. The architecture and
personas are written the way the API serves them, so the page draws them with the same components.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from api.main import describe_architecture
from evals.run import write_results
from fynn.personas import load_personas
from fynn.skills import SkillLibrary

# (case id, label on the Demo page). Chosen to show each kind of result, not only wins.
CASES: tuple[tuple[str, str], ...] = (
    ("mi-001", "Blog's example question"),
    ("mi-010", "Needs a second domain"),
    ("mi-015", "Written for the comparison"),
    ("st-011", "Where After lost"),
)
TOKEN_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def _usage(case: Mapping[str, Any]) -> dict[str, int]:
    """Router plus answer tokens, the way the API reports one reply."""
    answer = case.get("usage") or {}
    router = (case.get("routing") or {}).get("usage") or {}
    return {k: int(answer.get(k, 0)) + int(router.get(k, 0)) for k in TOKEN_FIELDS}


def _side(case: Mapping[str, Any], results: Mapping[str, Any]) -> dict[str, Any]:
    routing = case.get("routing") or {}
    return {
        "reply": case.get("reply") or "",
        "model": case.get("agent_model") or (results.get("models") or {}).get("agent", ""),
        "routing": {
            "strategy": routing.get("strategy", "skills"),
            "selected": list(routing.get("selected") or []),
            "carried": list(routing.get("carried") or []),
            "reason": routing.get("reason") or "",
            "error": routing.get("error"),
        },
        "usage": _usage(case),
        "passed": bool(case.get("passed")),
        "passes": int(case.get("passes", 1 if case.get("passed") else 0)),
        "repeats": int(case.get("repeats", 1)),
        "facts": [{"fact": f.get("fact", ""), "status": f.get("status", "")} for f in (case.get("judge") or {}).get("facts", [])],
        "check_failures": list((case.get("checks") or {}).get("failures") or []),
    }


def build_snapshot(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    library: SkillLibrary,
    cases: Sequence[tuple[str, str]] = CASES,
) -> dict[str, Any]:
    if before.get("bot") != "before" or after.get("bot") != "after":
        raise ValueError("--before must be a Before bot run and --after an After bot run")
    by_id = {name: {c["id"]: c for c in run.get("cases", [])} for name, run in (("before", before), ("after", after))}
    personas = load_personas()
    exchanges = []
    for case_id, label in cases:
        base, cand = by_id["before"].get(case_id), by_id["after"].get(case_id)
        if base is None or cand is None:
            raise ValueError(f"{case_id} is not in both results files")
        if base.get("message") != cand.get("message") or base.get("persona") != cand.get("persona"):
            raise ValueError(f"{case_id} has a different message or member in the two results files")
        if cand.get("persona") not in personas:
            raise ValueError(f"{case_id}: unknown persona {cand.get('persona')}")
        exchanges.append({
            "id": case_id,
            "label": label,
            "dataset": cand.get("dataset"),
            "persona": cand["persona"],
            "message": cand["message"],
            "before": _side(base, before),
            "after": _side(cand, after),
        })
    return {
        "sources": {name: {"name": run.get("name"), "created_at": run.get("created_at")} for name, run in (("before", before), ("after", after))},
        "architecture": describe_architecture(library),
        "personas": [p.model_dump(mode="json") for p in personas.values()],
        "exchanges": exchanges,
    }


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(prog="python -m evals.demo_snapshot", description=__doc__.splitlines()[0])
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    try:
        snapshot = build_snapshot(before, after, SkillLibrary.load())
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    write_results(args.out, snapshot)
    print(f"wrote {args.out}: {len(snapshot['exchanges'])} exchanges")
    return snapshot


if __name__ == "__main__":
    main()
