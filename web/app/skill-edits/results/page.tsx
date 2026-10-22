import type { Metadata } from "next";

import { ScenarioCard } from "@/components/evals/ScenarioCard";
import { Chip, NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getPersonas, getResultsData } from "@/lib/evalData";
import { formatTimestamp, KIND_LABELS, listLabel, plural, pPhrase } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Skill edits results" };

export default async function SkillEditsResultsPage() {
  const [data, personas] = await Promise.all([getResultsData(), getPersonas()]);
  const personaNames = Object.fromEntries(personas.map((p) => [p.id, p.name]));
  const ran = data.scenarios.filter((s) => s.comparison);
  // Edits compared with an After run that a newer one has since replaced.
  const after = data.after?.meta ?? null;
  const older = ran.filter((s) => {
    const baselineAt = s.comparison?.report.baseline.createdAt;
    return Boolean(baselineAt) && baselineAt !== after?.createdAt;
  });
  const olderBaselines = [...new Set(older.map((s) => s.comparison?.report.baseline.createdAt ?? ""))];

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Skill edits · Results" title="What the skill edits did">
        <p>
          Each edit reran only the cases that depend on it and was compared with the After bot&apos;s full run. The
          verdict is Passed only when no case was flagged as regressed; the net-change test next to it says whether the
          overall pass rate moved by more than run-to-run noise.
        </p>
      </PageHero>

      {after && older.length > 0 && (
        <NotGenerated
          title={older.length === ran.length ? "These edits predate the current After run" : "Some edits predate the current After run"}
        >
          {listLabel(older.map((s) => s.scenario.id.toUpperCase()))} {older.length === 1 ? "was" : "were"} compared with
          the After run of {listLabel(olderBaselines.map(formatTimestamp))}, kept in results/archive/. The current After
          run ({formatTimestamp(after.createdAt)}) covers {after.cases} cases, so cases added since then show in{" "}
          {older.length === 1 ? "that edit" : "those edits"} only once {older.length === 1 ? "it is" : "they are"} rerun
          against it.
        </NotGenerated>
      )}

      <OnThisPage
        links={[
          { href: "#glance", label: "At a glance" },
          ...data.scenarios.map((s) => ({ href: `#${s.scenario.id}`, label: s.scenario.id.toUpperCase() })),
        ]}
      />

      {ran.length > 0 && (
        <section aria-labelledby="glance" className="rounded-2xl border border-line bg-white p-4 sm:p-5">
          <h2 id="glance" className="scroll-mt-6 text-base font-semibold text-ink">
            At a glance
          </h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[40rem] border-collapse text-left text-sm">
              <caption className="sr-only">Verdict, flagged cases and net-change test for each skill edit</caption>
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-slate">
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Edit
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Cases rerun
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Improved / regressed
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Net change
                  </th>
                  <th scope="col" className="py-2 pr-3 font-semibold">
                    Verdict
                  </th>
                  <th scope="col" className="py-2 font-semibold">
                    Hypothesis
                  </th>
                </tr>
              </thead>
              <tbody className="text-ink">
                {ran.map(({ scenario, comparison, run }) => {
                  const report = comparison?.report;
                  if (!report) return null;
                  const test = report.pairedTest;
                  return (
                    <tr key={scenario.id} className="border-b border-line align-top">
                      <th scope="row" className="py-2.5 pr-3 font-medium">
                        <a href={`#${scenario.id}`} className="underline underline-offset-2">
                          {scenario.id.toUpperCase()}
                        </a>
                        <span className="block text-xs font-normal text-slate">{KIND_LABELS[scenario.kind] ?? scenario.kind}</span>
                      </th>
                      <td className="py-2.5 pr-3">{run?.cases ?? report.selection.caseCount}</td>
                      <td className="py-2.5 pr-3">
                        <span className="text-forest">{report.counts.improved}</span>
                        {" / "}
                        <span className={report.counts.regressed ? "text-red-800" : ""}>{report.counts.regressed}</span>
                        {report.counts.unstable > 0 && (
                          <span className="block text-xs text-slate">{report.counts.unstable} unstable</span>
                        )}
                      </td>
                      <td className="py-2.5 pr-3">
                        {test ? pPhrase(test.overall.pValue, test.alpha) : "n/a"}
                        <span className="block text-xs text-slate">
                          {test?.overall.significant ? "significant" : test ? "not significant" : ""}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3">
                        <Chip tone={report.verdict === "Passed" ? "lime" : "bad"}>{report.verdict || "unknown"}</Chip>
                      </td>
                      <td className="py-2.5">
                        {report.hypothesisResult ? (
                          <Chip tone={report.hypothesisResult.matches ? "lime" : "neutral"}>
                            {report.hypothesisResult.matches ? "Matched" : "Did not match"}
                          </Chip>
                        ) : (
                          "n/a"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs leading-5 text-slate">
            Hypothesis matches come from the flagged counts, not from a significance test.
          </p>
        </section>
      )}

      <section aria-labelledby="edits" className="flex flex-col gap-4">
        <SectionHeader id="edits" eyebrow="Each edit" title={`The ${plural(data.scenarios.length, "report")}`}>
          <p>Each card gives the edit, its hypothesis, the cases rerun, and every case that changed.</p>
        </SectionHeader>
        {data.scenarios.length ? (
          data.scenarios.map((result) => (
            <ScenarioCard key={result.scenario.id} result={result} caseCount={data.caseCount} personaNames={personaNames} />
          ))
        ) : (
          <NotGenerated title="Scenarios not found">No scenario.yaml files were found in scenarios/.</NotGenerated>
        )}
      </section>
    </div>
  );
}
