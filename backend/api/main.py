"""FastAPI app: chat with either bot, list personas, describe the architecture.

    uvicorn api.main:app --reload --port 8000     # run from backend/; see README for reload flags

The API is stateless: the client sends the whole conversation each time, and for
the After bot also the skills it picked on the previous turn (`carry_skills`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated, Any, Literal

import anthropic
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from api.limits import ChatLimits, client_address
from fynn import config
from fynn.bots import Bot, BotName, build_bots
from fynn.llm import AnthropicLLM, LLMError, has_credentials
from fynn.personas import Persona, load_personas
from fynn.skills import SkillLibrary

logger = logging.getLogger("fynn.api")

# Cheap guards for a public demo; the request limits are in api/limits.py.
MAX_MESSAGES = 20
MAX_USER_MESSAGE_CHARS = 2000
# Assistant turns are text this server generated and the client sends back, so their cap
# must cover the longest reply the agent can produce (about 6 characters per token at most).
MAX_ASSISTANT_MESSAGE_CHARS = config.AGENT_MAX_TOKENS * 6
# Input-size guard only; the After bot applies the real carry limit (MAX_CARRIED_SKILLS).
MAX_CARRY_SKILLS_INPUT = 10


@dataclass
class Runtime:
    library: SkillLibrary
    personas: dict[str, Persona]
    bots: dict[BotName, Bot]
    # Checked once at startup so a missing key gives a clear error instead of a generic 500.
    credentials_ok: bool = True
    limits: ChatLimits = field(default_factory=ChatLimits)


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    library = SkillLibrary.load()
    credentials_ok = has_credentials()
    try:
        # Without credentials, a placeholder key keeps the SDK from resolving (and possibly
        # failing on) a profile at startup; /chat answers 503 before this client is ever used.
        client = anthropic.Anthropic(
            max_retries=config.API_MAX_RETRIES, **({} if credentials_ok else {"api_key": "not-configured"})
        )
    except anthropic.AnthropicError:
        logger.exception("could not build the Anthropic client; chat is disabled")
        credentials_ok = False
        client = anthropic.Anthropic(max_retries=config.API_MAX_RETRIES, api_key="not-configured")
    llm = AnthropicLLM(
        client,
        json_timeout=config.API_ROUTER_TIMEOUT_SECONDS,
        text_timeout=config.API_AGENT_TIMEOUT_SECONDS,
    )
    return Runtime(
        library=library,
        personas=load_personas(),
        bots=build_bots(llm, library),
        credentials_ok=credentials_ok,
        limits=ChatLimits(per_visitor_per_hour=config.CHAT_LIMIT_PER_VISITOR_PER_HOUR, per_day=config.CHAT_LIMIT_PER_DAY),
    )


RuntimeDep = Annotated[Runtime, Depends(get_runtime)]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

    @model_validator(mode="after")
    def content_fits_role(self) -> ChatMessage:
        if not self.content.strip():
            raise ValueError("message content must not be blank")
        limit = MAX_USER_MESSAGE_CHARS if self.role == "user" else MAX_ASSISTANT_MESSAGE_CHARS
        if len(self.content) > limit:
            raise ValueError(f"{self.role} message is longer than {limit} characters")
        return self


class ChatRequest(BaseModel):
    bot: BotName
    persona_id: str = Field(max_length=64)
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    # After only: the previous reply's routing.selected. Ignored for Before; unknown names are dropped.
    carry_skills: list[str] = Field(default_factory=list, max_length=MAX_CARRY_SKILLS_INPUT)

    @field_validator("messages")
    @classmethod
    def alternating_from_user(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        # The Messages API needs user/assistant turns that alternate, starting and ending with the user.
        for index, message in enumerate(messages):
            expected = "user" if index % 2 == 0 else "assistant"
            if message.role != expected:
                raise ValueError("messages must alternate user/assistant, starting and ending with user")
        if messages[-1].role != "user":
            raise ValueError("the last message must come from the user")
        return messages


class RoutingOut(BaseModel):
    strategy: Literal["single_agent", "skills"]
    selected: list[str]
    carried: list[str]
    reason: str
    error: str | None


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class ChatResponse(BaseModel):
    bot: BotName
    reply: str
    routing: RoutingOut
    model: str
    stop_reason: str | None
    usage: UsageOut


# Every error body is {"detail": str, "retryable": bool}. Errors must be produced inside the
# CORS middleware so the browser can read them: the exception handlers below run there, and
# the catch-all middleware is added before CORSMiddleware, which makes CORS the outer layer.
def _error(status: int, detail: str, retryable: bool, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"detail": detail, "retryable": retryable}, status_code=status, headers=headers)


async def _catch_unhandled(request: Request, call_next: RequestResponseEndpoint) -> Response:
    try:
        return await call_next(request)
    except Exception:  # noqa: BLE001 (last resort; details stay in the server log)
        logger.exception("unhandled error on %s", request.url.path)
        return _error(500, "internal server error", retryable=False)


app = FastAPI(title="Fynn Lab API", version="0.1.0")
app.add_middleware(BaseHTTPMiddleware, dispatch=_catch_unhandled)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error(exc.status_code, str(exc.detail), retryable=False, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    problems = "; ".join(f"{'.'.join(str(part) for part in e['loc'])}: {e['msg']}" for e in exc.errors())
    return _error(422, problems, retryable=False)


@app.exception_handler(LLMError)
async def llm_error(_: Request, exc: LLMError) -> JSONResponse:
    return _error(502, f"model output could not be used: {exc}", retryable=True)


@app.exception_handler(anthropic.RateLimitError)
async def rate_limited(_: Request, exc: anthropic.RateLimitError) -> JSONResponse:
    retry_after = exc.response.headers.get("retry-after")
    return _error(503, "the model API is rate limiting requests", True, {"Retry-After": retry_after} if retry_after else None)


@app.exception_handler(anthropic.APIStatusError)
async def api_status_error(_: Request, exc: anthropic.APIStatusError) -> JSONResponse:
    if exc.status_code >= 500:
        return _error(503, "the model API is overloaded or unavailable", retryable=True)
    return _error(502, f"the model API rejected the request ({exc.status_code})", retryable=False)


@app.exception_handler(anthropic.APITimeoutError)
async def api_timeout(_: Request, exc: anthropic.APITimeoutError) -> JSONResponse:
    # APITimeoutError subclasses APIConnectionError; the more specific handler wins.
    return _error(504, "the model took too long to answer", retryable=True)


@app.exception_handler(anthropic.APIConnectionError)
async def api_connection_error(_: Request, exc: anthropic.APIConnectionError) -> JSONResponse:
    return _error(504, "could not reach the model API", retryable=True)


class MissingCredentials(Exception):
    pass


@app.exception_handler(MissingCredentials)
async def missing_credentials(_: Request, exc: MissingCredentials) -> JSONResponse:
    # Retryable: once the key is added and the API restarted, the same message will go through.
    return _error(
        503,
        "No usable Anthropic credentials: add ANTHROPIC_API_KEY to backend/.env (or fix your ant auth profile) "
        "and restart the API.",
        True,
    )


@app.exception_handler(anthropic.AnthropicError)
async def anthropic_error(_: Request, exc: anthropic.AnthropicError) -> JSONResponse:
    # Remaining SDK errors (e.g. credentials, response validation) are not fixed by retrying.
    logger.error("model API client error: %r", exc)
    return _error(502, f"model API client error: {type(exc).__name__}", retryable=False)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/personas")
def personas(runtime: RuntimeDep) -> list[dict[str, Any]]:
    return [p.model_dump(mode="json") for p in runtime.personas.values()]


@app.get("/architecture")
def architecture(runtime: RuntimeDep) -> dict[str, Any]:
    return describe_architecture(runtime.library)


def describe_architecture(library: SkillLibrary) -> dict[str, Any]:
    """Domains, skills, models, skill budgets and request limits, for the site's diagrams. Also written
    into the recorded demo (evals.demo_snapshot), so the static site renders the same diagrams."""
    return {
        "models": {"router": config.ROUTER_MODEL, "agent": config.AGENT_MODEL},
        "max_new_skills_per_turn": config.MAX_NEW_SKILLS_PER_TURN,
        "max_carried_skills": config.MAX_CARRIED_SKILLS,
        # Request limits, so the web client doesn't have to hard-code them.
        "limits": {"max_messages": MAX_MESSAGES, "max_user_message_chars": MAX_USER_MESSAGE_CHARS},
        "always_on": [s.name for s in library.always_on],
        "domains": [
            {"id": domain, "title": title, "skills": [s.name for s in library.domain_skills(domain)]}
            for domain, title in config.DOMAINS.items()
        ],
        "topics": [{"name": s.name, "domain": s.domain, "description": s.description} for s in library.topics],
    }


@app.post("/chat")
def chat(request: ChatRequest, http: Request, runtime: RuntimeDep) -> ChatResponse:
    if not runtime.credentials_ok:
        raise MissingCredentials()
    persona = runtime.personas.get(request.persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail=f"unknown persona {request.persona_id!r}")
    visitor = client_address(http.client.host if http.client else None, http.headers.get("x-forwarded-for"), config.TRUST_FORWARDED)
    refused = runtime.limits.take(visitor)
    if refused is not None:
        detail = (
            "This demo has reached its limit for today. It resets at midnight UTC."
            if refused.scope == "day"
            else "You have reached this demo's hourly limit. Try again later."
        )
        raise HTTPException(status_code=429, detail=detail, headers={"Retry-After": str(refused.retry_after)})

    messages = [m.model_dump() for m in request.messages]
    reply = runtime.bots[request.bot].reply(persona, messages, carry_skills=request.carry_skills)
    routing = reply.routing
    return ChatResponse(
        bot=reply.bot,
        reply=reply.text,
        routing=RoutingOut(
            strategy=routing.strategy,
            selected=routing.selected,
            carried=routing.carried,
            reason=routing.reason,
            error=routing.error,
        ),
        model=reply.model,
        stop_reason=reply.stop_reason,
        usage=UsageOut(
            input_tokens=reply.usage.input_tokens,
            output_tokens=reply.usage.output_tokens,
            cache_read_input_tokens=reply.usage.cache_read_input_tokens,
            cache_creation_input_tokens=reply.usage.cache_creation_input_tokens,
        ),
    )
