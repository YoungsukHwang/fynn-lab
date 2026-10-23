import type { Metadata } from "next";
import Link from "next/link";

import { CaseChangeList } from "@/components/evals/CaseChangeList";
import { Dumbbell, PairTile } from "@/components/evals/charts";
import { TestBadge, TransitionStats } from "@/components/evals/Comparison";
import { ModelList } from "@/components/evals/RunDetails";
import { NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { type CaseGroup, getBeforeAfterData, getPersonas } from "@/lib/evalData";
import { formatTimestamp, plural, pPhrase, runsPerCase } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Before vs After results" };

const SECTIONS = [
  { href: "#headline", label: "Headline" },
  { href: "#where", label: "Where they differ" },
  { href: "#skills", label: "Skills reaching the answer" },
  { href: "#cases", label: "Case by case" },
];

const BOT_LABELS = { baseline: "Before", candidate: "After" };
const BOT_TRANSITIONS = {
  improved: "Pass on After only",
  regressed: "Pass on Before only",
  unchanged_pass: "Pass on both",
  unchanged_fail: "Fail on both",
  unstable: "Varied across runs",
};

/** "Before 26 of 31, After 25 of 31" (passing runs when cases ran more than once). */
function passed(group: CaseGroup | null | undefined): string {
  if (!group?.before || !group.after) return "n/a";
  return `Before ${group.before.passed} of ${group.before.runs}, After ${group.after.passed} of ${group.after.runs}`;
}

export default async function BeforeAfterResultsPage() {
  const [data, personas] = await Promise.all([getBeforeAfterData(), getPersonas()]);
  const personaNames = Object.fromEntries(personas.map((p) => [p.id, p.name]));
  const { before, after, comparison, overall } = data;
  const cross = data.byDomains.find((g) => g.key === "cross");
  const single = data.byDomains.find((g) => g.key === "single");
  const test = comparison?.report.pairedTest ?? null;
  const routing = comparison?.report.routing ?? null;
  const lengths = comparison?.report.lengths ?? null;
  const afterMisses = routing ? routing.candidate.skills.filter((s) => s.available < s.labeled) : [];
  const repeated = (before?.meta.repeats ?? 1) > 1 || (after?.meta.repeats ?? 1) > 1;

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
      <PageHero eyebrow="Before vs After · Results" title="After wins where a question needs a second domain">
        {cross?.after && single?.after ? (
          <p>
            On the {plural(cross.after.cases, "case")} that need skills from more than one domain, the After bot passes{" "}
            {cross.after.passed}
            {repeated ? ` of ${cross.after.runs} runs` : ""} and the Before bot {cross.before?.passed ?? "n/a"}: a Before
            agent holds only one domain&apos;s skills. On the {single.after.cases} that fit in one domain{" "}
            {Math.abs((single.after.rate ?? 0) - (single.before?.rate ?? 0)) <= 0.05
              ? "the bots are about even"
              : "the gap is much smaller"}{" "}
            ({passed(single)}). So the overall rate depends on how many such questions the eval set holds.
          </p>
        ) : (
          <p>The case groups need both results files.</p>
        )}
      </PageHero>

      {data.pending.length > 0 && (
        <NotGenerated title={`${plural(data.pending.length, "case")} not in these runs yet`}>
          {data.pending.join(", ")} will show here once both bots are rerun.
        </NotGenerated>
      )}

      <OnThisPage links={SECTIONS} />

      <section aria-labelledby="headline" className="flex flex-col gap-4">
        <SectionHeader id="headline" eyebrow="Headline" title="Cases passed, and expected facts present">
          <p>
            A case passes only when the judge finds every expected fact. The share of facts present is a steadier second
            measure. {repeated ? "Counts are passing runs." : "Each case ran once per bot."}
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

      <section aria-labelledby="where" className="flex flex-col gap-4">
        <SectionHeader id="where" eyebrow="Where they differ" title="Pass rate by whether one domain is enough">
          <p>
            A case needs a second domain when its labeled skills sit in two or more of the Before bot&apos;s domains (
            <Link href="/before-after/framework#domains" className="font-medium text-ink underline underline-offset-2">
              how this is counted
            </Link>
            ).
          </p>
        </SectionHeader>
        <Dumbbell
          id="groups"
          title="Pass rate on each bot"
          description="On the highlighted row a Before agent always lacks one of a case's skills; elsewhere only a misrouted message does."
          caption="Pass rate on each bot, by whether a case needs a second domain"
          emphasisLabel="Can differ"
          groups={[
            {
              title: "Is one domain enough?",
              rows: [
                ...data.byDomains.map((g) => ({ ...g, emphasis: g.key === "cross" })),
                ...(overall ? [{ ...overall, note: "" }] : []),
              ],
            },
          ]}
        />
        <p className="text-sm leading-6 text-slate">
          LLM answers vary, so the same case can pass once and fail the next time. The net-change test asks whether the
          overall gap is bigger than that.{" "}
          {test &&
            `Here it gives ${pPhrase(test.overall.pValue, test.alpha)}, from the cases ${
              repeated ? "whose runs did not all agree" : "that flipped"
            }.`}
        </p>
      </section>

      {routing && (
        <section aria-labelledby="skills" className="flex flex-col gap-4">
          <SectionHeader id="skills" eyebrow="Skills reaching the answer" title="Did the answering agent get every skill it needed?">
            <p>
              A case is labeled with the topic skills its answer needs. A Before agent has every skill of its one domain;
              the After agent has the skills its router picked.
            </p>
          </SectionHeader>
          <PairTile
            label={`${repeated ? "Runs" : "Cases"} where every labeled skill reached the agent`}
            unit={repeated ? "runs" : "cases"}
            before={{ value: routing.baseline.allAvailable, of: routing.baseline.runs }}
            after={{ value: routing.candidate.allAvailable, of: routing.candidate.runs }}
            hint={`needing a second domain: Before ${routing.baseline.byGroup.cross.allAvailable} of ${routing.baseline.byGroup.cross.runs}, After ${routing.candidate.byGroup.cross.allAvailable} of ${routing.candidate.byGroup.cross.runs}`}
          />
          <p className="text-sm leading-6 text-slate">
            {afterMisses.length
              ? `The After router left out a labeled skill in ${plural(
                  routing.candidate.runs - routing.candidate.allAvailable,
                  repeated ? "run" : "case",
                )} (missing: ${afterMisses.map((s) => s.name).join(", ")}).`
              : "The After router picked every labeled skill."}{" "}
            {lengths &&
              `Replies run long on both bots: a median of ${lengths.baseline.medianWords} words for Before and ${lengths.candidate.medianWords} for After, and ${lengths.baseline.overLimit} of ${lengths.baseline.replies} and ${lengths.candidate.overLimit} of ${lengths.candidate.replies} replies go over the ${lengths.candidate.limit}-word rule, which nothing grades.`}
          </p>
        </section>
      )}

      <section aria-labelledby="cases" className="flex flex-col gap-4">
        <SectionHeader id="cases" eyebrow="Case by case" title="The cases that came out differently">
          <p>Open a case to read both replies and why the judge failed one of them.</p>
        </SectionHeader>
        {comparison ? (
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate">How each of the {comparison.report.overall.total} cases came out.</p>
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
                    {BOT_TRANSITIONS[key]} ({changes.length})
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
          </div>
        ) : (
          <NotGenerated title="Case-by-case report not generated yet">
            results/reports/before-vs-after/report.json does not exist yet.
          </NotGenerated>
        )}
        <p className="text-xs leading-5 text-slate">
          Before: {before ? `${formatTimestamp(before.meta.createdAt)}, ${runsPerCase(before.meta.repeats)} per case` : "not run"}.
          After: {after ? `${formatTimestamp(after.meta.createdAt)}, ${runsPerCase(after.meta.repeats)} per case` : "not run"}.
        </p>
        {after?.meta.models && <ModelList models={after.meta.models} />}
      </section>
    </div>
  );
}
