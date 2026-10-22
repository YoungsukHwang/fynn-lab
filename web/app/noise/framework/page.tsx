import type { Metadata } from "next";

import { OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";

export const metadata: Metadata = { title: "Noise & A/A framework" };

const SECTIONS = [
  { href: "#why", label: "Why it matters" },
  { href: "#method", label: "The method" },
  { href: "#calibration", label: "Calibration and power" },
  { href: "#reading", label: "Reading a result" },
];

const PIECES: { title: string; body: React.ReactNode }[] = [
  {
    title: "Repeated runs",
    body: (
      <>
        <code className="font-mono text-xs text-ink">run.py --repeats K</code> runs every case K times and keeps every
        run. A case&apos;s pass fraction is its passing runs over its runs; three runs are recommended.
      </>
    ),
  },
  {
    title: "Flag rule",
    body: "A case counts as regressed only when it fails at least m of its K runs and passed every baseline run (m is a majority unless set otherwise). Improvements are the mirror image. Anything else that varied is listed as unstable, and sharp moves among those are called out.",
  },
  {
    title: "Net-change test",
    body: "With one run per side, an exact McNemar test on the cases that flipped. With repeated runs, an exact permutation test that shuffles each case's runs between the two sides; with one run each it gives exactly the McNemar p-value. Both ask whether the overall pass rate moved.",
  },
  {
    title: "Persona interval",
    body: "A persona-cluster bootstrap interval for the mean change, shown as a description of how much the change varies between personas. With six personas it is not a test.",
  },
  {
    title: "Holm across datasets",
    body: "The per-dataset tests are Holm-corrected together. The overall test is the primary one and is not adjusted.",
  },
  {
    title: "A/A noise floor",
    body: "How many cases flip between two runs of the baseline with nothing changed: estimated from the baseline's own repeats as single-run flips, or counted under the flag rule in a second baseline run passed with --aa.",
  },
  {
    title: "Errored runs",
    body: "An API error says nothing about the bot, so errored runs are left out when a case has other runs on that side. A side whose every run errored counts as failing for the flag rule and is left out of the test and the noise floor.",
  },
];

/** One row of a range chart: a label, a bar from low to high on a 0 to max axis, and the range as text. */
function RangeBar({
  label,
  low,
  high,
  emphasis,
  marker,
  text,
  max = 100,
}: {
  label: string;
  low: number;
  high: number;
  emphasis?: boolean;
  marker?: { at: number; text: string };
  text?: string;
  max?: number; // the axis runs from 0 to max percent
}) {
  const at = (v: number) => `${(v / max) * 100}%`;
  return (
    <div className="grid grid-cols-[4.5rem_minmax(0,1fr)_5.5rem] items-center gap-3">
      <dt className="text-sm font-semibold text-ink">{label}</dt>
      <span aria-hidden="true" className="relative h-6">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <span key={t} className="absolute top-0 h-full w-px bg-line" style={{ left: `${t * 100}%` }} />
        ))}
        {/* Emphasis is ink, not a series color: fynn and coral mean After and Before elsewhere on the site. */}
        <span
          className={`absolute top-1/2 h-2.5 -translate-y-1/2 rounded-full forced-colors:bg-[CanvasText] ${
            emphasis ? "bg-ink" : "bg-field"
          }`}
          style={{ left: at(low), width: `max(0.5rem, ${((high - low) / max) * 100}%)` }}
        />
        {marker && (
          <>
            <span className="absolute -top-1 h-8 w-0.5 bg-red-800 forced-colors:bg-[CanvasText]" style={{ left: at(marker.at) }} />
            <span className="absolute -top-4 -translate-x-1/2 text-[10px] font-semibold text-red-800" style={{ left: at(marker.at) }}>
              {marker.text}
            </span>
          </>
        )}
      </span>
      <dd className="text-right text-sm font-semibold text-ink">
        {text ?? (low === high ? `${low}%` : `${low} to ${high}%`)}
      </dd>
    </div>
  );
}

function Axis({ max = 100 }: { max?: number }) {
  return (
    <div aria-hidden="true" className="grid grid-cols-[4.5rem_minmax(0,1fr)_5.5rem] gap-3">
      <span />
      <span className="relative h-4 text-[11px] text-dim">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <span
            key={t}
            className={`absolute ${t === 0 ? "" : t === 1 ? "-translate-x-full" : "-translate-x-1/2"} ${
              t === 0.25 || t === 0.75 ? "hidden sm:block" : ""
            }`}
            style={{ left: `${t * 100}%` }}
          >
            {t * max}%
          </span>
        ))}
      </span>
      <span />
    </div>
  );
}

