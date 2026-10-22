import type { Metadata } from "next";
import Link from "next/link";

import { CaseChangeList } from "@/components/evals/CaseChangeList";
import { Dumbbell, PairTile } from "@/components/evals/charts";
import { TestBadge } from "@/components/evals/NoiseCheck";
import { ModelList } from "@/components/evals/RunDetails";
import { TransitionStats, UNSTABLE_LABEL } from "@/components/evals/ScenarioCard";
import { NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { type CaseGroup, getBeforeAfterData, getPersonas } from "@/lib/evalData";
import { datasetLabel, deltaLabel, deltaPoints, formatTimestamp, pct, plural, pPhrase, runsPerCase } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Before vs After results" };

const SECTIONS = [
  { href: "#headline", label: "Headline" },
  { href: "#where", label: "Where they differ" },
  { href: "#cases", label: "Case by case" },
];

const BOT_LABELS = { baseline: "Before", candidate: "After" };
const BOT_TRANSITIONS = {
  improved: "Pass on After only",
  regressed: "Pass on Before only",
  unchanged_pass: "Pass on both",
  unchanged_fail: "Fail on both",
};

function vsLine(group: CaseGroup | null | undefined, what: "pass" | "facts"): string {
  if (!group?.before || !group.after) return "n/a";
  const [b, a] = [group.before, group.after];
  return what === "pass"
    ? `Before ${b.passed} of ${b.runs}, After ${a.passed} of ${a.runs}`
    : `Before ${b.factsPresent} of ${b.factsGraded}, After ${a.factsPresent} of ${a.factsGraded}`;
}

function points(group: CaseGroup | null | undefined): number | null {
  return deltaPoints(group?.before?.rate, group?.after?.rate);
}

export default async function BeforeAfterResultsPage() {
  const [data, personas] = await Promise.all([getBeforeAfterData(), getPersonas()]);
  const personaNames = Object.fromEntries(personas.map((p) => [p.id, p.name]));
  const { before, after, comparison, overall } = data;
  const cross = data.byDomains.find((g) => g.key === "cross");
  const single = data.byDomains.find((g) => g.key === "single");
  const test = comparison?.report.pairedTest ?? null;
  const repeated = (before?.meta.repeats ?? 1) > 1 || (after?.meta.repeats ?? 1) > 1;
  // Datasets where both bots are at 90% or more: they leave no room to tell the designs apart.
  const ceiling = data.byDataset
    .filter((g) => (g.before?.rate ?? 0) >= 0.9 && (g.after?.rate ?? 0) >= 0.9)
    .map((g) => datasetLabel(g.key));
  const mismatch = overall?.after && after && overall.after.cases !== after.meta.cases;

  if (!before && !after) {
    return (
      <div className="flex flex-col gap-6">
        <PageHero eyebrow="Before vs After · Results" title="What the eval found">
          <p>Neither results/before.json nor results/after.json exists yet.</p>
        </PageHero>
        <NotGenerated>Run both bots on the eval set (see &ldquo;Running the evals&rdquo; in the README), then rebuild.</NotGenerated>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Before vs After · Results" title="Where the two designs can differ">
        <p>
          The After bot passes {pct(overall?.after?.rate)} of the cases against {pct(overall?.before?.rate)} for the
          Before bot.
          {cross?.after && single?.after && (
            <>
              {" "}
              Its lead is {deltaLabel(points(cross))} on the {plural(cross.after.cases, "case")} that need a second
              domain, where a Before agent lacks some of the skills, and {deltaLabel(points(single))} on the{" "}
              {single.after.cases} that fit in one.
            </>
          )}
        </p>
      </PageHero>

      {data.pending.length > 0 && (
        <NotGenerated title={`${plural(data.pending.length, "case")} not in these runs yet`}>
          The eval set has grown since these results were written. {data.pending.length === 1 ? "This case" : "These cases"}{" "}
          ({data.pending.length > 6 ? `${data.pending[0]} to ${data.pending[data.pending.length - 1]}` : data.pending.join(", ")})
          {data.pending.length === 1 ? " is" : " are"} on the{" "}
          <Link href="/before-after/framework#eval-set" className="font-medium text-ink underline underline-offset-2">
            Framework tab
          </Link>{" "}
          and will show here once both bots are rerun.
        </NotGenerated>
      )}

      <OnThisPage links={SECTIONS} />

      {/* Headline */}
      <section aria-labelledby="headline" className="flex flex-col gap-4">
        <SectionHeader id="headline" eyebrow="Headline" title="Cases passed, and expected facts present">
          <p>
            A case passes only when the judge finds every expected fact, so one missed clause fails it. The share of
            facts present is a steadier second measure.{" "}
            {repeated
              ? `Rates are over every run (Before ${runsPerCase(before?.meta.repeats ?? 1)}, After ${runsPerCase(after?.meta.repeats ?? 1)} per case).`
              : "Each case ran once per bot."}
          </p>
        </SectionHeader>
        <div className="grid gap-3 lg:grid-cols-2">
          <PairTile
            label="Cases passed"
            unit={repeated ? "runs" : "cases"}
            before={overall?.before ? { value: overall.before.passed, of: overall.before.runs } : null}
            after={overall?.after ? { value: overall.after.passed, of: overall.after.runs } : null}
            hint={test ? `net-change test ${pPhrase(test.overall.pValue, test.alpha)}` : undefined}
          />
          <PairTile
            label="Expected facts present"
            unit="facts"
            before={overall?.before ? { value: overall.before.factsPresent, of: overall.before.factsGraded } : null}
            after={overall?.after ? { value: overall.after.factsPresent, of: overall.after.factsGraded } : null}
            hint="every fact the judge graded"
          />
        </div>
      </section>

      {/* Where they differ */}
      <section aria-labelledby="where" className="flex flex-col gap-4">
        <SectionHeader id="where" eyebrow="Where they differ" title="Pass rate by group">
          <p>
            A case needs a second domain when its labeled skills sit in two or more of the Before bot&apos;s domains (
            <Link href="/before-after/framework#domains" className="font-medium text-ink underline underline-offset-2">
              how this is counted
            </Link>
            ). Hover or focus a row for the counts, or open the table under the chart.
          </p>
        </SectionHeader>

        <Dumbbell
          id="groups"
          title="Pass rate on each bot"
          description="Only in the highlighted group can a Before agent lack one of a case's labeled skills."
          caption="Pass rate on each bot, by whether a case needs a second domain, by number of questions and by dataset"
          emphasisLabel="Can differ"
          groups={[
            {
              title: "Is one domain enough?",
              rows: [
                ...data.byDomains.map((g) => ({ ...g, emphasis: g.key === "cross" })),
                ...(overall ? [{ ...overall, note: "" }] : []),
              ],
            },
            {
              title: "Needs a second domain, by questions",
              rows: data.crossByQuestions.map((g) => ({ ...g, label: `${g.label}, second domain` })),
            },
            {
              title: "Questions in the message",
              note: "several questions often span several domains",
              rows: data.byQuestions,
            },
            {
              title: "Dataset",
              note: ceiling.length ? `${ceiling.join(" and ")} at 90% or more on both bots` : undefined,
              rows: data.byDataset.map((g) => ({ ...g, label: datasetLabel(g.key) })),
            },
          ]}
        />

        <div className="rounded-2xl border border-dashed border-line bg-white px-4 py-3 text-sm leading-6 text-slate">
          <p className="font-semibold text-ink">How to read this</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 marker:text-dim">
            {single?.before && single.after && (
              <li>
                {plural(single.after.cases, "case")} fit in one Before domain. There the Before agent already holds every
                labeled skill, plus its domain neighbors, while After loads only the skills it routes to. Passed:{" "}
                {vsLine(single, "pass")}. Flips here come from that difference in context, or from run-to-run noise, not
                from missing guidance.
              </li>
            )}
            {cross?.before && cross.after && (
              <li>
                {plural(cross.after.cases, "case")} need a second domain, where a Before agent lacks some labeled skills.
                Passed: {vsLine(cross, "pass")}. Facts present: {vsLine(cross, "facts")}.
                {data.crossByQuestions.length > 1 &&
                  ` By number of questions: ${data.crossByQuestions.map((g) => `${g.label}, ${deltaLabel(points(g))}`).join("; ")}.`}
              </li>
            )}
            <li>
              These groups are small, so read them as where to look rather than as findings. The{" "}
              <Link href="/noise/results#before-vs-after" className="font-medium text-ink underline underline-offset-2">
                noise check
              </Link>{" "}
              says how much of the overall gap could be chance, and the cases below show what changed.
            </li>
            {mismatch && (
              <li>
                The case files list {overall?.after?.cases} of the {after?.meta.cases} cases in the results file; the
                groups use only cases in both.
              </li>
            )}
          </ul>
        </div>
      </section>

      {/* Case by case */}
      <section aria-labelledby="cases" className="flex flex-col gap-4">
        <SectionHeader id="cases" eyebrow="Case by case" title="The cases that came out differently">
          <p>Open a case to read both replies and why the judge failed one of them.</p>
        </SectionHeader>
        {comparison ? (
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate">
                How each of the {comparison.report.overall.total} cases came out on the two bots.
              </p>
              <TestBadge test={test} />
            </div>
            <div className="mt-3">
              <TransitionStats comparison={comparison} labels={BOT_TRANSITIONS} />
            </div>
            {(
              [
                ["improved", comparison.improved],
                ["regressed", comparison.regressed],
                ["unstable", comparison.unstable],
              ] as const
            ).map(([key, changes]) =>
              changes.length > 0 ? (
                <div key={key} className="mt-4">
                  <h3 className="text-sm font-semibold text-ink">
                    {key === "unstable" ? UNSTABLE_LABEL : BOT_TRANSITIONS[key]} ({changes.length})
                  </h3>
                  <div className="mt-2">
                    <CaseChangeList
                      changes={changes}
                      labels={BOT_LABELS}
                      personaNames={personaNames}
                      tag={{ ids: data.crossDomain.ids, label: "Needs a second domain" }}
                      headingLevel={4}
                    />
                  </div>
                </div>
              ) : null,
            )}
            {comparison.notes.length > 0 && (
              <ul className="mt-3 space-y-1 text-xs leading-5 text-slate">
                {comparison.notes.map((note) => (
                  <li key={note}>Note: {note}</li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <NotGenerated title="Case-by-case report not generated yet">
            results/reports/before-vs-after/report.json does not exist yet, so the cases that pass on only one bot are
            not listed.
          </NotGenerated>
        )}

        <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
          <h3 className="text-sm font-semibold text-ink">Runs compared</h3>
          <p className="mt-1 text-xs leading-5 text-slate">
            Before: {before ? `${formatTimestamp(before.meta.createdAt)}, ${runsPerCase(before.meta.repeats)} per case` : "not run"}.
            After: {after ? `${formatTimestamp(after.meta.createdAt)}, ${runsPerCase(after.meta.repeats)} per case` : "not run"}.
          </p>
          {after?.meta.models && (
            <div className="mt-2">
              <ModelList models={after.meta.models} />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
