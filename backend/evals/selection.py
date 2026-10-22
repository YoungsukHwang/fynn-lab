"""Dependent-test selection: which eval cases a skill change can affect (SPEC section 3).

| What changed                          | Cases rerun                                             |
|---------------------------------------|---------------------------------------------------------|
| body of a topic skill                 | labeled with the skill, or routed to it in the baseline |
| description of a topic skill          | all (the router reads it)                               |
| anything in an always-on skill        | all (in every prompt)                                   |
| domain of a topic skill               | all (only the Before bot is affected)                   |
| type, or a skill added or removed     | all                                                     |
| nothing                               | none                                                    |
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from evals.cases import EvalCase
from evals.stats import case_runs
from fynn.skills import Skill, SkillLibrary, SkillType

# Parts a change can touch. "meta" is used when only hashes are known (type or domain changed).
PARTS = ("added", "removed", "type", "domain", "meta", "description", "body")


@dataclass(frozen=True)
class SkillChange:
    skill: str
    parts: tuple[str, ...]
    type: SkillType | None  # the candidate's type (the base's for a removed skill)
    domain: str | None


def _by_name(library: SkillLibrary) -> dict[str, Skill]:
    return {s.name: s for s in library.all}


def diff_libraries(base: SkillLibrary, candidate: SkillLibrary) -> list[SkillChange]:
    old, new = _by_name(base), _by_name(candidate)
    changes: list[SkillChange] = []
    for name in sorted(set(old) | set(new)):
        b, c = old.get(name), new.get(name)
        if b is None and c is not None:
            changes.append(SkillChange(name, ("added",), c.type, c.domain))
            continue
        if c is None and b is not None:
            changes.append(SkillChange(name, ("removed",), b.type, b.domain))
            continue
        assert b is not None and c is not None
        parts = []
        if b.type != c.type:
            parts.append("type")
        if b.domain != c.domain:
            parts.append("domain")
        if b.hashes.description != c.hashes.description:
            parts.append("description")
        if b.hashes.body != c.hashes.body:
            parts.append("body")
        if parts:
            changes.append(SkillChange(name, tuple(parts), c.type, c.domain))
    return changes


def diff_fingerprint(base: Mapping[str, Mapping[str, str]], candidate: SkillLibrary) -> list[SkillChange]:
    """Diff a results file's `skill_fingerprint` against a library (only hashes are known for the base)."""
    new = _by_name(candidate)
    changes: list[SkillChange] = []
    for name in sorted(set(base) | set(new)):
        b, c = base.get(name), new.get(name)
        if b is None and c is not None:
            changes.append(SkillChange(name, ("added",), c.type, c.domain))
            continue
        if c is None:
            changes.append(SkillChange(name, ("removed",), None, None))
            continue
        assert b is not None
        hashes = asdict(c.hashes)
        parts = [part for part in ("meta", "description", "body") if b.get(part) != hashes[part]]
        if parts:
            changes.append(SkillChange(name, tuple(parts), c.type, c.domain))
    return changes


def _reason_for_all(change: SkillChange) -> str | None:
    """Why this change reruns every case, or None when only dependent cases need rerunning."""
    name, parts = change.skill, change.parts
    if "added" in parts:
        return f"skill {name} was added"
    if "removed" in parts:
        return f"skill {name} was removed"
    if "type" in parts:
        return f"type of {name} changed (it moves between always-on and topic prompts)"
    if "meta" in parts:
        return f"type or domain of {name} changed"
    if change.type == "always_on":
        return f"always-on skill {name} changed (it is in every prompt)"
    if "description" in parts:
        return f"description of topic skill {name} changed (the router reads it, so routing can change anywhere)"
    if "domain" in parts:
        return f"domain of {name} changed (affects only the Before bot's agents and router catalog)"
    return None


def baseline_routing(baseline_results: Mapping[str, Any] | None) -> dict[str, set[str]]:
    """Case id -> what the baseline router actually loaded (skill names for After, domains for Before).

    With repeated runs this is the union over the runs: a skill loaded in any run can change the answer.
    """
    routed: dict[str, set[str]] = {}
    for case in (baseline_results or {}).get("cases", []):
        loaded: set[str] = set()
        for run in case_runs(case):
            routing = run.get("routing") or {}
            loaded |= set(routing.get("selected") or []) | set(routing.get("carried") or [])
        routed[case["id"]] = loaded
    return routed


def select_for_changes(
    cases: Sequence[EvalCase],
    changes: Sequence[SkillChange],
    baseline_results: Mapping[str, Any] | None = None,
) -> tuple[list[str], str]:
    if not changes:
        return [], "no skill changed: nothing to rerun"

    reasons = [r for r in (_reason_for_all(change) for change in changes) if r]
    if reasons:
        return [c.id for c in cases], f"all cases: {'; '.join(reasons)}"

    # Only topic-skill bodies changed. A body is in the prompt only when the skill is loaded:
    # by After when the router picks it, by Before when the router picks its domain.
    bodies = [change for change in changes if "body" in change.parts]
    routed = baseline_routing(baseline_results)
    ids = []
    for case in cases:
        loaded = routed.get(case.id, set())
        for change in bodies:
            if change.skill in case.skills or change.skill in loaded or (change.domain and change.domain in loaded):
                ids.append(case.id)
                break
    names = ", ".join(change.skill for change in bodies)
    source = "or routed to it in the baseline" if baseline_results is not None else "(no baseline routing given)"
    return ids, f"body of topic skill {names} changed: cases labeled with it {source} ({len(ids)} of {len(cases)})"


def select_cases(
    cases: Sequence[EvalCase],
    base_lib: SkillLibrary,
    cand_lib: SkillLibrary,
    baseline_results: Mapping[str, Any] | None = None,
) -> tuple[list[str], str]:
    """Case ids to rerun for the change from `base_lib` to `cand_lib`, and the rule that chose them."""
    return select_for_changes(cases, diff_libraries(base_lib, cand_lib), baseline_results)


def select_changed(
    cases: Sequence[EvalCase], baseline_results: Mapping[str, Any], cand_lib: SkillLibrary
) -> tuple[list[str], str]:
    """Like select_cases, with the base taken from the baseline results' skill fingerprint."""
    changes = diff_fingerprint(baseline_results.get("skill_fingerprint") or {}, cand_lib)
    return select_for_changes(cases, changes, baseline_results)
