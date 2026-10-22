"use client";

import { useEffect, useRef } from "react";

import type { Architecture, BotName, Routing } from "@/lib/api";

import { AfterDiagram, BeforeDiagram } from "./ArchitectureDiagram";
import { Markdown } from "./Markdown";
import type { AssistantTurn, ColumnState } from "./types";

// Static class strings per column (Tailwind can't see classes assembled at runtime).
const COPY: Record<
  BotName,
  { title: string; tag: string; badge: string; bar: string; explanation: string }
> = {
  before: {
    title: "Before",
    tag: "single-agent router",
    badge: "bg-peach-soft text-ember",
    bar: "bg-peach",
    explanation:
      "The earlier design described in the post. A small router model hands each message to exactly one expert agent, which answers with its domain's guidance plus shared instructions. A question that spans several domains gets only one domain's expertise.",
  },
  after: {
    title: "After",
    tag: "skill-based",
    badge: "bg-fynn-soft text-cobalt",
    bar: "bg-fynn",
    explanation:
      "The design the post moved to. A small router picks the topic skills the message needs, and one agent answers with them plus always-on skills (tone, response rules, guardrails).",
  },
};

// What Fynn Lab adds on top of the post, shown separately so it isn't read as Kikoff's design.
function additionNote(bot: BotName, architecture: Architecture): string {
  if (bot === "before") {
    return "Added in Fynn Lab: the post doesn't name its expert agents, so these four domains are this project's own grouping of the same skill files.";
  }
  return `Added in Fynn Lab, not in the post: at most ${architecture.max_new_skills_per_turn} new skills per message, and up to ${architecture.max_carried_skills} of the previous turn's skills stay loaded for one more turn so follow-up questions keep their context.`;
}

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
    <div className="rounded-xl border border-line bg-canvas px-3 py-2.5 text-xs text-slate">
      <div>
        <span className="font-semibold text-ink">{bot === "before" ? "Agent" : "Skills"}: </span>
        {pickedLabel(bot, routing, architecture)}
        {routing.carried.length > 0 && <span> + carried: {routing.carried.join(", ")}</span>}
      </div>
      {routing.error ? (
        <div className="mt-1 text-ember">Router failed, answered without newly routed guidance: {routing.error}</div>
      ) : (
        <div className="mt-1 leading-5">
          <span className="font-semibold text-ink">Router reason: </span>
          {routing.reason}
        </div>
      )}
    </div>
  );
}

function AssistantMeta({ turn }: { turn: AssistantTurn }) {
  const { usage } = turn;
  return (
    <div className="mt-2 border-t border-line pt-1.5 text-[11px] text-dim">
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
  // After a failed turn the last reply's routing is stale, so show it only when the column is idle.
  const idle = !state.pending && !state.error;
  const routing = idle ? (lastAssistant?.routing ?? null) : null;
  const Diagram = bot === "before" ? BeforeDiagram : AfterDiagram;

  useEffect(() => {
    // Scroll only the transcript box (never the window), and only when a turn was added.
    const box = transcript.current;
    const grew = state.turns.length > seenTurns.current;
    seenTurns.current = state.turns.length;
    if (box && (grew || state.pending)) box.scrollTop = box.scrollHeight;
  }, [state.turns.length, state.pending]);

  const announcement =
    idle && lastAssistant
      ? `${copy.title} replied. ${bot === "before" ? "Agent" : "Skills"}: ${pickedLabel(bot, lastAssistant.routing, architecture)}.`
      : "";

  return (
    <section
      className="flex min-w-0 flex-col gap-4 overflow-hidden rounded-2xl border border-line bg-white p-4 pt-0 sm:p-5 sm:pt-0"
      aria-label={`${copy.title} bot`}
    >
      <div className={`-mx-4 h-1.5 sm:-mx-5 ${copy.bar}`} aria-hidden="true" />
      <header>
        <h2 className="flex items-center gap-2 text-xl font-semibold tracking-tight text-ink">
          {copy.title}
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${copy.badge}`}>{copy.tag}</span>
        </h2>
        <p className="mt-1.5 text-sm leading-6 text-slate">{copy.explanation}</p>
        <p className="mt-2.5 rounded-xl border border-dashed border-line px-3 py-2 text-xs leading-5 text-slate">
          {additionNote(bot, architecture)}
        </p>
      </header>

      <Diagram architecture={architecture} routing={routing} pending={state.pending} carryNext={state.carry} />

      {lastAssistant && idle && (
        <RoutingSummary bot={bot} routing={lastAssistant.routing} architecture={architecture} />
      )}

      <p className="sr-only" role="status">
        {announcement}
      </p>

      <div
        ref={transcript}
        className="flex max-h-[28rem] min-h-40 flex-col gap-3 overflow-y-auto rounded-xl bg-canvas p-3 sm:max-h-[32rem]"
      >
        {state.turns.length === 0 && !state.pending && !state.error && (
          <p className="m-auto text-center text-sm text-dim">Send a message to compare the two designs.</p>
        )}
        {state.turns.map((turn, index) =>
          turn.role === "user" ? (
            <div key={index} className="ml-8 self-end break-words rounded-2xl rounded-br-md bg-ink px-3.5 py-2 text-sm text-white">
              {turn.content}
            </div>
          ) : (
            <div key={index} className="mr-4 break-words rounded-2xl rounded-bl-md border border-line bg-white px-3.5 py-2.5">
              <Markdown text={turn.content} />
              <AssistantMeta turn={turn} />
            </div>
          ),
        )}
        {state.pending && (
          <p className="flex items-center gap-2 text-sm text-slate">
            <span className="flex gap-1" aria-hidden="true">
              <span className="h-1.5 w-1.5 rounded-full bg-dim motion-safe:animate-bounce [animation-delay:-0.2s]" />
              <span className="h-1.5 w-1.5 rounded-full bg-dim motion-safe:animate-bounce [animation-delay:-0.1s]" />
              <span className="h-1.5 w-1.5 rounded-full bg-dim motion-safe:animate-bounce" />
            </span>
            Routing, then answering...
          </p>
        )}
        {state.error && (
          <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-800">
            <p>Not answered: {state.error.message}</p>
            <p className="mt-1 text-xs text-red-700">Your question: {state.error.text}</p>
            {state.error.retryable ? (
              <button
                type="button"
                className="mt-2 rounded-full border border-red-300 bg-white px-3 py-1 text-xs font-semibold text-red-800 hover:bg-red-100 disabled:opacity-50"
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
