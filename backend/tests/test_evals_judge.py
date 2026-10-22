import pytest

from evals.cases import EvalCase
from evals.judge import JUDGE_EFFORT, JUDGE_MAX_TOKENS, Judge, judge_schema
from fynn import config
from fynn.llm import LLMError
from fynn.personas import Persona
from tests.conftest import ROUTER_USAGE, FakeLLM

CASE = EvalCase(
    id="mi-001",
    dataset="multi_intent",
    persona="tester",
    message="Why did my score drop? Where is my secured card?",
    intents=2,
    skills=["score-changes", "secured-card"],
    expected_facts=["Names the late payment as a likely cause", "Gives the ship date 2026-10-06"],
)


def _grades(*statuses: str) -> dict:
    return {
        "facts": [{"id": f"F{i}", "status": s, "note": f"note {i}"} for i, s in enumerate(statuses, start=1)],
        "reason": "summary",
    }


def test_all_present_passes(persona: Persona) -> None:
    llm = FakeLLM([_grades("PRESENT", "PRESENT")])
    result = Judge(llm).grade(CASE, persona, "the reply")

    assert result.passed
    assert [f.fact for f in result.facts] == CASE.expected_facts
    assert [f.note for f in result.facts] == ["note 1", "note 2"]
    assert result.reason == "summary"
    assert result.usage == ROUTER_USAGE

    call = llm.json_calls[0]
    assert call["model"] == config.JUDGE_MODEL
    assert call["effort"] == JUDGE_EFFORT == "medium"
    assert call["max_tokens"] == JUDGE_MAX_TOKENS == 4096
    assert call["schema"] == judge_schema(CASE)
    prompt = call["messages"][0]["content"]
    assert "This is the signed-in member's profile" in prompt  # render_profile output
    assert '"current":600' in prompt
    assert "F1. Names the late payment as a likely cause" in prompt
    assert "<reply>\nthe reply\n</reply>" in prompt
    for rule in ("Paraphrase", "Length is not evidence", "unconditional"):
        assert rule in call["system"]


@pytest.mark.parametrize("statuses", [("PRESENT", "ABSENT"), ("CONTRADICTED", "PRESENT")])
def test_any_non_present_fact_fails(persona: Persona, statuses: tuple[str, str]) -> None:
    # The model's own opinion of the verdict is never used: passed is computed in code.
    result = Judge(FakeLLM([_grades(*statuses)])).grade(CASE, persona, "reply")
    assert not result.passed
    assert [f.status for f in result.facts] == list(statuses)


def test_grades_are_matched_by_id_not_order(persona: Persona) -> None:
    data = {
        "facts": [
            {"id": "F2", "status": "ABSENT", "note": "no date"},
            {"id": "F1", "status": "PRESENT", "note": "late payment named"},
        ],
        "reason": "r",
    }
    result = Judge(FakeLLM([data])).grade(CASE, persona, "reply")
    assert [(f.fact, f.status) for f in result.facts] == [
        ("Names the late payment as a likely cause", "PRESENT"),
        ("Gives the ship date 2026-10-06", "ABSENT"),
    ]


def test_ungraded_fact_is_an_error(persona: Persona) -> None:
    data = {"facts": [{"id": "F1", "status": "PRESENT", "note": ""}], "reason": "r"}
    with pytest.raises(LLMError, match="F2") as excinfo:
        Judge(FakeLLM([data])).grade(CASE, persona, "reply")
    assert excinfo.value.usage == ROUTER_USAGE


def test_custom_model(persona: Persona) -> None:
    llm = FakeLLM([_grades("PRESENT", "PRESENT")])
    Judge(llm, model="judge-x").grade(CASE, persona, "reply")
    assert llm.json_calls[0]["model"] == "judge-x"
