import type { Metadata } from "next";

import { NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getModelsData, type ModelRow, type PairedFlip } from "@/lib/evalData";
import { formatTimestamp, pPhrase } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Answer model and judge" };

const SECTIONS = [
  { href: "#cost", label: "Cost and quality" },
  { href: "#length", label: "Reply length" },
  { href: "#judge", label: "The judge" },
];

const NAMES: Record<string, string> = {
  "claude-haiku-5-5": "Haiku 5.5",
  "claude-sonnet-5-5": "Sonnet 5.5",
  "claude-opus-5-5": "Opus 5.5",
};
const modelName = (id: string) => NAMES[id] ?? id;
const sourceName = (rows: ModelRow[], source: string) => modelName(rows.find((r) => r.source === source)?.model ?? source);
const dollars = (value: number) => `$${value.toFixed(2)}`;
const percent = (value: number | null) => (value === null ? "n/a" : `${(value * 100).toFixed(value > 0.99 ? 1 : 0)}%`);

function PassBar({ passed, of }: { passed: number; of: number }) {
  const share = of ? passed / of : 0;
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-mist" aria-hidden="true">
      <div className="h-full rounded-full bg-fynn" style={{ width: `${(share * 100).toFixed(1)}%` }} />
    </div>
  );
}

function FlipLine({ rows, flip, would = false }: { rows: ModelRow[]; flip: PairedFlip; would?: boolean }) {
  return (
    <li>
      <span className="font-semibold text-ink">
        {sourceName(rows, flip.a)} to {sourceName(rows, flip.b)}:
      </span>{" "}
      {flip.up} cases {would ? "would pass" : "pass"} only on {sourceName(rows, flip.b)}, {flip.down} only on{" "}
      {sourceName(rows, flip.a)}, {pPhrase(flip.p)}.
    </li>
  );
}

