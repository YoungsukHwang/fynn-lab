"""Shared fixtures: a scripted fake LLM and small on-disk skill/persona sets."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# No test may reach the real API. This runs before any fynn import, so backend/.env is never
# loaded, every credential source the SDK checks is removed, and any request that slips
# through goes to an unroutable local port instead of api.anthropic.com.
os.environ["FYNN_ENV_FILE"] = os.devnull
for _name in [n for n in os.environ if n.startswith("ANTHROPIC_")]:
    del os.environ[_name]
os.environ["ANTHROPIC_CONFIG_DIR"] = str(Path(tempfile.mkdtemp()) / "no-profile")
os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"

import pytest  # noqa: E402

from fynn.llm import Generation, Usage  # noqa: E402
from fynn.personas import Persona  # noqa: E402
from fynn.skills import SkillLibrary  # noqa: E402


ROUTER_USAGE = Usage(input_tokens=10, output_tokens=5, cache_read_input_tokens=1, cache_creation_input_tokens=2)
AGENT_USAGE = Usage(input_tokens=100, output_tokens=50, cache_read_input_tokens=3000, cache_creation_input_tokens=40)


class FakeLLM:
    """Records every call. Structured calls return queued JSON (or raise a queued exception);
    text calls return a fixed reply, or raise `text_error` when set."""

    def __init__(self, json_responses: list[dict[str, Any] | Exception] | None = None, reply: str = "fake reply"):
        self.json_responses = list(json_responses or [])
        self.reply = reply
        self.stop_reason = "end_turn"
        self.text_error: Exception | None = None
        self.json_calls: list[dict[str, Any]] = []
        self.text_calls: list[dict[str, Any]] = []

    def generate_json(self, **kwargs: Any) -> tuple[dict[str, Any], Usage]:
        self.json_calls.append(kwargs)
        response = self.json_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response, ROUTER_USAGE

    def generate(self, **kwargs: Any) -> Generation:
        # Snapshot the history: callers keep appending to the same list after the call.
        self.text_calls.append({**kwargs, "messages": list(kwargs["messages"])})
        if self.text_error is not None:
            raise self.text_error
        return Generation(text=self.reply, model=kwargs["model"], stop_reason=self.stop_reason, usage=AGENT_USAGE)


def write_skill(directory: Path, name: str, skill_type: str, domain: str | None, body: str = "") -> Path:
    domain_line = f"domain: {domain}\n" if domain else ""
    text = (
        f"---\nname: {name}\ndescription: >-\n  Covers {name}. Use when the member asks about {name}.\n"
        f"type: {skill_type}\n{domain_line}---\n## Facts\n- {body or name + ' fact'}\n"
    )
    path = directory / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


# A minimal library: one always-on skill and one topic skill per domain, plus a second score skill.
MINI_SKILLS = [
    ("tone", "always_on", None),
    ("guardrails", "always_on", None),
    ("score-changes", "topic", "score-and-reports"),
    ("utilization", "topic", "score-and-reports"),
    ("secured-card", "topic", "credit-products"),
    ("rent-reporting", "topic", "rent-and-bills"),
    ("collections", "topic", "debt-and-collections"),
]


@pytest.fixture
def mini_library(tmp_path: Path) -> SkillLibrary:
    for name, skill_type, domain in MINI_SKILLS:
        write_skill(tmp_path, name, skill_type, domain)
    return SkillLibrary.load(tmp_path)


@pytest.fixture
def persona() -> Persona:
    return Persona.model_validate(
        {
            "id": "tester",
            "name": "Test",
            "summary": "A test member.",
            "as_of": "2026-10-15",
            "credit": {"score": {"model": "VantageScore 3.0", "current": 600}},
            "products": {"secured_card": {"status": "shipped", "shipped_on": "2026-10-06"}},
            "recent_events": ["2026-10-06: secured card shipped"],
        }
    )


@pytest.fixture
def persona_dir(tmp_path: Path, persona: Persona) -> Path:
    directory = tmp_path / "personas"
    directory.mkdir()
    (directory / "tester.json").write_text(json.dumps(persona.model_dump(mode="json")), encoding="utf-8")
    return directory
