import Link from "next/link";

import type { Comparison, RateCell, ScenarioResult } from "@/lib/evalData";
import {
  datasetLabel,
  deltaLabel,
  deltaPoints,
  EXPECTED_LABELS,
  formatTimestamp,
  KIND_LABELS,
  OBSERVED_LABELS,
  pct,
  runsPerCase,
} from "@/lib/evalLabels";

import { CaseChangeList } from "./CaseChangeList";
import { TestBadge, VerdictNote } from "./NoiseCheck";
import { Chip, NotGenerated } from "./ui";

function Rate({ cell, total }: { cell: RateCell; total: number }) {
  return (
    <>
      <span className="font-semibold">{pct(cell.rate)}</span>
      <span className="block text-[11px] text-slate">
        {cell.passed} of {cell.runs}
        {cell.runs !== total && " runs"}
      </span>
    </>
  );
}

/** True when either side of the comparison ran each case more than once. */
export function isRepeated(comparison: Comparison): boolean {
  const rule = comparison.report.flagRule;
  return rule !== null && Math.max(rule.baselineRepeats, rule.candidateRepeats) > 1;
}

function deltaClass(points: number | null): string {
  if (points === null || points === 0) return "text-slate";
  return points > 0 ? "text-forest" : "text-red-800";
}

export function RatesTable({ comparison, labels }: { comparison: Comparison; labels: { baseline: string; candidate: string } }) {
  const { report } = comparison;
  const rows = Object.entries(report.byDataset).map(
    ([dataset, row]) => [dataset, row, deltaPoints(row.baseline.rate, row.candidate.rate)] as const,
  );
  const overallDelta = deltaPoints(report.overall.baseline.rate, report.overall.candidate.rate);
  return (
    <table className="w-full table-fixed border-collapse text-left text-xs">
      <caption className="sr-only">
        Pass rates by dataset on the rerun cases: {labels.baseline} vs {labels.candidate}
      </caption>
      <thead>
        <tr className="border-b border-line text-[11px] uppercase tracking-wide text-slate">
          <th scope="col" className="w-[30%] py-1.5 pr-2 font-semibold sm:w-[28%]">
            Dataset
          </th>
          <th scope="col" className="hidden w-[10%] py-1.5 pr-2 font-semibold sm:table-cell">
            Cases
          </th>
          <th scope="col" className="py-1.5 pr-2 font-semibold">
            {labels.baseline}
          </th>
          <th scope="col" className="py-1.5 pr-2 font-semibold">
            {labels.candidate}
          </th>
          <th scope="col" className="py-1.5 font-semibold">
            Change
          </th>
        </tr>
      </thead>
      <tbody className="text-ink">
        {rows.map(([dataset, row, delta]) => (
          <tr key={dataset} className="border-b border-line align-top">
            <th scope="row" className="py-2 pr-2 font-medium">
              {datasetLabel(dataset)}
            </th>
            <td className="hidden py-2 pr-2 sm:table-cell">{row.total}</td>
            <td className="py-2 pr-2">
              <Rate cell={row.baseline} total={row.total} />
            </td>
            <td className="py-2 pr-2">
              <Rate cell={row.candidate} total={row.total} />
            </td>
            <td className={`py-2 font-medium ${deltaClass(delta)}`}>{deltaLabel(delta)}</td>
          </tr>
        ))}
        <tr className="align-top">
          <th scope="row" className="py-2 pr-2 font-semibold">
            All compared cases
          </th>
          <td className="hidden py-2 pr-2 font-semibold sm:table-cell">{report.overall.total}</td>
          <td className="py-2 pr-2">
            <Rate cell={report.overall.baseline} total={report.overall.total} />
          </td>
          <td className="py-2 pr-2">
            <Rate cell={report.overall.candidate} total={report.overall.total} />
          </td>
          <td className={`py-2 font-semibold ${deltaClass(overallDelta)}`}>{deltaLabel(overallDelta)}</td>
        </tr>
      </tbody>
    </table>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: "good" | "bad" | "neutral" }) {
  const colors = {
    good: "border-lime-soft bg-lime-soft text-forest",
    bad: value > 0 ? "border-red-200 bg-red-50 text-red-800" : "border-line bg-canvas text-ink",
    neutral: "border-line bg-canvas text-ink",
  }[tone];
  return (
    <div className={`rounded-xl border px-3 py-2 ${colors}`}>
      <dt className="text-[11px] font-medium uppercase tracking-wide">{label}</dt>
      <dd className="mt-0.5 text-lg font-semibold leading-6">{value}</dd>
    </div>
  );
}

export const UNSTABLE_LABEL = "Unstable";

