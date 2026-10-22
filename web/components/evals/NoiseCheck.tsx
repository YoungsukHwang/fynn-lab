import type { FlagRule, NoiseFloor, NoiseRow, PairedTest, PairedTestRow, Report } from "@/lib/evalData";
import { countLabel, datasetLabel, plural, pPhrase, pValue, signedPoints, TEST_METHOD_LABELS } from "@/lib/evalLabels";

import { Chip } from "./ui";

// How the noise check names the two kinds of flip ("Improved" in a scenario, "After only" for the bots).
export interface FlipLabels {
  improved: string;
  regressed: string;
  // Shorter column headers for phones, where "Regressed" does not fit its column.
  improvedShort?: string;
  regressedShort?: string;
}

function HeaderLabel({ full, short }: { full: string; short?: string }) {
  if (!short) return <>{full}</>;
  return (
    <>
      <span aria-hidden="true" className="sm:hidden">
        {short}
      </span>
      <span className="sr-only sm:not-sr-only">{full}</span>
    </>
  );
}

function significance(row: PairedTestRow): { label: string; tone: "lime" | "bad" | "neutral" } {
  if (row.significant === null) return { label: "No test", tone: "neutral" };
  if (!row.significant) return { label: "Not significant", tone: "neutral" };
  return (row.meanDiff ?? 0) > 0
    ? { label: "Significant improvement", tone: "lime" }
    : { label: "Significant regression", tone: "bad" };
}

/** A short line for next to the verdict, e.g. "Net change p = 0.070, Not significant". */
export function TestBadge({ test }: { test: PairedTest | null }) {
  if (!test) return null;
  const { label, tone } = significance(test.overall);
  return (
    <p className="flex flex-wrap items-center gap-1.5 text-xs text-slate">
      <span>Net change {pPhrase(test.overall.pValue, test.alpha)}</span>
      <Chip tone={tone}>{label}</Chip>
    </p>
  );
}

/** The report's sentence for when the verdict and the paired test tell different stories. */
export function VerdictNote({ note }: { note: string | null }) {
  if (!note) return null;
  return <p className="max-w-md text-xs leading-5 text-slate sm:text-right">{note}</p>;
}

function Tile({ label, value, children }: { label: string; value: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-canvas px-3 py-2.5">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate">{label}</dt>
      <dd>
        <span className="mt-0.5 block text-lg font-semibold leading-6 text-ink">{value}</span>
        <span className="mt-1 block text-xs leading-5 text-slate">{children}</span>
      </dd>
    </div>
  );
}

function interval(row: PairedTestRow): string | null {
  return row.ciLow === null || row.ciHigh === null ? null : `${signedPoints(row.ciLow)} to ${signedPoints(row.ciHigh)}`;
}

function testDetail(test: PairedTest, flips: FlipLabels): string {
  const row = test.overall;
  const leftOut = row.leftOut
    ? ` ${plural(row.leftOut, "case")} with only errored runs on one side ${row.leftOut === 1 ? "was" : "were"} left out.`
    : "";
  if (row.cases === 0) return `No case to test.${leftOut}`;
  if (test.method === "mcnemar_exact") {
    const flipped = (row.improved ?? 0) + (row.regressed ?? 0);
    return `${TEST_METHOD_LABELS.mcnemar_exact} on the ${plural(flipped, "case")} that flipped (${flips.improved}: ${row.improved ?? 0}, ${flips.regressed}: ${row.regressed ?? 0}).${leftOut}`;
  }
  const range = interval(row);
  const personas = range
    ? `Across ${plural(row.clusters ?? 0, "persona")} the change ranged ${range} (a ${Math.round((test.ci?.confidence ?? 0.95) * 100)}% bootstrap interval, descriptive only).`
    : `Only ${plural(row.clusters ?? 0, "persona")}, too few for a persona interval.`;
  return `${TEST_METHOD_LABELS.run_permutation}, shuffling each case's runs between the two sides; ${row.informative ?? 0} of ${plural(row.cases, "case")} had runs that disagreed. Mean pass-fraction change ${signedPoints(row.meanDiff)}. ${personas}${leftOut}`;
}

function noiseValue(noise: NoiseFloor | null): string {
  if (!noise) return "Not measured";
  const count = countLabel(noise.overall.flips);
  if (noise.unit === "flag_rule") return `${count} ${noise.overall.flips === 1 ? "case" : "cases"} flagged`;
  return `About ${count} single-run ${noise.overall.flips === 1 ? "flip" : "flips"}`;
}

