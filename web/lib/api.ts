// Client for the Fynn Lab FastAPI backend (backend/api/main.py).

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

// Request limits come from GET /architecture; these defaults are used only until it loads.
export const DEFAULT_LIMITS = { max_messages: 20, max_user_message_chars: 2000 };
// A reply normally takes 10 to 30 seconds. The backend caps the router call at 20 s and the answer
// call at 90 s with no SDK retries (backend/fynn/config.py), so past 120 s the request is abandoned
// as retryable.
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
  limits: { max_messages: number; max_user_message_chars: number };
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
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(`The API at ${API_URL} returned an unexpected response.`, response.status, false);
  }
}

export function getPersonas(): Promise<Persona[]> {
  return request<Persona[]>("/personas");
}

export function getArchitecture(): Promise<Architecture> {
  return request<Architecture>("/architecture");
}

function combineSignals(signal: AbortSignal | undefined, timeout: AbortSignal): AbortSignal {
  if (!signal) return timeout;
  // AbortSignal.any is missing in older browsers; fall back to the caller's signal (no timeout).
  return typeof AbortSignal.any === "function" ? AbortSignal.any([signal, timeout]) : signal;
}

// async so that anything thrown while building the request becomes a rejection the caller handles.
export async function sendChat(
  body: { bot: BotName; persona_id: string; messages: ChatMessage[]; carry_skills?: string[] },
  signal?: AbortSignal,
): Promise<ChatResponse> {
  const timeout = AbortSignal.timeout(CHAT_TIMEOUT_MS);
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: combineSignals(signal, timeout),
  });
}
