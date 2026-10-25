"""Run the eval set against one bot and write a results JSON.

    python -m evals.run --bot after --repeats 3 --out ../results/after.json
    python -m evals.run --bot after --repeats 3 --scenario s1 --baseline ../results/after.json \
        --out ../results/scenarios/s1-k3.json
    python -m evals.run --bot after --max-skills 5 --baseline ../results/after.json \
        --out ../results/cap5.json
    python -m evals.run --bot after --rerun-errors ../results/after.partial.json --out ../results/after.json

Each case is single-turn: the case message is the only user message and nothing is carried.
With --repeats K each case runs K times, so the report can tell a real change from run-to-run noise.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.cases import DATASETS, EvalCase, load_cases
from evals.checks import run_checks
from evals.judge import Judge
from evals.scenarios import Scenario, load_scenario, scenario_library
from evals.selection import select_cases, select_changed
from evals.setup import setup_changes, setup_fingerprint
from evals.stats import case_runs, run_repeats, run_skill_cap
from fynn import config
from fynn.bots import Bot, BotName, BotReply, build_bots
from fynn.llm import LLM, LLMError, Usage
from fynn.personas import Persona, load_personas
from fynn.skills import SkillLibrary

EVAL_MAX_RETRIES = 2
RECOMMENDED_REPEATS = 3
CASE_FIELDS = ("id", "dataset", "persona", "intents", "message", "skills")
COUNT_FIELDS = ("repeats", "passes", "pass_fraction", "errors", "runs")  # added by combine_runs
# Errors that every later call would hit too (a bad key, no permission, an unknown model id, no
# credit), so the run stops.
FATAL_MARKERS = ("AuthenticationError:", "PermissionDeniedError:", "NotFoundError:", "credit balance is too low")
SKIPPED_ERROR = "skipped: the run stopped after a fatal API error"


def is_fatal(error: str | None) -> bool:
    text = (error or "").lower()
    return any(marker.lower() in text for marker in FATAL_MARKERS)


def _usage_dict(usage: Usage) -> dict[str, int]:
    return asdict(usage)


def _answer_usage(reply: BotReply) -> Usage:
    """The answering model's tokens alone. A reply's usage also counts the router's call, which
    runs on a different model and so has a different price."""
    total, router = reply.usage, reply.routing.usage
    return Usage(**{f.name: getattr(total, f.name) - getattr(router, f.name) for f in fields(Usage)})


def _blank_result(case: EvalCase) -> dict[str, Any]:
    return {
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


def _skipped(case: EvalCase) -> dict[str, Any]:
    return {**_blank_result(case), "status": "error", "error": SKIPPED_ERROR}


def run_case(case: EvalCase, persona: Persona, bot: Bot, judge: Judge) -> dict[str, Any]:
    """One case end to end. Never raises: a failure is recorded with status "error"."""
    result = _blank_result(case)
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
            "usage": _usage_dict(routing.usage),  # the router's call, kept apart from the answer's
        }
        result["reply"] = reply.text
        result["agent_model"] = reply.model  # the model that answered, which a server-side fallback can change
        result["usage"] = _usage_dict(_answer_usage(reply))

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


def combine_runs(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """One case's K runs as one result, with its pass count and pass fraction.

    A single run keeps its fields. For K > 1, `passed` is the majority outcome and the other
    top-level fields come from the first run with that outcome (so a case that mostly fails shows
    a failing reply); `runs` keeps every run without the case fields.
    """
    passes = sum(1 for run in runs if run["passed"])
    counts = {"repeats": len(runs), "passes": passes, "pass_fraction": round(passes / len(runs), 4)}
    if len(runs) == 1:
        return {**runs[0], **counts}
    majority = passes * 2 > len(runs)
    shown = next(run for run in runs if run["passed"] == majority)
    return {
        **shown,
        **counts,
        "passed": majority,
        "errors": sum(1 for run in runs if run["status"] == "error"),
        "runs": [{k: v for k, v in run.items() if k not in CASE_FIELDS} for run in runs],
    }


def run_jobs(
    jobs: Sequence[tuple[EvalCase, int]],
    *,
    bot: Bot,
    judge: Judge,
    personas: Mapping[str, Persona],
    repeats: int = 1,
    workers: int = 8,
    progress: Callable[[str], None] | None = print,
) -> dict[tuple[str, int], dict[str, Any]]:
    """Run (case, run index) jobs in parallel. After the first fatal error the jobs not yet started
    are cancelled and recorded as skipped errors, so a run with no credit left stops at once."""
    runs: dict[tuple[str, int], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(run_case, case, personas[case.persona], bot, judge): (case, r) for case, r in jobs}
        stopped = False
        for done, future in enumerate(as_completed(futures), start=1):
            case, r = futures[future]
            if future.cancelled():
                runs[(case.id, r)] = _skipped(case)
                continue
            result = future.result()
            runs[(case.id, r)] = result
            if progress:
                label = "ERROR" if result["status"] == "error" else ("PASS" if result["passed"] else "FAIL")
                detail = f" ({result['error']})" if result["error"] else ""
                which = f" run {r + 1}/{repeats}" if repeats > 1 else ""
                progress(f"[{done}/{len(jobs)}] {case.id}{which} {label}{detail}")
            if not stopped and is_fatal(result["error"]):
                stopped = True
                cancelled = sum(1 for pending in futures if pending.cancel())
                if progress:
                    progress(f"stopping: a fatal API error; {cancelled} runs not started")
    return runs


def run_cases(
    cases: Sequence[EvalCase],
    *,
    bot: Bot,
    judge: Judge,
    personas: Mapping[str, Persona],
    repeats: int = 1,
    workers: int = 8,
    progress: Callable[[str], None] | None = print,
) -> list[dict[str, Any]]:
    """Run every case `repeats` times in parallel; one combined result per case, in case order."""
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    jobs = [(case, r) for r in range(repeats) for case in cases]
    runs = run_jobs(jobs, bot=bot, judge=judge, personas=personas, repeats=repeats, workers=workers, progress=progress)
    return [combine_runs([runs[(case.id, r)] for r in range(repeats)]) for case in cases]


def first_fatal(results: Mapping[str, Any]) -> str | None:
    """The first fatal error in a results file's runs, or None."""
    return next((run["error"] for case in results.get("cases", []) for run in case_runs(case) if is_fatal(run.get("error"))), None)


