import { CaseChangeList } from "@/components/evals/CaseChangeList";
import { Chip, type ChipTone } from "@/components/evals/ui";
import type { Attribution, CaseChange, Comparison, Decision } from "@/lib/evalData";
import { formatTimestamp, plural } from "@/lib/evalLabels";

/** One skill edit (or the skill-cap change) and the report that compared it with the After run. */
export interface EditResult {
  id: string; // anchor id, e.g. "s4" or "cap4"
  label: string; // short name shown on chips, e.g. "S4" or "Cap 4"
  title: string;
  kind: string; // "Topic skill body edit", "Skill cap", ...
  skill: string | null;
  change: string;
  why: string;
  shipped: string | null;
  rerun: number | null; // cases rerun
  outOf: number | null; // cases in the baseline run
  comparison: Comparison | null;
}

export const DECISIONS: Record<Decision, { label: string; tone: ChipTone }> = {
  ship: { label: "Ship", tone: "lime" },
  tradeoff: { label: "Tradeoff", tone: "peach" },
  "do not ship": { label: "Do not ship", tone: "bad" },
  "no effect": { label: "No effect", tone: "neutral" },
};

// The three kinds of flip, each with a mark as well as a color so the strip never relies on color alone.
const MARKS = {
  fixed: { mark: "+", label: "Fixed by the edit", box: "bg-forest text-white forced-colors:border forced-colors:border-[CanvasText]" },
  broken: { mark: "−", label: "Broken by the edit", box: "bg-red-800 text-white forced-colors:border forced-colors:border-[CanvasText]" },
  chance: { mark: "·", label: "Flipped by chance", box: "border border-field bg-white text-slate" },
} as const;

type MarkKind = keyof typeof MARKS;

function DecisionChip({ attribution, shipped }: { attribution: Attribution; shipped: string | null }) {
  const decision = DECISIONS[attribution.decision];
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Chip tone={decision.tone}>{decision.label}</Chip>
      {shipped && <Chip tone="dark">Shipped {shipped}</Chip>}
    </span>
  );
}

function Square({ kind, id, direction }: { kind: MarkKind; id: string; direction?: "up" | "down" }) {
  const mark = MARKS[kind];
  const what = kind === "chance" ? `${mark.label} (${direction === "up" ? "now passes" : "now fails"})` : mark.label;
  return (
    <li title={`${id}: ${what}`} className={`grid h-6 min-w-6 place-items-center rounded-md px-1 text-xs font-semibold ${mark.box}`}>
      <span aria-hidden="true">{kind === "chance" ? (direction === "up" ? "↑" : "↓") : mark.mark}</span>
      <span className="sr-only">
        {id}: {what}
      </span>
    </li>
  );
}

/** "Fixed 3 cases and broke none; 7 others flipped by chance." */
export function decisionSentence(a: Attribution): string {
  const chance = a.chanceUp.length + a.chanceDown.length;
  const broke = a.broken.length ? `broke ${plural(a.broken.length, "case")}` : "broke none";
  return `Fixed ${plural(a.fixed.length, "case")} and ${broke}${chance ? `; ${plural(chance, "other case")} flipped by chance` : ""}.`;
}

