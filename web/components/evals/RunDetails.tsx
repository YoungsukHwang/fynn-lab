import type { Models, RunMeta } from "@/lib/evalData";
import { formatTimestamp, pct } from "@/lib/evalLabels";

import { NotGenerated } from "./ui";

export function sameModels(runs: RunMeta[]): Models | null {
  const first = runs[0]?.models;
  if (!first) return null;
  const same = runs.every(
    (run) =>
      run.models?.router === first.router && run.models?.agent === first.agent && run.models?.judge === first.judge,
  );
  return same ? first : null;
}

export function ModelList({ models }: { models: Models }) {
  return (
    <dl className="grid gap-2 sm:grid-cols-3">
      {(
        [
          ["Router (both bots)", models.router],
          ["Answering agent", models.agent],
          ["Judge", models.judge],
        ] as const
      ).map(([label, model]) => (
        <div key={label} className="rounded-xl bg-canvas px-3 py-2">
          <dt className="text-[11px] font-medium uppercase tracking-wide text-slate">{label}</dt>
          <dd className="mt-0.5 font-mono text-xs text-ink">{model}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Every results file read for a page: bot, scenario, when it ran, runs per case and pass counts. */
export function RunDetails({ runs }: { runs: RunMeta[] }) {
  if (!runs.length) {
    return <NotGenerated>No results files were found in the results directory when the site was built.</NotGenerated>;
  }
  const common = sameModels(runs);
  return (
    <>
      {common && (
        <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
          <h3 className="text-sm font-semibold text-ink">Models (the same in every run)</h3>
          <div className="mt-2">
            <ModelList models={common} />
          </div>
        </div>
      )}
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {runs.map((run) => (
          <li key={run.file} className="rounded-2xl border border-line bg-white p-4">
            <p className="flex flex-wrap items-baseline gap-x-2">
              <span className="text-sm font-semibold text-ink">{run.name || run.file}</span>
              <span className="font-mono text-xs text-slate">results/{run.file}</span>
            </p>
            <dl className="mt-2 grid grid-cols-[6rem_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs leading-5">
              <dt className="text-slate">Bot</dt>
              <dd className="text-ink">{run.bot === "before" ? "Before" : run.bot === "after" ? "After" : run.bot}</dd>
              {run.scenario && (
                <>
                  <dt className="text-slate">Scenario</dt>
                  <dd className="text-ink">{run.scenario.toUpperCase()}</dd>
                </>
              )}
              <dt className="text-slate">Written</dt>
              <dd className="text-ink">{formatTimestamp(run.createdAt)}</dd>
              <dt className="text-slate">Runs per case</dt>
              <dd className="text-ink">{run.repeats}</dd>
              <dt className="text-slate">Passed</dt>
              <dd className="text-ink">
                {run.passed} of {run.total} {run.repeats > 1 ? "runs" : "cases"} ({pct(run.rate)}), {run.errors}{" "}
                {run.errors === 1 ? "error" : "errors"}
              </dd>
              {run.selectionRule && (
                <>
                  <dt className="text-slate">Selection</dt>
                  <dd className="text-ink">{run.selectionRule}</dd>
                </>
              )}
            </dl>
            {!common && run.models && (
              <div className="mt-3">
                <ModelList models={run.models} />
              </div>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
