import type { Metadata } from "next";
import Link from "next/link";

import { CaseChangeList } from "@/components/evals/CaseChangeList";
import { Dumbbell, PairTile } from "@/components/evals/charts";
import { TestBadge, TransitionStats } from "@/components/evals/Comparison";
import { ModelList } from "@/components/evals/RunDetails";
import { NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { type CaseGroup, getBeforeAfterData, getHoldoutData, getPersonas } from "@/lib/evalData";
import { formatTimestamp, pct, plural, pPhrase, runsPerCase } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Before vs After results" };

const HOLDOUT_PLAN = "https://github.com/YoungsukHwang/fynn-lab/blob/main/backend/evals/holdout/README.md";

const SECTIONS = [
  { href: "#where", label: "Where they differ" },
  { href: "#holdout", label: "Held-out check" },
  { href: "#mix", label: "Traffic mix" },
  { href: "#overall", label: "Overall" },
  { href: "#skills", label: "Skills reaching the answer" },
  { href: "#cases", label: "Case by case" },
];

const BOT_LABELS = { baseline: "Before", candidate: "After" };
const LINK = "font-medium text-ink underline underline-offset-2";
// Share of member questions that need a second domain; nobody has measured it for this product.
const MIX = [0.05, 0.1, 0.2, 0.3];

/** "Before 26 of 31, After 25 of 31" (passing runs when cases ran more than once). */
function passed(group: CaseGroup | null | undefined): string {
  if (!group?.before || !group.after) return "n/a";
  return `Before ${group.before.passed} of ${group.before.runs}, After ${group.after.passed} of ${group.after.runs}`;
}

/** After's pass rate minus Before's, in rate units; null when a side is missing. */
function gap(group: CaseGroup | null | undefined): number | null {
  const before = group?.before?.rate;
  const after = group?.after?.rate;
  return before == null || after == null ? null : after - before;
}

const points = (rate: number) => `${rate >= 0 ? "+" : ""}${Math.round(rate * 100)} pts`;

export default async function BeforeAfterResultsPage() {
  const [data, personas, holdout] = await Promise.all([getBeforeAfterData(), getPersonas(), getHoldoutData()]);
  const holdoutCross = holdout.byDomains.find((g) => g.key === "holdout-cross");
  const holdoutSingle = holdout.byDomains.find((g) => g.key === "holdout-single");
  const holdoutTest = holdout.report?.pairedTest?.overall ?? null;
  const personaNames = Object.fromEntries(personas.map((p) => [p.id, p.name]));
  const { before, after, comparison, overall } = data;
  const cross = data.byDomains.find((g) => g.key === "cross");
  const single = data.byDomains.find((g) => g.key === "single");
  const designed = data.byConstruction.find((g) => g.key === "designed");
  const organic = data.byConstruction.find((g) => g.key === "organic");
  const test = comparison?.report.pairedTest ?? null;
  const routing = comparison?.report.routing ?? null;
  const lengths = comparison?.report.lengths ?? null;
  const cost = comparison?.report.costPer1000 ?? null;
  const flag = comparison?.report.flagRule ?? null;
  const afterMisses = routing ? routing.candidate.skills.filter((s) => s.available < s.labeled) : [];
  const repeated = (before?.meta.repeats ?? 1) > 1 || (after?.meta.repeats ?? 1) > 1;
  const unit = repeated ? "runs" : "cases";
  const saving =
    cost?.baseline && cost.candidate ? Math.round((100 * (cost.baseline - cost.candidate)) / cost.baseline) : null;
  const sharp = comparison?.report.sharpChanges.dropped ?? [];

  // The flag rule in words, so the case-by-case labels say what they count.
  const k = flag?.candidateRepeats ?? 1;
  const m = flag?.minFails ?? 1;
  const transitions = repeated
    ? {
        improved: `After passes ${m}+ of ${k}, Before none`,
        regressed: `Before passes all ${k}, After fails ${m}+`,
        unchanged_pass: "Pass on both, every run",
        unchanged_fail: "Fail on both, every run",
        unstable: "Runs did not all agree",
      }
    : {
        improved: "Pass on After only",
        regressed: "Pass on Before only",
        unchanged_pass: "Pass on both",
        unchanged_fail: "Fail on both",
        unstable: "Runs did not all agree",
      };

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

  const crossGap = gap(cross);
  const organicGap = gap(organic);
  const singleGap = gap(single);

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Before vs After · Results" title="After wins where a question needs a second domain">
        {cross?.after && cross.before && single?.after && single.before ? (
          <>
            <p>
              On questions that need skills from a second domain, After passes {pct(cross.after.rate)} of {unit} and
              Before {pct(cross.before.rate)}: a Before agent holds only one domain&apos;s skills. On questions one domain
              covers, {Math.abs(singleGap ?? 0) <= 0.05 ? "the two are about even" : "the gap is much smaller"} (
              {pct(single.before.rate)} and {pct(single.after.rate)})
              {saving !== null && saving > 0 ? `, and After costs about ${saving}% less per reply` : ""}.
            </p>
            {designed?.after && designed.before && organic?.after && organic.before && (
              <p>
                {plural(designed.after.cases, "of the multi-domain case")} were written for this comparison around facts
                a Before agent lacks, and Before rarely passes them ({passed(designed)}). On the other{" "}
                {plural(organic.after.cases, "multi-domain case")} the gap is smaller but still there ({passed(organic)}).
              </p>
            )}
            {holdoutCross?.after && holdoutCross.before && (
              <p>
                On {holdout.caseCount} held-out questions, written after the skills were frozen, the pattern held: on
                those needing a second domain, {passed(holdoutCross)}.
              </p>
            )}
          </>
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

      <section aria-labelledby="where" className="flex flex-col gap-4">
        <SectionHeader id="where" eyebrow="Where they differ" title="Pass rate by kind of question">
          <p>
            A case needs a second domain when its labeled skills sit in two or more of the Before bot&apos;s domains (
            <Link href="/before-after/framework#domains" className={LINK}>
              how this is counted
            </Link>
            ). Most of those cases were written for this comparison, with every extra question built around a fact only
            another domain&apos;s skill held, so they show the mechanism; the other multi-domain cases show how big the
            gap is when a case was not built around the Before domains.
          </p>
        </SectionHeader>
        <Dumbbell
          id="groups"
          title={`Pass rate on each bot${repeated ? ", over all runs" : ""}`}
          description="On the multi-domain rows a Before agent always lacks one of a case's skills; on the one-domain row only a misrouted message does."
          caption="Pass rate on each bot, by kind of question"
          emphasisLabel="Can differ"
          groups={[
            {
              title: "Kind of question",
              rows: data.byConstruction.map((g) => ({ ...g, emphasis: g.key !== "single" })),
            },
          ]}
        />
      </section>

      {holdout.overall?.after && holdout.overall.before && (
        <section aria-labelledby="holdout" className="flex flex-col gap-4">
          <SectionHeader id="holdout" eyebrow="Held-out check" title={`On ${holdout.caseCount} questions the skills were never tuned to`}>
            <p>
              The skill edits were made by reading failures on the main set, so part of its gap could be tuning. These
              cases were written after the skills were frozen, by drafting agents that never saw an eval result, and
              committed with written expectations before either bot ran on them (
              <a href={HOLDOUT_PLAN} className={LINK}>
                the plan
              </a>
              ). Same skills, code and models as the main run, three runs per case.
            </p>
          </SectionHeader>
          <Dumbbell
            id="holdout-groups"
            title="Pass rate on each bot, held-out cases and the main set"
            description="Held-out rows first; the main set's rows are repeated for comparison."
            caption="Pass rate on each bot, held-out and main set, by kind of question"
            emphasisLabel="Can differ"
            groups={[
              { title: "Held-out cases", rows: holdout.byDomains.map((g) => ({ ...g, emphasis: g.key === "holdout-cross" })) },
              { title: "Main set", rows: data.byConstruction.map((g) => ({ ...g, emphasis: g.key !== "single" })) },
            ]}
          />
          <p className="text-sm leading-6 text-slate">
            {holdoutTest?.meanDiff != null &&
              `Across all ${holdout.caseCount} held-out cases: ${passed(holdout.overall)} runs, a mean gain of ${points(
                holdoutTest.meanDiff,
              )} per case (${pPhrase(holdoutTest.pValue)} on the run-permutation test), with ${plural(
                holdout.report?.transitions.improved.length ?? 0,
                "case",
              )} better on After and ${holdout.report?.transitions.regressed.length ?? 0} worse. `}
            Two of the three expectations written beforehand did not hold. The gap on held-out questions that need a
            second domain came out close to the main set&apos;s designed cases, not its other multi-domain cases,
            mostly because After passed every run; and After passed more of the held-out runs than of the main
            set&apos;s, not fewer. The one-domain expectation held
            {holdoutSingle?.after && holdoutSingle.before ? ` (${passed(holdoutSingle)})` : ""}. It is a small check,
            and its cases were written by LLM agents from the same skill files the facts come from, so it is not
            independent of how the facts were sourced.
          </p>
        </section>
      )}

      {crossGap !== null && singleGap !== null && (
        <section aria-labelledby="mix" className="flex flex-col gap-4">
          <SectionHeader id="mix" eyebrow="Traffic mix" title="What the gap would be on real traffic">
            <p>
              The overall gain depends on how often members ask questions that need a second domain, which nobody has
              measured here. It is the share of such questions times their gap, plus the rest times the one-domain gap.
              The lower figure uses only the multi-domain cases not written for this comparison.
            </p>
          </SectionHeader>
          <div className="overflow-x-auto rounded-2xl border border-line bg-white">
            <table className="w-full min-w-[30rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate">
                  <th className="px-4 py-3">Share needing a second domain</th>
                  <th className="px-4 py-3 text-right">Expected gain, other multi-domain cases</th>
                  <th className="px-4 py-3 text-right">Expected gain, all multi-domain cases</th>
                </tr>
              </thead>
              <tbody>
                {MIX.map((share) => (
                  <tr key={share} className="border-b border-line last:border-0">
                    <td className="px-4 py-3 font-medium text-ink">{Math.round(share * 100)}%</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {organicGap === null ? "n/a" : points(share * organicGap + (1 - share) * singleGap)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{points(share * crossGap + (1 - share) * singleGap)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section aria-labelledby="overall" className="flex flex-col gap-4">
        <SectionHeader id="overall" eyebrow="Overall" title="On this eval set as a whole">
          <p>
            These totals mix the kinds of question in the proportions this eval set was built with, so read them with
            the table above. A case passes only when the judge finds every expected fact; the share of facts present is a
            steadier second measure. {repeated ? "Counts are passing runs." : "Each case ran once per bot."}
          </p>
        </SectionHeader>
        <div className="grid gap-3 lg:grid-cols-2">
          <PairTile
            label={repeated ? "Runs passed" : "Cases passed"}
            unit={unit}
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
        <p className="text-sm leading-6 text-slate">
          LLM answers vary, so the same case can pass once and fail the next time. The net-change test asks whether the
          gap is bigger than that on these cases; it holds the cases fixed, so it says nothing about other questions.{" "}
          {test &&
            `Here it gives ${pPhrase(test.overall.pValue, test.alpha)}, from the cases ${
              repeated ? "whose runs did not all agree" : "that flipped"
            }.`}{" "}
          {cost?.baseline && cost.candidate
            ? `Cost per 1,000 replies, answer and router at list prices with a warm cache: Before $${cost.baseline.toFixed(2)}, After $${cost.candidate.toFixed(2)}.`
            : ""}
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
            unit={unit}
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
          <p>
            Open a case to read both replies and why the judge failed one of them.
            {repeated &&
              ` Each case ran ${k} times per bot. A case counts as better on After only when After passed at least ${m} of ${k} runs and Before none, and as worse only when Before passed every run and After failed at least ${m}; any other case whose runs did not all agree is listed under that heading.`}
          </p>
        </SectionHeader>
        {comparison ? (
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate">How each of the {comparison.report.overall.total} cases came out.</p>
              <TestBadge test={test} />
            </div>
            <div className="mt-3">
              <TransitionStats comparison={comparison} labels={transitions} />
            </div>
            {sharp.length > 0 && (
              <p className="mt-3 text-sm leading-6 text-slate">
                <span className="font-semibold text-ink">Dropped sharply on After:</span> {sharp.join(", ")}, listed under
                runs that did not all agree because Before did not pass every run.
              </p>
            )}
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
                    {transitions[key]} ({changes.length})
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
          The answering model runs at low effort. The cases, facts and skills were written by the same author, and the
          shipped skill edits were made after reading failures on these cases, so no case in the main set is held out;
          the held-out check above uses cases written after the skills were frozen.
        </p>
        {after?.meta.models && <ModelList models={after.meta.models} />}
      </section>
    </div>
  );
}
