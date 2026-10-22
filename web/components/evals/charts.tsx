// Before/After charts for the eval pages: a dumbbell (one row per group, a dot per bot on a
// shared 0-100% axis) and a two-value stat tile. Server components; the hover readout is CSS
// (group-hover and group-focus), and every value is also printed beside the marks and in a table.

import type { GroupStat } from "@/lib/evalData";
import { deltaLabel, deltaPoints, pct, plural } from "@/lib/evalLabels";

export interface DumbbellRow {
  key: string;
  label: string;
  note?: string;
  before: GroupStat | null;
  after: GroupStat | null;
  emphasis?: boolean;
}

export interface DumbbellGroup {
  title: string;
  note?: string;
  rows: DumbbellRow[];
}

const TICKS = [0, 25, 50, 75, 100];
const GRID = "grid grid-cols-[minmax(0,1fr)_7.5rem] gap-x-3 sm:grid-cols-[11rem_minmax(0,1fr)_8.5rem]";
// Marks are background fills; forced-colors mode repaints backgrounds, so give them a system color there.
const FORCED = "forced-colors:bg-[CanvasText]";
const TIE_FILL = "linear-gradient(90deg, var(--color-coral) 50%, var(--color-fynn) 50%)";

function Dot({ rate, tone }: { rate: number; tone: "before" | "after" | "tie" }) {
  // A tie is one dot, half coral and half blue, so neither bot's dot hides the other.
  const fill = tone === "before" ? "bg-coral" : tone === "after" ? "bg-fynn" : "";
  return (
    <span
      aria-hidden="true"
      className={`absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-white ${fill} ${FORCED}`}
      style={{
        left: `${Math.max(0, Math.min(1, rate)) * 100}%`,
        ...(tone === "tie" ? { background: TIE_FILL } : {}),
      }}
    />
  );
}

function deltaClass(points: number | null): string {
  if (points === null || points === 0) return "text-slate";
  return points > 0 ? "text-forest" : "text-red-800";
}

function share(stat: GroupStat | null): string {
  if (!stat || !stat.runs) return "n/a";
  const unit = stat.runs === stat.cases ? "" : " runs";
  return `${stat.passed} of ${stat.runs}${unit}`;
}

function facts(stat: GroupStat | null): string {
  return stat && stat.factsGraded > 0 ? `${stat.factsPresent} of ${stat.factsGraded}` : "n/a";
}

/** The row's values as one sentence, for the accessible name and the hover readout. */
function describe(row: DumbbellRow): string {
  return `${row.label}: Before ${pct(row.before?.rate)} (${share(row.before)} passed, facts ${facts(row.before)}), After ${pct(
    row.after?.rate,
  )} (${share(row.after)} passed, facts ${facts(row.after)})`;
}

function Readout({ row }: { row: DumbbellRow }) {
  // Below sm the track is narrow, so the readout anchors to its left edge instead of its center.
  return (
    <span
      aria-hidden="true"
      className="absolute bottom-full left-0 z-10 mb-2 hidden w-60 max-w-[calc(100vw-3rem)] rounded-xl border border-line bg-white px-3 py-2 text-left text-xs leading-5 text-ink shadow-lg group-hover:block group-focus:block sm:left-1/2 sm:-translate-x-1/2"
    >
      <span className="block font-semibold">{row.label}</span>
      {(["before", "after"] as const).map((side) => {
        const stat = row[side];
        return (
          <span key={side} className="flex items-center gap-2">
            <span aria-hidden="true" className={`inline-block h-0.5 w-3 ${side === "before" ? "bg-coral" : "bg-fynn"}`} />
            <span className="font-semibold">{pct(stat?.rate)}</span>
            <span className="text-slate">
              {side === "before" ? "Before" : "After"}: {share(stat)} passed; facts {facts(stat)}
            </span>
          </span>
        );
      })}
    </span>
  );
}

/**
 * Pass rate per group on both bots: a coral dot for Before, a blue dot for After, on one shared
 * 0-100% axis. Rows come in titled groups (small multiples that share the axis). The row marked
 * `emphasis` is named in its text as well as tinted.
 */
