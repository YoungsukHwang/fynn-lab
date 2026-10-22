import type { Bucket } from "@/lib/evalData";
import { pct } from "@/lib/evalLabels";

// Static class strings (Tailwind can't see classes assembled at runtime).
const TONES = {
  before: { bar: "bg-peach", label: "text-ember" },
  after: { bar: "bg-fynn", label: "text-cobalt" },
} as const;

export interface BarSeries {
  label: string;
  tone: keyof typeof TONES;
  bucket: Bucket | null;
}

export interface BarGroup {
  key: string;
  label: string;
  note?: string;
  series: BarSeries[];
}

function Row({ series }: { series: BarSeries }) {
  const { bucket } = series;
  const ran = bucket !== null && bucket.total > 0;
  const width = ran && typeof bucket.rate === "number" ? Math.max(0, Math.min(1, bucket.rate)) * 100 : 0;
  const tone = TONES[series.tone];
  return (
    <div className="grid grid-cols-[3.25rem_minmax(0,1fr)] items-center gap-x-2 gap-y-1 sm:grid-cols-[3.75rem_minmax(0,1fr)_8.5rem]">
      <span className={`text-xs font-semibold ${tone.label}`}>{series.label}</span>
      <span aria-hidden="true" className="block h-3 overflow-hidden rounded-full bg-mist">
        <span className={`block h-full rounded-full ${tone.bar}`} style={{ width: `${width}%` }} />
      </span>
      <span className="col-start-2 text-xs text-ink sm:col-start-3">
        {ran ? (
          <>
            <span className="font-semibold">{pct(bucket.rate)}</span>
            <span className="text-slate">
              {" "}
              ({bucket.passed} of {bucket.total} passed{bucket.errors ? `, ${bucket.errors} errors` : ""})
            </span>
          </>
        ) : (
          <span className="text-slate">{bucket ? "No cases" : "Not run yet"}</span>
        )}
      </span>
    </div>
  );
}

/** Paired horizontal pass-rate bars, one group per row, with the numbers printed next to each bar. */
export function RateBars({
  title,
  description,
  groups,
  emphasis = false,
}: {
  title: string;
  description?: React.ReactNode;
  groups: BarGroup[];
  emphasis?: boolean;
}) {
  return (
    <figure
      className={`rounded-2xl border bg-white p-4 sm:p-5 ${emphasis ? "border-ink ring-1 ring-ink" : "border-line"}`}
    >
      <figcaption>
        <h3 className="text-base font-semibold text-ink">{title}</h3>
        {description && <p className="mt-1 text-sm leading-6 text-slate">{description}</p>}
      </figcaption>
      <ul className="mt-4 space-y-4">
        {groups.map((group) => (
          <li key={group.key}>
            <p className="text-sm font-semibold text-ink">
              {group.label}
              {group.note && <span className="font-normal text-slate"> · {group.note}</span>}
            </p>
            <div className="mt-1.5 space-y-1.5">
              {group.series.map((series) => (
                <Row key={series.label} series={series} />
              ))}
            </div>
          </li>
        ))}
      </ul>
    </figure>
  );
}
