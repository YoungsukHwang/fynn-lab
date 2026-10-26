import type { Metadata } from "next";

import { EditCard, type EditResult, EditScorecard } from "@/components/evals/EditResults";
import { NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getCapData, getPersonas, getResultsData } from "@/lib/evalData";
import { KIND_LABELS } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Skill edits results" };

export default async function SkillEditsResultsPage() {
  const [data, capData, personas] = await Promise.all([getResultsData(), getCapData(), getPersonas()]);
  const personaNames = Object.fromEntries(personas.map((p) => [p.id, p.name]));

  const edits: EditResult[] = data.scenarios.map(({ scenario, run, comparison }) => ({
    id: scenario.id,
    label: scenario.id.toUpperCase(),
    title: scenario.title,
    kind: KIND_LABELS[scenario.kind] ?? scenario.kind,
    skill: scenario.skill,
    change: scenario.change,
    why: scenario.motivation,
    shipped: scenario.shipped,
    rerun: run?.cases ?? null,
    outOf: comparison?.baselineCases ?? null,
    comparison,
  }));
  if (capData.comparison) {
    edits.push({
      id: "cap4",
      label: `Cap ${capData.cap ?? "?"}`,
      title: `Raise the skill cap from ${capData.baselineCap ?? "?"} to ${capData.cap ?? "?"}`,
      kind: "Skill cap",
      skill: null,
      change: `The After router may pick up to ${capData.cap ?? "?"} new topic skills per message instead of ${capData.baselineCap ?? "?"}.`,
      why: `${capData.overCap.length} cases are labeled with more topic skills than the cap of ${capData.baselineCap ?? "?"}, so the router had to leave one out.`,
      shipped: capData.shipped,
      rerun: capData.runCases,
      outOf: capData.comparison.baselineCases,
      comparison: capData.comparison,
    });
  }
  const ran = edits.filter((e) => e.comparison?.report.attribution);

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Skill edits · Results" title="What each skill edit did">
        <p>
          Each edit changed one skill (or the skill cap) on the After bot and reran the cases it could affect. A case
          counts as fixed or broken by the edit only when the edit could reach its prompt. The rest count as chance:
          the same prompt can pass once and fail the next time, and the router now and then changes its picks.
        </p>
        <p>
          Three smaller routing fixes to skill descriptions shipped on 2026-10-23 alongside the cap change; their
          reports are in the repository&apos;s history rather than on this page.
        </p>
      </PageHero>

      <OnThisPage
        links={[{ href: "#scorecard", label: "All edits" }, ...edits.map((e) => ({ href: `#${e.id}`, label: e.label }))]}
      />

      <section aria-labelledby="scorecard" className="flex flex-col gap-4">
        <SectionHeader id="scorecard" eyebrow="All edits" title="Fixed, broken, or chance">
          <p>
            Ship means the edit fixed cases and broke none. Tradeoff means it broke some but fixed at least as many. Do
            not ship means it broke more than it fixed. No effect means no case it could reach flipped. A decision the
            paired test of the net change does not back (a significant gain for Ship, a significant loss for Do not
            ship) is shown as a lead, such as &ldquo;Lead: ship&rdquo;: a case the edit could reach may still have
            flipped by chance. With one run per case, few edits flip enough cases for the test to back them.
          </p>
        </SectionHeader>
        {ran.length ? (
          <EditScorecard edits={edits} />
        ) : (
          <NotGenerated title="No edit has a report yet">Run a scenario and its report, then rebuild.</NotGenerated>
        )}
      </section>

      <section aria-labelledby="edits" className="flex flex-col gap-4">
        <SectionHeader id="edits" eyebrow="Each edit" title="The cases behind each decision">
          <p>Open a case to read the reply before and with the edit, and why the judge failed one of them.</p>
        </SectionHeader>
        {edits.map((edit) => (
          <EditCard key={edit.id} edit={edit} personaNames={personaNames} />
        ))}
      </section>
    </div>
  );
}
