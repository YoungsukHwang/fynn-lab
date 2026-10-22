import { Markdown } from "@/components/Markdown";
import type { CaseChange, CaseSide } from "@/lib/evalData";
import { datasetLabel, excerpt, questionsLabel, runsLabel } from "@/lib/evalLabels";

import { Chip, type ChipTone, Expander } from "./ui";

const STATUS_TONE: Record<string, ChipTone> = { PRESENT: "lime", ABSENT: "neutral", CONTRADICTED: "bad" };

function ReplyPanel({ label, side, level }: { label: string; side: CaseSide | null; level: 4 | 5 }) {
  const Heading = level === 4 ? "h4" : "h5";
  if (!side) {
    return (
      <div className="rounded-xl border border-dashed border-field px-3 py-2.5 text-sm text-slate">
        {label}: no details in the results files.
      </div>
    );
  }
  const reply = side.reply ? excerpt(side.reply) : null;
  const failed = side.passed === false;
  const runs = runsLabel(side.passes, side.runs, side.errored, side.allErrored);
  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-xl border border-line bg-canvas px-3 py-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Heading className="text-sm font-semibold text-ink">{label}</Heading>
        {side.passed !== null && (
          <Chip tone={failed ? "bad" : "lime"}>
            {runs ? (failed ? "Shown run failed" : "Shown run passed") : failed ? "Not passed" : "Passed"}
          </Chip>
        )}
        {runs && <span className="text-xs text-slate">{runs}</span>}
      </div>
      {side.routed && (
        <p className="text-xs text-slate">
          <span className="font-semibold text-ink">Routed to: </span>
          {side.routed.length ? side.routed.join(", ") : "none"}
        </p>
      )}
      {reply ? (
        <>
          <p className="whitespace-pre-line break-words text-sm leading-6 text-ink">{reply.text}</p>
          {reply.truncated && side.reply && (
            <details className="text-sm">
              <summary className="cursor-pointer text-xs font-medium text-ink underline underline-offset-2">
                Show the full reply
              </summary>
              <div className="mt-2 break-words rounded-lg border border-line bg-white px-3 py-2">
                <Markdown text={side.reply} />
              </div>
            </details>
          )}
        </>
      ) : (
        <p className="text-sm text-slate">No reply recorded.</p>
      )}
      {side.error && <p className="text-xs text-red-800">Error: {side.error}</p>}
      {failed && (side.judgeReason || side.notPresent.length > 0 || side.checkFailures.length > 0) && (
        <div className="border-t border-line pt-2">
          {side.judgeReason && (
            <p className="text-xs leading-5 text-ink">
              <span className="font-semibold">Judge reason: </span>
              {side.judgeReason}
            </p>
          )}
          {side.notPresent.length > 0 && (
            <>
              <p className="mt-2 text-xs font-semibold text-ink">Facts not graded PRESENT</p>
              <ul className="mt-1 space-y-1.5">
                {side.notPresent.map((fact) => (
                  <li key={fact.fact} className="text-xs leading-5 text-ink">
                    <Chip tone={STATUS_TONE[fact.status] ?? "neutral"}>{fact.status}</Chip> {fact.fact}
                    {fact.note && <span className="block text-slate">Judge note: {fact.note}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
          {side.checkFailures.length > 0 && (
            <>
              <p className="mt-2 text-xs font-semibold text-ink">Code check failures</p>
              <ul className="mt-1 list-disc space-y-1 pl-4 text-xs leading-5 text-ink marker:text-dim">
                {side.checkFailures.map((failure) => (
                  <li key={failure} className="break-all">
                    {failure}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

/** One expander per changed case, with both replies side by side and why the failing one failed. */
export function CaseChangeList({
  changes,
  labels,
  personaNames,
  tag,
  headingLevel = 5,
}: {
  changes: CaseChange[];
  labels: { baseline: string; candidate: string };
  personaNames: Record<string, string>;
  tag?: { ids: string[]; label: string }; // marks some cases, e.g. the ones that need a second domain
  headingLevel?: 4 | 5; // the level of each reply panel's heading, one below the list's own heading
}) {
  return (
    <ul className="space-y-2">
      {changes.map((change) => (
        <li key={change.id}>
          <Expander
            summary={
              <span className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
                <span className="shrink-0 font-mono text-xs leading-5 text-slate">{change.id}</span>
                <span className="min-w-0 flex-1 text-sm leading-5 text-ink">{change.message || "(message not found)"}</span>
                {tag?.ids.includes(change.id) && (
                  <span className="shrink-0">
                    <Chip tone="fynn">{tag.label}</Chip>
                  </span>
                )}
                {change.sharp && (
                  <span className="shrink-0">
                    <Chip tone={change.sharp === "dropped" ? "bad" : "lime"}>
                      {change.sharp === "dropped" ? "Dropped sharply" : "Rose sharply"}
                    </Chip>
                  </span>
                )}
              </span>
            }
          >
            <p className="text-xs leading-5 text-slate">
              {datasetLabel(change.dataset)}
              {change.intents !== null && ` · ${questionsLabel(change.intents)}`}
              {change.persona && ` · member: ${personaNames[change.persona] ?? change.persona}`}
              {change.skills.length > 0 && ` · labeled skills: ${change.skills.join(", ")}`}
            </p>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <ReplyPanel label={labels.baseline} side={change.baseline} level={headingLevel} />
              <ReplyPanel label={labels.candidate} side={change.candidate} level={headingLevel} />
            </div>
          </Expander>
        </li>
      ))}
    </ul>
  );
}