export function TransitionStats({
  comparison,
  labels,
}: {
  comparison: Comparison;
  labels: { improved: string; regressed: string; unchanged_pass: string; unchanged_fail: string };
}) {
  const { counts } = comparison.report;
  const showUnstable = counts.unstable > 0 || isRepeated(comparison);
  return (
    <dl className={`grid grid-cols-2 gap-2 ${showUnstable ? "sm:grid-cols-5" : "sm:grid-cols-4"}`}>
      <Stat label={labels.improved} value={counts.improved} tone="good" />
      <Stat label={labels.regressed} value={counts.regressed} tone="bad" />
      <Stat label={labels.unchanged_pass} value={counts.unchanged_pass} tone="neutral" />
      <Stat label={labels.unchanged_fail} value={counts.unchanged_fail} tone="neutral" />
      {showUnstable && <Stat label={UNSTABLE_LABEL} value={counts.unstable} tone="neutral" />}
    </dl>
  );
}

const SCENARIO_LABELS = { baseline: "Baseline", candidate: "With the edit" };
const SCENARIO_COLUMNS = { baseline: "Baseline", candidate: "With edit" };
export const SCENARIO_TRANSITIONS = {
  improved: "Improved",
  regressed: "Regressed",
  unchanged_pass: "Still passing",
  unchanged_fail: "Still failing",
};

