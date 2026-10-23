import type { Metadata } from "next";
import Link from "next/link";

import { type FlipLabels, NoiseCheck } from "@/components/evals/NoiseCheck";
import { RunDetails } from "@/components/evals/RunDetails";
import { SCENARIO_TRANSITIONS } from "@/components/evals/ScenarioCard";
import { Chip, NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { type Comparison, getCapData, getCases, getResultsData } from "@/lib/evalData";
import { pPhrase, signedPoints, TEST_METHOD_LABELS } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Noise & A/A results" };

const SECTIONS = [
  { href: "#glance", label: "At a glance" },
  { href: "#checks", label: "Each comparison" },
  { href: "#runs", label: "Runs and repeats" },
];

const BOT_FLIPS: FlipLabels = { improved: "After only", regressed: "Before only" };
const SCENARIO_FLIPS: FlipLabels = { ...SCENARIO_TRANSITIONS, improvedShort: "Better", regressedShort: "Worse" };

/** A small diverging bar centred on zero: a change in pass rate, up to plus or minus 50 points across.
 *  A larger change fills its half and gets a square end, so the clipping is visible. */
function ChangeBar({ diff }: { diff: number | null }) {
  const width = diff === null ? 0 : Math.min(1, Math.abs(diff) / 0.5) * 50;
  const clipped = diff !== null && Math.abs(diff) > 0.5;
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden="true" className="relative block h-2.5 w-20 flex-none rounded-full bg-mist">
        <span className="absolute inset-y-0 left-1/2 w-px bg-field" />
        {diff !== null && diff !== 0 && (
          <span
            className={`absolute inset-y-0 forced-colors:bg-[CanvasText] ${
              diff > 0 ? `bg-forest ${clipped ? "" : "rounded-r-full"}` : `bg-red-800 ${clipped ? "" : "rounded-l-full"}`
            }`}
            style={diff > 0 ? { left: "50%", width: `${width}%` } : { right: "50%", width: `${width}%` }}
          />
        )}
      </span>
      <span className="tabular-nums">{signedPoints(diff)}</span>
    </span>
  );
}

interface Row {
  id: string;
  name: string;
  title: string;
  comparison: Comparison;
  flips: FlipLabels;
  href: string;
  shipCheck: boolean; // false for Before vs After: two different bots, not an edit to ship or hold back
}

