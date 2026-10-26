import { CaseChangeList } from "@/components/evals/CaseChangeList";
import { Chip, type ChipTone } from "@/components/evals/ui";
import type { Attribution, CaseChange, Comparison, Decision } from "@/lib/evalData";
import { EXPECTED_LABELS, formatTimestamp, plural, pPhrase, runsPerCase } from "@/lib/evalLabels";

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

/** "Ship", or "Lead: ship" when the test on the cases the edit could reach does not back the decision. */
export function decisionLabel(a: Attribution): string {
  const label = DECISIONS[a.decision].label;
  return a.tested === false ? `Lead: ${label.toLowerCase()}` : label;
}

/** The reached test's p. It is stored rounded, so an exact p just above 0.05 can be stored as 0.05 itself. */
function reachedPhrase(a: Attribution): string {
  return a.reachedP === 0.05 && a.reachedSignificant === false ? "p just above 0.05" : pPhrase(a.reachedP);
}

/** A significant test on the reached cases that still leaves a Ship or Do not ship a lead: those cases moved the other way. */
function movedAgainst(a: Attribution): boolean {
  return a.decision !== "tradeoff" && a.tested === false && a.reachedSignificant === true;
}

function DecisionChip({ attribution, shipped }: { attribution: Attribution; shipped: string | null }) {
  // A lead keeps a quiet chip, so only decisions the test backs carry the decision's color.
  const tone = attribution.tested === false ? "neutral" : DECISIONS[attribution.decision].tone;
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Chip tone={tone}>{decisionLabel(attribution)}</Chip>
      {shipped && <Chip tone="dark">Shipped {shipped}</Chip>}
    </span>
  );
}

/** The report's own evidence next to the decision: the test on the reached cases, the net-change test, the prediction. */
function Evidence({ comparison }: { comparison: Comparison }) {
  const { report } = comparison;
  const test = report.pairedTest;
  const hyp = report.hypothesisResult;
  const runs = report.flagRule ? Math.max(report.flagRule.baselineRepeats, report.flagRule.candidateRepeats) : 1;
  const a = report.attribution;
  return (
    <dl className="mt-3 grid gap-x-4 gap-y-1 rounded-xl bg-canvas px-3 py-2.5 text-sm leading-6 sm:grid-cols-[11rem_minmax(0,1fr)]">
      {a && (
        <>
          <dt className="text-slate">Test on reached cases</dt>
          <dd className="text-ink">
            {a.reachedP === null
              ? runs === 1
                ? "no case it could reach flipped"
                : "no case it could reach was flagged"
              : `${reachedPhrase(a)}, ${
                  runs === 1 ? `on ${a.fixed.length} fixed against ${a.broken.length} broken` : `${runsPerCase(runs)} per case`
                } (${
                  a.decision === "tradeoff"
                    ? "a tradeoff stays a lead whatever it shows"
                    : movedAgainst(a)
                      ? "but the reached cases moved the other way, so it does not back the decision"
                      : "the one that decides"
                })`}
          </dd>
        </>
      )}
      <dt className="text-slate">Net-change test</dt>
      <dd className="text-ink">
        {test
          ? `${pPhrase(test.overall.pValue, test.alpha)} on every ${runs === 1 ? "flip" : "case"}, ${runsPerCase(runs)} per case`
          : "not run"}
      </dd>
      {hyp && (
        <>
          <dt className="text-slate">Prediction</dt>
          <dd className="text-ink">
            Written before the run: {(EXPECTED_LABELS[hyp.expected] ?? hyp.expected).replace(/^[^:]*: /, "")}. Result:{" "}
            {plural(report.transitions.improved.length, "case")} improved and {report.transitions.regressed.length}{" "}
            regressed, counting every flip. {hyp.matches ? "The prediction held." : "The prediction did not hold."}
          </dd>
        </>
      )}
    </dl>
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
          prompt; the rest count as chance.
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
                <th scope="col" className="py-2 pr-3 font-semibold">Test on reached cases</th>
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
                    <td className="py-2 pr-3 text-xs">
                      {a.reachedP !== null ? `${reachedPhrase(a)}${movedAgainst(a) ? ", the other way" : ""}` : "n/a"}
                    </td>
                    <td className="py-2">{decisionLabel(a)}{edit.shipped ? ` (shipped ${edit.shipped})` : ""}</td>
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
          <Evidence comparison={comparison} />
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
              . These were outside the edit&apos;s reach: it was not in their answering prompt, or was not the only
              thing that changed it.
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
