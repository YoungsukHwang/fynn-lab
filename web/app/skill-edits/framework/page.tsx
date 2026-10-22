import type { Metadata } from "next";
import Link from "next/link";

import { LoopDiagram } from "@/components/evals/LoopDiagram";
import { Chip, NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getFrameworkData } from "@/lib/evalData";
import { EXPECTED_LABELS, KIND_LABELS, plural } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Skill edits framework" };

const SECTIONS = [
  { href: "#loop", label: "The loop" },
  { href: "#selection", label: "Test selection" },
  { href: "#scenarios", label: "Scenarios" },
];

const SELECTION_RULES = [
  {
    change: "The body of a topic skill",
    rerun: "Cases labeled with that skill, plus cases whose baseline run actually loaded it",
    why: "A body is in the prompt only when its skill is loaded. The baseline's routing is checked too, because a case can load a skill it isn't labeled with. For the Before bot, loaded means routed to the skill's domain.",
  },
  {
    change: "The description of a topic skill",
    rerun: "All cases",
    why: "The router reads every description, so routing can change for any message, not just this skill's.",
  },
  {
    change: "Anything in an always-on skill",
    rerun: "All cases",
    why: "Always-on skills (tone, response rules, guardrails) are in every prompt.",
  },
  {
    change: "A skill's domain or type, or a skill added or removed",
    rerun: "All cases",
    why: "A domain change reshapes the Before bot's agents and router catalog. A type change moves a skill between the always-on and topic parts of the prompt.",
  },
  { change: "Nothing", rerun: "No cases", why: "There is nothing to retest." },
];

