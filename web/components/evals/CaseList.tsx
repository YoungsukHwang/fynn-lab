import type { EvalCase, PersonaInfo } from "@/lib/evalData";
import { DATASET_INFO, datasetLabel, questionsLabel } from "@/lib/evalLabels";

import { Chip, Expander } from "./ui";

function Patterns({ title, note, patterns }: { title: string; note: string; patterns: string[] }) {
  if (!patterns.length) return null;
  return (
    <div className="mt-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate">{title}</h4>
      <p className="mt-0.5 text-xs text-slate">{note}</p>
      <ul className="mt-1.5 space-y-1">
        {patterns.map((pattern) => (
          <li key={pattern}>
            <code className="block whitespace-pre-wrap break-all rounded-lg bg-canvas px-2 py-1 font-mono text-[11px] leading-4 text-ink">
              {pattern}
            </code>
          </li>
        ))}
      </ul>
    </div>
  );
}

function CaseDetails({ evalCase, persona }: { evalCase: EvalCase; persona: PersonaInfo | undefined }) {
  return (
    <Expander
      summary={
        <span className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-3">
          <span className="shrink-0 font-mono text-xs leading-5 text-slate">{evalCase.id}</span>
          <span className="min-w-0 flex-1 text-sm leading-5 text-ink">{evalCase.message}</span>
          <span className="shrink-0 text-xs leading-5 text-slate">{questionsLabel(evalCase.intents)}</span>
        </span>
      }
    >
      <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[8rem_minmax(0,1fr)]">
        <dt className="text-xs font-semibold uppercase tracking-wide text-slate">Member</dt>
        <dd className="text-ink">
          {persona ? `${persona.name} (${evalCase.persona})` : evalCase.persona}
        </dd>
        <dt className="text-xs font-semibold uppercase tracking-wide text-slate">Labeled skills</dt>
        <dd className="flex flex-wrap gap-1.5">
          {evalCase.skills.length ? (
            evalCase.skills.map((skill) => (
              <Chip key={skill} tone="fynn" mono>
                {skill}
              </Chip>
            ))
          ) : (
            <span className="text-slate">None (no topic skill is needed)</span>
          )}
        </dd>
      </dl>
      <h4 className="mt-3 text-xs font-semibold uppercase tracking-wide text-slate">Expected facts</h4>
      <ol className="mt-1.5 list-decimal space-y-1 pl-5 text-sm leading-6 text-ink marker:text-dim">
        {evalCase.expectedFacts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ol>
      <Patterns
        title="Banned patterns"
        note="Regular expressions, matched case-insensitively. Any match fails the case."
        patterns={evalCase.mustNotRegex}
      />
      <Patterns
        title="Required patterns"
        note="Regular expressions, matched case-insensitively. Each must appear in the reply."
        patterns={evalCase.mustIncludeRegex}
      />
    </Expander>
  );
}

/** Every eval case, grouped by dataset; each dataset and each case expands on demand. */
export function CaseList({ cases, personas }: { cases: EvalCase[]; personas: PersonaInfo[] }) {
  const personaById = new Map(personas.map((p) => [p.id, p]));
  const datasets = [...new Set(cases.map((c) => c.dataset))];
  return (
    <div className="space-y-3">
      {datasets.map((dataset) => {
        const inDataset = cases.filter((c) => c.dataset === dataset);
        return (
          <Expander
            key={dataset}
            tone="canvas"
            summary={
              <span className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-sm font-semibold text-ink">{datasetLabel(dataset)}</span>
                <span className="font-mono text-xs text-slate">{dataset}</span>
                <span className="text-xs text-slate">
                  {inDataset.length} {inDataset.length === 1 ? "case" : "cases"}
                </span>
                {DATASET_INFO[dataset] && (
                  <span className="basis-full text-xs leading-5 text-slate">{DATASET_INFO[dataset].description}</span>
                )}
              </span>
            }
          >
            <ul className="space-y-2">
              {inDataset.map((evalCase) => (
                <li key={evalCase.id}>
                  <CaseDetails evalCase={evalCase} persona={personaById.get(evalCase.persona)} />
                </li>
              ))}
            </ul>
          </Expander>
        );
      })}
    </div>
  );
}