export default async function ModelsPage() {
  const data = await getModelsData();
  const rows = data.models;
  if (!rows.length) {
    return (
      <div className="flex flex-col gap-6">
        <PageHero eyebrow="Models · Results" title="Answer model and judge">
          <p>results/reports/models/report.json does not exist yet.</p>
        </PageHero>
        <NotGenerated>Run evals.models_report (see &ldquo;Running the evals&rdquo; in the README), then rebuild.</NotGenerated>
      </div>
    );
  }
  const cheapest = rows[0];
  const priciest = rows[rows.length - 1];
  const middle = rows.length > 2 ? rows[rows.length - 2] : null;
  const topPair = data.paired.find((f) => middle && f.a === middle.source && f.b === priciest?.source) ?? null;
  const opusAgain = data.judges.find((j) => j.label.includes("(again)"));
  const otherJudges = data.judges.filter((j) => j !== opusAgain);
  const runDate = rows[0]?.createdAt ? formatTimestamp(rows[0].createdAt) : "";

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Models · Results" title="A mid-size answer model was enough here">
        <p>
          The After bot answered all {cheapest?.cases} cases with each model, graded by the same Opus judge, one run per
          case.{" "}
          {middle && priciest && (
            <>
              {modelName(middle.model)} passed {middle.passed} and {modelName(priciest.model)} {priciest.passed}, at{" "}
              {dollars(middle.costPer1000.total)} against {dollars(priciest.costPer1000.total)} per 1,000 conversations.{" "}
            </>
          )}
          {cheapest && (
            <>
              {modelName(cheapest.model)} cost {dollars(cheapest.costPer1000.total)} and passed {cheapest.passed}.{" "}
            </>
          )}
          The judge itself is steady: grading the same replies twice changed few verdicts.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      <section aria-labelledby="cost" className="flex flex-col gap-4">
        <SectionHeader id="cost" eyebrow="Cost and quality" title="Cases passed, and what 1,000 conversations cost">
          <p>
            Cost is the answering model plus the Haiku router at list prices, per 1,000 single-message conversations. The
            eval&apos;s own judge is not included.
          </p>
        </SectionHeader>
        <ul className="grid gap-3 md:grid-cols-3">
          {rows.map((r) => (
            <li key={r.source} className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 sm:p-5">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-base font-semibold text-ink">{modelName(r.model)}</p>
                <p className="text-sm font-semibold tabular-nums text-ink">{dollars(r.costPer1000.total)}</p>
              </div>
              <div>
                <p className="text-3xl font-semibold tabular-nums tracking-tight text-ink">
                  {r.passed}
                  <span className="text-base font-medium text-slate"> of {r.cases} passed</span>
                </p>
                <div className="mt-2">
                  <PassBar passed={r.passed} of={r.cases} />
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
                <dt className="text-slate">Needs a second domain</dt>
                <dd className="text-right tabular-nums text-ink">
                  {r.byGroup.cross.passed} of {r.byGroup.cross.cases}
                </dd>
                <dt className="text-slate">One domain</dt>
                <dd className="text-right tabular-nums text-ink">
                  {r.byGroup.single.passed} of {r.byGroup.single.cases}
                </dd>
                <dt className="text-slate">Expected facts present</dt>
                <dd className="text-right tabular-nums text-ink">{percent(r.facts.graded ? r.facts.present / r.facts.graded : null)}</dd>
                <dt className="text-slate">Answer + router per 1,000</dt>
                <dd className="text-right tabular-nums text-ink">
                  {dollars(r.costPer1000.answer)} + {dollars(r.costPer1000.router)}
                </dd>
              </dl>
            </li>
          ))}
        </ul>
        <div className="rounded-2xl border border-line bg-white p-4 text-sm leading-6 text-slate sm:p-5">
          <p className="font-semibold text-ink">Is the gap bigger than run-to-run noise?</p>
          <p className="mt-1">Exact McNemar test on the cases where the two models came out differently:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            {data.paired.map((flip) => (
              <FlipLine key={`${flip.a}-${flip.b}`} rows={rows} flip={flip} />
            ))}
          </ul>
          {topPair && middle && priciest && topPair.p !== null && topPair.p >= 0.05 && (
            <p className="mt-2">
              So {modelName(middle.model)} and {modelName(priciest.model)} could not be told apart with one run per case.
              That is not proof they are equally good: a gap of a few cases would not show at this size.
            </p>
          )}
        </div>
      </section>

      <section aria-labelledby="length" className="flex flex-col gap-4">
        <SectionHeader id="length" eyebrow="Reply length" title="The rule nothing grades">
          <p>
            The response rules ask for replies under about {rows[0]?.lengths.limit ?? 250} words, but neither the code checks
            nor the judge look at length, and the judge rewards complete answers. Counting words shows whether the ranking
            depends on that ungraded rule.
          </p>
        </SectionHeader>
        <div className="overflow-x-auto rounded-2xl border border-line bg-white">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate">
                <th className="px-4 py-3">Answer model</th>
                <th className="px-4 py-3 text-right">Median words</th>
                <th className="px-4 py-3 text-right">Over {rows[0]?.lengths.limit ?? 250} words</th>
                <th className="px-4 py-3 text-right">Passed</th>
                <th className="px-4 py-3 text-right">Passed if over 300 words fails</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.source} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-medium text-ink">{modelName(r.model)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.lengths.medianWords ?? "n/a"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {r.lengths.overLimit} of {r.lengths.replies}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.passed}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{r.passedIfOver300Fails}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.pairedIfOver300Fails.length > 0 && (
          <div className="text-sm leading-6 text-slate">
            <p>If replies over 300 words counted as failures, the same paired test would give:</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {data.pairedIfOver300Fails.map((flip) => (
                <FlipLine key={`cap-${flip.a}-${flip.b}`} rows={rows} flip={flip} would />
              ))}
            </ul>
          </div>
        )}
        <p className="text-sm leading-6 text-slate">
          Words are counted by splitting on spaces, so markdown markers count too.
        </p>
      </section>

      <section aria-labelledby="judge" className="flex flex-col gap-4">
        <SectionHeader id="judge" eyebrow="The judge" title="Grading the same replies again">
          <p>
            Every pass or fail above comes from one Opus judge. To check it, the {rows.length * (rows[0]?.cases ?? 0)}{" "}
            stored replies were graded again by Opus and by two cheaper models, with no bot run again.
          </p>
        </SectionHeader>
        {opusAgain && (
          <div className="rounded-2xl border border-lime-soft bg-lime-soft p-4 text-sm leading-6 text-forest sm:p-5">
            <p className="font-semibold">
              The same Opus judge changed {opusAgain.verdictFlips} of {opusAgain.replies} verdicts when it graded again.
            </p>
            <p className="mt-1">
              So the judge is a small part of the run-to-run noise: most cases that flip between runs flip because the
              answer changed.
            </p>
          </div>
        )}
        <div className="overflow-x-auto rounded-2xl border border-line bg-white">
          <table className="w-full min-w-[34rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate">
                <th className="px-4 py-3">Judge</th>
                <th className="px-4 py-3 text-right">Facts graded the same as the first Opus pass</th>
                <th className="px-4 py-3 text-right">Verdicts changed</th>
                <th className="px-4 py-3 text-right">Cost to grade 64 replies</th>
              </tr>
            </thead>
            <tbody>
              {[...(opusAgain ? [opusAgain] : []), ...otherJudges].map((j) => (
                <tr key={j.label} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-medium text-ink">
                    {j === opusAgain ? "Opus 5.5, graded again" : modelName(j.model)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{percent(j.factAgreement)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {j.verdictFlips} of {j.replies}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{dollars(j.costPerRun)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm leading-6 text-slate">
          Agreeing with Opus is not the same as being right. Which judge is closest to a person is the next check.
        </p>
        {data.human ? (
          <div className="overflow-x-auto rounded-2xl border border-line bg-white">
            <table className="w-full min-w-[30rem] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate">
                  <th className="px-4 py-3">Judge against a person&apos;s labels</th>
                  <th className="px-4 py-3 text-right">Facts</th>
                  <th className="px-4 py-3 text-right">Agree</th>
                  <th className="px-4 py-3 text-right">Stricter</th>
                  <th className="px-4 py-3 text-right">More lenient</th>
                </tr>
              </thead>
              <tbody>
                {data.human.judges.map((j) => (
                  <tr key={j.name} className="border-b border-line last:border-0">
                    <td className="px-4 py-3 font-medium text-ink">{j.name}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{j.facts}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {percent(j.rate)}
                      {j.interval && (
                        <span className="text-slate">
                          {" "}
                          ({percent(j.interval[0])} to {percent(j.interval[1])})
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{j.stricter}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{j.lenient}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <NotGenerated title="Human labels in progress">
            A person is grading 32 sampled replies blind, with the judge&apos;s own rules. Their labels will show here, next
            to each judge.
          </NotGenerated>
        )}
      </section>

      <p className="text-xs leading-5 text-slate">
        Runs from {runDate}, with the skills and the cap of 3 in place before the S3, S5, S6 and cap-4 edits shipped. List
        prices; the router&apos;s share is{" "}
        {rows.some((r) => r.costPer1000.estimatedSplit)
          ? `estimated from the router tokens recorded per case in the After run of ${
              data.routerUsageFrom ? formatTimestamp(data.routerUsageFrom.createdAt) : "a later run"
            }.`
          : "recorded per case."}
      </p>
    </div>
  );
}
