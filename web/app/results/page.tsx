import type { Metadata } from "next";

export const metadata: Metadata = { title: "Monitoring results" };

export default function ResultsPage() {
  return (
    <div className="max-w-3xl rounded-2xl border border-line bg-white p-6 sm:p-8">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-forest">Coming in milestone M5</p>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Monitoring results</h1>
      <p className="mt-2 text-sm leading-6 text-slate">
        Results of offline regression testing on a fixed eval set, filled in once the evals from M3 and M4 have run.
      </p>
      <p className="mt-4 text-sm font-semibold text-ink">This page will show:</p>
      <ul className="mt-3 list-disc space-y-2 pl-5 marker:text-dim text-sm text-ink">
        <li>Before vs after pass rates for each dataset, and by how many questions a message contains.</li>
        <li>
          Regression reports for three skill edits to the After bot: a topic-skill body edit, an always-on skill edit,
          and a skill description edit. Each comes with the hypothesis written before the run, and whether the result
          matched it.
        </li>
      </ul>
    </div>
  );
}
