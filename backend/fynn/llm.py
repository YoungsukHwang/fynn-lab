"""Thin wrapper around the Anthropic SDK.

Bots and evals depend on the `LLM` protocol, so tests can swap in a fake.
Conversation history is always sent as plain text turns: earlier thinking
blocks are never replayed, which keeps us clear of the preserved-thinking
history check even though the system prompt changes from turn to turn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic

from fynn.prompts import PromptBlock

# Server-side refusal fallback ("default" picks the recommended model per refusal category).
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0  # uncached input only
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
        )


class LLMError(RuntimeError):
    """The model returned something we cannot use. `usage` keeps the tokens the failed call billed."""

    def __init__(self, message: str, usage: Usage | None = None):
        super().__init__(message)
        self.usage = usage or Usage()


@dataclass(frozen=True)
class Generation:
    text: str
    model: str
    stop_reason: str | None
    usage: Usage


class LLM(Protocol):
    def generate(
        self, *, model: str, system: list[PromptBlock], messages: list[dict[str, str]], effort: str, max_tokens: int
    ) -> Generation: ...

    def generate_json(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        effort: str,
        max_tokens: int,
    ) -> tuple[dict[str, Any], Usage]: ...


def _usage(response: Any) -> Usage:
    usage = response.usage
    return Usage(
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_read_input_tokens or 0,
        usage.cache_creation_input_tokens or 0,
    )


def system_param(blocks: list[PromptBlock]) -> list[dict[str, Any]]:
    """System text blocks, with a 5-minute cache breakpoint after each block marked `cache`."""
    param: list[dict[str, Any]] = []
    for block in blocks:
        item: dict[str, Any] = {"type": "text", "text": block.text}
        if block.cache:
            item["cache_control"] = {"type": "ephemeral"}
        param.append(item)
    return param


class AnthropicLLM:
    def __init__(self, client: anthropic.Anthropic | None = None):
        self._client = client or anthropic.Anthropic()

    def generate(
        self, *, model: str, system: list[PromptBlock], messages: list[dict[str, str]], effort: str, max_tokens: int
    ) -> Generation:
        response = self._client.beta.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_param(system),
            messages=messages,
            output_config={"effort": effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return Generation(text=text, model=response.model, stop_reason=response.stop_reason, usage=_usage(response))

    def generate_json(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        effort: str,
        max_tokens: int,
    ) -> tuple[dict[str, Any], Usage]:
        # No `fallbacks` here: the router runs on Haiku, which has no server-side fallback.
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        )
        usage = _usage(response)
        if response.stop_reason in ("refusal", "max_tokens"):
            raise LLMError(f"structured call stopped with {response.stop_reason}", usage)
        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            raise LLMError("structured call returned no text block", usage)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"structured call returned invalid JSON: {exc}", usage) from exc
        if not isinstance(data, dict):
            raise LLMError("structured call returned JSON that is not an object", usage)
        return data, usage
