import type { Metadata } from "next";

export const metadata: Metadata = { title: "Monitoring framework" };

export default function FrameworkPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight">Monitoring framework</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Here, monitoring means offline regression testing: every skill change is checked on a fixed eval set before it
        ships. Production monitoring is out of scope for this version.
      </p>
      <p className="mt-2 text-sm text-zinc-600">Coming in milestone M5. This page will show:</p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-zinc-700">
        <li>
          The regression loop: edit a skill, run the test cases that depend on it, read the regression report, then
          decide whether to ship.
        </li>
        <li>The eval set: synthetic personas, behavior datasets and example test cases.</li>
        <li>How answers are scored: code checks, plus an LLM judge that compares each answer with expected facts.</li>
        <li>The map from each skill to the test cases that depend on it.</li>
      </ul>
    </div>
  );
}
