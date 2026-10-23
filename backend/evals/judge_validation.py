"""Check the LLM judge against human labels and against other judge models.

    python -m evals.judge_validation sample --runs ../results/models/after-*.json \
        --include after-sonnet:mi-023 --out ../results/validation/sample.json
    python -m evals.judge_validation page --sample ../results/validation/sample.json --out judge-check.html
    python -m evals.judge_validation regrade --results ../results/models/after-sonnet.json \
        --judge-model claude-sonnet-5-5 --out ../results/validation/regrades/sonnet-on-after-sonnet.json
    python -m evals.judge_validation agreement --sample ../results/validation/sample.json \
        --labels ../results/validation/human-labels.json --regrades ../results/validation/regrades \
        --runs ../results/models/after-*.json --out ../results/validation/agreement

`sample` draws replies from results files for a person to label blind, and `page` writes the labeling
page for it: each fact gets the judge's own three statuses, without the judge's verdict or the
answering model. `regrade` grades replies already stored in a results file with another judge model
(no bot runs again). `agreement` compares every judge with the human labels, and each regrade with
the judge that graded the run. Only `regrade` calls the API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.cases import EvalCase, load_cases
from evals.judge import FACT_STATUSES, Judge, fact_ids
from evals.run import is_fatal, write_results
from evals.setup import setup_fingerprint
from evals.stats import cluster_bootstrap
from fynn import config
from fynn.llm import LLM, LLMError
from fynn.personas import Persona, load_personas, render_profile

TARGETED = "targeted"
FACT_ORDER = list(FACT_STATUSES)
PAGE_TEMPLATE = Path(__file__).with_name("judge_check_page.html")
SKIPPED_ERROR = "skipped: the regrade stopped after a fatal API error"

Key = tuple[str, str]  # (source, case id)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def source_name(path: Path) -> str:
    return path.stem


def _statuses(case: Mapping[str, Any]) -> dict[str, str]:
    facts = (case.get("judge") or {}).get("facts") or []
    return {f"F{i}": f["status"] for i, f in enumerate(facts, start=1)}


def _fact_texts(case: Mapping[str, Any]) -> list[str]:
    return [f["fact"] for f in (case.get("judge") or {}).get("facts") or []]


def eligible(case: Mapping[str, Any], current: EvalCase | None) -> bool:
    """A graded reply whose expected facts still read as they do in the case files."""
    if case.get("status") != "ok" or not case.get("reply") or current is None:
        return False
    return _fact_texts(case) == list(current.expected_facts)


def stratum(case: Mapping[str, Any]) -> str:
    return "judge_pass" if (case.get("judge") or {}).get("passed") else "judge_fail"


# ---------------------------------------------------------------- sample


def build_sample(
    runs: Mapping[str, Mapping[str, Any]],
    cases: Sequence[EvalCase],
    personas: Mapping[str, Persona],
    *,
    per_stratum: int,
    include: Iterable[Key] = (),
    seed: int = 0,
) -> dict[str, Any]:
    """Draw `per_stratum` replies from each (source, judge pass/fail) cell, plus the `include`d
    (source, case id) pairs as targeted items. Items are shuffled and numbered R01, R02, ...

    Sources and includes are taken in sorted order, so the same files, includes and seed give the
    same sample whatever order the command line lists them in."""
    by_id = {c.id: c for c in cases}
    rng = random.Random(seed)
    wanted = sorted(set(include))
    population: Counter[str] = Counter()
    picked: list[tuple[str, Mapping[str, Any], str]] = []
    for source in sorted(runs):
        pool: dict[str, list[Mapping[str, Any]]] = {"judge_pass": [], "judge_fail": []}
        for case in runs[source]["cases"]:
            if (source, case["id"]) in wanted or not eligible(case, by_id.get(case["id"])):
                continue
            pool[stratum(case)].append(case)
        for name, members in pool.items():
            population[f"{source}/{name}"] = len(members)
            chosen = rng.sample(members, min(per_stratum, len(members)))
            picked.extend((source, case, name) for case in sorted(chosen, key=lambda c: c["id"]))
    for source, case_id in wanted:
        case = next((c for c in runs.get(source, {}).get("cases", []) if c["id"] == case_id), None)
        if case is None or not eligible(case, by_id.get(case_id)):
            raise SystemExit(f"--include {source}:{case_id}: no graded reply with the current facts")
        picked.append((source, case, TARGETED))

    rng.shuffle(picked)  # so an item's number says nothing about its source or the judge's verdict
    items = []
    for n, (source, case, name) in enumerate(picked, start=1):
        current = by_id[case["id"]]
        items.append(
            {
                "item": f"R{n:02d}",
                "source": source,
                "case": case["id"],
                "stratum": name,
                "persona": case["persona"],
                "message": current.message,
                "reply": case["reply"],
                "reply_sha": _sha(case["reply"]),
                "facts": [
                    {"id": fid, "fact": fact}
                    for fid, fact in zip(fact_ids(current), current.expected_facts, strict=True)
                ],
                "judge": {"model": runs[source]["models"]["judge"], "statuses": _statuses(case)},
            }
        )
    used = sorted({item["persona"] for item in items})
    return {
        "kind": "judge_sample",
        "sample_id": _sha(json.dumps([[i["item"], i["source"], i["case"], i["reply_sha"]] for i in items])),
        "created_at": _now(),
        "args": {
            "runs": sorted(runs),
            "per_stratum": per_stratum,
            "include": [f"{s}:{c}" for s, c in wanted],
            "seed": seed,
        },
        "sources": {
            source: {"created_at": runs[source].get("created_at"), "models": runs[source].get("models")}
            for source in sorted(runs)
        },
        "population": dict(population),
        "profiles": {pid: render_profile(personas[pid]) for pid in used},
        "items": items,
    }


def blind_items(sample: Mapping[str, Any]) -> list[dict[str, Any]]:
    """What a labeler sees: no source, stratum or judge statuses."""
    return [{k: item[k] for k in ("item", "persona", "message", "reply", "facts")} for item in sample["items"]]


def build_page(sample: Mapping[str, Any], template: str, translations: Mapping[str, Any] | None = None) -> str:
    """The labeling page: the template with the blind items, the profiles they use and the sample id.
    `translations` ({"messages": {en: text}, "facts": {en: text}}) adds reading aids under the English,
    which stays what is graded."""
    items = blind_items(sample)
    if translations:
        messages, facts = translations.get("messages", {}), translations.get("facts", {})
        for item in items:
            if item["message"] in messages:
                item["message_ko"] = messages[item["message"]]
            item["facts"] = [{**f, **({"ko": facts[f["fact"]]} if f["fact"] in facts else {})} for f in item["facts"]]
    data = {"sample_id": sample["sample_id"], "items": items, "profiles": sample["profiles"]}
    # "</" would end the <script> element that holds the data.
    return template.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))


# ---------------------------------------------------------------- regrade


def make_judge_llm() -> LLM:
    from evals.run import make_llms

    return make_llms()[1]


def regrade(
    results: Mapping[str, Any],
    cases: Sequence[EvalCase],
    personas: Mapping[str, Persona],
    judge: Judge,
    *,
    workers: int = 6,
    progress: Callable[[str], None] | None = print,
) -> list[dict[str, Any]]:
    """Grade every eligible stored reply again with `judge`, one row per reply in results order.
    After a fatal API error the replies not yet started are recorded as skipped errors, so a run
    with no credit left stops at once."""
    by_id = {c.id: c for c in cases}
    todo = [case for case in results["cases"] if eligible(case, by_id.get(case["id"]))]
    graded: dict[str, dict[str, Any]] = {}
    stop = threading.Event()

    def row(case: Mapping[str, Any], status: str, error: str | None, judged: dict[str, Any] | None) -> dict[str, Any]:
        return {"id": case["id"], "reply_sha": _sha(case["reply"]), "status": status, "error": error, "judge": judged}

    def one(case: Mapping[str, Any]) -> dict[str, Any]:
        if stop.is_set():
            return row(case, "error", SKIPPED_ERROR, None)
        current = by_id[case["id"]]
        try:
            result = judge.grade(current, personas[current.persona], case["reply"])
        except Exception as exc:  # noqa: BLE001 (one bad reply must not sink the regrade)
            error = f"{type(exc).__name__}: {exc}"
            if is_fatal(error):
                stop.set()
            usage = exc.usage if isinstance(exc, LLMError) else None
            failed = None if usage is None else {"facts": [], "reason": "", "passed": False, "usage": asdict(usage)}
            return row(case, "error", error, failed)
        judged = {
            "facts": [asdict(f) for f in result.facts],
            "reason": result.reason,
            "passed": result.passed,
            "usage": asdict(result.usage),
        }
        return row(case, "ok", None, judged)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, case) for case in todo]
        for done, future in enumerate(as_completed(futures), start=1):
            r = future.result()
            graded[r["id"]] = r
            if progress and r["error"] != SKIPPED_ERROR:
                verdict = "error" if r["status"] == "error" else ("PASS" if r["judge"]["passed"] else "FAIL")
                progress(f"[{done}/{len(todo)}] {r['id']} {verdict}")
    return [graded[case["id"]] for case in todo]


def regrade_complete(rows: Sequence[Mapping[str, Any]]) -> bool:
    """False after a fatal API error (even one that hit only replies already in flight) or when every
    reply errored, as for an eval run: such a file says nothing about the judge."""
    if any(r["error"] and (r["error"] == SKIPPED_ERROR or is_fatal(r["error"])) for r in rows):
        return False
    return not rows or any(r["status"] == "ok" for r in rows)


def build_regrade(
    *,
    source: Path,
    results: Mapping[str, Any],
    judge_model: str,
    label: str,
    judge_code: str,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ok = [r for r in rows if r["status"] == "ok"]
    return {
        "kind": "judge_regrade",
        "label": label,
        "created_at": _now(),
        "complete": regrade_complete(rows),
        "source": source_name(source),
        "source_created_at": results.get("created_at"),
        "models": {"answer": (results.get("models") or {}).get("agent"), "judge": judge_model},
        "judge_code": judge_code,  # the judge prompt and checks this regrade ran with
        "cases": list(rows),
        "summary": {
            "graded": len(ok),
            "passed": sum(1 for r in ok if r["judge"]["passed"]),
            "errors": len(rows) - len(ok),
        },
    }


def partial_path(out: Path) -> Path:
    return out.with_name(out.stem + ".partial.json")


# ---------------------------------------------------------------- agreement


def _binary(status: str) -> str:
    return "PRESENT" if status == "PRESENT" else "NOT_PRESENT"


def kappa(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two raters over the same items."""
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(1 for a, b in pairs if a == b) / n
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    expected = sum(left[k] * right[k] for k in set(left) | set(right)) / (n * n)
    if expected == 1:
        return None
    return round((observed - expected) / (1 - expected), 4)