function capitalize(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

function noiseDetail(noise: NoiseFloor | null, note: string | null, rule: FlagRule): string {
  if (!noise) {
    return `${capitalize(note ?? "no baseline repeats and no A/A run")}. Measuring it needs repeated runs, or a second run of the baseline with nothing changed.`;
  }
  const cases = plural(noise.overall.cases, "case");
  if (noise.unit === "flag_rule") {
    const how = noise.sameRule
      ? "under the same flag rule"
      : `under a different rule (${noise.minFails ?? 1} of ${noise.repeats} failing runs instead of ${rule.minFails} of ${rule.candidateRepeats}), since the A/A run had ${plural(noise.repeats, "run")} per case`;
    return `${countLabel(noise.overall.flips)} of ${cases} flagged in a second run of the baseline with nothing changed, ${how} (${noise.overall.regressed ?? 0} regressed, ${noise.overall.improved ?? 0} improved).`;
  }
  const unmeasured = noise.unmeasured.length
    ? ` Left out for lack of runs once errors are taken out: ${noise.unmeasured.join(", ")}.`
    : "";
  const comparison =
    (noise.overall.flips ?? 0) >= 0.5
      ? " The flag rule needs a stable baseline, so far fewer cases are flagged by chance than this; a second baseline run with the same number of runs gives a like-for-like count."
      : "";
  return `Expected between two single runs of the baseline, out of ${cases}, from its ${plural(noise.repeats, "run")} per case.${comparison}${unmeasured}`;
}

function noiseHeader(noise: NoiseFloor | null): string {
  if (!noise) return "A/A floor";
  if (noise.unit !== "flag_rule") return "A/A single-run flips";
  return noise.sameRule ? "A/A flags" : `A/A flags (${noise.minFails ?? 1} of ${noise.repeats})`;
}

function ruleValue(rule: FlagRule): string {
  if (rule.baselineRepeats === 1 && rule.candidateRepeats === 1) return "Pass, then fail";
  return `Fails ${rule.minFails} of ${rule.candidateRepeats}`;
}

function Holm({ row, alpha }: { row: PairedTestRow; alpha: number }) {
  const tone = !row.significant ? "text-ink" : (row.meanDiff ?? 0) > 0 ? "font-semibold text-forest" : "font-semibold text-red-800";
  return <span className={tone}>{pValue(row.pHolm, alpha)}</span>;
}

function TestTable({ test, noise, flips }: { test: PairedTest; noise: NoiseFloor | null; flips: FlipLabels }) {
  const mcnemar = test.method === "mcnemar_exact";
  const rows: [string, PairedTestRow, NoiseRow | undefined][] = Object.entries(test.byDataset).map(([dataset, row]) => [
    datasetLabel(dataset),
    row,
    noise?.byDataset[dataset],
  ]);
  const th = "py-1.5 pr-2 align-bottom font-semibold";
  const td = "py-2 pr-2";
  // Columns that only fit on wider screens; each is repeated in the tiles above.
  const sm = "hidden sm:table-cell";
  const lg = "hidden lg:table-cell";
  const cells = (row: PairedTestRow, aa: NoiseRow | undefined, overall: boolean) => (
    <>
      <td className={`${td} ${sm}`}>{row.cases}</td>
      {mcnemar ? (
        <>
          <td className={td}>{row.improved ?? "n/a"}</td>
          <td className={td}>{row.regressed ?? "n/a"}</td>
        </>
      ) : (
        <>
          <td className={`${td} ${lg}`}>{row.informative ?? "n/a"}</td>
          <td className={td}>{signedPoints(row.meanDiff)}</td>
          <td className={`${td} ${lg}`}>{interval(row) ?? "n/a"}</td>
        </>
      )}
      <td className={`${td} ${sm}`}>{pValue(row.pValue, test.alpha)}</td>
      <td className={td}>{overall ? <span className="text-slate">not adjusted</span> : <Holm row={row} alpha={test.alpha} />}</td>
      <td className={`py-2 ${sm}`}>{aa ? countLabel(aa.flips) : "n/a"}</td>
    </>
  );
  return (
    <table className="w-full table-fixed border-collapse text-left text-xs">
      <caption className="sr-only">
        Paired test of the net change by dataset, with Holm-adjusted p-values and the A/A noise floor
      </caption>
      <thead>
        <tr className="border-b border-line text-[11px] uppercase tracking-normal text-slate hyphens-auto sm:tracking-wide">
          <th scope="col" className={`${th} w-[27%] sm:w-[22%]`}>
            Dataset
          </th>
          <th scope="col" className={`${th} ${sm}`}>
            Cases
          </th>
          {mcnemar ? (
            <>
              <th scope="col" className={th}>
                <HeaderLabel full={flips.improved} short={flips.improvedShort} />
              </th>
              <th scope="col" className={th}>
                <HeaderLabel full={flips.regressed} short={flips.regressedShort} />
              </th>
            </>
          ) : (
            <>
              <th scope="col" className={`${th} ${lg}`}>
                Runs disagreed
              </th>
              <th scope="col" className={th}>
                Mean change
              </th>
              <th scope="col" className={`${th} ${lg} lg:w-[18%]`}>
                Persona interval
              </th>
            </>
          )}
          <th scope="col" className={`${th} ${sm}`}>
            p
          </th>
          <th scope="col" className={th}>
            p (Holm)
          </th>
          <th scope="col" className={`py-1.5 align-bottom font-semibold ${sm}`}>
            {noiseHeader(noise)}
          </th>
        </tr>
      </thead>
      <tbody className="text-ink">
        {rows.map(([label, row, aa]) => (
          <tr key={label} className="border-b border-line align-top">
            <th scope="row" className={`${td} font-medium`}>
              {label}
            </th>
            {cells(row, aa, false)}
          </tr>
        ))}
        <tr className="align-top font-semibold">
          <th scope="row" className={td}>
            All compared cases
          </th>
          {cells(test.overall, noise?.overall, true)}
        </tr>
      </tbody>
    </table>
  );
}

/** Did the overall pass rate move more than run-to-run noise would explain? The test, the A/A floor and the flag rule. */
export function NoiseCheck({
  id,
  label: name,
  report,
  flips,
}: {
  id: string;
  label: string; // names the region for screen readers, e.g. "S2" or "Before vs After"
  report: Omit<Report, "failures" | "improvements">;
  flips: FlipLabels;
}) {
  const { pairedTest: test, noiseFloor: noise, flagRule: rule } = report;
  if (!test || !rule) return null;
  const { label, tone } = significance(test.overall);
  const headingId = `${id}-noise-check`;
  return (
    <section aria-labelledby={headingId} className="rounded-xl border border-line px-3 py-3 sm:px-4">
      <h4 id={headingId} className="text-sm font-semibold text-ink">
        Net change or noise?<span className="sr-only"> ({name})</span>
      </h4>
      <p className="mt-1 text-xs leading-5 text-slate">
        LLM replies vary from run to run, so a case can flip with nothing changed. The paired test asks whether the
        overall pass rate moved more than that variation would explain. It tests the net change, so a real tradeoff,
        with as many cases fixed as broken, can still read as not significant.
      </p>
      <dl className="mt-3 grid gap-2 sm:grid-cols-3">
        <Tile
          label="Net-change test"
          value={
            <span className="flex flex-wrap items-center gap-2">
              {pPhrase(test.overall.pValue, test.alpha)}
              <Chip tone={tone}>{label}</Chip>
            </span>
          }
        >
          {testDetail(test, flips)}
        </Tile>
        <Tile label="A/A noise floor" value={noiseValue(noise)}>
          {noiseDetail(noise, report.noiseFloorNote, rule)}
        </Tile>
        <Tile label="Flag rule" value={ruleValue(rule)}>
          {capitalize(rule.text)}.
        </Tile>
      </dl>
      <div className="mt-3">
        <TestTable test={test} noise={noise} flips={flips} />
      </div>
      <p className="mt-2 text-xs leading-5 text-slate">
        Significant means p at or below {test.alpha}.{" "}
        {test.family === 1
          ? "With one dataset there is nothing to adjust for."
          : `The ${test.family} per-dataset p-values are Holm-corrected together, which controls the chance of any false positive among them. The overall test is the primary one and is not adjusted, so across every row that chance can reach twice ${test.alpha}.`}
        {test.ci &&
          ` The persona interval resamples personas ${test.ci.resamples} times; with this few personas it describes how the change varies between them and is not a test.`}
      </p>
    </section>
  );
}
