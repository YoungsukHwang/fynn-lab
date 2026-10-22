"""The two chatbots compared in the demo and the evals."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal, Protocol

from fynn import config
from fynn.llm import LLM, LLMError, Usage
from fynn.personas import Persona
from fynn.prompts import PromptBlock, after_system_prompt, before_system_prompt, join_blocks
from fynn.routers import AgentRouter, Routing, SkillRouter
from fynn.skills import SkillLibrary

BotName = Literal["before", "after"]

REFUSAL_REPLY = (
    "I can't help with that one here. If you need a person, you can reach support in the app "
    "under Help > Chat with support."
)
EMPTY_REPLY = "Sorry, I couldn't finish that answer. Could you ask again?"


@dataclass(frozen=True)
class BotReply:
    bot: BotName
    text: str
    routing: Routing
    system_prompt: str
    model: str
    stop_reason: str | None
    usage: Usage


class Bot(Protocol):
    name: BotName

    def reply(
        self, persona: Persona, messages: list[dict[str, str]], carry_skills: list[str] | None = None
    ) -> BotReply: ...


def _check_messages(messages: list[dict[str, str]]) -> None:
    if not messages or messages[-1]["role"] != "user":
        raise ValueError("messages must end with a user message")


class _BaseBot:
    name: BotName

    def __init__(self, llm: LLM, library: SkillLibrary):
        self._llm = llm
        self._library = library

    @staticmethod
    def _route(
        router: AgentRouter | SkillRouter,
        strategy: Literal["single_agent", "skills"],
        messages: list[dict[str, str]],
    ) -> Routing:
        # A router refusal, truncation or bad output should not sink the turn: answer
        # without newly routed guidance (the After bot still applies carried skills),
        # record what went wrong, and keep the tokens the failed router call billed.
        try:
            return router.route(messages)
        except LLMError as exc:
            return Routing(strategy, [], "", exc.usage, error=str(exc))

    def _answer(self, routing: Routing, system: list[PromptBlock], messages: list[dict[str, str]]) -> BotReply:
        generation = self._llm.generate(
            model=config.AGENT_MODEL,
            system=system,
            messages=messages,
            effort=config.AGENT_EFFORT,
            max_tokens=config.AGENT_MAX_TOKENS,
        )
        if generation.stop_reason == "refusal":
            text = REFUSAL_REPLY
        elif not generation.text.strip():
            text = EMPTY_REPLY
        else:
            text = generation.text
        return BotReply(
            bot=self.name,
            text=text,
            routing=routing,
            system_prompt=join_blocks(system),
            model=generation.model,
            stop_reason=generation.stop_reason,
            usage=routing.usage + generation.usage,
        )


class BeforeBot(_BaseBot):
    """Before: the earlier design in the post (its beta). Route each message to exactly one domain expert agent."""

    name: BotName = "before"

    def __init__(self, llm: LLM, library: SkillLibrary):
        super().__init__(llm, library)
        self._router = AgentRouter(llm, library)

    def reply(
        self, persona: Persona, messages: list[dict[str, str]], carry_skills: list[str] | None = None
    ) -> BotReply:
        # carry_skills is accepted for a uniform interface; the beta design has no skills to carry.
        _check_messages(messages)
        routing = self._route(self._router, "single_agent", messages)
        domain = routing.selected[0] if routing.selected else None
        return self._answer(routing, before_system_prompt(self._library, domain, persona), messages)


class AfterBot(_BaseBot):
    """After: the skill design the post moved to. Route to the topic skills the message needs, answer with one agent.

    Skills picked on the previous turn (`carry_skills`) stay loaded for one more turn,
    up to MAX_CARRIED_SKILLS, so a follow-up does not lose the guidance behind the
    answer it follows up on.
    """

    name: BotName = "after"

    def __init__(self, llm: LLM, library: SkillLibrary):
        super().__init__(llm, library)
        self._router = SkillRouter(llm, library)

    def reply(
        self, persona: Persona, messages: list[dict[str, str]], carry_skills: list[str] | None = None
    ) -> BotReply:
        _check_messages(messages)
        routing = self._route(self._router, "skills", messages)
        known = set(self._library.topic_names)
        carried: list[str] = []
        for name in carry_skills or []:
            if name in known and name not in routing.selected and name not in carried:
                carried.append(name)
        routing = replace(routing, carried=carried[: config.MAX_CARRIED_SKILLS])
        skills = [self._library.get(name) for name in routing.active]
        return self._answer(routing, after_system_prompt(self._library, skills, persona), messages)


def build_bots(llm: LLM, library: SkillLibrary) -> dict[BotName, Bot]:
    return {"before": BeforeBot(llm, library), "after": AfterBot(llm, library)}
