"""Two checks on a results file that pass or fail does not cover. They read results only.

- Routing: did the answering agent get every topic skill the case is labeled with? The After bot
  gets the skills its router picks; a Before agent gets every skill of the one domain it is routed to.
- Length: how long the replies are, against the response rules' limit of about 250 words, which
  neither the code checks nor the judge grade.
"""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from typing import Any

from fynn.skills import SkillLibrary

WORD_LIMIT = 250  # skills/response-rules.md: "Keep the reply under about 250 words"
LONG = 300


def _ok(results: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [c for c in results.get("cases", []) if c.get("status") == "ok"]


def available_skills(routing: Mapping[str, Any], domains: Mapping[str, str | None]) -> set[str]:
    """The topic skills in the answering agent's prompt."""
    selected = list(routing.get("selected") or [])
    if routing.get("strategy") == "single_agent":
        return {skill for skill, domain in domains.items() if selected and domain == selected[0]}
    return set(selected) | set(routing.get("carried") or [])


def routing_quality(results: Mapping[str, Any], library: SkillLibrary) -> dict[str, Any]:
    """How often the answering agent had every labeled skill, overall and by whether a case needs
    a second domain, plus per skill how often it was labeled, available, and (After) picked."""
    domains = {s.name: s.domain for s in library.topics}
    rows = [c for c in _ok(results) if c.get("routing")]
    strategy = rows[0]["routing"].get("strategy") if rows else None
    groups = {"cross": {"cases": 0, "all_available": 0}, "single": {"cases": 0, "all_available": 0}}
    skills: dict[str, dict[str, int]] = {}
    covered = 0
    for case in rows:
        labeled = {s for s in case.get("skills", []) if s in domains}
        available = available_skills(case["routing"], domains)
        picked = set(case["routing"].get("selected") or []) if strategy == "skills" else set()
        group = "cross" if len({domains[s] for s in labeled}) > 1 else "single"
        has_all = labeled <= available
        covered += has_all
        groups[group]["cases"] += 1
        groups[group]["all_available"] += has_all
        for skill in labeled | picked:
            row = skills.setdefault(skill, {"labeled": 0, "available": 0, "picked": 0, "picked_unlabeled": 0})
            if skill in labeled:
                row["labeled"] += 1
                row["available"] += skill in available
            if skill in picked:
                row["picked"] += 1
                row["picked_unlabeled"] += skill not in labeled
    return {
        "strategy": strategy,
        "cases": len(rows),
        "all_available": covered,
        "by_group": groups,
        "skills": dict(sorted(skills.items())),
    }


def reply_lengths(results: Mapping[str, Any]) -> dict[str, Any]:
    """Words per reply (split on whitespace, so markdown markers count as words)."""
    words = [len((c.get("reply") or "").split()) for c in _ok(results) if c.get("reply")]
    return {
        "replies": len(words),
        "median_words": statistics.median(words) if words else None,
        "mean_words": round(statistics.fmean(words), 1) if words else None,
        "limit": WORD_LIMIT,
        "over_limit": sum(1 for w in words if w > WORD_LIMIT),
        "over_300": sum(1 for w in words if w > LONG),
    }
