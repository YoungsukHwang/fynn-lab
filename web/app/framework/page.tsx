import type { Metadata } from "next";
import Link from "next/link";

import { CaseList } from "@/components/evals/CaseList";
import { LoopDiagram } from "@/components/evals/LoopDiagram";
import { Chip, NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getFrameworkData } from "@/lib/evalData";
import { DATASET_INFO, datasetLabel, EXPECTED_LABELS, KIND_LABELS, runsPerCase } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Monitoring framework" };

const SECTIONS = [
  { href: "#loop", label: "The loop" },
  { href: "#eval-set", label: "Eval set" },
  { href: "#scoring", label: "Scoring" },
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

const FACT_STATUSES = [
  { status: "PRESENT", tone: "lime" as const, text: "The reply states the fact or an equivalent." },
  { status: "ABSENT", tone: "neutral" as const, text: "The reply leaves it out, or is too vague to check." },
  { status: "CONTRADICTED", tone: "bad" as const, text: "The reply says something incompatible with it." },
];

const JUDGE_SUMMARY = [
  "It sees the member's profile, the message, the expected facts and the reply.",
  "It grades each expected fact on its own, using only the reply text.",
  "Paraphrase, a different order, or rounding that keeps the meaning still counts as PRESENT.",
  "A fact that holds only under a condition is CONTRADICTED if the reply states it as certain.",
  "A fact phrased as something to avoid, such as “does not promise approval”, is PRESENT when the reply avoids it.",
  "It ignores tone, formatting and extra correct content, and length is not evidence.",
  "It uses the profile only to check the figures, dates and product status a fact refers to.",
  "For each fact it writes a one-sentence note pointing at the reply, then a short overall reason.",
];

function StepCard({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex flex-col rounded-2xl border border-line bg-white p-4 sm:p-5">
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="grid h-6 w-6 place-items-center rounded-full bg-lime-soft text-xs font-semibold text-forest"
        >
          {n}
        </span>
        <h3 className="text-base font-semibold text-ink">{title}</h3>
      </div>
      <div className="mt-2 flex-1 text-sm leading-6 text-slate">{children}</div>
    </li>
  );
}

function runsSentence(repeats: { before: number | null; after: number | null }): string {
  const { before, after } = repeats;
  if (before === null && after === null) return "The runner can run each case several times (three is recommended).";
  if (before !== null && after !== null && before !== after) {
    return `In the latest full runs each case ran ${runsPerCase(before)} on the Before bot and ${runsPerCase(after)} on the After bot.`;
  }
  if (before === null || after === null) {
    const [bot, k] = after !== null ? ["After", after] : ["Before", before ?? 1];
    return `In the latest ${bot} run each case ran ${runsPerCase(k)}; the ${bot === "After" ? "Before" : "After"} bot has no full run yet.`;
  }
  return after === 1
    ? "In the latest full runs each case ran once per bot; the runner can repeat cases (three times is recommended)."
    : `In the latest full runs each case ran ${after} times per bot.`;
}

export default async function FrameworkPage() {
  const { repeats, cases, personas, skills, scenarios, judgeInstructions, judgeModel } = await getFrameworkData();

  const countBy = (key: (c: (typeof cases)[number]) => string) =>
    cases.reduce<Record<string, number>>((acc, c) => ({ ...acc, [key(c)]: (acc[key(c)] ?? 0) + 1 }), {});
  const casesPerPersona = countBy((c) => c.persona);
  const casesPerDataset = countBy((c) => c.dataset);
  const datasets = Object.keys(DATASET_INFO).filter((d) => casesPerDataset[d]).concat(
    Object.keys(casesPerDataset).filter((d) => !(d in DATASET_INFO)),
  );
  const withBanned = cases.filter((c) => c.mustNotRegex.length > 0).length;
  const withRequired = cases.filter((c) => c.mustIncludeRegex.length > 0).length;
  const topicSkills = skills.filter((s) => s.type === "topic");
  const alwaysOn = skills.filter((s) => s.type === "always_on");

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Monitoring framework" title="Regression tests for every skill change">
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

      {/* 2. Eval set */}
      <section aria-labelledby="eval-set" className="flex flex-col gap-5">
        <SectionHeader
          id="eval-set"
          eyebrow="2 · Eval set"
          title={
            cases.length
              ? `${cases.length} cases, ${personas.length} synthetic members, ${datasets.length} datasets`
              : "Eval set"
          }
        >
          <p>
            Each case is one member message, sent as a single-turn chat with nothing carried over from earlier turns.
            The members, their credit data and the products are fictional. The cases live in{" "}
            <code className="font-mono text-xs text-ink">backend/evals/cases/</code>.
          </p>
        </SectionHeader>

        <div>
          <h3 className="text-base font-semibold text-ink">Synthetic members</h3>
          {personas.length ? (
            <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {personas.map((persona) => (
                <li key={persona.id} className="rounded-2xl border border-line bg-white p-4">
                  <div className="flex items-start gap-3">
                    <span
                      aria-hidden="true"
                      className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-lime-soft text-sm font-semibold text-forest"
                    >
                      {persona.name.slice(0, 1)}
                    </span>
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-baseline gap-x-2 text-sm font-semibold text-ink">
                        {persona.name}
                        <span className="font-mono text-xs font-normal text-slate">{persona.id}</span>
                      </p>
                      <p className="text-xs text-slate">
                        {casesPerPersona[persona.id] ?? 0} {casesPerPersona[persona.id] === 1 ? "case" : "cases"}
                      </p>
                    </div>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate">{persona.summary}</p>
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-3">
              <NotGenerated title="Personas not found">No files were found in personas/.</NotGenerated>
            </div>
          )}
        </div>

        <div>
          <h3 className="text-base font-semibold text-ink">Datasets</h3>
          {datasets.length ? (
            <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {datasets.map((dataset) => (
                <li key={dataset} className="rounded-2xl border border-line bg-white p-4">
                  <p className="text-3xl font-semibold tracking-tight text-ink">{casesPerDataset[dataset]}</p>
                  <p className="mt-1 text-sm font-semibold text-ink">{datasetLabel(dataset)}</p>
                  <p className="font-mono text-xs text-slate">{dataset}</p>
                  {DATASET_INFO[dataset] && (
                    <p className="mt-2 text-sm leading-6 text-slate">{DATASET_INFO[dataset].description}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div>
          <h3 className="text-base font-semibold text-ink">All {cases.length || ""} test cases</h3>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate">
            Open a dataset, then a case, to see its member, the topic skills it is labeled with (what a correct After
            router should pick), the facts a good reply must contain, and any banned or required patterns.
          </p>
          <div className="mt-3">
            {cases.length ? (
              <CaseList cases={cases} personas={personas} />
            ) : (
              <NotGenerated title="Eval cases not found">No case files were found in backend/evals/cases/.</NotGenerated>
            )}
          </div>
        </div>
      </section>

      {/* 3. Scoring */}
      <section aria-labelledby="scoring" className="flex flex-col gap-5">
        <SectionHeader id="scoring" eyebrow="3 · Scoring" title="Code checks, then an LLM judge">
          <p>
            Every reply is scored in two steps. A case passes only if both pass.{" "}
            {runsSentence(repeats)}
          </p>
          <p>
            Replies vary from run to run, so every regression report also tests whether the overall pass rate moved
            more than that noise would explain: an exact McNemar test on the cases that flipped (one run per case) or
            an exact permutation test that shuffles each case&apos;s runs between the two sides (repeated runs). The
            per-dataset tests are Holm-corrected together, and an A/A noise floor is shown when one was measured.
            These test the net change, so a balanced tradeoff can read as not significant. With repeated runs, a case
            is flagged as regressed only when it fails at least m of its K runs (a majority by default) after passing
            every baseline run.
          </p>
        </SectionHeader>

        <ol className="grid gap-3 lg:grid-cols-3">
          <StepCard n={1} title="Code checks">
            <ul className="list-disc space-y-1.5 pl-5 marker:text-dim">
              <li>The reply must not be empty.</li>
              <li>
                No banned pattern may match ({withBanned} of {cases.length} cases have them). They catch only
                clear-cut violations, such as &ldquo;I guarantee&rdquo; or repeating a card number back; whether a
                sentence makes a promise in context is left to the judge.
              </li>
              <li>
                Every required pattern must appear ({withRequired} of {cases.length} cases have them), such as the
                member&apos;s own utilization figure.
              </li>
              <li>Patterns are matched case-insensitively.</li>
            </ul>
          </StepCard>
          <StepCard n={2} title="LLM judge">
            <p>
              {judgeModel ? (
                <>
                  <code className="font-mono text-xs text-ink">{judgeModel.model}</code>{" "}
                  {judgeModel.source === "results"
                    ? "(the judge model recorded in the latest results)"
                    : "(the configured default; no results recorded yet)"}
                </>
              ) : (
                "A larger model than the bots use"
              )}{" "}
              grades each expected fact of the case against the reply:
            </p>
            <ul className="mt-2 space-y-1.5">
              {FACT_STATUSES.map((item) => (
                <li key={item.status} className="flex flex-col items-start gap-1">
                  <Chip tone={item.tone}>{item.status}</Chip>
                  <span>{item.text}</span>
                </li>
              ))}
            </ul>
          </StepCard>
          <StepCard n={3} title="Verdict">
            <p>
              A case <strong className="font-semibold text-ink">passes</strong> only if every code check passes{" "}
              <strong className="font-semibold text-ink">and</strong> the judge grades every expected fact PRESENT.
            </p>
            <p className="mt-2">
              The verdict is computed in code from the grades, not by the judge. A case whose run errors counts as not
              passed. The three statuses and the every-fact rule are Fynn Lab&apos;s choices.
            </p>
          </StepCard>
        </ol>

        <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
          <h3 className="text-base font-semibold text-ink">What the judge is told, in plain English</h3>
          <ul className="mt-2 grid list-disc gap-x-8 gap-y-1.5 pl-5 text-sm leading-6 text-slate marker:text-dim md:grid-cols-2">
            {JUDGE_SUMMARY.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {judgeInstructions && (
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer font-medium text-ink">
                Full judge instructions (from backend/evals/judge.py)
              </summary>
              <pre className="mt-2 whitespace-pre-wrap break-words rounded-xl bg-canvas p-3 font-mono text-xs leading-5 text-ink">
                {judgeInstructions}
              </pre>
            </details>
          )}
        </div>
      </section>

      {/* 4. Dependent-test selection */}
      <section aria-labelledby="selection" className="flex flex-col gap-5">
        <SectionHeader id="selection" eyebrow="4 · Test selection" title="Rerun only what a change can affect">
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
          <details className="rounded-2xl border border-line bg-white p-4 text-sm sm:p-5">
            <summary className="cursor-pointer font-semibold text-ink">
              Which cases are labeled with each skill
            </summary>
            <p className="mt-2 text-sm leading-6 text-slate">
              Labels are the topic skills a correct After router should pick for the case. A body edit reruns these
              cases plus any case the baseline run routed to the skill.
              {alwaysOn.length > 0 &&
                ` The always-on skills (${alwaysOn.map((s) => s.name).join(", ")}) are in every prompt, so every case depends on them.`}
            </p>
            <ul className="mt-3 divide-y divide-line">
              {topicSkills.map((skill) => {
                const labeled = cases.filter((c) => c.skills.includes(skill.name));
                return (
                  <li key={skill.name} className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-start sm:gap-4">
                    <span className="sm:w-56 sm:shrink-0">
                      <span className="font-mono text-xs font-medium text-ink">{skill.name}</span>
                      {skill.domain && <span className="block text-xs text-slate">domain: {skill.domain}</span>}
                    </span>
                    <span className="text-xs leading-5 text-slate">
                      <span className="font-semibold text-ink">
                        {labeled.length} {labeled.length === 1 ? "case" : "cases"}
                      </span>
                      {labeled.length > 0 && `: ${labeled.map((c) => c.id).join(", ")}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          </details>
        )}
      </section>

      {/* 5. Scenarios */}
      <section aria-labelledby="scenarios" className="flex flex-col gap-5">
        <SectionHeader id="scenarios" eyebrow="5 · Scenarios" title="Three skill edits to the After bot">
          <p>
            Each scenario edits one skill on the After bot, one per kind of change. Its hypothesis was written down
            before the scenario ran; the results page reports whether it held. The real <code className="font-mono text-xs text-ink">skills/</code>{" "}
            folder is never modified: a scenario&apos;s edited copy is laid over it at run time.
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
                    href={`/results#${scenario.id}`}
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
