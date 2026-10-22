"""The two routing strategies.

Before: a small model picks exactly one expert agent (domain).
After: a small model picks every topic skill the latest message needs (up to a cap).

Both routers see the same skill descriptions, so the routing signal is equal;
only the decision shape differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fynn import config
from fynn.llm import LLM, LLMError, Usage
from fynn.skills import SkillLibrary

AGENT_ROUTER_SYSTEM = (
    "You route messages for a credit coach. Choose exactly one expert agent to answer the "
    "member's latest message: the agent whose expertise covers the most important part of it. "
    "Use earlier turns only to interpret the latest message."
)


def skill_router_system(max_skills: int) -> str:
    # Built per call so a changed cap (e.g. in an eval sweep) reaches the router prompt too.
    return (
        "You select guidance for a credit coach. Choose every topic skill the coach needs to fully "
        "answer the member's latest message. A message with several questions usually needs several "
        f"skills. Choose at most {max_skills}, most important first. Choose none for greetings, "
        "thanks, or messages no skill covers. Use earlier turns only to interpret the latest message."
    )


@dataclass(frozen=True)
class Routing:
    strategy: Literal["single_agent", "skills"]
    selected: list[str]  # picked for the latest message (domain ids or skill names)
    reason: str
    usage: Usage
    carried: list[str] = field(default_factory=list)  # After only: kept from the previous turn
    error: str | None = None  # set when the router failed and the bot answered without it

    @property
    def active(self) -> list[str]:
        return self.selected + self.carried


def render_transcript(messages: list[dict[str, str]], limit: int = config.ROUTER_CONTEXT_MESSAGES) -> str:
    speaker = {"user": "Member", "assistant": "Coach"}
    recent = messages[-limit:]
    return "\n\n".join(f"{speaker[m['role']]}: {m['content']}" for m in recent)


class AgentRouter:
    def __init__(self, llm: LLM, library: SkillLibrary):
        self._llm = llm
        self._library = library

    def agent_catalog(self) -> str:
        lines = []
        for domain, title in config.DOMAINS.items():
            covers = " ".join(s.description for s in self._library.domain_skills(domain))
            lines.append(f"- {domain} ({title}): {covers}")
        return "\n".join(lines)

    def route(self, messages: list[dict[str, str]]) -> Routing:
        schema = {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "agent": {"type": "string", "enum": list(config.DOMAINS)},
            },
            "required": ["reason", "agent"],
            "additionalProperties": False,
        }
        prompt = (
            f"Expert agents:\n{self.agent_catalog()}\n\n"
            f"Conversation (latest message last):\n{render_transcript(messages)}\n\n"
            "Give a one-sentence reason, then the agent id."
        )
        data, usage = self._llm.generate_json(
            model=config.ROUTER_MODEL,
            system=AGENT_ROUTER_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            effort=config.ROUTER_EFFORT,
            max_tokens=config.ROUTER_MAX_TOKENS,
        )
        agent = data.get("agent")
        if agent not in config.DOMAINS:
            raise LLMError(f"router returned unknown agent {agent!r}", usage)
        return Routing("single_agent", [agent], str(data.get("reason", "")), usage)


class SkillRouter:
    def __init__(self, llm: LLM, library: SkillLibrary, max_skills: int | None = None):
        if max_skills is not None and max_skills < 1:
            raise ValueError(f"max_skills must be at least 1, not {max_skills}")
        self._llm = llm
        self._library = library
        self._max_skills = max_skills  # None: config.MAX_NEW_SKILLS_PER_TURN, read on each call

    def skill_catalog(self) -> str:
        return "\n".join(f"- {s.name}: {s.description}" for s in self._library.topics)

    def route(self, messages: list[dict[str, str]]) -> Routing:
        max_skills = config.MAX_NEW_SKILLS_PER_TURN if self._max_skills is None else self._max_skills
        schema = {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string", "enum": self._library.topic_names}},
            },
            "required": ["reason", "skills"],
            "additionalProperties": False,
        }
        prompt = (
            f"Topic skills:\n{self.skill_catalog()}\n\n"
            f"Conversation (latest message last):\n{render_transcript(messages)}\n\n"
            "Give a one-sentence reason, then the skill names."
        )
        data, usage = self._llm.generate_json(
            model=config.ROUTER_MODEL,
            system=skill_router_system(max_skills),
            messages=[{"role": "user", "content": prompt}],
            schema=schema,
            effort=config.ROUTER_EFFORT,
            max_tokens=config.ROUTER_MAX_TOKENS,
        )
        known = set(self._library.topic_names)
        selected: list[str] = []
        for name in data.get("skills", []):
            if name in known and name not in selected:
                selected.append(name)
        return Routing("skills", selected[:max_skills], str(data.get("reason", "")), usage)
