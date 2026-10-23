import type { Metadata } from "next";
import Link from "next/link";

import { CaseList } from "@/components/evals/CaseList";
import { Chip, NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { caseDomains, getFrameworkData, getSkillCap } from "@/lib/evalData";
import { DATASET_INFO, datasetLabel, plural } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Before vs After framework" };

const SECTIONS = [
  { href: "#designs", label: "The two designs" },
  { href: "#domains", label: "Which cases can differ" },
  { href: "#eval-set", label: "Eval set" },
  { href: "#scoring", label: "Scoring" },
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

function DesignCard({
  tone,
  name,
  title,
  points,
}: {
  tone: "before" | "after";
  name: string;
  title: string;
  points: React.ReactNode[];
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-line bg-white">
      <div aria-hidden="true" className={`h-1.5 ${tone === "before" ? "bg-coral" : "bg-fynn"}`} />
      <div className="p-4 sm:p-5">
        <p className={`text-sm font-semibold ${tone === "before" ? "text-ember" : "text-cobalt"}`}>{name}</p>
        <h3 className="mt-0.5 text-lg font-semibold tracking-tight text-ink">{title}</h3>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate marker:text-dim">
          {points.map((point, i) => (
            <li key={i}>{point}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default async function BeforeAfterFrameworkPage() {
  const [{ cases, personas, skills, judgeInstructions, judgeModel }, cap] = await Promise.all([
    getFrameworkData(),
    getSkillCap(),
  ]);
  const capText = cap ?? "a fixed number of";
  const overCap = cap === null ? [] : cases.filter((c) => c.skills.length > cap);
  const added = cases.filter((c) => c.added); // cases written after the first Before vs After run
  const addedDates = [...new Set(added.flatMap((c) => (c.added ? [c.added] : [])))].sort();

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

  // The Before bot's domains, each with the topic skills its one agent always sees.
  const domains = [...new Set(topicSkills.map((s) => s.domain).filter((d): d is string => Boolean(d)))].sort();
  const skillDomain = new Map(topicSkills.flatMap((s) => (s.domain ? [[s.name, s.domain] as const] : [])));
  const spans = cases.map((c) => ({ evalCase: c, domains: caseDomains(c, skillDomain) }));
  const cross = spans.filter((s) => s.domains.length > 1);
  const crossIds = new Set(cross.map((s) => s.evalCase.id));
  const addedNeedSecond = added.filter((c) => crossIds.has(c.id)).length;
  // "mi-013 to mi-036" when the added ids run on without a gap in one dataset; otherwise list them.
  const addedNumbers = added.map((c) => Number(c.id.slice(3)));
  const addedRange =
    added.length > 1 &&
    new Set(added.map((c) => c.dataset)).size === 1 &&
    addedNumbers.every((n, i) => i === 0 || n === (addedNumbers[i - 1] ?? 0) + 1)
      ? `${added[0]?.id} to ${added[added.length - 1]?.id}`
      : added.map((c) => c.id).join(", ");
  const crossPerDataset = cross.reduce<Record<string, number>>(
    (acc, s) => ({ ...acc, [s.evalCase.dataset]: (acc[s.evalCase.dataset] ?? 0) + 1 }),
    {},
  );

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Before vs After · Framework" title="How the two bots are compared">
        <p>
          Both bots answer the same {cases.length || ""} member messages with the same skill files, member profiles and
          answer model. Only the routing and the way each prompt is put together differ. Each reply is scored against a
          fixed list of facts it should contain.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      {/* 1. The two designs */}
      <section aria-labelledby="designs" className="flex flex-col gap-4">
        <SectionHeader id="designs" eyebrow="1 · The two designs" title="One domain agent, or the skills the message needs">
          <p>
            Both designs come from the post. The products, the personas and the four Before agents are Fynn Lab&apos;s
            own, and so are the After bot&apos;s cap of {capText} new skills per message and its carry-over. Try them
            side by side on the{" "}
            <Link href="/" className="font-medium text-ink underline underline-offset-2">
              Demo
            </Link>
            .
          </p>
        </SectionHeader>
        <div className="grid gap-3 lg:grid-cols-2">
          <DesignCard
            tone="before"
            name="Before"
            title="Single-agent router"
            points={[
              "A small model picks one domain for the whole message.",
              "That domain's agent answers with every topic skill in its domain, plus the always-on skills.",
              "A message that spans two domains still gets only one domain's skills.",
            ]}
          />
          <DesignCard
            tone="after"
            name="After"
            title="Composable skills"
            points={[
              `A small model picks up to ${capText} topic skills for the message, from any domain.`,
              "One agent answers with those skills plus the always-on skills.",
              "It carries up to 2 of the previous turn's skills for one more turn (not used here: every case is a single turn).",
            ]}
          />
        </div>
      </section>

      {/* 2. Which cases can differ */}
      <section aria-labelledby="domains" className="flex flex-col gap-4">
        <SectionHeader
          id="domains"
          eyebrow="2 · Which cases can differ"
          title={`${cross.length} of ${cases.length} cases need more than one domain`}
        >
          <p>
            Each Before agent holds every topic skill of its domain. When a message stays inside one domain, the Before
            agent already has every skill the case is labeled with, usually with a few neighbors, while the After bot
            loads only the skills it routes to. So composing skills can add missing guidance only when a message needs
            skills from two or more domains. In the other cases the two prompts still differ (full domain against a
            routed subset), so their results can differ too, but not because one bot lacks a needed skill.
          </p>
        </SectionHeader>

        {domains.length > 0 && (
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <h3 className="text-base font-semibold text-ink">What each Before agent sees</h3>
            <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {domains.map((domain) => (
                <li key={domain} className="rounded-xl bg-canvas px-3 py-2.5">
                  <p className="text-sm font-semibold text-ink">{domain}</p>
                  <ul className="mt-1.5 flex flex-wrap gap-1">
                    {topicSkills
                      .filter((s) => s.domain === domain)
                      .map((s) => (
                        <li key={s.name}>
                          <Chip mono>{s.name}</Chip>
                        </li>
                      ))}
                  </ul>
                </li>
              ))}
            </ul>
            {alwaysOn.length > 0 && (
              <p className="mt-3 text-xs leading-5 text-slate">
                Always-on, in every prompt of both bots: {alwaysOn.map((s) => s.name).join(", ")}.
              </p>
            )}
          </div>
        )}

        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <p className="text-sm font-semibold text-ink">Cases that need a second domain</p>
            <p className="mt-1 text-4xl font-semibold tracking-tight text-ink">
              {cross.length}
              <span className="text-lg font-medium text-slate"> of {cases.length}</span>
            </p>
            <table className="mt-3 w-full border-collapse text-left text-xs">
              <caption className="sr-only">Cases that need a second domain, by dataset</caption>
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wide text-slate">
                  <th scope="col" className="py-1.5 pr-2 font-semibold">
                    Dataset
                  </th>
                  <th scope="col" className="py-1.5 pr-2 font-semibold">
                    Cases
                  </th>
                  <th scope="col" className="py-1.5 font-semibold">
                    Need a second domain
                  </th>
                </tr>
              </thead>
              <tbody className="text-ink">
                {datasets.map((d) => (
                  <tr key={d} className="border-b border-line">
                    <th scope="row" className="py-1.5 pr-2 font-medium">
                      {datasetLabel(d)}
                    </th>
                    <td className="py-1.5 pr-2">{casesPerDataset[d]}</td>
                    <td className="py-1.5">{crossPerDataset[d] ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <p className="text-sm font-semibold text-ink">The cases, and the domains their labeled skills span</p>
            <ul className="mt-2 divide-y divide-line">
              {cross.map(({ evalCase, domains: spanned }) => (
                <li key={evalCase.id} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-start sm:gap-3">
                  <span className="shrink-0 font-mono text-xs leading-5 text-slate">{evalCase.id}</span>
                  <span className="min-w-0 flex-1 text-xs leading-5 text-ink">
                    {plural(evalCase.intents, "question")}: {spanned.join(", ")}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs leading-5 text-slate">
              Labels are the topic skills a correct After router should pick. A case can also lean on a skill it is not
              labeled with; the Before agent gets such neighbors for free when they sit in its domain.
            </p>
          </div>
        </div>

        {overCap.length > 0 && (
          <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
            <p className="text-sm font-semibold text-ink">
              {plural(overCap.length, "case")} {overCap.length === 1 ? "needs" : "need"} more topic skills than the After
              bot&apos;s cap of {cap}
            </p>
            <p className="mt-1 text-sm leading-6 text-slate">
              The After router can pick at most {cap} new skills per message, so on these cases it must leave one out.
              They show what raising the cap would change (
              <Link href="/before-after/results#cap" className="font-medium text-ink underline underline-offset-2">
                the cap result
              </Link>
              ).
            </p>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {overCap.map((c) => (
                <li key={c.id}>
                  <Chip mono>
                    {c.id}: {c.skills.length} skills
                  </Chip>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* 3. Eval set */}
      <section aria-labelledby="eval-set" className="flex flex-col gap-5">
        <SectionHeader
          id="eval-set"
          eyebrow="3 · Eval set"
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
          {added.length > 0 && (
            <p>
              {plural(added.length, "case")} ({addedRange}) {added.length === 1 ? "was" : "were"} added on{" "}
              {addedDates.join(" and ")}, after the first Before vs After run showed little difference, to test where the
              two designs differ.{" "}
              {addedNeedSecond === added.length
                ? "Each needs a second domain"
                : `${addedNeedSecond} of them need a second domain`}
              , so they weigh the overall pass rate toward the cases where After can gain. The results tab shows them
              apart from the cases of the first run.
            </p>
          )}
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
                      <p className="text-xs text-slate">{plural(casesPerPersona[persona.id] ?? 0, "case")}</p>
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

      {/* 4. Scoring */}
      <section aria-labelledby="scoring" className="flex flex-col gap-5">
        <SectionHeader id="scoring" eyebrow="4 · Scoring" title="Code checks, then an LLM judge">
          <p>
            Every reply is scored in two steps, and a case passes only if both pass. How to tell a real difference from
            run-to-run variation is on the{" "}
            <Link href="/noise/framework" className="font-medium text-ink underline underline-offset-2">
              Noise &amp; A/A
            </Link>{" "}
            tab.
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
              passed. The three statuses and the every-fact rule are Fynn Lab&apos;s choices. Because one missed fact
              fails a whole case, the results also show the share of facts present.
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
    </div>
  );
}