export default function NoiseFrameworkPage() {
  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Noise & A/A · Framework" title="Telling a real change from run-to-run noise">
        <p>
          The bots, the router and the judge are all LLM calls, so the same case can pass in one run and fail in the
          next with nothing changed. Every comparison on this site is checked against that variation before it is read
          as an effect.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      <section aria-labelledby="why" className="flex flex-col gap-4">
        <SectionHeader id="why" eyebrow="1 · Why it matters" title="A per-case verdict says little on its own">
          <p>
            The verdict is Passed only when no case regresses. With 40 cases and one run each, a few cases flip by chance
            in almost every rerun, so an unchanged bot usually reads Not passed. Repeating runs and asking for a stable
            baseline cuts that down, but does not remove it.
          </p>
        </SectionHeader>
        <figure className="rounded-2xl border border-line bg-white p-4 sm:p-5">
          <figcaption>
            <h3 className="text-base font-semibold text-ink">How often an unchanged bot still reads Not passed</h3>
            <p className="mt-1 text-sm leading-6 text-slate">
              Fynn Lab simulations on this eval set&apos;s layout (40 cases), across plausible mixes of stable and flaky
              cases.
            </p>
          </figcaption>
          <div className="mt-3 space-y-2">
            <Axis />
            <dl className="space-y-2">
              <RangeBar label="1 run" low={93} high={99.7} text="93 to 99.7%" />
              <RangeBar label="3 runs" low={53} high={70} emphasis />
            </dl>
          </div>
        </figure>
      </section>

      <section aria-labelledby="method" className="flex flex-col gap-4">
        <SectionHeader id="method" eyebrow="2 · The method" title="Seven pieces">
          <p>
            Repeated runs come from <code className="font-mono text-xs text-ink">backend/evals/run.py</code>; the rest
            is in <code className="font-mono text-xs text-ink">backend/evals/stats.py</code>, which never calls the API
            and only reads results files.
          </p>
        </SectionHeader>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PIECES.map((piece, i) => (
            <li key={piece.title} className="flex flex-col rounded-2xl border border-line bg-white p-4 sm:p-5">
              <div className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="grid h-6 w-6 place-items-center rounded-full bg-lime-soft text-xs font-semibold text-forest"
                >
                  {i + 1}
                </span>
                <h3 className="text-base font-semibold text-ink">{piece.title}</h3>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate">{piece.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="calibration" className="flex flex-col gap-4">
        <SectionHeader id="calibration" eyebrow="3 · Calibration and power" title="Honest at 5%, and why three runs">
          <p>
            Fynn Lab simulated comparisons on this eval set&apos;s layout (40 cases, 6 personas), with nothing changed
            and with a real drop built in. The ranges cover different mixes of stable and flaky cases.
          </p>
        </SectionHeader>
        <div className="grid gap-3 lg:grid-cols-2">
          <figure className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <figcaption>
              <h3 className="text-base font-semibold text-ink">False alarms with nothing changed</h3>
              <p className="mt-1 text-sm leading-6 text-slate">
                Share of no-change comparisons the net-change test calls significant at 0.05, on a 0 to 10% scale.
                The red line marks 5%; the exact test stays at or below it.
              </p>
            </figcaption>
            <div className="mt-5 space-y-2">
              <Axis max={10} />
              <dl className="space-y-2">
                <RangeBar label="3 runs" low={0} high={4} emphasis marker={{ at: 5, text: "5% line" }} max={10} />
              </dl>
            </div>
          </figure>
          <figure className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <figcaption>
              <h3 className="text-base font-semibold text-ink">Catching a real drop</h3>
              <p className="mt-1 text-sm leading-6 text-slate">
                Share of comparisons where the overall test catches 8 cases falling from passing 95% of the time to 30%.
              </p>
            </figcaption>
            <div className="mt-3 space-y-2">
              <Axis />
              <dl className="space-y-2">
                <RangeBar label="1 run" low={20} high={30} />
                <RangeBar label="3 runs" low={75} high={95} emphasis />
              </dl>
            </div>
          </figure>
        </div>
      </section>

      <section aria-labelledby="reading" className="flex flex-col gap-4">
        <SectionHeader id="reading" eyebrow="4 · Reading a result" title="Not significant is not the same as no difference">
          <p>
            A p-value above 0.05 means the data cannot rule out chance, not that the two runs are the same. With 40 cases
            and one run each, a 10-point improvement is detected only about one time in five. Read a non-significant
            result together with its size and the noise floor, and rerun with more runs or more cases when the
            question matters.
          </p>
          <p>
            The test looks at the net change. An edit that fixes as many cases as it breaks has a net change near zero
            and reads as not significant, even when both effects are real; the improved and regressed lists show that
            case.
          </p>
        </SectionHeader>
      </section>
    </div>
  );
}
