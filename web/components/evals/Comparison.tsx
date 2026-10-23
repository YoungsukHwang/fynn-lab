import type { Comparison, PairedTest, PairedTestRow } from "@/lib/evalData";
import { pPhrase } from "@/lib/evalLabels";

import { Chip } from "./ui";

function significance(row: PairedTestRow): { label: string; tone: "lime" | "bad" | "neutral" } {
  if (row.significant === null) return { label: "No test", tone: "neutral" };
  if (!row.significant) return { label: "Not significant", tone: "neutral" };
  return (row.meanDiff ?? 0) > 0
    ? { label: "Significant improvement", tone: "lime" }
    : { label: "Significant regression", tone: "bad" };
}

/** A short line for the net-change test, e.g. "Net change p = 0.019, Significant improvement". */
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

/** How every compared case came out: passing on one side only, on both, or on neither. */
export function TransitionStats({
  comparison,
  labels,
}: {
  comparison: Comparison;
  labels: { improved: string; regressed: string; unchanged_pass: string; unchanged_fail: string; unstable?: string };
}) {
  const { counts } = comparison.report;
  // With repeated runs a case can also vary across runs; then it is its own tile, so the tiles add up to every case.
  const unstable = counts.unstable > 0;
  return (
    <dl className={`grid grid-cols-2 gap-2 ${unstable ? "sm:grid-cols-5" : "sm:grid-cols-4"}`}>
      <Stat label={labels.improved} value={counts.improved} tone="good" />
      <Stat label={labels.regressed} value={counts.regressed} tone="bad" />
      <Stat label={labels.unchanged_pass} value={counts.unchanged_pass} tone="neutral" />
      <Stat label={labels.unchanged_fail} value={counts.unchanged_fail} tone="neutral" />
      {unstable && <Stat label={labels.unstable ?? "Varied across runs"} value={counts.unstable} tone="neutral" />}
    </dl>
  );
}
