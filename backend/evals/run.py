"""Run the eval set against one bot and write a results JSON.

    python -m evals.run --bot after --out ../results/after.json
    python -m evals.run --bot after --scenario s1 --baseline ../results/after.json \
        --out ../results/scenarios/s1.json

Each case is single-turn: the case message is the only user message and nothing is carried.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.cases import DATASETS, EvalCase, load_cases
from evals.checks import run_checks
from evals.judge import Judge
from evals.scenarios import Scenario, load_scenario, scenario_library
from evals.selection import select_cases, select_changed
from fynn import config
from fynn.bots import Bot, BotName, build_bots
from fynn.llm import LLM, LLMError, Usage
from fynn.personas import Persona, load_personas
from fynn.skills import SkillLibrary

EVAL_MAX_RETRIES = 2


def _usage_dict(usage: Usage) -> dict[str, int]:
    return asdict(usage)


def run_case(case: EvalCase, persona: Persona, bot: Bot, judge: Judge) -> dict[str, Any]:
    """One case end to end. Never raises: a failure is recorded with status "error"."""
    result: dict[str, Any] = {
        "id": case.id,
        "dataset": case.dataset,
        "persona": case.persona,
        "intents": case.intents,
        "message": case.message,
        "skills": list(case.skills),
        "routing": None,
        "reply": None,
        "checks": None,
        "judge": None,
        "passed": False,
        "status": "ok",
        "error": None,
        "usage": _usage_dict(Usage()),
    }
    stage = "bot"
    try:
        reply = bot.reply(persona, [{"role": "user", "content": case.message}], carry_skills=[])
        routing = reply.routing
        result["routing"] = {
            "strategy": routing.strategy,
            "selected": list(routing.selected),
            "carried": list(routing.carried),
            "reason": routing.reason,
            "error": routing.error,
        }
        result["reply"] = reply.text
        result["usage"] = _usage_dict(reply.usage)

        checks = run_checks(case, reply.text)
        result["checks"] = {"passed": checks.passed, "failures": list(checks.failures)}

        stage = "judge"
        graded = judge.grade(case, persona, reply.text)
        result["judge"] = {
            "facts": [asdict(fact) for fact in graded.facts],
            "reason": graded.reason,
            "passed": graded.passed,
            "usage": _usage_dict(graded.usage),
        }
        result["passed"] = checks.passed and graded.passed
    except Exception as exc:  # noqa: BLE001 (one bad case must not sink the run)
        result["status"] = "error"
        result["error"] = f"{stage}: {type(exc).__name__}: {exc}"
        result["passed"] = False
        if isinstance(exc, LLMError) and stage == "judge":
            result["judge"] = {"facts": [], "reason": "", "passed": False, "usage": _usage_dict(exc.usage)}
        elif isinstance(exc, LLMError):
            result["usage"] = _usage_dict(exc.usage)
    return result


def run_cases(
    cases: Sequence[EvalCase],
    *,
    bot: Bot,
    judge: Judge,
    personas: Mapping[str, Persona],
    workers: int = 8,
    progress: Callable[[str], None] | None = print,
) -> list[dict[str, Any]]:
    """Run every case in parallel; results come back in case order."""
    results: dict[str, dict[str, Any]] = {}
    total = len(cases)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(run_case, case, personas[case.persona], bot, judge): case for case in cases}
        for done, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results[result["id"]] = result
            if progress:
                label = "ERROR" if result["status"] == "error" else ("PASS" if result["passed"] else "FAIL")
                detail = f" ({result['error']})" if result["error"] else ""
                progress(f"[{done}/{total}] {result['id']} {label}{detail}")
    return [results[case.id] for case in cases]


def _bucket(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    errors = sum(1 for r in results if r["status"] == "error")
    return {"passed": passed, "total": total, "rate": round(passed / total, 4) if total else None, "errors": errors}


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "overall": _bucket(results),
        "by_dataset": {name: _bucket([r for r in results if r["dataset"] == name]) for name in DATASETS},
        "by_intents": {str(n): _bucket([r for r in results if r["intents"] == n]) for n in (1, 2, 3)},
    }


def build_results(
    *,
    name: str,
    bot: BotName,
    library: SkillLibrary,
    case_results: Sequence[Mapping[str, Any]],
    scenario: Scenario | None = None,
    selection: tuple[list[str], str] | None = None,
    judge_model: str = config.JUDGE_MODEL,
) -> dict[str, Any]:
    return {
        "name": name,
        "bot": bot,
        "scenario": scenario.id if scenario else None,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": {"router": config.ROUTER_MODEL, "agent": config.AGENT_MODEL, "judge": judge_model},
        "skill_fingerprint": {name: asdict(hashes) for name, hashes in library.fingerprint().items()},
        "selection": {"rule": selection[1], "case_ids": list(selection[0])} if selection else None,
        "cases": list(case_results),
        "summary": summarize(case_results),
    }


def write_results(path: Path, results: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def make_llms() -> tuple[LLM, LLM]:
    """(bot LLM, judge LLM). The only place the eval runner builds real API clients."""
    import anthropic

    from fynn.llm import AnthropicLLM, has_credentials

    if not has_credentials():
        raise SystemExit("No Anthropic credentials found (set ANTHROPIC_API_KEY in backend/.env).")
    return AnthropicLLM(anthropic.Anthropic(max_retries=EVAL_MAX_RETRIES)), AnthropicLLM()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m evals.run", description=__doc__.splitlines()[0])
    parser.add_argument("--bot", required=True, choices=["before", "after"])
    parser.add_argument("--out", required=True, type=Path, help="results JSON to write")
    parser.add_argument("--scenario", help="overlay scenarios/<id>/skills on skills/")
    parser.add_argument("--baseline", type=Path, help="baseline results JSON; enables dependent-test selection")
    parser.add_argument("--dataset", choices=DATASETS)
    parser.add_argument("--limit", type=int, help="run at most N cases (after filtering)")
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    cases = load_cases()
    personas = load_personas()
    base_lib = SkillLibrary.load()
    scenario = load_scenario(args.scenario) if args.scenario else None
    library = scenario_library(scenario) if scenario else base_lib

    if args.dataset:
        cases = [c for c in cases if c.dataset == args.dataset]

    selection: tuple[list[str], str] | None = None
    if args.baseline:
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        if baseline.get("bot") != args.bot:
            raise SystemExit(f"baseline was run on bot {baseline.get('bot')!r}, not {args.bot!r}")
        if scenario:
            base_fp = {name: asdict(h) for name, h in base_lib.fingerprint().items()}
            if baseline.get("skill_fingerprint") != base_fp:
                print("warning: the baseline was not run on the current skills/; selection diffs against skills/")
            selection = select_cases(cases, base_lib, library, baseline)
        else:
            selection = select_changed(cases, baseline, library)
        wanted = set(selection[0])
        cases = [c for c in cases if c.id in wanted]
        print(f"selection: {selection[1]}")

    if args.limit is not None:
        cases = cases[: args.limit]

    case_results: list[dict[str, Any]] = []
    if cases:  # an empty selection needs no API client at all
        bot_llm, judge_llm = make_llms()
        bot = build_bots(bot_llm, library)[args.bot]
        judge = Judge(judge_llm)
        label = f" scenario {scenario.id}" if scenario else ""
        print(f"running {len(cases)} cases on the {args.bot} bot{label} with {args.workers} workers")
        case_results = run_cases(cases, bot=bot, judge=judge, personas=personas, workers=args.workers)

    results = build_results(
        name=args.out.stem,
        bot=args.bot,
        library=library,
        case_results=case_results,
        scenario=scenario,
        selection=selection,
    )
    write_results(args.out, results)

    summary = results["summary"]
    overall = summary["overall"]
    print(f"passed {overall['passed']}/{overall['total']} ({overall['errors']} errors)")
    for name, bucket in summary["by_dataset"].items():
        if bucket["total"]:
            print(f"  {name}: {bucket['passed']}/{bucket['total']}")
    print(f"wrote {args.out}")
    return results


if __name__ == "__main__":
    main(sys.argv[1:])
