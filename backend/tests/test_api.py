from collections.abc import Callable, Iterator
from pathlib import Path

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from api.limits import ChatLimits, Refusal, client_address
from api.main import MAX_ASSISTANT_MESSAGE_CHARS, MAX_USER_MESSAGE_CHARS, Runtime, app, get_runtime
from fynn import config
from fynn.bots import build_bots
from fynn.llm import LLMError
from fynn.personas import load_personas
from fynn.skills import SkillLibrary
from tests.conftest import FakeLLM

ORIGIN = {"Origin": "http://localhost:3000"}
TWO_SKILLS = {"reason": "two questions", "skills": ["score-changes", "secured-card"]}


@pytest.fixture
def make_client(mini_library: SkillLibrary, persona_dir: Path) -> Iterator[Callable[[FakeLLM], TestClient]]:
    def make(llm: FakeLLM) -> TestClient:
        runtime = Runtime(library=mini_library, personas=load_personas(persona_dir), bots=build_bots(llm, mini_library))
        app.dependency_overrides[get_runtime] = lambda: runtime
        return TestClient(app)

    yield make
    app.dependency_overrides.clear()


@pytest.fixture
def client(make_client: Callable[[FakeLLM], TestClient]) -> TestClient:
    return make_client(FakeLLM([TWO_SKILLS]))


def _chat(client: TestClient, messages: list[dict], **extra) -> httpx2.Response:
    body = {"bot": "after", "persona_id": "tester", "messages": messages}
    body.update(extra)
    return client.post("/chat", json=body, headers=ORIGIN)


USER = [{"role": "user", "content": "two questions"}]


def test_chat_returns_reply_routing_and_full_usage(client: TestClient) -> None:
    response = _chat(client, USER)
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "fake reply"
    assert body["routing"] == {
        "strategy": "skills",
        "selected": ["score-changes", "secured-card"],
        "carried": [],
        "reason": "two questions",
        "error": None,
    }
    assert body["usage"] == {
        "input_tokens": 110,
        "output_tokens": 55,
        "cache_read_input_tokens": 3001,
        "cache_creation_input_tokens": 42,
    }
    assert body["stop_reason"] == "end_turn"


def test_chat_carries_skills_from_previous_turn(make_client) -> None:
    client = make_client(FakeLLM([{"reason": "follow-up", "skills": ["utilization"]}]))
    history = [*USER, {"role": "assistant", "content": "answer"}, {"role": "user", "content": "follow-up"}]
    response = _chat(client, history, carry_skills=["score-changes", "secured-card"])
    assert response.status_code == 200
    assert response.json()["routing"]["carried"] == ["score-changes", "secured-card"]


def test_chat_drops_unknown_carry_skills(make_client) -> None:
    client = make_client(FakeLLM([{"reason": "x", "skills": []}]))
    response = _chat(client, USER, carry_skills=["astrology", "collections"])
    assert response.status_code == 200
    assert response.json()["routing"]["carried"] == ["collections"]


def test_before_accepts_and_ignores_its_own_routing_as_carry(make_client) -> None:
    client = make_client(FakeLLM([{"reason": "score", "agent": "score-and-reports"}]))
    history = [*USER, {"role": "assistant", "content": "answer"}, {"role": "user", "content": "follow-up"}]
    response = _chat(client, history, bot="before", carry_skills=["score-and-reports"])
    assert response.status_code == 200
    assert response.json()["routing"]["carried"] == []


def test_not_found_and_validation_errors_use_the_error_format(client: TestClient) -> None:
    missing = client.post("/chat", json={"bot": "after", "persona_id": "nobody", "messages": USER}, headers=ORIGIN)
    assert missing.status_code == 404
    assert missing.json() == {"detail": "unknown persona 'nobody'", "retryable": False}
    assert missing.headers["access-control-allow-origin"] == ORIGIN["Origin"]

    invalid = _chat(client, [{"role": "user", "content": "  "}])
    assert invalid.status_code == 422
    body = invalid.json()
    assert isinstance(body["detail"], str) and "blank" in body["detail"]
    assert body["retryable"] is False


