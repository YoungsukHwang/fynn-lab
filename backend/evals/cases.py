"""Eval cases: the YAML format in evals/cases/ and its validation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from fynn.personas import load_personas
from fynn.skills import SkillLibrary

DATASETS = ("single_topic", "multi_intent", "context_use", "safety_basic")
Dataset = Literal["single_topic", "multi_intent", "context_use", "safety_basic"]
ID_PREFIXES: dict[str, str] = {
    "single_topic": "st",
    "multi_intent": "mi",
    "context_use": "cu",
    "safety_basic": "sb",
}

CASES_DIR = Path(__file__).resolve().parent / "cases"
# Cases written after the skills were frozen and never used to change them; run with evals.run --cases.
HOLDOUT_DIR = Path(__file__).resolve().parent / "holdout"

# Every regex in a case is matched case-insensitively.
REGEX_FLAGS = re.IGNORECASE


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    dataset: Dataset
    persona: str
    message: str = Field(min_length=1)
    intents: int = Field(ge=1, le=3)  # distinct questions in the message
    skills: list[str]  # topic skills a correct After router should pick (dependency labels)
    expected_facts: list[str] = Field(min_length=2, max_length=5)
    must_not_regex: list[str] = Field(default_factory=list)
    must_include_regex: list[str] = Field(default_factory=list)
    # Written so that every question beyond the Before router's likely pick hinges on a fact found only in
    # another domain's topic skill: a Before agent cannot pass these by design. Reports split them out.
    designed: bool = False

    @field_validator("skills")
    @classmethod
    def _distinct_skills(cls, skills: list[str]) -> list[str]:
        if len(set(skills)) != len(skills):
            raise ValueError("skills must not repeat")
        return skills

    @field_validator("expected_facts")
    @classmethod
    def _non_empty_facts(cls, facts: list[str]) -> list[str]:
        if any(not fact.strip() for fact in facts):
            raise ValueError("expected_facts must not contain empty strings")
        return facts

    @field_validator("must_not_regex", "must_include_regex")
    @classmethod
    def _compiles(cls, patterns: list[str]) -> list[str]:
        for pattern in patterns:
            try:
                re.compile(pattern, REGEX_FLAGS)
            except re.error as exc:
                raise ValueError(f"invalid regex {pattern!r}: {exc}") from exc
        return patterns

    @model_validator(mode="after")
    def _id_matches_dataset(self) -> EvalCase:
        prefix = ID_PREFIXES[self.dataset]
        if not re.fullmatch(rf"{prefix}-\d{{3}}", self.id):
            raise ValueError(f"id {self.id!r} must look like {prefix}-001 for dataset {self.dataset}")
        return self


class CaseFormatError(ValueError):
    """A case file breaks the format or points at a persona or skill that does not exist."""


def load_cases(
    directory: Path | None = None,
    *,
    personas: Iterable[str] | None = None,
    topic_skills: Iterable[str] | None = None,
) -> list[EvalCase]:
    """Load `<dataset>.yaml` files (each a YAML list of cases), in DATASETS order.

    `personas` and `topic_skills` default to the repo's persona ids and topic skill names.
    """
    directory = directory or CASES_DIR
    persona_ids = set(personas) if personas is not None else set(load_personas())
    topic_names = set(topic_skills) if topic_skills is not None else set(SkillLibrary.load().topic_names)

    paths = sorted(directory.glob("*.yaml"))
    unknown = [p.name for p in paths if p.stem not in DATASETS]
    if unknown:
        raise CaseFormatError(f"unexpected case files {unknown}; expected one of {[d + '.yaml' for d in DATASETS]}")

    cases: list[EvalCase] = []
    seen: set[str] = set()
    for dataset in DATASETS:
        path = directory / f"{dataset}.yaml"
        if not path.exists():
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(raw, list):
            raise CaseFormatError(f"{path.name}: must be a YAML list of cases")
        for index, item in enumerate(raw):
            where = f"{path.name}[{index}]"
            try:
                case = EvalCase.model_validate(item)
            except ValueError as exc:
                raise CaseFormatError(f"{where}: {exc}") from exc
            if case.dataset != dataset:
                raise CaseFormatError(f"{where} ({case.id}): dataset {case.dataset!r} does not match the file")
            if case.id in seen:
                raise CaseFormatError(f"{where}: duplicate case id {case.id!r}")
            if case.persona not in persona_ids:
                raise CaseFormatError(f"{where} ({case.id}): unknown persona {case.persona!r}")
            bad = [s for s in case.skills if s not in topic_names]
            if bad:
                raise CaseFormatError(f"{where} ({case.id}): {bad} are not topic skills")
            seen.add(case.id)
            cases.append(case)

    if not cases:
        raise FileNotFoundError(f"no eval cases in {directory}")
    return cases
