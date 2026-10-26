// The A/B test as a flowchart, drawn with HTML and CSS: one column of steps, with the daily checks in a
// dashed loop. Each check's continuing answer is the labeled arrow below it; the other answer branches to
// the side on wide screens (indented below the check on phones). The steps are an ordered list, so screen
// readers get the same sequence; the arrow glyphs are decorative.

import { StepNumber } from "@/components/evals/LoopDiagram";

const LINK = "font-medium underline underline-offset-2";

function Down({ label }: { label?: string }) {
  return (
    <p className="flex items-center gap-2 py-1 pl-[1.1rem] text-xs leading-5 text-slate">
      <span aria-hidden="true" className="text-sm leading-none text-dim">
        ▼
      </span>
      {label}
    </p>
  );
}

function Phase({ children }: { children: React.ReactNode }) {
  return <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-forest">{children}</p>;
}

function Step({ n, title, children, why }: { n: number; title: string; children: React.ReactNode; why?: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-white px-3.5 py-3">
      <div className="flex items-center gap-2">
        <StepNumber n={n} />
        <h3 className="text-sm font-semibold leading-5 text-ink">{title}</h3>
      </div>
      <p className="mt-1.5 text-sm leading-6 text-slate">{children}</p>
      {why && <p className="mt-2 border-t border-line pt-2 text-xs leading-5 text-slate">{why}</p>}
    </div>
  );
}

/** A check and the answer that leaves the main path: to the right on wide screens, indented below on phones. */
function Check({
  question,
  side,
}: {
  question: string;
  side: { answer: string; title: string; body: React.ReactNode; tone: "stop" | "loop" };
}) {
  const box = side.tone === "stop" ? "border-red-200 bg-red-50 text-red-800" : "border-dashed border-field bg-white text-slate";
  return (
    <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,15rem)] sm:items-center sm:gap-8">
      <p className="flex items-center gap-2 rounded-xl border-2 border-ink bg-canvas px-3.5 py-3 text-sm font-semibold leading-5 text-ink">
        <span aria-hidden="true" className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-ink text-xs text-white">
          ?
        </span>
        {question}
      </p>
      <div className={`relative ml-6 rounded-xl border px-3.5 py-2.5 sm:ml-0 ${box}`}>
        <span aria-hidden="true" className="absolute -left-5 top-2.5 text-sm leading-none text-dim sm:hidden">
          ↳
        </span>
        <span aria-hidden="true" className="absolute -left-6 top-1/2 hidden -translate-y-1/2 text-sm leading-none text-dim sm:block">
          ▶
        </span>
        <p className="text-sm font-semibold leading-5">
          {side.answer}: {side.title}
        </p>
        <p className="mt-0.5 text-xs leading-5">{side.body}</p>
      </div>
    </div>
  );
}

export function AbTestFlow() {
  return (
    <figure className="rounded-2xl border border-line bg-white p-4 sm:p-6">
      <ol className="max-w-3xl">
        <li>
          <Phase>Before it starts</Phase>
          <Step
            n={1}
            title="Fix the plan"
            why={
              <>
                Why one primary metric: if a change does nothing, 20 metrics tested at 5% still show about one
                significant result by chance, as likely against B as for it. The others get a correction, such as the
                Holm method, which keeps the chance of any false win at 5% or less. Why whole weeks: weekdays and
                weekends differ, reactions to anything new fade (compare week one with week two), and what members ask
                shifts around paydays and statement dates, so a full monthly cycle is safer.
              </>
            }
          >
            One primary metric, a margin for each guardrail (how much worse it may get), the number of members needed
            (below), and a length in whole weeks that reaches it.
          </Step>
          <Down />
        </li>
        <li>
          <Phase>While it runs</Phase>
          <Step
            n={2}
            title="Split members at random"
            why="Watch for spillover: if B sends fewer chats to human support, A's queue gets shorter too, and A looks better than it would alone."
          >
            By member, half and half. Each member sees one version on every visit and device, so no chat switches bots
            midway.
          </Step>
          <Down />
        </li>
        <li>
          <Step n={3} title="Count each member from their first coach chat">
            Members who never open the coach cannot be affected, and nobody sees a difference before opening it, so
            both groups enter at the same rate.
          </Step>
          <Down />
        </li>
        <li>
          <div className="rounded-2xl border-2 border-dashed border-field p-3 sm:p-4">
            <p className="mb-2.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-forest">
              <span aria-hidden="true" className="text-sm leading-none">
                ↻
              </span>
              Every day until the planned end
            </p>
            <Check
              question="Is a guardrail clearly worse?"
              side={{
                answer: "Yes",
                title: "stop early for harm",
                body: "The test ends here. Stopping for harm is always allowed.",
                tone: "stop",
              }}
            />
            <Down label="No: go on to the next check" />
            <Check
              question="Has it reached the planned end?"
              side={{
                answer: "No",
                title: "run another day",
                body: (
                  <>
                    Back to the first check tomorrow, without reading the primary metric: stopping the first time it
                    looks significant makes false wins far more common than 5%. Sequential testing allows planned looks.
                  </>
                ),
                tone: "loop",
              }}
            />
          </div>
          <Down label="Yes: leave the loop" />
        </li>
        <li>
          <Phase>After it ends</Phase>
          <Step n={4} title="Analyze by member">
            The member is the unit, since one member&apos;s messages are alike. The primary metric is one value per
            member, adjusted with CUPED (below). Reply-level guardrails, such as 95th percentile latency, are computed
            over all replies, with intervals that resample whole members. The primary metric decides; each guardrail
            must stay within its margin.
          </Step>
          <Down />
        </li>
        <li className="rounded-xl bg-ink px-3.5 py-3 text-white">
          <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-lime">Then</p>
          <p className="mt-1 text-sm leading-6">
            The readout in{" "}
            <a href="#launch" className={`${LINK} text-white focus-visible:outline-lime!`}>
              section 5
            </a>
            : the split first, then the guardrails, then the primary metric with its confidence interval.
          </p>
        </li>
      </ol>
    </figure>
  );
}
