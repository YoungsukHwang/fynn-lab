import type { Metadata } from "next";

export const metadata: Metadata = { title: "Monitoring results" };

export default function ResultsPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Monitoring results</h1>
      <p className="mt-2 text-sm text-zinc-600">Coming in milestone M5, once the evals from M3 and M4 have run. This page will show:</p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-zinc-700">
        <li>Before vs after pass rates for each dataset, and by how many questions a message contains.</li>
        <li>
          Regression reports for three skill edits to the after bot: a clean improvement, an always-on edit with
          hidden regressions, and a description edit that shifts routing.
        </li>
      </ul>
    </div>
  );
}