/** Every edit as one row: its flipped cases as marks, grouped fixed, broken, chance, then its decision. */
export function EditScorecard({ edits }: { edits: EditResult[] }) {
  const rows = edits.filter((e) => e.comparison?.report.attribution);
  return (
    <figure className="rounded-2xl border border-line bg-white p-4 sm:p-5">
      <figcaption>
        <h3 className="text-base font-semibold text-ink">What each edit changed</h3>
        <p className="mt-1 text-sm leading-6 text-slate">
          One mark per case that flipped. A flip counts for the edit only when the edit could reach that case&apos;s
          prompt; the rest got the same prompt as before, so they flipped by chance.
        </p>
      </figcaption>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-slate" aria-label="Legend">
        {(Object.keys(MARKS) as MarkKind[]).map((kind) => (
          <li key={kind} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={`grid h-5 min-w-5 place-items-center rounded-md px-1 text-[11px] font-semibold ${MARKS[kind].box}`}>
              {kind === "chance" ? "↑↓" : MARKS[kind].mark}
            </span>
            {MARKS[kind].label}
          </li>
        ))}
      </ul>
      <ol className="mt-4 divide-y divide-line">
        {rows.map((edit) => {
          const a = edit.comparison?.report.attribution as Attribution;
          return (
            <li key={edit.id} className="grid gap-2 py-3 sm:grid-cols-[14rem_minmax(0,1fr)_auto] sm:items-center sm:gap-4">
              <a href={`#${edit.id}`} className="min-w-0 text-sm text-ink underline-offset-2 hover:underline">
                <span className="font-semibold">{edit.label}</span>
                <span className="block text-xs leading-5 text-slate">{edit.title}</span>
              </a>
              <ul className="flex flex-wrap gap-1" aria-label={`${edit.label}: ${decisionSentence(a)}`}>
                {a.fixed.map((id) => <Square key={`f-${id}`} kind="fixed" id={id} />)}
                {a.broken.map((id) => <Square key={`b-${id}`} kind="broken" id={id} />)}
                {a.chanceUp.map((id) => <Square key={`u-${id}`} kind="chance" id={id} direction="up" />)}
                {a.chanceDown.map((id) => <Square key={`d-${id}`} kind="chance" id={id} direction="down" />)}
                {a.fixed.length + a.broken.length + a.chanceUp.length + a.chanceDown.length === 0 && (
                  <li className="text-xs text-slate">no case flipped</li>
                )}
              </ul>
              <DecisionChip attribution={a} shipped={edit.shipped} />
            </li>
          );
        })}
      </ol>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-medium text-ink">Show as a table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-left text-sm">
            <caption className="sr-only">Cases each edit fixed, broke, or that flipped by chance</caption>
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wide text-slate">
                <th scope="col" className="py-2 pr-3 font-semibold">Edit</th>
                <th scope="col" className="py-2 pr-3 font-semibold">Fixed</th>
                <th scope="col" className="py-2 pr-3 font-semibold">Broken</th>
                <th scope="col" className="py-2 pr-3 font-semibold">By chance</th>
                <th scope="col" className="py-2 font-semibold">Decision</th>
              </tr>
            </thead>
            <tbody className="text-ink">
              {rows.map((edit) => {
                const a = edit.comparison?.report.attribution as Attribution;
                return (
                  <tr key={edit.id} className="border-b border-line align-top last:border-0">
                    <th scope="row" className="py-2 pr-3 font-medium">{edit.label}</th>
                    <td className="py-2 pr-3 font-mono text-xs">{a.fixed.join(", ") || "none"}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{a.broken.join(", ") || "none"}</td>
                    <td className="py-2 pr-3 font-mono text-xs">{[...a.chanceUp.map((id) => `${id} (now passes)`), ...a.chanceDown.map((id) => `${id} (now fails)`)].join(", ") || "none"}</td>
                    <td className="py-2">{DECISIONS[a.decision].label}{edit.shipped ? ` (shipped ${edit.shipped})` : ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}

const EDIT_LABELS = { baseline: "Before the edit", candidate: "With the edit" };

function pick(changes: CaseChange[], ids: string[]): CaseChange[] {
  const wanted = new Set(ids);
  return changes.filter((c) => wanted.has(c.id));
}

/** One edit: what changed, its decision, the cases it fixed and broke (open to read both replies), and the chance flips. */
export function EditCard({ edit, personaNames }: { edit: EditResult; personaNames: Record<string, string> }) {
  const comparison = edit.comparison;
  const a = comparison?.report.attribution ?? null;
  const headingId = `${edit.id}-title`;
  return (
    <article id={edit.id} aria-labelledby={headingId} className="scroll-mt-6 rounded-2xl border border-line bg-white p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <Chip tone="dark">{edit.label}</Chip>
            <Chip tone="fynn">{edit.kind}</Chip>
            {edit.skill && <Chip mono>{edit.skill}</Chip>}
          </div>
          <h3 id={headingId} className="mt-2 text-xl font-semibold tracking-tight text-ink">
            {edit.title}
          </h3>
        </div>
        {a && <DecisionChip attribution={a} shipped={edit.shipped} />}
      </div>

      <dl className="mt-3 grid gap-3 text-sm leading-6 lg:grid-cols-2">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate">What changed</dt>
          <dd className="mt-0.5 text-ink">{edit.change}</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate">Why</dt>
          <dd className="mt-0.5 text-ink">{edit.why}</dd>
        </div>
      </dl>

      {!comparison || !a ? (
        <p className="mt-4 text-sm text-slate">Not run yet.</p>
      ) : (
        <>
          <p className="mt-4 text-base font-semibold text-ink">{decisionSentence(a)}</p>
          {(
            [
              ["Fixed by the edit", pick(comparison.improved, a.fixed)],
              ["Broken by the edit", pick(comparison.regressed, a.broken)],
            ] as const
          ).map(([title, changes]) =>
            changes.length ? (
              <div key={title} className="mt-3">
                <h4 className="text-sm font-semibold text-ink">
                  {title} ({changes.length})
                </h4>
                <div className="mt-2">
                  <CaseChangeList changes={changes} labels={EDIT_LABELS} personaNames={personaNames} headingLevel={5} />
                </div>
              </div>
            ) : null,
          )}
          {a.chanceUp.length + a.chanceDown.length > 0 && (
            <p className="mt-3 text-sm leading-6 text-slate">
              <span className="font-semibold text-ink">Flipped by chance:</span>{" "}
              {[
                ...a.chanceUp.map((id) => `${id} ↑`),
                ...a.chanceDown.map((id) => `${id} ↓`),
              ].join(", ")}
              . The edit could not reach these cases, so they got the same prompt as before.
            </p>
          )}
          <p className="mt-3 text-xs leading-5 text-slate">
            {edit.rerun !== null && `Reran ${plural(edit.rerun, "case")}${edit.outOf ? ` of ${edit.outOf}` : ""}. `}
            Compared with the After run of {formatTimestamp(comparison.report.baseline.createdAt)}. How flips are
            counted: {a.rule}; a case the edit can reach may still have flipped by chance.
            {a.errored.length > 0 && ` Left out because one side only errored: ${a.errored.join(", ")}.`}
            {comparison.report.factsChanged.length > 0 &&
              ` Not compared: ${comparison.report.factsChanged.join(", ")}, whose expected facts were reworded after the baseline ran.`}
          </p>
        </>
      )}
    </article>
  );
}
