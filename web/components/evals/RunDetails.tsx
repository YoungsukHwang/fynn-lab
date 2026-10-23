import type { Models } from "@/lib/evalData";

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
