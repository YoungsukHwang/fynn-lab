import type { Metadata } from "next";

import { Demo } from "@/components/Demo";
import { RecordedDemo } from "@/components/RecordedDemo";
import { getRecordedDemo } from "@/lib/evalData";

// The layout's title template only applies to child segments, so the root page sets its full title.
export const metadata: Metadata = { title: { absolute: "Demo | Fynn Lab" } };

const SAME = ["Same skill files", "Same member profile", "Same answer model"];
// The static site (FYNN_STATIC_SITE=1, see next.config.ts) shows recorded replies: alone when it was built
// without a backend URL, or next to the live chat, as the fallback when the hosted backend does not answer.
const STATIC_SITE = process.env.FYNN_STATIC_SITE === "1";
const LIVE = !STATIC_SITE || Boolean(process.env.NEXT_PUBLIC_API_URL);

export default async function DemoPage() {
  const recorded = STATIC_SITE ? await getRecordedDemo() : null;
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
