"use client";

import { useEffect, useRef } from "react";

import type { Architecture, BotName, Routing } from "@/lib/api";

import { AfterDiagram, BeforeDiagram } from "./ArchitectureDiagram";
import { Markdown } from "./Markdown";
import type { AssistantTurn, ColumnState } from "./types";

const COPY: Record<BotName, { title: string; tag: string; badge: string; explanation: string }> = {
  before: {
    title: "Before",
    tag: "single-agent router",
    badge: "bg-amber-100 text-amber-900",
    explanation:
      "The beta design. A small router model hands each message to exactly one expert agent. A question that spans several domains gets one domain's expertise; the other parts are answered from shared instructions only.",
  },
  after: {
    title: "After",
    tag: "skill-based",
    badge: "bg-teal-100 text-teal-900",
    explanation:
      "The skill design. A small router picks every topic skill the message needs and keeps the previous turn's skills for one more turn. One agent answers with those skills plus always-on tone, response rules and guardrails.",
  },
};

function formatNumber(value: number): string {
  return value.toLocaleString("en-US");
}

function pickedLabel(bot: BotName, routing: Routing, architecture: Architecture): string {
  if (bot === "before") {
    const domain = architecture.domains.find((d) => d.id === routing.selected[0]);
    return domain ? domain.title : "none";
  }
  return routing.selected.length ? routing.selected.join(", ") : "none";
}

function RoutingSummary({ bot, routing, architecture }: { bot: BotName; routing: Routing; architecture: Architecture }) {
  return (
    <div className="rounded-md bg-zinc-50 px-3 py-2 text-xs text-zinc-700">
      <div>
        <span className="font-medium text-zinc-900">{bot === "before" ? "Agent" : "Skills"}: </span>
        {pickedLabel(bot, routing, architecture)}
        {routing.carried.length > 0 && <span className="text-zinc-600"> + carried: {routing.carried.join(", ")}</span>}
      </div>
      {routing.error ? (
        <div className="mt-1 text-amber-800">Router failed, answered without newly routed guidance: {routing.error}</div>
      ) : (
        <div className="mt-1 text-zinc-600">Router reason: {routing.reason}</div>
      )}
    </div>
  );
}

function AssistantMeta({ turn }: { turn: AssistantTurn }) {
  const { usage } = turn;
  return (
    <div className="mt-2 text-[11px] text-zinc-500">
      Answered by {turn.model} · router + agent tokens: {formatNumber(usage.input_tokens)} in,{" "}
      {formatNumber(usage.output_tokens)} out
      {usage.cache_read_input_tokens > 0 && `, ${formatNumber(usage.cache_read_input_tokens)} read from cache`}
      {usage.cache_creation_input_tokens > 0 && `, ${formatNumber(usage.cache_creation_input_tokens)} written to cache`}
    </div>
  );
}

interface ChatColumnProps {
  bot: BotName;
  state: ColumnState;
  architecture: Architecture;
  onRetry: (bot: BotName, text: string) => void;
  retryDisabled: boolean;
}

export function ChatColumn({ bot, state, architecture, onRetry, retryDisabled }: ChatColumnProps) {
  const copy = COPY[bot];
  const transcript = useRef<HTMLDivElement>(null);
  // Refs survive the route being hidden and re-shown, so re-showing does not scroll again.
  const seenTurns = useRef(state.turns.length);
  const lastAssistant = state.turns.findLast((t): t is AssistantTurn => t.role === "assistant");
  const routing = state.pending ? null : (lastAssistant?.routing ?? null);
  const Diagram = bot === "before" ? BeforeDiagram : AfterDiagram;

  useEffect(() => {
    // Scroll only the transcript box (never the window), and only when a turn was added.
    const box = transcript.current;
    const grew = state.turns.length > seenTurns.current;
    seenTurns.current = state.turns.length;
    if (box && (grew || state.pending)) box.scrollTop = box.scrollHeight;
  }, [state.turns.length, state.pending]);

  const announcement =
    !state.pending && lastAssistant
      ? `${copy.title} replied. ${bot === "before" ? "Agent" : "Skills"}: ${pickedLabel(bot, lastAssistant.routing, architecture)}.`
      : "";

  return (
    <section className="flex min-w-0 flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4" aria-label={`${copy.title} bot`}>
      <header>
        <h2 className="flex items-center gap-2 text-lg font-semibold text-zinc-900">
          {copy.title}
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${copy.badge}`}>{copy.tag}</span>
        </h2>
        <p className="mt-1 text-sm text-zinc-600">{copy.explanation}</p>
      </header>

      <Diagram architecture={architecture} routing={routing} pending={state.pending} />

      {lastAssistant && !state.pending && (
        <RoutingSummary bot={bot} routing={lastAssistant.routing} architecture={architecture} />
      )}

      <p className="sr-only" role="status">
        {announcement}
      </p>

      <div
        ref={transcript}
        className="flex max-h-[28rem] min-h-40 flex-col gap-3 overflow-y-auto rounded-md border border-zinc-100 bg-zinc-50/60 p-3 sm:max-h-[32rem]"
      >
        {state.turns.length === 0 && !state.pending && !state.error && (
          <p className="m-auto text-center text-sm text-zinc-500">Send a message to compare the two designs.</p>
        )}
        {state.turns.map((turn, index) =>
          turn.role === "user" ? (
            <div key={index} className="ml-8 self-end break-words rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white">
              {turn.content}
            </div>
          ) : (
            <div key={index} className="mr-4 break-words rounded-lg border border-zinc-200 bg-white px-3 py-2">
              <Markdown text={turn.content} />
              <AssistantMeta turn={turn} />
            </div>
          ),
        )}
        {state.pending && <p className="text-sm text-zinc-500">Routing, then answering...</p>}
        {state.error && (
          <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            <p>Not answered: {state.error.message}</p>
            <p className="mt-1 text-xs text-red-700">Your question: {state.error.text}</p>
            {state.error.retryable ? (
              <button
                type="button"
                className="mt-2 rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-800 hover:bg-red-100 disabled:opacity-50"
                onClick={() => state.error && onRetry(bot, state.error.text)}
                disabled={retryDisabled}
              >
                Retry this message
              </button>
            ) : (
              <p className="mt-2 text-xs">Retrying won&apos;t help here. Start a new conversation instead.</p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
