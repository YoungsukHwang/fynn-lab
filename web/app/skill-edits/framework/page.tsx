import type { Metadata } from "next";
import Link from "next/link";

import { LoopDiagram } from "@/components/evals/LoopDiagram";
import { Chip, NotGenerated, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getFrameworkData } from "@/lib/evalData";
import { KIND_LABELS, plural } from "@/lib/evalLabels";

export const metadata: Metadata = { title: "Skill edits framework" };

const SECTIONS = [
  { href: "#loop", label: "The loop" },
  { href: "#rerun", label: "What reruns" },
  { href: "#counting", label: "Fixed, broken, chance" },
  { href: "#edits", label: "The edits" },
];

// Which cases each kind of change reruns, and the only way it can reach a case's answer.
const CHANGES = [
  {
    change: "A topic skill's body",
    rerun: "The cases labeled with that skill or routed to it last time",
    reaches:
      "A case whose answer loaded the edited skill both before and with the edit. The router never reads bodies, so when only one side loaded it, the router changed the prompt too and the flip is not put on the edit",
  },
  {
    change: "A topic skill's description",
    rerun: "Every case",
    reaches: "A case where the edited skill entered or left the routing, since only the router reads descriptions",
  },
  {
    change: "The skill cap",
    rerun: "Every case",
    reaches:
      "A case whose routing changed where the cap mattered: the run with the lower cap filled it, or the run with the higher cap went past it",
  },
  {
    change: "An always-on skill",
    rerun: "Every case",
    reaches: "Every case, since always-on skills are in every prompt",
  },
];

export default async function SkillEditsFrameworkPage() {
  const { scenarios } = await getFrameworkData();

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Skill edits · Framework" title="Checking a skill edit before it ships">
        <p>
          A skill edit is like a code change: it can fix one answer and quietly break another. So before an edit ships,
          the eval cases it can affect are rerun and compared with the last run of the After bot.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      <section aria-labelledby="loop" className="flex flex-col gap-4">
        <SectionHeader id="loop" eyebrow="1 · The loop" title="Edit, rerun, count, decide">
          <p>
            Every edit goes through the same loop. The real <code className="font-mono text-xs text-ink">skills/</code>{" "}
            folder is not touched while an edit is tested: its edited copy is laid over it for the run.
          </p>
        </SectionHeader>
        <LoopDiagram />
      </section>

      <section aria-labelledby="rerun" className="flex flex-col gap-4">
        <SectionHeader id="rerun" eyebrow="2 · What reruns" title="Rerun only what an edit can affect">
          <p>
            Each run records what the router picked for every case, so the next run knows which cases depend on which
            skill.
          </p>
        </SectionHeader>
        <ul className="grid gap-3 sm:grid-cols-2">
          {CHANGES.map((c) => (
            <li key={c.change} className="rounded-2xl border border-line bg-white p-4">
              <p className="text-sm font-semibold text-ink">{c.change}</p>
              <p className="mt-1 text-sm leading-6 text-slate">
                <span className="font-semibold text-ink">Reruns:</span> {c.rerun}.
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="counting" className="flex flex-col gap-4">
        <SectionHeader id="counting" eyebrow="3 · Fixed, broken, chance" title="Telling the edit apart from chance">
          <p>
            The same prompt can pass one time and fail the next: in cases these edits could not reach and whose routing
            did not change, about one in eight flipped between runs. The router also reorders, and now and then changes, its picks between identical
            runs. So a flip only counts for the edit when the edit itself could have changed that case&apos;s answering
            prompt (routes compare as sets, so a new order alone does not count). Descriptions and the cap are also in
            the router&apos;s instructions, so these rules assume such an edit acts only through the skills it adds or
            removes. Each kind of edit has one way in (when an edit also comes with a cap change, the cases where the
            cap mattered count too):
          </p>
        </SectionHeader>
        <ul className="divide-y divide-line rounded-2xl border border-line bg-white">
          {CHANGES.map((c) => (
            <li key={c.change} className="grid gap-1 px-4 py-3 text-sm leading-6 sm:grid-cols-[14rem_minmax(0,1fr)] sm:gap-4">
              <span className="font-semibold text-ink">{c.change}</span>
              <span className="text-slate">{c.reaches}.</span>
            </li>
          ))}
        </ul>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["Fixed by the edit", "The edit reached the case, and it now passes."],
            ["Broken by the edit", "The edit reached the case, and it now fails."],
            [
              "Flipped by chance",
              "Outside the edit's reach: the edit was not in the case's answering prompt, or was not the only thing that changed it.",
            ],
          ].map(([title, body]) => (
            <div key={title} className="rounded-2xl border border-line bg-white p-4">
              <p className="text-sm font-semibold text-ink">{title}</p>
              <p className="mt-1 text-sm leading-6 text-slate">{body}</p>
            </div>
          ))}
        </div>
        <p className="text-sm leading-6 text-slate">
          The decision follows from the first two: <span className="font-semibold text-ink">Ship</span> when the edit
          fixed cases and broke none, <span className="font-semibold text-ink">Tradeoff</span> when it broke some but
          fixed at least as many, <span className="font-semibold text-ink">Do not ship</span> when it broke more than it
          fixed, and <span className="font-semibold text-ink">No effect</span> when no case it could reach flipped. A
          case the edit could reach may still have flipped by chance. So the decision counts as backed only when an exact
          test on the cases the edit could reach is significant in the decision&apos;s direction; otherwise it is shown
          as a <span className="font-semibold text-ink">lead</span> (for example &ldquo;Lead: ship&rdquo;): worth
          checking with more runs, not proof. A tradeoff is always a lead. With one run per case the test compares fixed
          against broken, so a Ship needs at least six fixed cases and none broken, and a Do not ship at least six
          broken and none fixed (or eight against one); with more runs it is the run-permutation test on those cases.
          Whether a case is reached depends on its routing, not on its result, so the cases outside the reach can be
          set aside for this test.
        </p>
      </section>

      <section aria-labelledby="edits" className="flex flex-col gap-5">
        <SectionHeader id="edits" eyebrow="4 · The edits" title={`${plural(scenarios.length, "skill edit")}, and a cap change`}>
          <p>
            Each edit changes one skill on the After bot. The cap change lets the router pick four skills instead of
            three.
          </p>
        </SectionHeader>
        {scenarios.length ? (
          <ul className="grid gap-3 lg:grid-cols-3">
            {scenarios.map((scenario) => (
              <li key={scenario.id} className="flex flex-col rounded-2xl border border-line bg-white p-4 sm:p-5">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Chip tone="dark">{scenario.id.toUpperCase()}</Chip>
                  <Chip tone="fynn">{KIND_LABELS[scenario.kind] ?? scenario.kind}</Chip>
                  {scenario.shipped && <Chip tone="lime">Shipped {scenario.shipped}</Chip>}
                </div>
                <h3 className="mt-2 text-base font-semibold leading-6 text-ink">{scenario.title}</h3>
                <p className="mt-1 text-xs text-slate">
                  Skill: <span className="font-mono text-ink">{scenario.skill}</span>
                </p>
                <p className="mt-2 flex-1 text-sm leading-6 text-slate">{scenario.change}</p>
                <Link
                  href={`/skill-edits/results#${scenario.id}`}
                  className="mt-3 self-start text-sm font-semibold text-ink underline underline-offset-2"
                >
                  See the {scenario.id.toUpperCase()} result<span className="sr-only">: {scenario.title}</span>
                </Link>
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
