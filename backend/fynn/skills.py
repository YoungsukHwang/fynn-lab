"""Skill files: parsing, validation, and the library both bots share."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from fynn import config

SkillType = Literal["always_on", "topic"]

_FRONTMATTER = re.compile(r"\A---\n(?P<meta>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)


class SkillFormatError(ValueError):
    """A skill file does not follow the expected format."""


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class SkillHashes:
    """Separate hashes, because what changed decides which eval cases must rerun:
    a description edit can change routing for any message, a body edit only matters
    where the skill is loaded, and type/domain changes move the skill between prompts."""

    description: str
    body: str
    meta: str


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    type: SkillType
    domain: str | None
    body: str
    source: str

    @property
    def content_hash(self) -> str:
        """Short hash of the whole file; changes whenever the skill is edited."""
        return _short_hash(self.source)

    @property
    def hashes(self) -> SkillHashes:
        return SkillHashes(
            description=_short_hash(self.description),
            body=_short_hash(self.body),
            meta=_short_hash(f"{self.type}|{self.domain}"),
        )


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise SkillFormatError(f"{path.name}: missing or malformed YAML frontmatter")

    meta = yaml.safe_load(match["meta"]) or {}
    body = match["body"].strip()
    name = meta.get("name")
    description = str(meta.get("description") or "").strip()
    skill_type = meta.get("type")
    domain = meta.get("domain")

    if name != path.stem:
        raise SkillFormatError(f"{path.name}: name {name!r} must equal the file name")
    if skill_type not in ("always_on", "topic"):
        raise SkillFormatError(f"{path.name}: type must be always_on or topic, got {skill_type!r}")
    if skill_type == "topic" and domain not in config.DOMAINS:
        raise SkillFormatError(f"{path.name}: topic skill needs a domain from {list(config.DOMAINS)}")
    if skill_type == "always_on" and domain is not None:
        raise SkillFormatError(f"{path.name}: always_on skills have no domain")
    if not description:
        raise SkillFormatError(f"{path.name}: description is empty")
    if not body:
        raise SkillFormatError(f"{path.name}: body is empty")

    return Skill(
        name=name,
        description=description,
        type=skill_type,
        domain=domain,
        body=body,
        source=text,
    )


class SkillLibrary:
    """All skills, in a fixed (name-sorted) order so prompts are deterministic."""

    def __init__(self, skills: list[Skill]):
        self._by_name = {s.name: s for s in sorted(skills, key=lambda s: s.name)}
        if len(self._by_name) != len(skills):
            raise SkillFormatError("duplicate skill names")

    @classmethod
    def load(cls, directory: Path = config.SKILLS_DIR) -> SkillLibrary:
        paths = sorted(directory.glob("*.md"))
        if not paths:
            raise FileNotFoundError(f"no skill files in {directory}")
        return cls([parse_skill(p) for p in paths])

    def get(self, name: str) -> Skill:
        return self._by_name[name]

    @property
    def all(self) -> list[Skill]:
        return list(self._by_name.values())

    @property
    def always_on(self) -> list[Skill]:
        return [s for s in self._by_name.values() if s.type == "always_on"]

    @property
    def topics(self) -> list[Skill]:
        return [s for s in self._by_name.values() if s.type == "topic"]

    @property
    def topic_names(self) -> list[str]:
        return [s.name for s in self.topics]

    def domain_skills(self, domain: str) -> list[Skill]:
        return [s for s in self.topics if s.domain == domain]

    def fingerprint(self) -> dict[str, SkillHashes]:
        """Skill name -> hashes; the regression runner diffs these to decide what to rerun."""
        return {s.name: s.hashes for s in self._by_name.values()}