def _bucket(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts runs, so with K repeats `total` is K times the case count and `rate` the mean pass fraction."""
    runs = [run for r in results for run in case_runs(r)]
    passed = sum(1 for run in runs if run["passed"])
    total = len(runs)
    errors = sum(1 for run in runs if run["status"] == "error")
    return {"passed": passed, "total": total, "rate": round(passed / total, 4) if total else None, "errors": errors}


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "overall": _bucket(results),
        "by_dataset": {name: _bucket([r for r in results if r["dataset"] == name]) for name in DATASETS},
        "by_intents": {str(n): _bucket([r for r in results if r["intents"] == n]) for n in (1, 2, 3)},
    }


def run_models(judge_model: str = config.JUDGE_MODEL) -> dict[str, str]:
    return {"router": config.ROUTER_MODEL, "agent": config.AGENT_MODEL, "judge": judge_model}


def build_results(
    *,
    name: str,
    bot: BotName,
    library: SkillLibrary,
    case_results: Sequence[Mapping[str, Any]],
    scenario: Scenario | None = None,
    selection: tuple[list[str], str] | None = None,
    judge_model: str = config.JUDGE_MODEL,
    repeats: int = 1,
    skill_cap: int | None = None,
    setup: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """`setup` is the setup fingerprint taken when the run started; recomputing it at the end would
    record code edited during the run instead of the code that ran."""
    return {
        "name": name,
        "bot": bot,
        "scenario": scenario.id if scenario else None,
        "repeats": repeats,
        # After bot only: the most new topic skills its router may pick per message.
        "skill_cap": (config.MAX_NEW_SKILLS_PER_TURN if skill_cap is None else skill_cap) if bot == "after" else None,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": run_models(judge_model),
        "skill_fingerprint": {name: asdict(hashes) for name, hashes in library.fingerprint().items()},
        "setup_fingerprint": dict(setup) if setup is not None else setup_fingerprint(),
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
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help=f"runs per case (default 1; {RECOMMENDED_REPEATS} recommended, so reports can separate change from noise)",
    )
    parser.add_argument(
        "--max-skills",
        type=int,
        help=f"After bot only: the most new topic skills the router may pick per message (default {config.MAX_NEW_SKILLS_PER_TURN})",
    )
    parser.add_argument(
        "--rerun-errors",
        type=Path,
        metavar="PATH",
        help="rerun only the runs that errored in this results file (often a .partial.json) and write the merged file to --out",
    )
    args = parser.parse_args(argv)
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.rerun_errors and (args.baseline or args.dataset or args.limit is not None):
        parser.error("--rerun-errors keeps the file's own cases, so it cannot be combined with --baseline, --dataset or --limit")
    if args.max_skills is not None:
        if args.bot != "after":
            parser.error("--max-skills applies only to the after bot")
        if args.max_skills < 1:
            parser.error("--max-skills must be at least 1")
    return args


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)
    setup = setup_fingerprint()  # before any API call, so it describes the code that runs
    if args.rerun_errors:
        return rerun_errors(args, setup)
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
        if run_repeats(baseline) != args.repeats:
            print(f"warning: the baseline ran each case {run_repeats(baseline)} times and this run {args.repeats}")
        if scenario:
            base_fp = {name: asdict(h) for name, h in base_lib.fingerprint().items()}
            if baseline.get("skill_fingerprint") != base_fp:
                print("warning: the baseline was not run on the current skills/; selection diffs against skills/")
            selection = select_cases(cases, base_lib, library, baseline)
        else:
            selection = select_changed(cases, baseline, library)
        # A different cap, model, prompt or judge code, or bot setting can change any case, so every case reruns.
        reasons: list[str] = []
        base_cap = run_skill_cap(baseline)
        cap = config.MAX_NEW_SKILLS_PER_TURN if args.max_skills is None else args.max_skills
        if args.bot == "after" and cap != base_cap:
            reasons.append(f"the skill cap changed from {base_cap} to {cap}")
        reasons += [f"{part} changed" for part in setup_changes(baseline, run_models(), setup)]
        if "setup_fingerprint" not in baseline:
            print("warning: the baseline predates setup fingerprints; prompt, judge and setting changes cannot be detected")
        if reasons:
            selection = ([c.id for c in cases], f"all cases: {'; '.join(reasons)}")
        wanted = set(selection[0])
        cases = [c for c in cases if c.id in wanted]
        print(f"selection: {selection[1]}")

    if args.limit is not None:
        cases = cases[: args.limit]

    case_results: list[dict[str, Any]] = []
    if cases:  # an empty selection needs no API client at all
        bot_llm, judge_llm = make_llms()
        bot = build_bots(bot_llm, library, args.max_skills)[args.bot]
        judge = Judge(judge_llm)
        label = f" scenario {scenario.id}" if scenario else ""
        times = f" x {args.repeats} runs" if args.repeats > 1 else ""
        cap_label = f", skill cap {args.max_skills}" if args.max_skills is not None else ""
        print(f"running {len(cases)} cases{times} on the {args.bot} bot{label}{cap_label} with {args.workers} workers")
        case_results = run_cases(
            cases, bot=bot, judge=judge, personas=personas, repeats=args.repeats, workers=args.workers
        )

    results = build_results(
        name=args.out.stem,
        bot=args.bot,
        library=library,
        case_results=case_results,
        scenario=scenario,
        selection=selection,
        repeats=args.repeats,
        skill_cap=args.max_skills,
        setup=setup,
    )
    return _finish(args, results)


def _finish(args: argparse.Namespace, results: dict[str, Any]) -> dict[str, Any]:
    """Write the results to --out, or, after a fatal error, to <out>.partial.json and exit with 1,
    so a run that ran out of credit never replaces a complete results file."""
    overall = results["summary"]["overall"]
    fatal = first_fatal(results) or (
        f"every run errored ({overall['errors']} of {overall['total']})" if overall["total"] and overall["errors"] == overall["total"] else None
    )
    if fatal:
        results["complete"] = False
        partial = args.out.with_name(f"{args.out.stem}.partial.json")
        write_results(partial, results)
        raise SystemExit(
            f"stopped: {fatal}\nwrote the finished runs to {partial}; once the cause is fixed, run the rest with "
            f"--rerun-errors {partial} --out {args.out}"
        )
    if not results["cases"] and args.out.exists():
        # Nothing was selected to rerun: keep the results file already there rather than empty it.
        print(f"nothing to rerun, so {args.out} is left as it is")
        return results
    write_results(args.out, results)
    rerun_from = getattr(args, "rerun_errors", None)
    if rerun_from and rerun_from.name.endswith(".partial.json") and rerun_from.resolve() != args.out.resolve():
        print(f"{rerun_from} is merged into {args.out} and can be deleted")

    summary = results["summary"]
    overall = summary["overall"]
    unit = " runs" if results.get("repeats", 1) > 1 else ""
    print(f"passed {overall['passed']}/{overall['total']}{unit} ({overall['errors']} errors)")
    for name, bucket in summary["by_dataset"].items():
        if bucket["total"]:
            print(f"  {name}: {bucket['passed']}/{bucket['total']}")
    print(f"wrote {args.out}")
    return results


def _case_changed(stored: Mapping[str, Any], case: EvalCase) -> bool:
    """Whether a case's recorded fields or graded facts differ from the case file now. Regex edits are
    not recorded in results, so they cannot be seen here."""
    if any(stored.get(key) != (list(case.skills) if key == "skills" else getattr(case, key)) for key in CASE_FIELDS):
        return True
    graded = [[f.get("fact") for f in (run.get("judge") or {}).get("facts") or []] for run in case_runs(stored)]
    return any(facts and facts != list(case.expected_facts) for facts in graded)


def rerun_errors(args: argparse.Namespace, setup: Mapping[str, str]) -> dict[str, Any]:
    """Rerun the runs that errored in an earlier results file, keep its other runs, and write the merge.

    The rerun must use the setup that file recorded (bot, scenario, skill cap, skills, models, bot and
    judge code), or the merged file would mix two setups; anything else stops before an API call.
    """
    previous = json.loads(args.rerun_errors.read_text(encoding="utf-8"))
    scenario_id = previous.get("scenario")
    repeats = run_repeats(previous)
    cap = run_skill_cap(previous)
    problems: list[str] = []
    if previous.get("bot") != args.bot:
        problems.append(f"it was run on the {previous.get('bot')} bot, not {args.bot}")
    if args.scenario and args.scenario != scenario_id:
        problems.append(f"it was run with scenario {scenario_id!r}, not {args.scenario!r}")
    if args.max_skills is not None and args.max_skills != cap:
        problems.append(f"it used a skill cap of {cap}, not {args.max_skills}")
    if args.repeats not in (1, repeats):
        problems.append(f"it ran each case {repeats} times, not {args.repeats}")
    scenario = load_scenario(scenario_id) if scenario_id else None
    library = scenario_library(scenario) if scenario else SkillLibrary.load()
    if previous.get("skill_fingerprint") != {name: asdict(h) for name, h in library.fingerprint().items()}:
        problems.append("the skills changed since then")
    if "setup_fingerprint" not in previous:
        problems.append("it predates setup fingerprints, so the bot and judge code it ran cannot be checked")
    problems += [f"{part} changed since then" for part in setup_changes(previous, run_models(), setup)]
    cases = {c.id: c for c in load_cases()}
    missing = [c["id"] for c in previous.get("cases", []) if c["id"] not in cases]
    if missing:
        problems.append(f"these cases are no longer in the eval set: {', '.join(missing)}")
    edited = [c["id"] for c in previous.get("cases", []) if c["id"] in cases and _case_changed(c, cases[c["id"]])]
    if edited:
        problems.append(f"these cases were edited since then: {', '.join(edited)}")
    if problems:
        raise SystemExit(f"cannot rerun the errored runs of {args.rerun_errors}: " + "; ".join(problems))

    runs: dict[tuple[str, int], dict[str, Any]] = {}
    jobs: list[tuple[EvalCase, int]] = []
    for case_result in previous["cases"]:
        fields = {key: case_result[key] for key in CASE_FIELDS}
        for r, run in enumerate(case_runs(case_result)):
            if run.get("status") == "error":
                jobs.append((cases[case_result["id"]], r))
            else:
                runs[(case_result["id"], r)] = {**{k: v for k, v in run.items() if k not in COUNT_FIELDS}, **fields}
    if jobs:
        bot_llm, judge_llm = make_llms()
        bot = build_bots(bot_llm, library, cap if args.bot == "after" else None)[args.bot]
        print(f"rerunning {len(jobs)} errored runs from {args.rerun_errors} with {args.workers} workers")
        runs |= run_jobs(
            jobs, bot=bot, judge=Judge(judge_llm), personas=load_personas(), repeats=repeats, workers=args.workers
        )
    else:
        print(f"{args.rerun_errors} has no errored runs; rewriting it with a new timestamp and summary")
    case_results = [
        combine_runs([runs[(c["id"], r)] for r in range(len(case_runs(c)))]) for c in previous["cases"]
    ]
    selection = previous.get("selection")
    results = build_results(
        name=args.out.stem,
        bot=args.bot,
        library=library,
        case_results=case_results,
        scenario=scenario,
        selection=(selection["case_ids"], selection["rule"]) if selection else None,
        repeats=repeats,
        skill_cap=cap,
        setup=setup,
    )
    results["rerun_errors"] = {"from_created_at": previous.get("created_at"), "runs": len(jobs)}
    return _finish(args, results)


if __name__ == "__main__":
    main(sys.argv[1:])