def test_long_assistant_turn_does_not_break_the_conversation(client: TestClient) -> None:
    # The longest reply the agent could produce must pass validation when the client sends it back.
    long_answer = "w" * (config.AGENT_MAX_TOKENS * 4)
    history = [*USER, {"role": "assistant", "content": long_answer}, {"role": "user", "content": "thanks, and?"}]
    assert MAX_ASSISTANT_MESSAGE_CHARS >= len(long_answer) > MAX_USER_MESSAGE_CHARS
    assert _chat(client, history).status_code == 200


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "user", "content": "   \n"}],
        [{"role": "assistant", "content": "Hi, I'm Coach"}, {"role": "user", "content": "hi"}],
        [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}],
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
        [{"role": "user", "content": "x" * (MAX_USER_MESSAGE_CHARS + 1)}],
        [*USER, {"role": "assistant", "content": "y" * (MAX_ASSISTANT_MESSAGE_CHARS + 1)}, *USER],
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}] * 10 + USER,
    ],
)
def test_chat_validates_messages(client: TestClient, messages) -> None:
    assert _chat(client, messages).status_code == 422


def test_router_failure_still_answers(make_client) -> None:
    client = make_client(FakeLLM([LLMError("structured call stopped with refusal")]))
    response = _chat(client, USER)
    assert response.status_code == 200
    assert response.json()["routing"]["error"] == "structured call stopped with refusal"


def _status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request, headers={"retry-after": "7"})
    return cls("boom", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "status", "retryable"),
    [
        (LLMError("bad output"), 502, True),
        (_status_error(anthropic.RateLimitError, 429), 503, True),
        (_status_error(anthropic.OverloadedError, 529), 503, True),
        (_status_error(anthropic.BadRequestError, 400), 502, False),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")), 504, True),
        (anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com")), 504, True),
        (anthropic.AnthropicError("credentials could not be resolved"), 502, False),
        (TypeError("Could not resolve authentication method"), 500, False),
    ],
)
def test_model_errors_return_json_with_cors(make_client, error: Exception, status: int, retryable: bool) -> None:
    llm = FakeLLM([TWO_SKILLS])
    llm.text_error = error
    response = _chat(make_client(llm), USER)

    assert response.status_code == status
    assert response.json()["retryable"] is retryable
    assert response.headers["access-control-allow-origin"] == ORIGIN["Origin"]
    if isinstance(error, anthropic.RateLimitError):
        assert response.headers["retry-after"] == "7"
        assert "retry-after" in response.headers["access-control-expose-headers"].lower()


def test_router_path_errors_are_handled_too(make_client) -> None:
    overloaded = _status_error(anthropic.OverloadedError, 529)
    response = _chat(make_client(FakeLLM([overloaded])), USER)
    assert response.status_code == 503
    assert response.headers["access-control-allow-origin"] == ORIGIN["Origin"]


def test_architecture_describes_both_bots(client: TestClient) -> None:
    body = client.get("/architecture").json()
    assert body["always_on"] == ["guardrails", "tone"]
    assert body["max_new_skills_per_turn"] == 4
    assert body["max_carried_skills"] == 2
    assert body["limits"] == {"max_messages": 20, "max_user_message_chars": 2000}
    assert [d["id"] for d in body["domains"]] == [
        "score-and-reports",
        "credit-products",
        "rent-and-bills",
        "debt-and-collections",
    ]
    assert {t["name"] for t in body["topics"]} == {"collections", "rent-reporting", "score-changes", "secured-card", "utilization"}


def test_personas_endpoint(client: TestClient) -> None:
    assert [p["id"] for p in client.get("/personas").json()] == ["tester"]


def test_chat_without_credentials_explains_how_to_fix(mini_library: SkillLibrary, persona_dir: Path) -> None:
    llm = FakeLLM([TWO_SKILLS])
    runtime = Runtime(
        library=mini_library,
        personas=load_personas(persona_dir),
        bots=build_bots(llm, mini_library),
        credentials_ok=False,
    )
    app.dependency_overrides[get_runtime] = lambda: runtime
    try:
        response = _chat(TestClient(app), USER)
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]
    # Retryable: after adding the key and restarting the API, the same message goes through.
    assert response.json()["retryable"] is True
    assert llm.json_calls == []  # nothing was sent to the model


