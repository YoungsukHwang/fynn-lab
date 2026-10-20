"""Terminal chat: carry-over between turns and recovery from errors."""

from collections.abc import Iterator

import anthropic
import httpx2
import pytest

from fynn import chat
from fynn.skills import SkillLibrary
from tests.conftest import FakeLLM


def _feed(monkeypatch: pytest.MonkeyPatch, lines: list[str]) -> None:
    answers: Iterator[str] = iter(lines)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))


def test_chat_carries_skills_and_recovers_from_errors(
    mini_library: SkillLibrary, persona_dir, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fynn.personas import load_personas

    monkeypatch.setattr(chat, "load_personas", lambda: load_personas(persona_dir))
    overloaded = anthropic.OverloadedError(
        "overloaded",
        response=httpx2.Response(529, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")),
        body=None,
    )
    llm = FakeLLM(
        [
            {"reason": "two questions", "skills": ["score-changes", "secured-card"]},
            {"reason": "follow-up", "skills": ["utilization"]},
            {"reason": "retry", "skills": ["utilization"]},
        ]
    )
    calls = {"n": 0}
    original = llm.generate

    def generate(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # the second answer fails once
            raise overloaded
        return original(**kwargs)

    llm.generate = generate  # type: ignore[method-assign]
    _feed(monkeypatch, ["two questions", "which card first?", "which card first?", "quit"])
    chat.run("tester", ["after"], llm, mini_library)

    out = capsys.readouterr().out
    assert "error, message not answered" in out
    # Turn 2 failed and was dropped from history, so turn 3 sends a valid alternating history ...
    last_messages = llm.text_calls[-1]["messages"]
    assert [m["role"] for m in last_messages] == ["user", "assistant", "user"]
    # ... and still carries the skills picked on the last answered turn.
    assert "carried: score-changes, secured-card" in out


def test_unknown_persona_is_rejected_by_argparse(monkeypatch: pytest.MonkeyPatch, persona_dir) -> None:
    from fynn.personas import load_personas

    monkeypatch.setattr(chat, "load_personas", lambda: load_personas(persona_dir))
    monkeypatch.setattr("sys.argv", ["fynn.chat", "--persona", "high_util"])
    with pytest.raises(SystemExit):
        chat.main()


def test_missing_credentials_stop_before_chatting(monkeypatch: pytest.MonkeyPatch, persona_dir) -> None:
    from fynn.personas import load_personas

    monkeypatch.setattr(chat, "load_personas", lambda: load_personas(persona_dir))
    monkeypatch.setattr("sys.argv", ["fynn.chat", "--persona", "tester"])
    with pytest.raises(SystemExit):
        chat.main()
