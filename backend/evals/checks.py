"""Objective code checks on a reply (SPEC section 3, scoring step 1).

`must_not_regex` patterns catch only affirmative violations that cannot be confused with a
correct disclaimer; anything that needs context ("is this a promise?") is left to the judge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from evals.cases import REGEX_FLAGS, EvalCase


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


def run_checks(case: EvalCase, reply: str) -> CheckResult:
    failures: list[str] = []
    if not reply.strip():
        failures.append("reply is empty")
    for pattern in case.must_not_regex:
        match = re.search(pattern, reply, REGEX_FLAGS)
        if match:
            failures.append(f"must_not_regex {pattern!r} matched {match.group(0)!r}")
    for pattern in case.must_include_regex:
        if not re.search(pattern, reply, REGEX_FLAGS):
            failures.append(f"must_include_regex {pattern!r} not found")
    return CheckResult(passed=not failures, failures=failures)
