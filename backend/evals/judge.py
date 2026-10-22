"""Reference-based LLM judge: grades a reply against the case's expected facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from evals.cases import EvalCase
from fynn import config
from fynn.llm import LLM, LLMError, Usage
from fynn.personas import Persona, render_profile

FactStatus = Literal["PRESENT", "ABSENT", "CONTRADICTED"]
FACT_STATUSES: tuple[FactStatus, ...] = ("PRESENT", "ABSENT", "CONTRADICTED")

JUDGE_EFFORT = "medium"
JUDGE_MAX_TOKENS = 4096

JUDGE_SYSTEM = """\
You grade replies from a credit coach chatbot against a fixed list of expected facts.

Grade each expected fact on its own, using only the reply text:
- PRESENT: the reply states the fact or something equivalent. Paraphrase, different wording, \
different order and rounding that keeps the meaning all count as PRESENT.
- ABSENT: the reply does not state the fact, or states it too vaguely to check.
- CONTRADICTED: the reply states something incompatible with the fact. A fact that holds only \
under a condition ("may", "if", "usually") is CONTRADICTED when the reply states it as certain \
or unconditional.
- A fact phrased as something the reply must not do ("does not promise approval") is PRESENT \
when the reply respects it and CONTRADICTED when the reply does that thing.

Rules:
- Grade only against the expected facts. Do not grade tone, formatting, extra correct content, \
or things the list does not ask for.
- Length is not evidence. A long or confident reply does not make a fact PRESENT.
- Use the member profile only to check figures, dates and product status the facts refer to.
- In each note, quote or point to the part of the reply you relied on, in one short sentence.
- The reason is one or two sentences summarizing which facts are missing or contradicted, \
or saying that all are present."""


@dataclass(frozen=True)
class FactGrade:
    fact: str
    status: FactStatus
    note: str


@dataclass(frozen=True)
class JudgeResult:
    facts: list[FactGrade]
    reason: str
    passed: bool
    usage: Usage = field(default_factory=Usage)


def fact_ids(case: EvalCase) -> list[str]:
    return [f"F{i}" for i in range(1, len(case.expected_facts) + 1)]


def judge_schema(case: EvalCase) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": fact_ids(case)},
                        "status": {"type": "string", "enum": list(FACT_STATUSES)},
                        "note": {"type": "string"},
                    },
                    "required": ["id", "status", "note"],
                    "additionalProperties": False,
                },
            },
            "reason": {"type": "string"},
        },
        "required": ["facts", "reason"],
        "additionalProperties": False,
    }


def judge_prompt(case: EvalCase, persona: Persona, reply: str) -> str:
    facts = "\n".join(f"{fid}. {fact}" for fid, fact in zip(fact_ids(case), case.expected_facts, strict=True))
    return (
        f"Member profile:\n{render_profile(persona)}\n\n"
        f"Member message:\n<message>\n{case.message}\n</message>\n\n"
        f"Expected facts:\n{facts}\n\n"
        f"Coach reply to grade:\n<reply>\n{reply}\n</reply>\n\n"
        "Grade every expected fact once, by id, then give the reason."
    )


class Judge:
    def __init__(self, llm: LLM, model: str = config.JUDGE_MODEL):
        self._llm = llm
        self.model = model

    def grade(self, case: EvalCase, persona: Persona, reply: str) -> JudgeResult:
        data, usage = self._llm.generate_json(
            model=self.model,
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": judge_prompt(case, persona, reply)}],
            schema=judge_schema(case),
            effort=JUDGE_EFFORT,
            max_tokens=JUDGE_MAX_TOKENS,
        )
        by_id: dict[str, dict[str, Any]] = {}
        for item in data.get("facts", []):
            if isinstance(item, dict) and item.get("id") not in by_id:
                by_id[str(item.get("id"))] = item

        grades: list[FactGrade] = []
        for fid, fact in zip(fact_ids(case), case.expected_facts, strict=True):
            item = by_id.get(fid)
            if item is None:
                raise LLMError(f"judge did not grade {fid}", usage)
            status = item.get("status")
            if status not in FACT_STATUSES:
                raise LLMError(f"judge returned unknown status {status!r} for {fid}", usage)
            grades.append(FactGrade(fact=fact, status=status, note=str(item.get("note", ""))))

        # The verdict is computed here, not by the model: every expected fact must be PRESENT.
        passed = all(grade.status == "PRESENT" for grade in grades)
        return JudgeResult(facts=grades, reason=str(data.get("reason", "")), passed=passed, usage=usage)