export function Dumbbell({
  id,
  title,
  description,
  groups,
  caption,
  emphasisLabel = "Highlighted",
}: {
  id: string;
  title: string;
  description?: React.ReactNode;
  groups: DumbbellGroup[];
  caption: string;
  emphasisLabel?: string;
}) {
  const visible = (row: DumbbellRow) => (row.before?.cases ?? row.after?.cases ?? 0) > 0;
  const shownGroups = groups.map((g) => ({ ...g, rows: g.rows.filter(visible) })).filter((g) => g.rows.length);
  const exactTie = (row: DumbbellRow) =>
    row.before != null &&
    row.after != null &&
    row.before.runs > 0 &&
    row.after.runs > 0 &&
    row.before.passed * row.after.runs === row.after.passed * row.before.runs;
  return (
    <figure aria-labelledby={`${id}-title`} className="rounded-2xl border border-line bg-white p-4 sm:p-5">
      <figcaption>
        <h3 id={`${id}-title`} className="text-base font-semibold text-ink">
          {title}
        </h3>
        {description && <p className="mt-1 text-sm leading-6 text-slate">{description}</p>}
      </figcaption>
      <ul aria-label="Legend" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate">
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-coral" /> Before: single-agent router
        </li>
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-fynn" /> After: skill-based
        </li>
        <li className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full" style={{ background: TIE_FILL }} /> Same rate on
          both
        </li>
      </ul>

      <div className="mt-3">
        {/* Axis labels, aligned with the track column */}
        <div className={GRID}>
          <span className="hidden sm:block" />
          <span aria-hidden="true" className="relative h-4 text-[11px] text-dim">
            {TICKS.map((t) => (
              <span
                key={t}
                className={`absolute top-0 ${t === 0 ? "" : t === 100 ? "-translate-x-full" : "-translate-x-1/2"}`}
                style={{ left: `${t}%` }}
              >
                {t}%
              </span>
            ))}
          </span>
          <span />
        </div>
        {shownGroups.map((group, gi) => {
          const groupId = `${id}-group-${gi}`;
          return (
            <div key={group.title} className="mt-3 first:mt-1">
              <h4 id={groupId} className="border-b border-line pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate">
                {group.title}
                {group.note && <span className="font-normal normal-case tracking-normal"> · {group.note}</span>}
              </h4>
              <ul aria-labelledby={groupId} className="divide-y divide-line">
                {group.rows.map((row) => {
                  const points = deltaPoints(row.before?.rate, row.after?.rate);
                  const tie = exactTie(row);
                  return (
                    <li
                      key={row.key}
                      className={`${GRID} items-center gap-y-1 py-2.5 ${row.emphasis ? "-mx-2 rounded-lg bg-fynn-soft/60 px-2" : ""}`}
                    >
                      <span className="col-span-2 min-w-0 sm:col-span-1">
                        <span className="flex flex-wrap items-center gap-1.5 text-sm font-semibold text-ink">
                          {row.label}
                          {row.emphasis && (
                            <span className="rounded-full border border-fynn px-1.5 text-[10px] font-semibold uppercase tracking-wide text-cobalt">
                              {emphasisLabel}
                            </span>
                          )}
                        </span>
                        <span className="block text-xs text-slate">
                          {plural(row.after?.cases ?? row.before?.cases ?? 0, "case")}
                        </span>
                        {row.note && <span className="block text-xs leading-4 text-slate">{row.note}</span>}
                      </span>
                      <span
                        tabIndex={0}
                        role="img"
                        aria-label={describe(row)}
                        className="group relative h-6 rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
                      >
                        {TICKS.map((t) => (
                          <span
                            key={t}
                            aria-hidden="true"
                            className="absolute top-0 h-full w-px bg-line"
                            style={{ left: `${t}%` }}
                          />
                        ))}
                        {row.before?.rate != null && row.after?.rate != null && !tie && (
                          <span
                            aria-hidden="true"
                            className={`absolute top-1/2 h-0.5 -translate-y-1/2 bg-field ${FORCED}`}
                            style={{
                              left: `${Math.min(row.before.rate, row.after.rate) * 100}%`,
                              width: `${Math.abs(row.after.rate - row.before.rate) * 100}%`,
                            }}
                          />
                        )}
                        {tie && row.after?.rate != null ? (
                          <Dot rate={row.after.rate} tone="tie" />
                        ) : (
                          <>
                            {row.before?.rate != null && <Dot rate={row.before.rate} tone="before" />}
                            {row.after?.rate != null && <Dot rate={row.after.rate} tone="after" />}
                          </>
                        )}
                        <Readout row={row} />
                      </span>
                      <span className="text-right text-xs leading-5 text-ink">
                        <span className="font-semibold">
                          {pct(row.before?.rate)} → {pct(row.after?.rate)}
                        </span>
                        <span className={`block font-medium ${deltaClass(points)}`}>{deltaLabel(points)}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-xs font-medium text-ink underline underline-offset-2">
          Show as a table
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[36rem] border-collapse text-left text-xs">
            <caption className="sr-only">{caption}</caption>
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wide text-slate">
                {["Group", "Cases", "Before", "After", "Change", "Facts present (Before, After)"].map((h) => (
                  <th key={h} scope="col" className="py-1.5 pr-2 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            {shownGroups.map((group) => (
              <tbody key={group.title} className="text-ink">
                <tr className="bg-canvas">
                  <th scope="colgroup" colSpan={6} className="px-1 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate">
                    {group.title}
                  </th>
                </tr>
                {group.rows.map((row) => (
                  <tr key={row.key} className="border-b border-line">
                    <th scope="row" className="py-1.5 pr-2 font-medium">
                      {row.label}
                      {row.emphasis && <span className="font-normal text-slate"> ({emphasisLabel.toLowerCase()})</span>}
                    </th>
                    <td className="py-1.5 pr-2">{row.after?.cases ?? row.before?.cases ?? 0}</td>
                    <td className="py-1.5 pr-2">
                      {pct(row.before?.rate)} ({share(row.before)})
                    </td>
                    <td className="py-1.5 pr-2">
                      {pct(row.after?.rate)} ({share(row.after)})
                    </td>
                    <td className="py-1.5 pr-2">{deltaLabel(deltaPoints(row.before?.rate, row.after?.rate))}</td>
                    <td className="py-1.5">
                      {facts(row.before)}, {facts(row.after)}
                    </td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
      </details>
    </figure>
  );
}

/** A headline number on both bots: value, then the counts, then the change. */
const BOT_SIDES = [
  { name: "Before", swatch: "bg-coral" },
  { name: "After", swatch: "bg-fynn" },
] as const;

export function PairTile({
  label,
  before,
  after,
  unit,
  hint,
  sides = BOT_SIDES,
}: {
  label: string;
  before: { value: number; of: number } | null;
  after: { value: number; of: number } | null;
  unit: string;
  hint?: string;
  sides?: readonly [{ name: string; swatch: string }, { name: string; swatch: string }]; // names and swatch classes
}) {
  const rate = (side: { value: number; of: number } | null) => (side && side.of ? side.value / side.of : null);
  const points = deltaPoints(rate(before), rate(after));
  return (
    <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <dl className="mt-2 grid grid-cols-2 gap-3">
        {(
          [
            [sides[0].name, before, sides[0].swatch],
            [sides[1].name, after, sides[1].swatch],
          ] as const
        ).map(([name, side, swatch]) => (
          <div key={name}>
            <dt className="flex items-center gap-1.5 text-xs font-medium text-slate">
              <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${swatch}`} />
              {name}
            </dt>
            <dd className="mt-0.5 text-3xl font-semibold tracking-tight text-ink">{pct(rate(side))}</dd>
            <dd className="text-xs text-slate">{side ? `${side.value} of ${side.of} ${unit}` : "Not run yet"}</dd>
          </div>
        ))}
      </dl>
      <p className={`mt-2 text-sm font-semibold ${deltaClass(points)}`}>
        {deltaLabel(points)}
        {hint && <span className="font-normal text-slate"> · {hint}</span>}
      </p>
    </div>
  );
}
