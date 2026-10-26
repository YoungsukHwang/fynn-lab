import type { Metadata } from "next";
import Link from "next/link";

import { Demo } from "@/components/Demo";
import { RecordedDemo } from "@/components/RecordedDemo";
import { getBeforeAfterData, getHoldoutData, getModelsData, getRecordedDemo } from "@/lib/evalData";
import { pct } from "@/lib/evalLabels";

// The layout's title template only applies to child segments, so the root page sets its full title.
export const metadata: Metadata = { title: { absolute: "Demo | Fynn Lab" } };

const SAME = ["Same skill files", "Same member profile", "Same answer model"];
// The static site (FYNN_STATIC_SITE=1, see next.config.ts) shows recorded replies: alone when it was built
// without a backend URL, or next to the live chat, as the fallback when the hosted backend does not answer.
const STATIC_SITE = process.env.FYNN_STATIC_SITE === "1";
const LIVE = !STATIC_SITE || Boolean(process.env.NEXT_PUBLIC_API_URL);

interface Highlight {
  label: string;
  value: string;
  detail: string;
  href: string;
}

/** The three results a first-time reader should see, from the committed results (none when a file is missing). */
async function highlights(): Promise<Highlight[]> {
  const [main, holdout, models] = await Promise.all([getBeforeAfterData(), getHoldoutData(), getModelsData()]);
  const cross = main.byDomains.find((g) => g.key === "cross");
  const heldCross = holdout.byDomains.find((g) => g.key === "holdout-cross");
  const judge = models.human?.judges.find((j) => j.name.startsWith("original"));
  const items: Highlight[] = [];
  if (cross?.after && cross.before) {
    items.push({
      label: "Questions that need a second domain",
      value: `${pct(cross.after.rate)} vs ${pct(cross.before.rate)}`,
      detail: "of runs passed, After against Before; about even when one domain is enough",
      href: "/before-after/results",
    });
  }
  if (heldCross?.after && heldCross.before) {
    items.push({
      label: "Pre-registered held-out check",
      value: `${heldCross.after.passed}/${heldCross.after.runs} vs ${heldCross.before.passed}/${heldCross.before.runs}`,
      detail: "runs passed, After against Before, on new multi-domain questions written after the skills were frozen",
      href: "/before-after/results#holdout",
    });
  }
  if (judge?.rate != null) {
    const stricter =
      judge.lenient === 0 && judge.stricter > 0 ? `; in all ${judge.stricter} disagreements the judge was the stricter one` : "";
    items.push({
      label: "LLM judge against a person",
      value: pct(judge.rate),
      detail: `of facts graded the same on ${judge.replies} sampled replies, graded blind${stricter}`,
      href: "/models#judge",
    });
  }
  return items;
}

export default async function DemoPage() {
  const [recorded, results] = await Promise.all([STATIC_SITE ? getRecordedDemo() : null, highlights()]);
  return (
    <div className="flex flex-col gap-6">
      <section className="overflow-hidden rounded-2xl bg-ink px-5 py-7 text-white sm:px-8 sm:py-9">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-lime">Before vs after</p>
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          Single agent vs composable skills
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-white/80 sm:text-base">
          {LIVE ? "Ask both bots the same question" : "Compare both bots' replies to the same question"} and
          watch which guidance each one loads. They differ in how each message is
          routed and how the prompt is put together. The After bot also keeps some of the previous turn&apos;s skills
          for one more turn, which is a Fynn Lab addition.
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <ul className="flex flex-wrap gap-2" aria-label="What both bots share">
            {SAME.map((item) => (
              <li key={item} className="rounded-full border border-white/20 px-3 py-1 text-xs text-white/90">
                {item}
              </li>
            ))}
          </ul>
          <p className="rounded-full bg-lime px-3 py-1 text-xs font-semibold text-ink">
            <span className="sr-only">What differs: </span>Different routing
          </p>
        </div>
      </section>
      <section aria-labelledby="study" className="flex flex-col gap-3">
        <h2 id="study" className="text-base font-semibold text-ink">
          A study of how to evaluate a skill-based LLM assistant
        </h2>
        <p className="max-w-4xl text-sm leading-6 text-slate">
          The two bots below are the test bed. Around them: an eval set graded by an LLM judge, a regression check for
          every skill edit, a check of the judge against a person, and a plan for experiments on real traffic.
        </p>
        {results.length > 0 && (
          <ul className="grid gap-3 sm:grid-cols-3">
            {results.map((item) => (
              <li key={item.label}>
                <Link
                  href={item.href}
                  className="flex h-full flex-col gap-1 rounded-2xl border border-line bg-white p-4 transition-colors hover:border-ink"
                >
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate">{item.label}</span>
                  <span className="text-2xl font-semibold tracking-tight text-ink tabular-nums">{item.value}</span>
                  <span className="text-sm leading-5 text-slate">{item.detail}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <p className="text-sm">
          <Link href="/before-after/results" className="font-semibold text-ink underline underline-offset-2">
            Read the results
          </Link>
        </p>
      </section>
      {LIVE ? (
        <Demo recorded={recorded} />
      ) : recorded ? (
        <RecordedDemo data={recorded} />
      ) : (
        <p className="text-sm text-slate">The recorded demo (results/demo/recorded.json) is missing from this build.</p>
      )}
    </div>
  );
}
