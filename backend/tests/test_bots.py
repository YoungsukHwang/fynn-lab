import pytest

from fynn import config
from fynn.bots import EMPTY_REPLY, REFUSAL_REPLY, AfterBot, BeforeBot
from fynn.llm import LLMError, Usage
from fynn.personas import Persona
from fynn.skills import SkillLibrary
from tests.conftest import AGENT_USAGE, ROUTER_USAGE, FakeLLM

MESSAGES = [{"role": "user", "content": "Why did my score drop, and where is my secured card?"}]


def _skills_in(prompt: str) -> set[str]:
    return {line.split('"')[1] for line in prompt.splitlines() if line.startswith("<skill name=")}


def test_before_bot_answers_with_one_domain(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([{"reason": "score", "agent": "score-and-reports"}])
    reply = BeforeBot(llm, mini_library).reply(persona, MESSAGES)

    assert reply.bot == "before"
    assert reply.text == "fake reply"
    assert reply.routing.selected == ["score-and-reports"]
    assert _skills_in(reply.system_prompt) == {"score-changes", "utilization", "tone", "guardrails"}

    call = llm.text_calls[0]
    assert call["model"] == config.AGENT_MODEL
    assert call["messages"] == MESSAGES
    # Router and agent usage are summed field by field, cache fields included.
    assert reply.usage == ROUTER_USAGE + AGENT_USAGE == Usage(110, 55, 3001, 42)


def test_after_bot_loads_every_selected_skill(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([{"reason": "two questions", "skills": ["score-changes", "secured-card"]}])
    reply = AfterBot(llm, mini_library).reply(persona, MESSAGES)

    assert reply.bot == "after"
    assert reply.routing.selected == ["score-changes", "secured-card"]
    assert reply.routing.carried == []
    assert _skills_in(reply.system_prompt) == {"score-changes", "secured-card", "tone", "guardrails"}


def test_after_bot_carries_previous_skills(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([{"reason": "follow-up on balances", "skills": ["utilization"]}])
    previous = ["score-changes", "utilization", "secured-card", "collections"]
    reply = AfterBot(llm, mini_library).reply(persona, MESSAGES, carry_skills=previous)

    # utilization was re-picked, so it is not carried; then at most MAX_CARRIED_SKILLS remain.
    assert reply.routing.selected == ["utilization"]
    assert reply.routing.carried == ["score-changes", "secured-card"][: config.MAX_CARRIED_SKILLS]
    assert reply.routing.active == ["utilization", *reply.routing.carried]
    assert _skills_in(reply.system_prompt) >= {"utilization", "score-changes", "secured-card"}


def test_after_bot_ignores_unknown_carried_skills(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([{"reason": "x", "skills": []}])
    reply = AfterBot(llm, mini_library).reply(persona, MESSAGES, carry_skills=["not-a-skill", "collections"])
    assert reply.routing.carried == ["collections"]


def test_before_bot_ignores_carry_skills(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([{"reason": "score", "agent": "score-and-reports"}])
    reply = BeforeBot(llm, mini_library).reply(persona, MESSAGES, carry_skills=["secured-card"])
    assert reply.routing.carried == []
    assert "secured-card" not in _skills_in(reply.system_prompt)


@pytest.mark.parametrize("bot_cls", [BeforeBot, AfterBot])
def test_router_failure_degrades_to_no_topic_guidance(
    mini_library: SkillLibrary, persona: Persona, bot_cls: type
) -> None:
    llm = FakeLLM([LLMError("structured call stopped with refusal")])
    reply = bot_cls(llm, mini_library).reply(persona, MESSAGES)

    assert reply.text == "fake reply"
    assert reply.routing.selected == []
    assert reply.routing.error == "structured call stopped with refusal"
    assert _skills_in(reply.system_prompt) == {"tone", "guardrails"}
    assert reply.usage == AGENT_USAGE


def test_router_failure_keeps_billed_router_tokens(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([LLMError("structured call stopped with max_tokens", usage=ROUTER_USAGE)])
    reply = AfterBot(llm, mini_library).reply(persona, MESSAGES)
    assert reply.usage == ROUTER_USAGE + AGENT_USAGE


def test_router_failure_still_applies_carried_skills(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([LLMError("structured call stopped with refusal")])
    reply = AfterBot(llm, mini_library).reply(persona, MESSAGES, carry_skills=["secured-card"])
    assert reply.routing.error is not None
    assert reply.routing.carried == ["secured-card"]
    assert _skills_in(reply.system_prompt) == {"secured-card", "tone", "guardrails"}


def test_refusal_gets_a_safe_reply(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([{"reason": "x", "skills": []}], reply="")
    llm.stop_reason = "refusal"
    reply = AfterBot(llm, mini_library).reply(persona, MESSAGES)
    assert reply.text == REFUSAL_REPLY


def test_blank_answer_gets_a_retry_reply(mini_library: SkillLibrary, persona: Persona) -> None:
    llm = FakeLLM([{"reason": "x", "skills": []}], reply="  \n")
    llm.stop_reason = "max_tokens"
    reply = AfterBot(llm, mini_library).reply(persona, MESSAGES)
    assert reply.text == EMPTY_REPLY
    assert reply.stop_reason == "max_tokens"


@pytest.mark.parametrize("messages", [[], [{"role": "assistant", "content": "hello"}]])
def test_bots_need_a_user_message_last(mini_library: SkillLibrary, persona: Persona, messages) -> None:
    with pytest.raises(ValueError):
        AfterBot(FakeLLM(), mini_library).reply(persona, messages)
