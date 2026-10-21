// Client for the Fynn Lab FastAPI backend (backend/api/main.py).

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

// Mirrors backend MAX_MESSAGES: a request may hold at most this many messages and must end with a user turn.
export const MAX_MESSAGES = 20;
// Mirrors backend MAX_USER_MESSAGE_CHARS.
export const MAX_USER_MESSAGE_CHARS = 2000;
// A reply normally takes 10 to 30 seconds; past this the request is abandoned as retryable.
const CHAT_TIMEOUT_MS = 120_000;

export type BotName = "before" | "after";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface Persona {
  id: string;
  name: string;
  summary: string;
  as_of: string;
  credit: {
    score?: { model?: string; current?: number; previous?: number; previous_as_of?: string };
    utilization?: {
      overall?: number | null;
      total_revolving_balance?: number | null;
      total_revolving_limit?: number | null;
    };
    [key: string]: unknown;
  };
  products: Record<string, Record<string, unknown> | null>;
  recent_events: string[];
}

export interface Routing {
  strategy: "single_agent" | "skills";
  selected: string[];
  carried: string[];
  reason: string;
  error: string | null;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
}

export interface ChatResponse {
  bot: BotName;
  reply: string;
  model: string;
  stop_reason: string | null;
  routing: Routing;
  usage: Usage;
}

export interface Architecture {
  models: { router: string; agent: string };
  max_new_skills_per_turn: number;
  max_carried_skills: number;
  always_on: string[];
  domains: { id: string; title: string; skills: string[] }[];
  topics: { name: string; domain: string; description: string }[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryable: boolean,
  ) {
    super(message);
  }
}

/** Thrown when the caller aborted the request on purpose (e.g. a reset); callers ignore it. */
export class RequestCancelled extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("The bot took too long to answer.", 0, true);
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new RequestCancelled();
    }
    const origin = typeof window === "undefined" ? "this page" : window.location.origin;
    throw new ApiError(
      `Can't reach the API at ${API_URL}. Check that the backend is running and allows requests from ${origin}.`,
      0,
      true,
    );
  }
  if (!response.ok) {
    // The backend sends every error as {detail: string, retryable: boolean}.
    const body = (await response.json().catch(() => null)) as { detail?: unknown; retryable?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status})`;
    throw new ApiError(detail, response.status, body?.retryable === true);
  }
  return (await response.json()) as T;
}

export function getPersonas(): Promise<Persona[]> {
  return request<Persona[]>("/personas");
}

export function getArchitecture(): Promise<Architecture> {
  return request<Architecture>("/architecture");
}

export function sendChat(
  body: { bot: BotName; persona_id: string; messages: ChatMessage[]; carry_skills?: string[] },
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const timeout = AbortSignal.timeout(CHAT_TIMEOUT_MS);
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
}