def compare(
    pairs: Sequence[tuple[str, str]], clusters: Sequence[str], weights: Sequence[float] | None = None
) -> dict[str, Any]:
    """Fact-level agreement of rater `a` (a judge) with rater `b` (the reference) on (a, b) pairs.

    `clusters` names the reply each pair comes from: the interval resamples replies, since the facts
    of one reply are graded together. `stricter` counts facts `a` failed that `b` passed, `lenient`
    the reverse."""
    n = len(pairs)
    binary = [(_binary(a), _binary(b)) for a, b in pairs]
    agree = [1.0 if a == b else 0.0 for a, b in binary]
    interval = cluster_bootstrap(list(zip(clusters, agree, strict=True))) if n else None
    ci = None
    if interval is not None and interval.low is not None and interval.high is not None:
        ci = [round(interval.low, 4), round(interval.high, 4)]
    out: dict[str, Any] = {
        "facts": n,
        "replies": len(set(clusters)),
        "agree": sum(1 for a, b in pairs if a == b),
        "agree_binary": int(sum(agree)),
        "rate_binary": round(sum(agree) / n, 4) if n else None,
        "ci_binary": ci,
        "kappa": kappa(pairs),
        "kappa_binary": kappa(binary),
        "stricter": sum(1 for a, b in binary if a == "NOT_PRESENT" and b == "PRESENT"),
        "lenient": sum(1 for a, b in binary if a == "PRESENT" and b == "NOT_PRESENT"),
        "confusion": {a: {b: sum(1 for x, y in pairs if (x, y) == (a, b)) for b in FACT_ORDER} for a in FACT_ORDER},
    }
    if weights is not None and n:
        out["weighted_rate_binary"] = round(sum(w * g for w, g in zip(weights, agree, strict=True)) / sum(weights), 4)
    return out


