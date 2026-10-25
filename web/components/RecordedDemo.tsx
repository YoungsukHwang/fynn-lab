"use client";

import { useState } from "react";

import type { BotName } from "@/lib/api";
import type { RecordedDemo as RecordedDemoData, RecordedExchange, RecordedSide } from "@/lib/evalData";

import { ChatColumn } from "./ChatColumn";
import { PersonaCard } from "./PersonaCard";
import type { ColumnState } from "./types";

const BOTS: BotName[] = ["before", "after"];
const REPO_URL = "https://github.com/YoungsukHwang/fynn-lab";

const STATUS: Record<string, { label: string; className: string }> = {
  PRESENT: { label: "Present", className: "bg-lime-soft text-forest" },
  ABSENT: { label: "Missing", className: "bg-peach-soft text-ember" },
  CONTRADICTED: { label: "Contradicted", className: "bg-peach-soft text-ember" },
};

function columnState(exchange: RecordedExchange, bot: BotName): ColumnState {
  const side = exchange[bot];
  return {
    turns: [
      { role: "user", content: exchange.message },
      { role: "assistant", content: side.reply, routing: side.routing, model: side.model, usage: side.usage },
    ],
    pending: false,
    error: null,
    carry: [],
  };
}

function Verdict({ side }: { side: RecordedSide }) {
  return (
    <div className="rounded-xl border border-line px-3 py-2.5 text-xs leading-5 text-slate">
      <p>
        <span className="font-semibold text-ink">Judge: {side.passed ? "passed" : "failed"} this reply.</span>{" "}
        {side.repeats > 1 && `The case passed in ${side.passes} of ${side.repeats} runs.`}
      </p>
      <ul className="mt-2 flex flex-col gap-1.5">
        {side.facts.map((f) => {
          const status = STATUS[f.status] ?? { label: f.status, className: "bg-mist text-ink" };
          return (
            <li key={f.fact} className="flex items-start gap-2">
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${status.className}`}>
                {status.label}
              </span>
              <span>{f.fact}</span>
            </li>
          );
        })}
      </ul>
      {side.checkFailures.length > 0 && (
        <p className="mt-2 text-ember">Code checks failed: {side.checkFailures.join("; ")}</p>
      )}
    </div>
  );
}

/** The Demo page on the static site: recorded replies from a committed eval run instead of a live chat. */
export function RecordedDemo({ data, live = false }: { data: RecordedDemoData; live?: boolean }) {
  const [index, setIndex] = useState(0);
  const exchange = data.exchanges[index];
  const persona = exchange ? data.personas.find((p) => p.id === exchange.persona) : undefined;
  const day = data.recordedAt?.slice(0, 10);

  return (
    <div className="flex flex-col gap-6">
      <section aria-label="About this demo" className="rounded-2xl border border-line bg-white p-4 text-sm leading-6 text-slate">
        {live ? (
          <p>
            <span className="font-semibold text-ink">Recorded replies</span> from the committed eval run
            {day ? ` of ${day}` : ""}. Each case ran three times per bot; the reply shown comes from a run with the
            case&apos;s usual result, with the router&apos;s pick and the judge&apos;s verdict on each expected fact.
          </p>
        ) : (
          <p>
            <span className="font-semibold text-ink">Recorded replies, not a live chat.</span> This site has no
            backend, so each question below shows both bots&apos; replies from the committed eval run
            {day ? ` of ${day}` : ""}. Each case ran three times per bot; the reply shown comes from a run with the
            case&apos;s usual result, with the router&apos;s pick and the judge&apos;s verdict on each expected fact. To
            ask your own questions, run the backend and the site locally (
            <a href={`${REPO_URL}#backend`} className="font-medium text-ink underline underline-offset-2">
              see the README
            </a>
            ).
          </p>
        )}
      </section>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Recorded questions">
        {data.exchanges.map((e, i) => (
          <button
            key={e.id}
            type="button"
            aria-pressed={i === index}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium ${
              i === index ? "bg-ink text-white" : "bg-mist text-ink hover:bg-lime-soft"
            }`}
            onClick={() => setIndex(i)}
          >
            {e.label} <span className={i === index ? "text-white/70" : "text-dim"}>({e.id})</span>
          </button>
        ))}
      </div>

      {exchange ? (
        <>
          {persona && <PersonaCard persona={persona} />}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {BOTS.map((bot) => (
              <ChatColumn
                key={`${exchange.id}-${bot}`}
                bot={bot}
                state={columnState(exchange, bot)}
                architecture={data.architecture}
                onRetry={() => {}}
                retryDisabled
                footer={<Verdict side={exchange[bot]} />}
              />
            ))}
          </div>
        </>
      ) : (
        <p className="text-sm text-slate">No recorded exchanges in results/demo/recorded.json.</p>
      )}
    </div>
  );
}
