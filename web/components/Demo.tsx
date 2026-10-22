"use client";

import { useEffect, useRef, useState } from "react";

import {
  ApiError,
  type Architecture,
  type BotName,
  type ChatMessage,
  getArchitecture,
  DEFAULT_LIMITS,
  getPersonas,
  type Persona,
  RequestCancelled,
  sendChat,
} from "@/lib/api";
import { EXAMPLE_QUESTIONS } from "@/lib/examples";

import { ChatColumn } from "./ChatColumn";
import { PersonaCard } from "./PersonaCard";
import { type ColumnState, EMPTY_COLUMN } from "./types";

const BOTS: BotName[] = ["before", "after"];
const DEFAULT_PERSONA = "rebuilder";

type Columns = Record<BotName, ColumnState>;
const EMPTY_COLUMNS: Columns = { before: EMPTY_COLUMN, after: EMPTY_COLUMN };

export function Demo() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [architecture, setArchitecture] = useState<Architecture | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [personaId, setPersonaId] = useState(DEFAULT_PERSONA);
  const [columns, setColumns] = useState<Columns>(EMPTY_COLUMNS);
  const [input, setInput] = useState("");
  const textarea = useRef<HTMLTextAreaElement>(null);
  // Bumped on reset; replies that arrive for an older conversation are dropped.
  const conversation = useRef(0);
  const inFlight = useRef<AbortController | null>(null);
  // Refs survive the route being hidden and shown again (cacheComponents Activity), so the
  // static demo data is fetched once per page load, not on every return to this page.
  const loadStarted = useRef(false);

  useEffect(() => {
    if (loadStarted.current) return;
    loadStarted.current = true;
    Promise.all([getPersonas(), getArchitecture()])
      .then(([loadedPersonas, loadedArchitecture]) => {
        setPersonas(loadedPersonas);
        setArchitecture(loadedArchitecture);
        setLoadError(null);
        setPersonaId((current) =>
          loadedPersonas.some((p) => p.id === current) ? current : (loadedPersonas[0]?.id ?? current),
        );
      })
      .catch((error: unknown) => {
        loadStarted.current = false;
        // Status -1: an unexpected client-side failure, not "backend unreachable" (status 0).
        setLoadError(error instanceof ApiError ? error : new ApiError("Could not load the demo data.", -1, false));
      });
  }, []);

  const persona = personas.find((p) => p.id === personaId) ?? null;
  const limits = architecture?.limits ?? DEFAULT_LIMITS;
  const pending = BOTS.some((bot) => columns[bot].pending);
  const blockedByError = BOTS.some((bot) => columns[bot].error !== null);
  // Every request must end with the new user turn and stay within the backend's message limit.
  const atLimit = BOTS.some((bot) => columns[bot].turns.length + 1 > limits.max_messages);
  const hasConversation = BOTS.some((bot) => columns[bot].turns.length > 0 || columns[bot].error !== null);

  function updateColumn(bot: BotName, update: (column: ColumnState) => ColumnState) {
    setColumns((previous) => ({ ...previous, [bot]: update(previous[bot]) }));
  }

  function focusComposer() {
    requestAnimationFrame(() => textarea.current?.focus());
  }

  function reset() {
    conversation.current += 1;
    inFlight.current?.abort();
    inFlight.current = null;
    setColumns(EMPTY_COLUMNS);
    focusComposer();
  }

  function send(text: string, bots: BotName[]) {
    const message = text.trim();
    if (!message || !persona || pending) return;
    const id = conversation.current;
    const controller = new AbortController();
    inFlight.current = controller;

    for (const bot of bots) {
      const column = columns[bot];
      if (column.turns.length + 1 > limits.max_messages) continue;
      const history: ChatMessage[] = [
        ...column.turns.map((turn) => ({ role: turn.role, content: turn.content })),
        { role: "user", content: message },
      ];
      updateColumn(bot, (c) => ({ ...c, turns: [...c.turns, { role: "user", content: message }], pending: true, error: null }));

      sendChat(
        { bot, persona_id: persona.id, messages: history, carry_skills: bot === "after" ? column.carry : [] },
        controller.signal,
      )
        .then((response) => {
          if (conversation.current !== id) return;
          updateColumn(bot, (c) => ({
            ...c,
            pending: false,
            carry: bot === "after" ? response.routing.selected : [],
            turns: [
              ...c.turns,
              {
                role: "assistant",
                content: response.reply,
                routing: response.routing,
                model: response.model,
                usage: response.usage,
              },
            ],
          }));
        })
        .catch((error: unknown) => {
          if (conversation.current !== id || error instanceof RequestCancelled) return;
          const apiError = error instanceof ApiError ? error : new ApiError("Unexpected error.", 0, false);
          // Drop the unanswered message so the history stays user/assistant alternating;
          // the error box keeps the text so it can be retried.
          updateColumn(bot, (c) => {
            const last = c.turns.at(-1);
            const turns = last?.role === "user" ? c.turns.slice(0, -1) : c.turns;
            return {
              ...c,
              turns,
              pending: false,
              error: { message: apiError.message, retryable: apiError.retryable, text: message },
            };
          });
        });
    }
    focusComposer();
  }

  if (loadError) {
    return (
      <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
        <p className="font-medium">{loadError.message}</p>
        {loadError.status === 0 ? (
          <p className="mt-1">
            Start it from the repo root with{" "}
            <code className="rounded bg-white px-1">cd backend && .venv/bin/uvicorn api.main:app --port 8000</code>, then reload
            this page.
          </p>
        ) : (
          <p className="mt-1">The backend returned an error. Check its log, then reload this page.</p>
        )}
      </div>
    );
  }

  if (!architecture || !persona) {
    return <p className="text-sm text-zinc-500">Loading personas and architecture...</p>;
  }

  const failed = BOTS.filter((bot) => columns[bot].error !== null);
  // Retrying helps only if every failed column can be retried; otherwise a reset is needed anyway.
  const canRetry = failed.length > 0 && failed.every((bot) => columns[bot].error?.retryable);
  const composerHint = atLimit
    ? `This conversation reached the demo limit of ${Math.floor(limits.max_messages / 2)} questions. Start a new conversation to keep going.`
    : blockedByError
      ? `${failed.length === BOTS.length ? "Neither bot answered" : "One bot didn't answer"} the last message. ${
          canRetry ? "Retry it, or start a new conversation," : "Start a new conversation"
        } before asking the next question.`
      : null;
  const canSend = !pending && !blockedByError && !atLimit && input.trim().length > 0;

  return (
    <div className="flex flex-col gap-5">
      <section className="flex flex-col gap-3" aria-label="Member">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-zinc-700">
            Member (synthetic persona)
            <select
              className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-base text-zinc-900 sm:text-sm"
              value={personaId}
              onChange={(event) => {
                setPersonaId(event.target.value);
                reset();
              }}
            >
              {personas.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id})
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
            onClick={reset}
            disabled={!hasConversation && !pending}
          >
            New conversation
          </button>
        </div>
        <PersonaCard persona={persona} />
      </section>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {BOTS.map((bot) => (
          <ChatColumn
            key={bot}
            bot={bot}
            state={columns[bot]}
            architecture={architecture}
            onRetry={(retryBot, text) => send(text, [retryBot])}
            retryDisabled={pending}
          />
        ))}
      </div>

      <form
        className="sticky bottom-0 flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white/95 p-2 shadow-sm backdrop-blur sm:p-3"
        onSubmit={(event) => {
          event.preventDefault();
          if (!canSend) return;
          send(input, BOTS);
          setInput("");
        }}
      >
        {composerHint && (
          <p className="text-xs text-amber-800" role="status">
            {composerHint}
          </p>
        )}
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible">
          {EXAMPLE_QUESTIONS.map((example) => (
            <button
              key={example.label}
              type="button"
              className="shrink-0 rounded-full border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
              onClick={() => {
                setInput(example.text);
                focusComposer();
              }}
              disabled={pending}
            >
              {example.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <label htmlFor="message" className="sr-only">
            Message to both bots
          </label>
          <textarea
            id="message"
            ref={textarea}
            className="min-h-10 flex-1 resize-y rounded-md border border-zinc-300 px-3 py-2 text-base text-zinc-900 sm:text-sm"
            rows={1}
            maxLength={limits.max_user_message_chars}
            placeholder="Ask both bots the same question. Enter sends, Shift+Enter adds a line."
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              // Ignore Enter while an IME (e.g. Korean) is still composing a character.
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <button
            type="submit"
            className="self-end rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50"
            disabled={!canSend}
          >
            {pending ? "Waiting..." : "Send to both"}
          </button>
        </div>
      </form>
    </div>
  );
}