def load_regrades(paths: Iterable[Path], warnings: list[str]) -> list[dict[str, Any]]:
    """Complete regrade files from the given files and directories. A partial file (the regrade
    stopped after a fatal error) is left out with a warning."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
        elif path.exists():
            files.append(path)
        else:
            warnings.append(f"{path} does not exist, so no regrades were read from it.")
    regrades = []
    for file in files:
        data = json.loads(file.read_text(encoding="utf-8"))
        if data.get("kind") != "judge_regrade":
            continue
        if not data.get("complete", True):
            warnings.append(f"{file.name} is a partial regrade (it stopped after a fatal error) and is left out.")
            continue
        regrades.append(data)
    return regrades


def judge_views(
    sample: Mapping[str, Any], regrades: Sequence[Mapping[str, Any]], warnings: list[str]
) -> dict[str, dict[Key, dict[str, str]]]:
    """Each judge's fact statuses for the sampled replies, by (source, case id). "original" is the
    judge that graded the run. A regrade row counts only for the reply and facts the sample holds."""
    models = sorted({item["judge"]["model"] for item in sample["items"]})
    by_key = {(i["source"], i["case"]): i for i in sample["items"]}
    views: dict[str, dict[Key, dict[str, str]]] = {
        f"original ({', '.join(models)})": {key: i["judge"]["statuses"] for key, i in by_key.items()}
    }
    for regrade_file in regrades:
        view: dict[Key, dict[str, str]] = {}
        stale = 0
        for r in regrade_file["cases"]:
            item = by_key.get((regrade_file["source"], r["id"]))
            if item is None or r["status"] != "ok":
                continue
            if r.get("reply_sha") != item["reply_sha"] or _fact_texts(r) != [f["fact"] for f in item["facts"]]:
                stale += 1
                continue
            view[(regrade_file["source"], r["id"])] = _statuses(r)
        if view:
            views.setdefault(regrade_file["label"], {}).update(view)
        elif not stale and any(r["status"] == "ok" for r in regrade_file["cases"]):
            warnings.append(f"{regrade_file['label']} on {regrade_file['source']}: none of its replies are in the sample.")
        if stale:
            warnings.append(
                f"{regrade_file['label']} on {regrade_file['source']}: {stale} sampled replies were regraded "
                "with a different reply or different facts than the sample holds, so they are left out."
            )
    return views


def labeled_fully(item: Mapping[str, Any], labels: Mapping[str, Mapping[str, str]]) -> bool:
    human = labels.get(item["item"]) or {}
    return all(f["id"] in human for f in item["facts"])


def human_agreement(
    sample: Mapping[str, Any],
    labels: Mapping[str, Mapping[str, str]],
    views: Mapping[str, Mapping[Key, Mapping[str, str]]],
    warnings: list[str],
) -> dict[str, Any]:
    """Every judge against the human labels on the randomly drawn replies that are fully labeled.
    The original judge is scored on all of them; any other judge on the ones it graded, next to the
    original judge on those same replies, so the two numbers compare like with like. Targeted
    replies are listed apart. The weighted rate undoes the stratified draw: each compared reply
    stands for population / compared replies of its cell."""
    original_name = next(iter(views))
    full = [i for i in sample["items"] if i["stratum"] != TARGETED and labeled_fully(i, labels)]
    population = sample.get("population", {})

    def score(name: str, view: Mapping[Key, Mapping[str, str]], items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        used = Counter(f"{i['source']}/{i['stratum']}" for i in items)
        pairs: list[tuple[str, str]] = []
        clusters: list[str] = []
        weights: list[float] = []
        by_source: dict[str, tuple[list[tuple[str, str]], list[str]]] = {}
        replies: list[tuple[bool, bool]] = []
        for item in items:
            cell = f"{item['source']}/{item['stratum']}"
            statuses = view[(item["source"], item["case"])]
            human = labels[item["item"]]
            item_pairs = [(statuses[f["id"]], human[f["id"]]) for f in item["facts"]]
            pairs.extend(item_pairs)
            clusters.extend([item["item"]] * len(item_pairs))
            weights.extend([population.get(cell, used[cell]) / used[cell]] * len(item_pairs))
            src_pairs, src_clusters = by_source.setdefault(item["source"], ([], []))
            src_pairs.extend(item_pairs)
            src_clusters.extend([item["item"]] * len(item_pairs))
            replies.append((all(a == "PRESENT" for a, _ in item_pairs), all(b == "PRESENT" for _, b in item_pairs)))
        return {
            **compare(pairs, clusters, weights),
            "cells_left_out": sorted(c for c, size in population.items() if size and not used[c]),
            "replies_agree": sum(1 for a, b in replies if a == b),
            "replies_judge_fail_human_pass": sum(1 for a, b in replies if not a and b),
            "replies_judge_pass_human_fail": sum(1 for a, b in replies if a and not b),
            "by_source": {s: compare(p, c) for s, (p, c) in sorted(by_source.items())},
        }

    judges: dict[str, Any] = {}
    for name, view in views.items():
        items = [i for i in full if (i["source"], i["case"]) in view]
        judges[name] = score(name, view, items)
        if name == original_name:
            continue
        if not items:
            warnings.append(f"{name} graded none of the labeled replies, so it has no human comparison.")
            continue
        same = score(original_name, views[original_name], items)
        judges[name]["original_on_same_replies"] = {
            k: same[k] for k in ("rate_binary", "ci_binary", "weighted_rate_binary", "kappa_binary", "stricter", "lenient")
        }
    for name, j in judges.items():
        if j["replies"] and j["cells_left_out"]:
            warnings.append(
                f"{name}: no compared reply stands for {', '.join(j['cells_left_out'])}, "
                "so its weighted rate leaves those cells out."
            )

    targeted = []
    for item in sample["items"]:
        if item["stratum"] != TARGETED or not labeled_fully(item, labels):
            continue
        key = (item["source"], item["case"])
        targeted.append(
            {
                "item": item["item"],
                "source": item["source"],
                "case": item["case"],
                "facts": [
                    {
                        "id": f["id"],
                        "human": labels[item["item"]][f["id"]],
                        **{name: (view.get(key) or {}).get(f["id"]) for name, view in views.items()},
                    }
                    for f in item["facts"]
                ],
            }
        )
    partial = sum(1 for i in sample["items"] if labels.get(i["item"]) and not labeled_fully(i, labels))
    return {
        "items": len(sample["items"]),
        "labeled_items": sum(1 for i in sample["items"] if labeled_fully(i, labels)),
        "partly_labeled_items": partial,
        "labeled_random_replies": len(full),
        "judges": judges,
        "targeted": targeted,
    }


def judge_vs_judge(
    runs: Mapping[str, Mapping[str, Any]],
    regrades: Sequence[Mapping[str, Any]],
    cases: Sequence[EvalCase],
    warnings: list[str],
) -> list[dict[str, Any]]:
    """Each regrade against the judge that graded its run, on every reply both graded."""
    by_id = {c.id: c for c in cases}
    out = []
    for regrade_file in regrades:
        name = f"{regrade_file['label']} on {regrade_file['source']}"
        source = runs.get(regrade_file["source"])
        if source is None:
            warnings.append(f"{name}: pass that results file with --runs to compare it with the original judge.")
            continue
        # Matched on the facts both graded, not on today's case files, so a later fact edit does not
        # drop a reply that both judges graded the same way.
        original = {c["id"]: c for c in source["cases"] if c.get("status") == "ok" and c.get("reply")}
        pairs: list[tuple[str, str]] = []
        clusters: list[str] = []
        passes = {"original": 0, "regrade": 0, "both": 0}
        stale = 0
        for r in regrade_file["cases"]:
            base = original.get(r["id"])
            if r["status"] != "ok" or base is None:
                continue
            if r.get("reply_sha") != _sha(base["reply"]) or _fact_texts(r) != _fact_texts(base):
                stale += 1
                continue
            new, old = _statuses(r), _statuses(base)
            pairs.extend((new[fid], old[fid]) for fid in old)
            clusters.extend([r["id"]] * len(old))
            passes["original"] += bool(base["judge"]["passed"])
            passes["regrade"] += bool(r["judge"]["passed"])
            passes["both"] += bool(base["judge"]["passed"] and r["judge"]["passed"])
        if stale:
            warnings.append(
                f"{name}: {stale} replies differ from the results file (it was rerun after the regrade, "
                "or the facts changed), so they are left out."
            )
        same_code = (
            None
            if "judge_code" not in regrade_file or "setup_fingerprint" not in source
            else regrade_file["judge_code"] == source["setup_fingerprint"].get("judge_code")
        )
        if same_code is False:
            warnings.append(f"{name}: the judge prompt or checks changed between the run and the regrade.")
        out.append(
            {
                "label": regrade_file["label"],
                "source": regrade_file["source"],
                "original_judge": (source.get("models") or {}).get("judge"),
                "same_judge_code": same_code,
                "passes": passes,
                **compare(pairs, clusters),
            }
        )
    return out


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def _ci(ci: Sequence[float] | None) -> str:
    return "n/a" if ci is None else f"{_pct(ci[0])} to {_pct(ci[1])}"


def _kappa(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def render_markdown(report: Mapping[str, Any]) -> str:
    human = report.get("human")
    lines = ["# Judge validation", ""]
    if report.get("warnings"):
        lines += ["## Warnings", "", *[f"- {w}" for w in report["warnings"]], ""]
    if human:
        lines += [
            f"Human labels on {human['labeled_items']} of {human['items']} sampled replies "
            f"({human['partly_labeled_items']} more partly labeled), {human['labeled_random_replies']} of them "
            "drawn at random. Agreement is fact by fact, on PRESENT against not PRESENT. The original judge "
            "is scored on every labeled random reply, any other judge on the ones it graded, with the original "
            "judge on those same replies next to it. The interval resamples replies; the weighted rate undoes "
            "the stratified draw.",
            "",
            "## Judges against the human labels",
            "",
            "| Judge | Replies | Facts | Agree | 95% interval | Weighted | Kappa | Stricter | More lenient | "
            "Replies agree | Original judge, same replies |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, j in human["judges"].items():
            same = j.get("original_on_same_replies")
            lines.append(
                f"| {name} | {j['replies']} | {j['facts']} | {_pct(j['rate_binary'])} | {_ci(j['ci_binary'])} | "
                f"{_pct(j.get('weighted_rate_binary'))} | {_kappa(j['kappa_binary'])} | {j['stricter']} | "
                f"{j['lenient']} | {j['replies_agree']} of {j['replies']} | "
                f"{'' if same is None else _pct(same['rate_binary']) + ' (weighted ' + _pct(same['weighted_rate_binary']) + ')'} |"
            )
        lines += ["", "Stricter: the judge failed a fact the human passed. More lenient: the reverse.", ""]
        lines += [
            "## By answering model",
            "",
            "| Judge | Source | Facts | Agree | Stricter | More lenient |",
            "|---|---|---|---|---|---|",
        ]
        for name, j in human["judges"].items():
            for source, s in j["by_source"].items():
                lines.append(
                    f"| {name} | {source} | {s['facts']} | {_pct(s['rate_binary'])} | {s['stricter']} | {s['lenient']} |"
                )
        if human["targeted"]:
            names = list(human["judges"])
            lines += [
                "",
                "## Targeted replies",
                "",
                "| Item | Source | Case | Fact | Human | " + " | ".join(names) + " |",
                "|---|---|---|---|---|" + "---|" * len(names),
            ]
            for t in human["targeted"]:
                for f in t["facts"]:
                    cells = " | ".join(str(f.get(n)) for n in names)
                    lines.append(f"| {t['item']} | {t['source']} | {t['case']} | {f['id']} | {f['human']} | {cells} |")
        lines.append("")
    pairs = report.get("judge_vs_judge") or []
    if pairs:
        lines += [
            "## Regrades against the original judge, every reply",
            "",
            "| Regrade | Source | Replies | Fact agreement | 95% interval | Kappa | Stricter | More lenient | "
            "Passes (original, regrade) |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for p in pairs:
            lines.append(
                f"| {p['label']} | {p['source']} | {p['replies']} | {_pct(p['rate_binary'])} | {_ci(p['ci_binary'])} | "
                f"{_kappa(p['kappa_binary'])} | {p['stricter']} | {p['lenient']} | "
                f"{p['passes']['original']}, {p['passes']['regrade']} |"
            )
        lines += ["", "Stricter: the regrade failed a fact the original judge passed.", ""]
    return "\n".join(lines)


def load_labels(path: Path, sample_id: str | None = None) -> dict[str, dict[str, str]]:
    """Human labels by item and fact id. Takes `{item: {fact id: status}}`, optionally under a "labels"
    key next to a "sample_id", or the labeling page's `{item: {"facts": {...}, "note": ..., "sample": ...}}`.
    Labels saved for another sample are refused: an item number means a different reply there."""
    data = json.loads(path.read_text(encoding="utf-8"))
    labels: dict[str, dict[str, str]] = {}
    for item, value in data.get("labels", data).items():
        if item == "sample_id":
            continue
        page = isinstance(value, dict) and isinstance(value.get("facts"), dict)
        facts = value["facts"] if page else value
        bad = {fid: s for fid, s in facts.items() if s not in FACT_STATUSES}
        if bad:
            raise SystemExit(f"{path}: item {item} has statuses outside {FACT_ORDER}: {bad}")
        saved_for = (value.get("sample") if page else None) or data.get("sample_id")
        if sample_id and saved_for and saved_for != sample_id:
            raise SystemExit(f"{path}: item {item} was labeled for sample {saved_for}, not {sample_id}")
        labels[item] = dict(facts)
    return labels


# ---------------------------------------------------------------- CLI


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _include(text: str) -> Key:
    source, sep, case_id = text.partition(":")
    if not sep or not source or not case_id:
        raise argparse.ArgumentTypeError(f"expected SOURCE:CASE_ID, got {text!r}")
    return source, case_id


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m evals.judge_validation", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sample", help="draw replies for blind human labels (no API calls)")
    s.add_argument("--runs", nargs="+", required=True, type=Path, help="results files; each file's name is its source")
    s.add_argument("--per-stratum", type=int, default=4, help="replies per (source, judge pass/fail) cell")
    s.add_argument("--include", action="append", default=[], type=_include, help="SOURCE:CASE_ID, labeled apart")
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", required=True, type=Path)
    s.add_argument("--force", action="store_true", help="overwrite an existing sample (its labels stop matching)")

    p = sub.add_parser("page", help="write the labeling page for a sample (no API calls)")
    p.add_argument("--sample", required=True, type=Path)
    p.add_argument("--translations", type=Path, help='reading aids: {"messages": {en: text}, "facts": {en: text}}')
    p.add_argument("--out", required=True, type=Path)

    r = sub.add_parser("regrade", help="grade stored replies with another judge model (calls the API)")
    r.add_argument("--results", required=True, type=Path)
    r.add_argument("--judge-model", default=config.JUDGE_MODEL)
    r.add_argument("--label", help="judge name in the agreement report (default: the model id)")
    r.add_argument("--workers", type=int, default=6)
    r.add_argument("--limit", type=int, help="grade only the first N replies (smoke tests)")
    r.add_argument("--out", required=True, type=Path)

    a = sub.add_parser("agreement", help="compare judges with the human labels and with each other (no API calls)")
    a.add_argument("--sample", required=True, type=Path)
    a.add_argument("--labels", type=Path, help="human labels JSON: {item: {fact id: status}}")
    a.add_argument("--regrades", nargs="*", default=[], type=Path, help="regrade files or directories")
    a.add_argument("--runs", nargs="*", default=[], type=Path, help="results files the regrades graded")
    a.add_argument("--out", required=True, type=Path, help="directory for agreement.json and agreement.md")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> dict[str, Any]:
    args = parse_args(argv)

    if args.command == "page":
        sample = _load(args.sample)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        translations = _load(args.translations) if args.translations else None
        page = build_page(sample, PAGE_TEMPLATE.read_text(encoding="utf-8"), translations)
        args.out.write_text(page, encoding="utf-8")
        print(f"wrote {args.out} for sample {sample['sample_id']} ({len(sample['items'])} replies)")
        return sample

    cases = load_cases()
    personas = load_personas()

    if args.command == "sample":
        if args.out.exists() and not args.force:
            raise SystemExit(f"{args.out} exists and its labels would stop matching; pass --force to draw a new sample")
        runs = {source_name(p): _load(p) for p in args.runs}
        sample = build_sample(runs, cases, personas, per_stratum=args.per_stratum, include=args.include, seed=args.seed)
        write_results(args.out, sample)
        cells = Counter(i["stratum"] for i in sample["items"])
        print(f"wrote {args.out}: sample {sample['sample_id']}, {len(sample['items'])} replies ({dict(cells)})")
        return sample

    if args.command == "regrade":
        judge_code = setup_fingerprint()["judge_code"]  # before any API call, so it describes the code that runs
        results = _load(args.results)
        llm = make_judge_llm()
        if args.limit is not None:
            results = {**results, "cases": results["cases"][: args.limit]}
        rows = regrade(results, cases, personas, Judge(llm, model=args.judge_model), workers=args.workers)
        out = build_regrade(
            source=args.results,
            results=results,
            judge_model=args.judge_model,
            label=args.label or args.judge_model,
            judge_code=judge_code,
            rows=rows,
        )
        s = out["summary"]
        if not out["complete"]:
            path = partial_path(args.out)
            write_results(path, out)
            print(f"stopped after a fatal API error: graded {s['graded']}, wrote {path}", file=sys.stderr)
            raise SystemExit(1)
        write_results(args.out, out)
        print(f"passed {s['passed']}/{s['graded']} ({s['errors']} errors)\nwrote {args.out}")
        return out

    sample = _load(args.sample)
    warnings: list[str] = []
    regrades = load_regrades(args.regrades, warnings)
    runs = {source_name(p): _load(p) for p in args.runs}
    report: dict[str, Any] = {"kind": "judge_agreement", "created_at": _now(), "sample_id": sample["sample_id"]}
    if args.labels:
        labels = load_labels(args.labels, sample["sample_id"])
        report["human"] = human_agreement(sample, labels, judge_views(sample, regrades, warnings), warnings)
    report["judge_vs_judge"] = judge_vs_judge(runs, regrades, cases, warnings)
    report["warnings"] = warnings
    args.out.mkdir(parents=True, exist_ok=True)
    write_results(args.out / "agreement.json", report)
    (args.out / "agreement.md").write_text(render_markdown(report), encoding="utf-8")
    for warning in warnings:
        print(f"warning: {warning}")
    print(f"wrote {args.out / 'agreement.md'}")
    return report


if __name__ == "__main__":
    main()