function Verdict({ verdict }: { verdict: string }) {
  const tone =
    verdict === "Passed"
      ? { box: "border-forest bg-lime-soft text-forest", mark: "✓" }
      : verdict === "Not passed"
        ? { box: "border-red-300 bg-red-50 text-red-800", mark: "✕" }
        : { box: "border-line bg-mist text-ink", mark: "?" };
  return (
    <p className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${tone.box}`}>
      <span aria-hidden="true">{tone.mark}</span>
      Verdict: {verdict || "unknown"}
    </p>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate">{label}</dt>
      <dd className="mt-0.5 text-sm leading-6 text-ink">{children}</dd>
    </div>
  );
}

function capitalize(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

export function ScenarioCard({
  result,
  caseCount,
  personaNames,
}: {
  result: ScenarioResult;
  caseCount: number;
  personaNames: Record<string, string>;
}) {
  const { scenario, comparison, run } = result;
  const report = comparison?.report;
  const hypothesis = report?.hypothesisResult;
  const headingId = `${scenario.id}-title`;
  return (
    <article
      id={scenario.id}
      aria-labelledby={headingId}
      className="scroll-mt-6 overflow-hidden rounded-2xl border border-line bg-white"
    >
      <div className="h-1.5 bg-fynn" aria-hidden="true" />
      <div className="p-4 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <Chip tone="dark">{scenario.id.toUpperCase()}</Chip>
              <Chip tone="fynn">{KIND_LABELS[scenario.kind] ?? scenario.kind}</Chip>
              {scenario.shipped && <Chip tone="lime">Shipped {scenario.shipped}</Chip>}
              <Chip mono>{scenario.skill}</Chip>
            </div>
            <h3 id={headingId} className="mt-2 text-xl font-semibold tracking-tight text-ink">
              {scenario.title}
            </h3>
          </div>
          {report && (
            <div className="flex flex-col items-start gap-1.5 sm:items-end">
              <Verdict verdict={report.verdict} />
              <TestBadge test={report.pairedTest} />
              <VerdictNote note={report.verdictNote} />
            </div>
          )}
        </div>

        <dl className="mt-4 grid gap-4 lg:grid-cols-2">
          <Field label="What changed">{scenario.change}</Field>
          <Field label="Why">{scenario.motivation}</Field>
        </dl>

        <div className="mt-4 rounded-xl border border-dashed border-line bg-canvas px-3.5 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate">Hypothesis, written before the run</p>
          <p className="mt-1 text-sm font-semibold text-ink">
            {EXPECTED_LABELS[scenario.hypothesis.expected] ?? scenario.hypothesis.expected}
          </p>
          <p className="mt-1 text-sm leading-6 text-slate">{scenario.hypothesis.detail}</p>
          {hypothesis && (
            <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink">
              <Chip tone={hypothesis.matches ? "lime" : "neutral"}>
                {hypothesis.matches ? "Matched the hypothesis" : "Did not match the hypothesis"}
              </Chip>
              <span>
                Observed: {OBSERVED_LABELS[hypothesis.observed] ?? hypothesis.observed}{" "}
                <span className="text-slate">(from the flagged counts, not a significance test)</span>.
              </span>
            </p>
          )}
        </div>

        {!comparison || !report ? (
          <div className="mt-4">
            <NotGenerated title={run ? "Regression report not generated yet" : "Results not generated yet"}>
              {run
                ? `The rerun finished (${run.cases} ${run.cases === 1 ? "case" : "cases"}${run.repeats > 1 ? `, ${run.repeats} runs each` : ""}, written ${formatTimestamp(run.createdAt)}), but its report is not in results/reports/${scenario.id}/ yet.`
                : `This scenario has not been run yet. Its results will appear here after the run and its regression report.`}
            </NotGenerated>
          </div>
        ) : (
          <>
            <dl className="mt-4 grid gap-4 lg:grid-cols-2">
              <Field label="Selection">
                <span className="font-semibold">
                  {run?.cases ?? report.selection.caseCount} of {comparison.baselineCases ?? (caseCount || "?")} cases
                  rerun.
                </span>{" "}
                <span className="text-slate">Rule: {capitalize(report.selection.rule)}.</span>
                {report.factsChanged.length > 0 && (
                  <span className="text-slate">
                    {" "}
                    Not compared: {report.factsChanged.join(", ")}, because{" "}
                    {report.factsChanged.length === 1 ? "its expected facts were" : "their expected facts were"} reworded
                    after the baseline ran.
                  </span>
                )}
              </Field>
              <Field label="Runs compared">
                <span className="text-slate">
                  Baseline: the &ldquo;{report.baseline.name || "unknown"}&rdquo; run (
                  {formatTimestamp(report.baseline.createdAt)}). With the edit: the &ldquo;
                  {report.candidate.name || "unknown"}&rdquo; run ({formatTimestamp(report.candidate.createdAt)}).{" "}
                  {report.flagRule && isRepeated(comparison)
                    ? `Each case ran ${runsPerCase(report.flagRule.baselineRepeats)} in the baseline and ${runsPerCase(report.flagRule.candidateRepeats)} with the edit.`
                    : "A case regresses when it passed in the baseline and fails with the edit."}
                </span>
              </Field>
            </dl>

            <div className="mt-4">
              <TransitionStats comparison={comparison} labels={SCENARIO_TRANSITIONS} />
            </div>

            <div className="mt-4">
              <RatesTable comparison={comparison} labels={SCENARIO_COLUMNS} />
            </div>

            <p className="mt-3 text-xs leading-5 text-slate">
              Is this more than run-to-run noise? See the{" "}
              <Link href={`/noise/results#${scenario.id}`} className="font-medium text-ink underline underline-offset-2">
                {scenario.id.toUpperCase()} noise check
              </Link>
              .
            </p>

            {(report.warnings.length > 0 ||
              comparison.notes.length > 0 ||
              report.errors.length > 0 ||
              report.baselineErrors.length > 0) && (
              <ul className="mt-3 space-y-1 text-xs leading-5 text-slate">
                {report.errors.length > 0 && <li>Cases that errored with the edit: {report.errors.join(", ")}.</li>}
                {report.baselineErrors.length > 0 && (
                  <li>Cases with an errored baseline run: {report.baselineErrors.join(", ")}.</li>
                )}
                {report.warnings.map((warning) => (
                  <li key={warning}>Warning: {warning}</li>
                ))}
                {comparison.notes.map((note) => (
                  <li key={note}>Note: {note}</li>
                ))}
              </ul>
            )}

            <div className="mt-5 space-y-4">
              <section aria-labelledby={`${scenario.id}-regressed`}>
                <h4 id={`${scenario.id}-regressed`} className="text-sm font-semibold text-ink">
                  <span className="sr-only">{scenario.id.toUpperCase()}: </span>
                  Regressed cases ({comparison.regressed.length})
                </h4>
                {comparison.regressed.length ? (
                  <div className="mt-2">
                    <CaseChangeList changes={comparison.regressed} labels={SCENARIO_LABELS} personaNames={personaNames} />
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-slate">No case regressed.</p>
                )}
              </section>
              <section aria-labelledby={`${scenario.id}-improved`}>
                <h4 id={`${scenario.id}-improved`} className="text-sm font-semibold text-ink">
                  <span className="sr-only">{scenario.id.toUpperCase()}: </span>
                  Improved cases ({comparison.improved.length})
                </h4>
                {comparison.improved.length ? (
                  <div className="mt-2">
                    <CaseChangeList changes={comparison.improved} labels={SCENARIO_LABELS} personaNames={personaNames} />
                  </div>
                ) : (
                  <p className="mt-1 text-sm text-slate">No case improved.</p>
                )}
              </section>
              {comparison.unstable.length > 0 && (
                <section aria-labelledby={`${scenario.id}-unstable`}>
                  <h4 id={`${scenario.id}-unstable`} className="text-sm font-semibold text-ink">
                    <span className="sr-only">{scenario.id.toUpperCase()}: </span>
                    Unstable cases ({comparison.unstable.length})
                  </h4>
                  <p className="mt-1 text-xs leading-5 text-slate">
                    The outcome varied across runs, but not enough for the flag rule, or the case was already unstable
                    in the baseline, so it is not counted as regressed or improved. A case marked &ldquo;Dropped
                    sharply&rdquo; or &ldquo;Rose sharply&rdquo; moved by at least {report.flagRule?.minFails ?? 1} of{" "}
                    {report.flagRule?.candidateRepeats ?? 1} runs; the flag rule leaves it out only because its baseline
                    was not stable.
                  </p>
                  <div className="mt-2">
                    <CaseChangeList changes={comparison.unstable} labels={SCENARIO_LABELS} personaNames={personaNames} />
                  </div>
                </section>
              )}
            </div>
          </>
        )}
      </div>
    </article>
  );
}
