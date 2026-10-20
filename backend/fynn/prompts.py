"""System prompt assembly for both bots.

Both bots use the same identity text, the same skill bodies, and the same member
profile block. The only difference is which skills get in and how they are
grouped, so any quality gap between the bots comes from the architecture.

Prompts are built as blocks ordered from most to least stable, so the API can
cache the shared prefix: identity + always-on/shared guidance (same for every
request of a bot), then the member profile (same for a whole conversation),
then the per-message expertise (changes with routing).
"""

from __future__ import annotations

from dataclasses import dataclass

from fynn import config
from fynn.personas import Persona, render_profile
from fynn.skills import Skill, SkillLibrary

IDENTITY = (
    "You are Coach, the AI credit coach inside a credit-building app. You help members "
    "understand their credit and choose practical next steps. Ground every answer in the "
    "member profile and the guidance below; the guidance is your only source of product "
    "and policy details."
)

NO_TOPIC_NOTE = (
    "No topic guidance was selected for this message. Answer briefly from the always-on "
    "guidance, and ask a clarifying question if the request is unclear."
)


@dataclass(frozen=True)
class PromptBlock:
    text: str
    cache: bool = False  # put a cache breakpoint at the end of this block


def join_blocks(blocks: list[PromptBlock]) -> str:
    return "\n\n".join(b.text for b in blocks)


def render_skill(skill: Skill) -> str:
    return f'<skill name="{skill.name}">\n{skill.body}\n</skill>'


def _section(title: str, body: str) -> str:
    return f"# {title}\n\n{body}"


def _skills(skills: list[Skill]) -> str:
    return "\n\n".join(render_skill(s) for s in skills)


def before_system_prompt(library: SkillLibrary, domain: str | None, persona: Persona) -> list[PromptBlock]:
    """Single expert agent: the shared instructions every agent repeats, plus its domain's skills.

    `domain` is None only when the router failed; the agent then answers without expertise.
    """
    if domain is None:
        expertise = _section("Your expertise", NO_TOPIC_NOTE)
    else:
        expertise = _section(f"Your expertise: {config.DOMAINS[domain]}", _skills(library.domain_skills(domain)))
    return [
        PromptBlock(f"{IDENTITY}\n\n{_section('Shared instructions', _skills(library.always_on))}", cache=True),
        PromptBlock(_section("Member profile", render_profile(persona)), cache=True),
        PromptBlock(expertise),
    ]


def after_system_prompt(library: SkillLibrary, selected: list[Skill], persona: Persona) -> list[PromptBlock]:
    """One agent: always-on skills, then the topic skills active for this message
    (the router's new picks first, then any carried from the previous turn)."""
    topics = _skills(selected) if selected else NO_TOPIC_NOTE
    return [
        PromptBlock(f"{IDENTITY}\n\n{_section('Always-on guidance', _skills(library.always_on))}", cache=True),
        PromptBlock(_section("Member profile", render_profile(persona)), cache=True),
        PromptBlock(_section("Topic guidance for this message", topics)),
    ]
