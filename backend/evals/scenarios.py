"""Skill-edit scenarios: scenarios/<id>/scenario.yaml plus edited copies of skill files.

The real skills/ directory is never modified; a scenario's files are overlaid at run time.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, PrivateAttr

from evals.selection import diff_libraries
from fynn import config
from fynn.skills import SkillLibrary, parse_skill

SCENARIOS_DIR = config.REPO_ROOT / "scenarios"

ScenarioKind = Literal["body", "always_on", "description"]
Expected = Literal["improve", "regress", "tradeoff"]


class ScenarioError(ValueError):
    """A scenario is malformed, or its skill files do not make the change its kind says."""


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected: Expected
    detail: str


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    kind: ScenarioKind
    skill: str
    change: str
    motivation: str
    hypothesis: Hypothesis
    shipped: date | None = None  # when the edit was copied into skills/; a shipped scenario no longer runs

    _directory: Path | None = PrivateAttr(default=None)

    @property
    def directory(self) -> Path:
        if self._directory is None:
            raise ScenarioError(f"scenario {self.id} was not loaded from disk")
        return self._directory

    @property
    def skill_files(self) -> list[Path]:
        return sorted((self.directory / "skills").glob("*.md"))


def load_scenario(scenario_id: str, directory: Path | None = None) -> Scenario:
    root = (directory or SCENARIOS_DIR) / scenario_id
    path = root / "scenario.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no scenario file at {path}")
    try:
        scenario = Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except ValueError as exc:
        raise ScenarioError(f"{path}: {exc}") from exc
    if scenario.id != scenario_id:
        raise ScenarioError(f"{path}: id {scenario.id!r} must equal the directory name {scenario_id!r}")
    scenario._directory = root
    if not (root / "skills" / f"{scenario.skill}.md").exists():
        raise ScenarioError(f"{scenario_id}: missing skills/{scenario.skill}.md")
    return scenario


def scenario_library(scenario: Scenario, skills_dir: Path | None = None) -> SkillLibrary:
    """The skills/ library with the scenario's skill files overlaid.

    Raises ScenarioError when the overlay changes anything other than what `kind` says, so a
    scenario always measures the single edit it describes.
    """
    base = SkillLibrary.load(skills_dir or config.SKILLS_DIR)
    skills = {s.name: s for s in base.all}
    for path in scenario.skill_files:
        overlay = parse_skill(path)
        skills[overlay.name] = overlay
    candidate = SkillLibrary(list(skills.values()))

    changes = diff_libraries(base, candidate)
    if scenario.shipped and not changes:
        raise ScenarioError(f"{scenario.id} was shipped to skills/ on {scenario.shipped}, so there is no edit left to run")
    expected = {"body": ("body",), "description": ("description",)}.get(scenario.kind)
    problems = []
    if [c.skill for c in changes] != [scenario.skill]:
        problems.append(f"changes {[(c.skill, c.parts) for c in changes]} must touch only {scenario.skill}")
    elif scenario.kind == "always_on":
        if changes[0].type != "always_on" or not set(changes[0].parts) <= {"description", "body"}:
            problems.append(f"{scenario.skill} must stay an always-on skill with only text edits")
    else:
        if candidate.get(scenario.skill).type != "topic" or changes[0].parts != expected:
            problems.append(f"{scenario.kind} scenario must change only the {scenario.kind} of a topic skill")
    if problems:
        raise ScenarioError(f"{scenario.id}: {'; '.join(problems)}")
    return candidate