def test_timeouts_and_unreachable_api_have_different_messages(make_client) -> None:
    request = httpx2.Request("POST", "https://api.anthropic.com")
    details = []
    for error in (anthropic.APITimeoutError(request=request), anthropic.APIConnectionError(request=request)):
        llm = FakeLLM([TWO_SKILLS])
        llm.text_error = error
        details.append(_chat(make_client(llm), USER).json()["detail"])
    assert details == ["the model took too long to answer", "could not reach the model API"]


def test_runtime_without_credentials_still_serves_static_data() -> None:
    # conftest leaves no usable credentials (and an explicit, missing profile dir that the SDK
    # would fail on). The runtime must still build, so /personas and /architecture keep working.
    get_runtime.cache_clear()
    try:
        runtime = get_runtime()
        assert runtime.credentials_ok is False
        assert runtime.personas and runtime.library.topics
    finally:
        get_runtime.cache_clear()


# ---- Public demo limits -------------------------------------------------------------------------


def _limited_client(mini_library: SkillLibrary, persona_dir: Path, limits: ChatLimits, routes: int) -> TestClient:
    runtime = Runtime(
        library=mini_library,
        personas=load_personas(persona_dir),
        bots=build_bots(FakeLLM([TWO_SKILLS] * routes), mini_library),
        limits=limits,
    )
    app.dependency_overrides[get_runtime] = lambda: runtime
    return TestClient(app)


def test_chat_refuses_a_visitor_over_the_hourly_limit(mini_library: SkillLibrary, persona_dir: Path) -> None:
    try:
        client = _limited_client(mini_library, persona_dir, ChatLimits(per_visitor_per_hour=2), routes=2)
        assert [_chat(client, USER).status_code for _ in range(2)] == [200, 200]
        refused = _chat(client, USER)
        assert refused.status_code == 429
        assert refused.json() == {"detail": "You have reached this demo's hourly limit. Try again later.", "retryable": False}
        assert 0 < int(refused.headers["Retry-After"]) <= 3600
        assert refused.headers["access-control-allow-origin"] == ORIGIN["Origin"]  # the site can read it
    finally:
        app.dependency_overrides.clear()


def test_chat_refuses_everyone_over_the_daily_cap(mini_library: SkillLibrary, persona_dir: Path) -> None:
    try:
        client = _limited_client(mini_library, persona_dir, ChatLimits(per_day=1), routes=1)
        assert _chat(client, USER).status_code == 200
        refused = _chat(client, USER)
        assert refused.status_code == 429 and "limit for today" in refused.json()["detail"]
        # A request the API rejects before answering does not use up the cap.
        assert _chat(client, USER, persona_id="nobody").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_limits_slide_by_the_hour_and_reset_each_utc_day() -> None:
    now = [86400 * 100 + 10.0]
    limits = ChatLimits(per_visitor_per_hour=2, per_day=3, clock=lambda: now[0])
    assert limits.take("a") is None and limits.take("a") is None
    refused = limits.take("a")
    assert refused is not None and refused.scope == "hour" and refused.retry_after == 3600
    assert limits.take("b") is None  # another visitor still has room
    day = limits.take("c")
    assert day is not None and day.scope == "day" and day.retry_after == 86400 - 10
    now[0] += 3600  # a's first requests leave the window, but the day's cap still holds
    assert limits.take("a") == Refusal("day", 86400 - 10 - 3600)
    now[0] = 86400 * 101  # midnight UTC
    assert limits.take("a") is None


def test_client_address_trusts_x_forwarded_for_only_when_told() -> None:
    assert client_address("10.0.0.1", "203.0.113.5, 10.0.0.1", trust_forwarded=False) == "10.0.0.1"
    assert client_address("10.0.0.1", "203.0.113.5, 10.0.0.1", trust_forwarded=True) == "203.0.113.5"
    assert client_address(None, None, trust_forwarded=True) == "unknown"
