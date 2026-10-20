from fynn.personas import Persona
from fynn.prompts import NO_TOPIC_NOTE, after_system_prompt, before_system_prompt, join_blocks
from fynn.skills import SkillLibrary


def _skills_in(prompt: str) -> set[str]:
    return {line.split('"')[1] for line in prompt.splitlines() if line.startswith("<skill name=")}


def test_before_prompt_has_one_domain_plus_shared(mini_library: SkillLibrary, persona: Persona) -> None:
    prompt = join_blocks(before_system_prompt(mini_library, "score-and-reports", persona))
    assert _skills_in(prompt) == {"score-changes", "utilization", "tone", "guardrails"}
    assert "Your expertise: Credit score & reports" in prompt
    assert "Today is 2026-10-15" in prompt


def test_after_prompt_has_selected_plus_always_on(mini_library: SkillLibrary, persona: Persona) -> None:
    selected = [mini_library.get("score-changes"), mini_library.get("secured-card"), mini_library.get("collections")]
    prompt = join_blocks(after_system_prompt(mini_library, selected, persona))
    assert _skills_in(prompt) == {"score-changes", "secured-card", "collections", "tone", "guardrails"}
    # Most stable first: always-on guidance, then the member profile, then the routed topics.
    assert prompt.index("Always-on guidance") < prompt.index("Member profile") < prompt.index("Topic guidance")


def test_before_prompt_without_domain_uses_note(mini_library: SkillLibrary, persona: Persona) -> None:
    prompt = join_blocks(before_system_prompt(mini_library, None, persona))
    assert NO_TOPIC_NOTE in prompt
    assert _skills_in(prompt) == {"tone", "guardrails"}


def test_after_prompt_without_topics_uses_note(mini_library: SkillLibrary, persona: Persona) -> None:
    prompt = join_blocks(after_system_prompt(mini_library, [], persona))
    assert NO_TOPIC_NOTE in prompt
    assert _skills_in(prompt) == {"tone", "guardrails"}


def test_stable_blocks_are_cached_and_shared(mini_library: SkillLibrary, persona: Persona) -> None:
    before = before_system_prompt(mini_library, "credit-products", persona)
    after = after_system_prompt(mini_library, [mini_library.get("secured-card")], persona)
    # Two cache breakpoints (guidance prefix, profile); the routed block varies and is not cached.
    assert [b.cache for b in before] == [True, True, False]
    assert [b.cache for b in after] == [True, True, False]
    # Both bots see the identical profile block.
    assert before[1] == after[1]


def test_cached_prefix_does_not_depend_on_routing(mini_library: SkillLibrary, persona: Persona) -> None:
    first = after_system_prompt(mini_library, [mini_library.get("secured-card")], persona)
    second = after_system_prompt(mini_library, [mini_library.get("collections")], persona)
    assert first[:2] == second[:2]
    assert before_system_prompt(mini_library, "credit-products", persona)[:2] == before_system_prompt(
        mini_library, "debt-and-collections", persona
    )[:2]
