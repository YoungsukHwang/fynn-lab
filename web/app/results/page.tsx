import type { Metadata } from "next";

import { CaseChangeList } from "@/components/evals/CaseChangeList";
import { type BarGroup, RateBars } from "@/components/evals/RateBars";
import { ScenarioCard, TransitionStats } from "@/components/evals/ScenarioCard";
import { NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { type Bucket, getPersonas, getResultsData, type Models, type RunMeta } from "@/lib/evalData";
import { DATASET_INFO, datasetLabel, formatTimestamp, pct, questionsLabel } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Monitoring results" };

const SECTIONS = [
  { href: "#before-vs-after", label: "Before vs After" },
  { href: "#scenarios", label: "Skill-edit scenarios" },
  { href: "#runs", label: "Run details" },
];

const BOT_LABELS = { baseline: "Before", candidate: "After" };
const BOT_TRANSITIONS = {
  improved: "Pass on After only",
  regressed: "Pass on Before only",
  unchanged_pass: "Pass on both",
  unchanged_fail: "Fail on both",
};

function casesNote(...buckets: (Bucket | undefined)[]): string | undefined {
  const total = buckets.find((b) => b && b.total > 0)?.total;
  return total ? `${total} ${total === 1 ? "case" : "cases"}` : undefined;
}

function OverallTile({ label, tone, bucket }: { label: string; tone: "before" | "after"; bucket: Bucket | null }) {
  const colors = tone === "before" ? { bar: "bg-peach", text: "text-ember" } : { bar: "bg-fynn", text: "text-cobalt" };
  const width = bucket && typeof bucket.rate === "number" ? bucket.rate * 100 : 0;
  return (
    <div className="rounded-xl border border-line bg-white p-4">
      <p className={`text-sm font-semibold ${colors.text}`}>{label}</p>
      {bucket && bucket.total > 0 ? (
        <>
          <p className="mt-1 text-4xl font-semibold tracking-tight text-ink">{pct(bucket.rate)}</p>
          <p className="text-sm text-slate">
            {bucket.passed} of {bucket.total} cases passed{bucket.errors ? `, ${bucket.errors} errors` : ""}
          </p>
          <span aria-hidden="true" className="mt-3 block h-3 overflow-hidden rounded-full bg-mist">
            <span className={`block h-full rounded-full ${colors.bar}`} style={{ width: `${width}%` }} />
          </span>
        </>
      ) : (
        <p className="mt-1 text-sm text-slate">Not run yet.</p>
      )}
    </div>
  );
}

function sameModels(runs: RunMeta[]): Models | null {
  const first = runs[0]?.models;
  if (!first) return null;
  const same = runs.every(
    (run) =>
      run.models?.router === first.router && run.models?.agent === first.agent && run.models?.judge === first.judge,
  );
  return same ? first : null;
}

function ModelList({ models }: { models: Models }) {
  return (
    <dl className="grid gap-2 sm:grid-cols-3">
      {(
        [
          ["Router (both bots)", models.router],
          ["Answering agent", models.agent],
          ["Judge", models.judge],
        ] as const
      ).map(([label, model]) => (
        <div key={label} className="rounded-xl bg-canvas px-3 py-2">
          <dt className="text-[11px] font-medium uppercase tracking-wide text-slate">{label}</dt>
          <dd className="mt-0.5 font-mono text-xs text-ink">{model}</dd>
        </div>
      ))}
    </dl>
  );
}

export default async function ResultsPage() {
  const [data, personas] = await Promise.all([getResultsData(), getPersonas()]);
  const personaNames = Object.fromEntries(personas.map((p) => [p.id, p.name]));
  const { before, after, beforeVsAfter } = data;

  const intentGroups: BarGroup[] = ["1", "2", "3"].map((n) => ({
    key: n,
    label: questionsLabel(n),
    note: casesNote(after?.summary.byIntents[n], before?.summary.byIntents[n]),
    series: [
      { label: "Before", tone: "before", bucket: before?.summary.byIntents[n] ?? null },
      { label: "After", tone: "after", bucket: after?.summary.byIntents[n] ?? null },
    ],
  }));
  const datasetKeys = Object.keys(DATASET_INFO);
  const datasetGroups: BarGroup[] = datasetKeys.map((dataset) => ({
    key: dataset,
    label: datasetLabel(dataset),
    note: casesNote(after?.summary.byDataset[dataset], before?.summary.byDataset[dataset]),
    series: [
      { label: "Before", tone: "before", bucket: before?.summary.byDataset[dataset] ?? null },
      { label: "After", tone: "after", bucket: after?.summary.byDataset[dataset] ?? null },
    ],
  }));
  const groupSizes = [...intentGroups, ...datasetGroups]
    .flatMap((group) => group.series.map((series) => series.bucket?.total ?? 0))
    .filter((total) => total > 0);
  const smallest = groupSizes.length ? Math.min(...groupSizes) : null;
  const largest = groupSizes.length ? Math.max(...groupSizes) : null;
  const commonModels = sameModels(data.runs);
  // report.py always warns that the bots differ here; that is the point of this comparison, so drop it.
  const beforeVsAfterWarnings = (beforeVsAfter?.report.warnings ?? []).filter((w) => !w.startsWith("bots differ"));

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Monitoring results" title="What the regression tests found">
        <p>
          Offline regression testing on a fixed eval set of {data.caseCount || "the"} cases: first the Before bot
          against the After bot, then three skill edits to the After bot. Each case runs once per bot, and there are no
          significance tests yet, so read small differences with care.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      {!data.hasAnyResults && (
        <NotGenerated>
          No results files were found when this site was built. Run the evals and regression reports (see
          &ldquo;Running the evals&rdquo; in the README), then rebuild the site. The hypotheses for the three
          scenarios are shown below.
        </NotGenerated>
      )}

      {/* A. Before vs After */}
      <section aria-labelledby="before-vs-after" className="flex flex-col gap-4">
        <SectionHeader id="before-vs-after" eyebrow="A · Architecture" title="Before vs After">
          <p>
            Both bots answer every case with the same skill files, member profiles and answer model; only how each bot
            routes the message and assembles its prompt differs. A case passes when the code checks pass and the judge
            grades every expected fact PRESENT.
          </p>
        </SectionHeader>

        {!before && !after ? (
          <NotGenerated>Neither before.json nor after.json exists yet.</NotGenerated>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <OverallTile label="Before: single-agent router" tone="before" bucket={before?.summary.overall ?? null} />
              <OverallTile label="After: skill-based" tone="after" bucket={after?.summary.overall ?? null} />
            </div>

            <div className="grid gap-3 lg:grid-cols-2">
              <RateBars
                emphasis
                title="Pass rate by number of questions in the message"
                description="A message with several questions often spans several domains, while the Before bot's router hands it to one domain's agent."
                groups={intentGroups}
              />
              <RateBars title="Pass rate by dataset" groups={datasetGroups} />
            </div>

            <p className="rounded-xl border border-dashed border-line bg-white px-4 py-3 text-xs leading-5 text-slate">
              Single run per case, with no repeated runs or significance testing yet.
              {smallest !== null &&
                ` With ${smallest === largest ? smallest : `${smallest} to ${largest}`} cases per group, a difference of one or two cases can be noise.`}
            </p>

            {beforeVsAfter ? (
              <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
                <h3 className="text-base font-semibold text-ink">Case by case</h3>
                <p className="mt-1 text-sm leading-6 text-slate">
                  How each of the {beforeVsAfter.report.overall.total} cases came out on the two bots.
                </p>
                <div className="mt-3">
                  <TransitionStats comparison={beforeVsAfter} labels={BOT_TRANSITIONS} />
                </div>
                {(
                  [
                    ["improved", beforeVsAfter.improved],
                    ["regressed", beforeVsAfter.regressed],
                  ] as const
                ).map(([key, changes]) =>
                  changes.length > 0 ? (
                    <div key={key} className="mt-4">
                      <h4 className="text-sm font-semibold text-ink">
                        {BOT_TRANSITIONS[key]} ({changes.length})
                      </h4>
                      <div className="mt-2">
                        <CaseChangeList changes={changes} labels={BOT_LABELS} personaNames={personaNames} />
                      </div>
                    </div>
                  ) : null,
                )}
                {(beforeVsAfterWarnings.length > 0 || beforeVsAfter.notes.length > 0) && (
                  <ul className="mt-3 space-y-1 text-xs leading-5 text-slate">
                    {beforeVsAfterWarnings.map((warning) => (
                      <li key={warning}>Warning: {warning}</li>
                    ))}
                    {beforeVsAfter.notes.map((note) => (
                      <li key={note}>Note: {note}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <NotGenerated title="Case-by-case report not generated yet">
                results/reports/before-vs-after/report.json does not exist yet, so the cases that pass on only one
                bot are not listed.
              </NotGenerated>
            )}
          </>
        )}
      </section>

      {/* B. Scenarios */}
      <section aria-labelledby="scenarios" className="flex flex-col gap-4">
        <SectionHeader id="scenarios" eyebrow="B · Skill edits" title="Three skill edits to the After bot">
          <p>
            Each edit goes through the regression loop: only the cases that depend on it are rerun, then compared with
            the After bot&apos;s full run. The verdict is Passed when no case regressed.
          </p>
          {data.scenarios.some((s) => s.comparison) && (
            <p>
              Each case ran once on each side, so a single case that flips either way may be run-to-run variation
              rather than an effect of the edit. Read the verdicts as what this one run showed.
            </p>
          )}
        </SectionHeader>
        {data.scenarios.length ? (
          data.scenarios.map((result) => (
            <ScenarioCard
              key={result.scenario.id}
              result={result}
              caseCount={data.caseCount}
              personaNames={personaNames}
            />
          ))
        ) : (
          <NotGenerated title="Scenarios not found">No scenario.yaml files were found in scenarios/.</NotGenerated>
        )}
      </section>

      {/* C. Run metadata */}
      <section aria-labelledby="runs" className="flex flex-col gap-4">
        <SectionHeader id="runs" eyebrow="C · Metadata" title="Run details">
          <p>Every results file read for this page. Times are when each run finished writing its results.</p>
        </SectionHeader>
        {data.runs.length ? (
          <>
            {commonModels && (
              <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
                <h3 className="text-sm font-semibold text-ink">Models (the same in every run)</h3>
                <div className="mt-2">
                  <ModelList models={commonModels} />
                </div>
              </div>
            )}
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {data.runs.map((run) => (
                <li key={run.file} className="rounded-2xl border border-line bg-white p-4">
                  <p className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-sm font-semibold text-ink">{run.name || run.file}</span>
                    <span className="font-mono text-xs text-slate">results/{run.file}</span>
                  </p>
                  <dl className="mt-2 grid grid-cols-[6rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs leading-5">
                    <dt className="text-slate">Bot</dt>
                    <dd className="text-ink">{run.bot === "before" ? "Before" : run.bot === "after" ? "After" : run.bot}</dd>
                    {run.scenario && (
                      <>
                        <dt className="text-slate">Scenario</dt>
                        <dd className="text-ink">{run.scenario.toUpperCase()}</dd>
                      </>
                    )}
                    <dt className="text-slate">Written</dt>
                    <dd className="text-ink">{formatTimestamp(run.createdAt)}</dd>
                    <dt className="text-slate">Cases</dt>
                    <dd className="text-ink">
                      {run.total} run, {run.passed} passed ({pct(run.rate)}), {run.errors} errors
                    </dd>
                    {run.selectionRule && (
                      <>
                        <dt className="text-slate">Selection</dt>
                        <dd className="text-ink">{run.selectionRule}</dd>
                      </>
                    )}
                  </dl>
                  {!commonModels && run.models && (
                    <div className="mt-3">
                      <ModelList models={run.models} />
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <NotGenerated>No results files were found in the results directory when the site was built.</NotGenerated>
        )}
      </section>
    </div>
  );
}
