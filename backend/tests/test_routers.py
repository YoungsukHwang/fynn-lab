import pytest

from fynn import config
from fynn.llm import LLMError
from fynn.routers import AgentRouter, SkillRouter, render_transcript
from fynn.skills import SkillLibrary
from tests.conftest import FakeLLM

THREE_PART = [{"role": "user", "content": "Why did my score drop? Where is my card? Should I get a new card?"}]
MANY_PICKS = ["score-changes", "made-up", "secured-card", "score-changes", "collections", "utilization", "rent-reporting"]


def test_agent_router_picks_exactly_one(mini_library: SkillLibrary) -> None:
    llm = FakeLLM([{"reason": "score question first", "agent": "score-and-reports"}])
    routing = AgentRouter(llm, mini_library).route(THREE_PART)
    assert routing.strategy == "single_agent"
    assert routing.selected == ["score-and-reports"]

    call = llm.json_calls[0]
    assert call["model"] == config.ROUTER_MODEL
    assert call["schema"]["properties"]["agent"]["enum"] == list(config.DOMAINS)
    # The router sees each domain described by its skills' descriptions.
    assert "Covers secured-card" in call["messages"][0]["content"]


def test_agent_router_rejects_unknown_agent(mini_library: SkillLibrary) -> None:
    llm = FakeLLM([{"reason": "?", "agent": "astrology"}])
    with pytest.raises(LLMError):
        AgentRouter(llm, mini_library).route(THREE_PART)


@pytest.mark.parametrize("cap", [1, 3, 5])
def test_skill_router_keeps_known_unique_and_capped(
    mini_library: SkillLibrary, monkeypatch: pytest.MonkeyPatch, cap: int
) -> None:
    monkeypatch.setattr(config, "MAX_NEW_SKILLS_PER_TURN", cap)
    llm = FakeLLM([{"reason": "several questions", "skills": MANY_PICKS}])
    routing = SkillRouter(llm, mini_library).route(THREE_PART)

    expected = ["score-changes", "secured-card", "collections", "utilization", "rent-reporting"][:cap]
    assert routing.strategy == "skills"
    assert routing.selected == expected
    # The cap in effect reaches the router prompt, not only the post-processing.
    assert f"Choose at most {cap}," in llm.json_calls[0]["system"]
    assert llm.json_calls[0]["schema"]["properties"]["skills"]["items"]["enum"] == mini_library.topic_names


def test_skill_router_cap_override_beats_config(mini_library: SkillLibrary) -> None:
    llm = FakeLLM([{"reason": "several questions", "skills": MANY_PICKS}])
    routing = SkillRouter(llm, mini_library, max_skills=4).route(THREE_PART)

    assert config.MAX_NEW_SKILLS_PER_TURN != 4
    assert routing.selected == ["score-changes", "secured-card", "collections", "utilization"]
    assert "Choose at most 4," in llm.json_calls[0]["system"]


@pytest.mark.parametrize("cap", [0, -1])
def test_skill_router_rejects_a_cap_below_one(mini_library: SkillLibrary, cap: int) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        SkillRouter(FakeLLM([]), mini_library, max_skills=cap)


def test_skill_router_allows_no_skills(mini_library: SkillLibrary) -> None:
    llm = FakeLLM([{"reason": "greeting", "skills": []}])
    assert SkillRouter(llm, mini_library).route([{"role": "user", "content": "hi"}]).selected == []


def test_transcript_uses_recent_messages_only() -> None:
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(7)]
    transcript = render_transcript(messages, limit=4)
    assert "m2" not in transcript
    assert transcript.startswith("Coach: m3")
    assert transcript.endswith("Member: m6")