export default async function NoiseResultsPage() {
  const [data, capData, cases] = await Promise.all([getResultsData(), getCapData(), getCases()]);
  const addedCount = cases.filter((c) => c.added).length;
  const rows: Row[] = [
    ...(data.beforeVsAfter
      ? [
          {
            id: "before-vs-after",
            name: "Before vs After",
            title: addedCount
              ? `The two bots on all cases, ${addedCount} of them added after the first run to test where they differ; the results page shows them apart`
              : "The two bots on all cases",
            comparison: data.beforeVsAfter,
            flips: BOT_FLIPS,
            href: "/before-after/results",
            shipCheck: false,
          },
        ]
      : []),
    ...data.scenarios.flatMap((s) =>
      s.comparison
        ? [
            {
              id: s.scenario.id,
              name: s.scenario.id.toUpperCase(),
              title: s.scenario.title,
              comparison: s.comparison,
              flips: SCENARIO_FLIPS,
              href: `/skill-edits/results#${s.scenario.id}`,
              shipCheck: true,
            },
          ]
        : [],
    ),
    ...(capData.comparison
      ? [
          {
            id: "skill-cap",
            name: `Cap ${capData.cap ?? "?"}`,
            title: `The After bot with a skill cap of ${capData.cap ?? "?"} instead of ${capData.baselineCap ?? "?"}`,
            comparison: capData.comparison,
            flips: SCENARIO_FLIPS,
            href: "/before-after/results#cap",
            shipCheck: true,
          },
        ]
      : []),
  ];
  const measured = rows.filter((r) => r.comparison.report.noiseFloor);
  const allSingle = data.runs.length > 0 && data.runs.every((run) => run.repeats === 1);

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Noise & A/A · Results" title="How much of each difference could be chance">
        <p>
          Every comparison on this site, checked the same way: the net-change test, the A/A noise floor when it has been
          measured, and the flag rule the verdict used.
        </p>
      </PageHero>

      {measured.length === 0 && (
        <NotGenerated title="No A/A noise floor measured yet">
          {allSingle
            ? "Every committed results file ran each case once, so no comparison has a noise floor. "
            : "No comparison has a noise floor yet. "}
          It comes for free once a baseline runs each case more than once (<code className="font-mono text-xs">--repeats 3</code>), or from a
          second baseline run passed to the report with <code className="font-mono text-xs">--aa</code>. Until then,
          read each difference against the net-change test alone; see the{" "}
          <Link href="/noise/framework#calibration" className="font-medium text-ink underline underline-offset-2">
            calibration
          </Link>{" "}
          for what one run per case can detect.
        </NotGenerated>
      )}

      <OnThisPage links={SECTIONS} />

      <section aria-labelledby="glance" className="flex flex-col gap-4">
        <SectionHeader id="glance" eyebrow="At a glance" title="Every comparison, one row each" />
        {rows.length ? (
          <div className="overflow-x-auto rounded-2xl border border-line bg-white p-4 sm:p-5">
            <table className="w-full min-w-[44rem] border-collapse text-left text-sm">
              <caption className="sr-only">Net-change test, noise floor and verdict for each comparison</caption>
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-slate">
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Comparison
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Runs per case
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Mean change <span className="font-normal normal-case tracking-normal">(bar to ±50 pts)</span>
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Net-change test
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    A/A floor
                  </th>
                  <th scope="col" className="py-2 font-semibold">
                    Verdict
                  </th>
                </tr>
              </thead>
              <tbody className="text-ink">
                {rows.map(({ id, name, comparison, shipCheck }) => {
                  const { pairedTest: test, flagRule: rule, noiseFloor: noise, verdict } = comparison.report;
                  return (
                    <tr key={id} className="border-b border-line align-top">
                      <th scope="row" className="py-2.5 pr-3 font-medium">
                        <a href={`#${id}`} className="underline underline-offset-2">
                          {name}
                        </a>
                      </th>
                      <td className="py-2.5 pr-3">
                        {rule ? `${rule.baselineRepeats} vs ${rule.candidateRepeats}` : "n/a"}
                      </td>
                      <td className="py-2.5 pr-3">
                        <ChangeBar diff={test?.overall.meanDiff ?? null} />
                      </td>
                      <td className="py-2.5 pr-3">
                        {test ? pPhrase(test.overall.pValue, test.alpha) : "n/a"}
                        <span className="block text-xs text-slate">
                          {test ? (TEST_METHOD_LABELS[test.method] ?? test.method) : ""}
                          {test?.overall.significant ? ", significant" : test ? ", not significant" : ""}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3">{noise ? "measured" : <span className="text-slate">not measured</span>}</td>
                      <td className="py-2.5">
                        {shipCheck ? (
                          <Chip tone={verdict === "Passed" ? "lime" : verdict === "Not passed" ? "bad" : "neutral"}>{verdict || "unknown"}</Chip>
                        ) : (
                          <span className="text-xs text-slate">not a ship check</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <NotGenerated>No regression reports were found in results/reports/.</NotGenerated>
        )}
      </section>

      <section aria-labelledby="checks" className="flex flex-col gap-4">
        <SectionHeader id="checks" eyebrow="Each comparison" title="The noise check behind each verdict" />
        {rows.map(({ id, name, title, comparison, flips, href, shipCheck }) => (
          <article key={id} id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-6 flex flex-col gap-2">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 id={`${id}-heading`} className="text-lg font-semibold tracking-tight text-ink">
                {name}: <span className="font-normal text-slate">{title}</span>
              </h3>
              <Link href={href} className="text-sm font-medium text-ink underline underline-offset-2">
                See the cases<span className="sr-only"> for {name}</span>
              </Link>
            </div>
            {shipCheck && comparison.report.verdictNote && (
              <p className="text-sm leading-6 text-slate">{comparison.report.verdictNote}</p>
            )}
            <div className="rounded-xl bg-white">
              <NoiseCheck id={id} label={name} report={comparison.report} flips={flips} />
            </div>
          </article>
        ))}
      </section>

      <section aria-labelledby="runs" className="flex flex-col gap-4">
        <SectionHeader id="runs" eyebrow="Runs and repeats" title="Every results file read for these pages">
          <p>Times are when each run finished writing its results.</p>
        </SectionHeader>
        <RunDetails runs={data.runs} />
      </section>
    </div>
  );
}