export default async function SkillEditsFrameworkPage() {
  const { cases, skills, scenarios } = await getFrameworkData();
  const topicSkills = skills.filter((s) => s.type === "topic");
  const alwaysOn = skills.filter((s) => s.type === "always_on");
  const most = Math.max(1, ...topicSkills.map((s) => cases.filter((c) => c.skills.includes(s.name)).length));

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Skill edits · Framework" title="Regression tests for every skill change">
        <p>
          Here, monitoring means offline regression testing on a fixed eval set. Before a skill edit ships, the test
          cases it can affect are rerun and compared with the last run. Production monitoring is out of scope for this
          version.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      {/* 1. The loop */}
      <section aria-labelledby="loop" className="flex flex-col gap-4">
        <SectionHeader id="loop" eyebrow="1 · The loop" title="Edit, test, report, decide">
          <p>
            Every change to a skill file goes through the same loop. Only the test cases that depend on the change are
            rerun, and the regression report decides whether it is safe to ship.
          </p>
        </SectionHeader>
        <LoopDiagram />
      </section>

      {/* 2. Dependent-test selection */}
      <section aria-labelledby="selection" className="flex flex-col gap-5">
        <SectionHeader id="selection" eyebrow="2 · Test selection" title="Rerun only what a change can affect">
          <p>
            Each skill keeps separate fingerprints (hashes) of its description, its body and its metadata (type and
            domain). Every results file stores those fingerprints and what the router picked for each case, so a new
            run can tell what changed and which cases depend on it. These rules are Fynn Lab&apos;s own.
          </p>
        </SectionHeader>

        {/* A table from md up; the same rules as a stacked list on phones (only one is ever displayed). */}
        <div className="overflow-hidden rounded-2xl border border-line bg-white">
          <table className="hidden w-full border-collapse text-left text-sm md:table">
            <caption className="sr-only">Which test cases are rerun for each kind of skill change</caption>
            <thead className="bg-canvas text-xs uppercase tracking-wide text-slate">
              <tr>
                <th scope="col" className="w-[24%] px-4 py-2.5 font-semibold">
                  What changed
                </th>
                <th scope="col" className="w-[30%] px-4 py-2.5 font-semibold">
                  Cases rerun
                </th>
                <th scope="col" className="px-4 py-2.5 font-semibold">
                  Why
                </th>
              </tr>
            </thead>
            <tbody>
              {SELECTION_RULES.map((rule) => (
                <tr key={rule.change} className="border-t border-line align-top">
                  <th scope="row" className="px-4 py-3 font-semibold text-ink">
                    {rule.change}
                  </th>
                  <td className="px-4 py-3 text-ink">{rule.rerun}</td>
                  <td className="px-4 py-3 text-slate">{rule.why}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="divide-y divide-line md:hidden">
            {SELECTION_RULES.map((rule) => (
              <li key={rule.change} className="px-4 py-3 text-sm leading-6">
                <p className="font-semibold text-ink">{rule.change}</p>
                <p className="text-ink">
                  <span className="font-semibold text-slate">Rerun: </span>
                  {rule.rerun}
                </p>
                <p className="text-slate">{rule.why}</p>
              </li>
            ))}
          </ul>
        </div>

        {topicSkills.length > 0 && (
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <h3 className="text-base font-semibold text-ink">Cases labeled with each topic skill</h3>
            <p className="mt-1 text-sm leading-6 text-slate">
              A body edit reruns these cases plus any case the baseline run routed to the skill.
              {alwaysOn.length > 0 &&
                ` The always-on skills (${alwaysOn.map((s) => s.name).join(", ")}) are in every prompt, so every case depends on them.`}
            </p>
            <ul className="mt-3 divide-y divide-line">
              {topicSkills.map((skill) => {
                const labeled = cases.filter((c) => c.skills.includes(skill.name));
                return (
                  <li key={skill.name} className="grid gap-1 py-2.5 sm:grid-cols-[13rem_minmax(0,1fr)] sm:gap-4">
                    <span>
                      <span className="font-mono text-xs font-medium text-ink">{skill.name}</span>
                      {skill.domain && <span className="block text-xs text-slate">domain: {skill.domain}</span>}
                    </span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-2">
                        <span aria-hidden="true" className="block h-2 flex-none rounded-r bg-fynn" style={{ width: `${(labeled.length / most) * 60}%` }} />
                        <span className="text-xs font-semibold text-ink">{plural(labeled.length, "case")}</span>
                      </span>
                      {labeled.length > 0 && (
                        <span className="mt-1 block text-xs leading-5 text-slate">{labeled.map((c) => c.id).join(", ")}</span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </section>

      {/* 3. Scenarios */}
      <section aria-labelledby="scenarios" className="flex flex-col gap-5">
        <SectionHeader id="scenarios" eyebrow="3 · Scenarios" title={`${plural(scenarios.length, "skill edit")} to the After bot`}>
          <p>
            Each scenario edits one skill on the After bot: a topic skill&apos;s body, its description, or an always-on
            skill. Its hypothesis was written down before the scenario ran; the results tab reports whether it held. The
            real{" "}
            <code className="font-mono text-xs text-ink">skills/</code> folder is never modified: a scenario&apos;s
            edited copy is laid over it at run time.
          </p>
        </SectionHeader>
        {scenarios.length ? (
          <ul className="grid gap-3 lg:grid-cols-3">
            {scenarios.map((scenario) => (
              <li key={scenario.id} className="flex flex-col overflow-hidden rounded-2xl border border-line bg-white">
                <div className="h-1.5 bg-fynn" aria-hidden="true" />
                <div className="flex flex-1 flex-col p-4 sm:p-5">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Chip tone="dark">{scenario.id.toUpperCase()}</Chip>
                    <Chip tone="fynn">{KIND_LABELS[scenario.kind] ?? scenario.kind}</Chip>
                  </div>
                  <h3 className="mt-2 text-base font-semibold leading-6 text-ink">{scenario.title}</h3>
                  <p className="mt-1 text-xs text-slate">
                    Skill: <span className="font-mono text-ink">{scenario.skill}</span>
                  </p>
                  <p className="mt-2 text-sm leading-6 text-slate">{scenario.change}</p>
                  <div className="mt-3 flex-1 rounded-xl bg-canvas px-3 py-2.5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate">
                      Hypothesis, written before the run
                    </p>
                    <p className="mt-0.5 text-sm font-semibold text-ink">
                      {EXPECTED_LABELS[scenario.hypothesis.expected] ?? scenario.hypothesis.expected}
                    </p>
                    <p className="mt-1 text-sm leading-6 text-slate">{scenario.hypothesis.detail}</p>
                  </div>
                  <Link
                    href={`/skill-edits/results#${scenario.id}`}
                    className="mt-3 self-start text-sm font-semibold text-ink underline underline-offset-2"
                  >
                    See the {scenario.id.toUpperCase()} result<span className="sr-only">: {scenario.title}</span>
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <NotGenerated title="Scenarios not found">No scenario.yaml files were found in scenarios/.</NotGenerated>
        )}
      </section>
    </div>
  );
}
