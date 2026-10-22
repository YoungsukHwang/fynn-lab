"""Wire-format checks for AnthropicLLM against a local fake API server (no real key needed)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import anthropic
import pytest

from fynn.llm import FALLBACK_BETA, AnthropicLLM, LLMError
from fynn.prompts import PromptBlock


class FakeAPI:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.responses: list[dict[str, Any]] = []
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 (http.server naming)
                length = int(self.headers["content-length"])
                api.requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": json.loads(self.rfile.read(length))}
                )
                payload = json.dumps(api.responses.pop(0)).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


def _message(text: str, stop_reason: str = "end_turn", model: str = "claude-opus-5-5") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "thinking", "thinking": "", "signature": "sig"}, {"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }


@pytest.fixture
def fake_api():
    api = FakeAPI()
    yield api
    api.server.shutdown()


@pytest.fixture
def llm(fake_api: FakeAPI) -> AnthropicLLM:
    return AnthropicLLM(anthropic.Anthropic(api_key="test-key", base_url=fake_api.url, max_retries=0))


def test_generate_sends_effort_fallback_and_cache_breakpoints(fake_api: FakeAPI, llm: AnthropicLLM) -> None:
    response = _message("hello there")
    response["usage"].update({"cache_read_input_tokens": 3000, "cache_creation_input_tokens": 0})
    fake_api.responses.append(response)
    system = [PromptBlock("guidance", cache=True), PromptBlock("profile", cache=True), PromptBlock("topics")]
    result = llm.generate(
        model="claude-opus-5-5", system=system, messages=[{"role": "user", "content": "hi"}], effort="low", max_tokens=100
    )
    assert result.text == "hello there"  # thinking block ignored
    assert result.usage.input_tokens == 12
    assert result.usage.cache_read_input_tokens == 3000

    request = fake_api.requests[0]
    assert FALLBACK_BETA in request["headers"]["anthropic-beta"]
    assert request["body"]["fallbacks"] == "default"
    assert request["body"]["output_config"] == {"effort": "low"}
    assert request["body"]["system"] == [
        {"type": "text", "text": "guidance", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "profile", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "topics"},
    ]


def test_generate_json_sends_schema_without_fallback(fake_api: FakeAPI, llm: AnthropicLLM) -> None:
    fake_api.responses.append(_message('{"reason": "r", "skills": ["utilization"]}', model="claude-haiku-5-5"))
    schema = {"type": "object", "properties": {"skills": {"type": "array"}}, "required": ["skills"]}
    data, usage = llm.generate_json(
        model="claude-haiku-5-5",
        system="router",
        messages=[{"role": "user", "content": "q"}],
        schema=schema,
        effort="low",
        max_tokens=50,
    )
    assert data["skills"] == ["utilization"]
    assert usage.output_tokens == 3

    body = fake_api.requests[0]["body"]
    assert "fallbacks" not in body
    assert body["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": schema}}


def test_generate_json_raises_on_refusal(fake_api: FakeAPI, llm: AnthropicLLM) -> None:
    fake_api.responses.append(_message("", stop_reason="refusal", model="claude-haiku-5-5"))
    with pytest.raises(LLMError):
        llm.generate_json(
            model="claude-haiku-5-5", system="s", messages=[{"role": "user", "content": "q"}], schema={}, effort="low", max_tokens=50
        )


@pytest.mark.parametrize(
    ("content", "stop_reason"),
    [
        ([{"type": "text", "text": "not json"}], "end_turn"),
        ([{"type": "text", "text": "[\"a\"]"}], "end_turn"),
        ([{"type": "text", "text": "null"}], "end_turn"),
        ([], "end_turn"),
        ([{"type": "text", "text": "{\"skills\": ["}], "max_tokens"),
    ],
)
def test_generate_json_wraps_unusable_output(fake_api: FakeAPI, llm: AnthropicLLM, content, stop_reason) -> None:
    response = _message("", stop_reason=stop_reason, model="claude-haiku-5-5")
    response["content"] = content
    fake_api.responses.append(response)
    with pytest.raises(LLMError) as raised:
        llm.generate_json(
            model="claude-haiku-5-5", system="s", messages=[{"role": "user", "content": "q"}], schema={}, effort="low", max_tokens=50
        )
    # The billed tokens travel with the error so callers can still count them.
    assert raised.value.usage.input_tokens == 12


def test_has_credentials_without_any_source(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fynn.llm import has_credentials

    # The realistic no-key case: no env credentials and no profile on disk, so the SDK chain returns None.
    monkeypatch.delenv("ANTHROPIC_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert has_credentials() is False


@pytest.mark.parametrize(
    ("env", "chain", "expected"),
    [
        ({"ANTHROPIC_API_KEY": "k"}, None, True),  # API key short-circuits the chain
        ({}, object(), True),  # token, profile or WIF resolved by the SDK
        ({}, None, False),  # nothing resolved
        ({}, RuntimeError("broken profile"), False),  # explicit profile that fails to load
    ],
)
def test_has_credentials_branches(monkeypatch: pytest.MonkeyPatch, env, chain, expected) -> None:
    import fynn.llm as llm_module

    for name, value in env.items():
        monkeypatch.setenv(name, value)

    def fake_chain():
        if isinstance(chain, Exception):
            raise chain
        return chain

    monkeypatch.setattr(llm_module, "default_credentials", fake_chain)
    assert llm_module.has_credentials() is expected


def test_router_and_agent_calls_use_their_own_clients() -> None:
    from types import SimpleNamespace

    class TextCall(Exception):
        pass

    class JsonCall(Exception):
        pass

    def raise_text(**_):
        raise TextCall

    def raise_json(**_):
        raise JsonCall

    llm = AnthropicLLM(anthropic.Anthropic(api_key="test-key"), json_timeout=20, text_timeout=90)
    assert llm._json_client.timeout == 20
    assert llm._text_client.timeout == 90
    # Route each call to a recorder to prove which (timeout-specific) client it uses.
    llm._text_client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=raise_text)))
    llm._json_client = SimpleNamespace(messages=SimpleNamespace(create=raise_json))
    with pytest.raises(TextCall):
        llm.generate(model="m", system=[], messages=[], effort="low", max_tokens=1)
    with pytest.raises(JsonCall):
        llm.generate_json(model="m", system="s", messages=[], schema={}, effort="low", max_tokens=1)
