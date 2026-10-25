import type { Metadata } from "next";
import Link from "next/link";

import { StepNumber } from "@/components/evals/LoopDiagram";
import { Chip, type ChipTone, Expander, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getFrameworkData } from "@/lib/evalData";

export const metadata: Metadata = { title: "Online evaluation framework" };

const SECTIONS = [
  { href: "#why", label: "Offline vs online" },
  { href: "#measure", label: "What to measure" },
  { href: "#ab-test", label: "A/B test" },
  { href: "#causal", label: "No random split" },
  { href: "#launch", label: "Launch" },
];

const LINK = "font-medium text-ink underline underline-offset-2";

// Chip tones avoid fynn and peach, which mean the After and Before bots everywhere else on the site.
function cards(personaCount: string): { chip: string; tone: ChipTone; items: string[] }[] {
  return [
    {
      chip: "Carries over",
      tone: "lime",
      items: [
        "Code checks on every reply, such as a banned “I guarantee”.",
        "The LLM judge, grading by a rubric (a fixed list of questions for any reply), after its grades are checked against human reviewers.",
        "The skill files and guardrails.",
      ],
    },
    {
      chip: "Stays offline",
      tone: "neutral",
      items: [
        "Expected facts and the pass or fail verdict.",
        "The same members on every run.",
        "Both bots answering the same message. Online, each member sees one bot.",
      ],
    },
    {
      chip: "Only online",
      tone: "dark",
      items: [
        "Follow-up turns. Every offline case is one turn, so the After bot's carry-over is never tested offline.",
        `Typos, new topics, and credit files unlike those of the ${personaCount}.`,
        "Whether a reply helped, not only whether it had the facts.",
      ],
    },
  ];
}

type Entry = { name: string; text: string };

const LANES: { eyebrow: string; title: string; entries: Entry[]; style: "decides" | "plain" | "later"; note?: string }[] = [
  {
    eyebrow: "Decides",
    title: "One primary metric",
    style: "decides",
    entries: [
      {
        name: "Asked again within a day",
        text: "The same question within 24 hours, matched by meaning. A follow-up that builds on the answer does not count. Lower is better.",
      },
    ],
  },
  {
    eyebrow: "Can stop it",
    title: "Guardrails",
    style: "plain",
    entries: [
      { name: "Safety violations", text: "Promising a score gain, suggesting a product to a member in hardship, repeating a card number." },
      { name: "Preventable handoffs", text: "Chats sent to human support that the coach should have solved." },
      { name: "Latency, 95th percentile", text: "95 of 100 replies arrive within it. An average hides the slow ones." },
      { name: "Cost per chat", text: "Before and After load different skills, so cost is measured." },
    ],
  },
  {
    eyebrow: "Explains",
    title: "Read, not decisive",
    style: "plain",
    entries: [
      {
        name: "Judged quality",
        text: "The judge grades a random daily sample. Risky topics (hardship, collections, disputes) get extra samples, weighted back to their real share. A weekly human audit, blind to version, shows whether the judge can be trusted.",
      },
      { name: "Thumbs up or down", text: "Few members click, and those who do tend to feel strongly." },
    ],
  },
  {
    eyebrow: "Too slow to decide a test",
    title: "Long-term outcomes",
    style: "later",
    entries: [
      {
        name: "What members do next",
        text: "Paying a card down before the statement date, on-time payments, staying with the app.",
      },
    ],
    note: "A small holdout kept on the old version for months shows whether gains on fast metrics reach these. If they never do, the fast metric is the wrong target.",
  },
];

const RULES: Entry[] = [
  {
    name: "Split and analyze by member",
    text: "Each member sees one version on every visit and device, so no chat switches bots mid-way. Per-reply metrics such as latency are combined per member, since one member's messages are alike.",
  },
  {
    name: "Count members from their first coach chat",
    text: "Others cannot be affected. Nobody sees a difference before opening the coach, so both groups open it at the same rate.",
  },
  {
    name: "Name one primary metric",
    text: "If a change does nothing, 20 metrics tested at 5% still show about one significant result by chance, as likely against B as for it. Correct the rest, for example with the Holm method, which keeps the chance of any false win at 5% or less.",
  },
  {
    name: "Set guardrail margins",
    text: "Guardrails need not improve. They must not get worse by more than a margin set in advance.",
  },
  {
    name: "Run whole weeks",
    text: "Long enough to reach the planned size. Weekdays and weekends differ, reactions to anything new fade (compare week one with week two), and payday outcomes need a full monthly cycle.",
  },
  {
    name: "Look once, at the planned end",
    text: "Stopping the first time the result looks significant makes false wins far more common than 5%. Sequential testing allows repeated looks without raising the false-win rate. Stopping early for harm is fine.",
  },
  {
    name: "Watch for spillover",
    text: "If B sends fewer members to human support, A's queue gets shorter too, and A looks better than it would alone.",
  },
];

type Method = { situation: string; method: string; what: string; assumes: string; probe: string };

// In the order of the tree: how the change reaches members picks the method.
const METHODS: Method[] = [
  {
    situation: "To everyone on one date (an urgent guardrails fix)",
    method: "Interrupted time series",
    what: "A break at the launch date, against the earlier trend.",
    assumes: "The trend would have continued, and nothing else that moves the outcome changed that date.",
    probe: "Fake dates, and a metric the change should not touch, show no break.",
  },
  {
    situation: "In waves (a few states first)",
    method: "Difference-in-differences",
    what: "The change in switched members, minus the change over the same weeks in members not yet switched.",
    assumes: "Parallel trends: without the change, both groups would have moved alike.",
    probe: "Parallel lines before launch. A fake earlier launch date finds nothing.",
  },
  {
    situation: "To one whole state, never the others",
    method: "Synthetic control",
    what: "That state against a weighted mix of the others.",
    assumes: "The mix would have kept tracking that state, and nothing else that moves the outcome changed at the same time.",
    probe: "A close fit before launch. Other states, run as fake switches, rarely show as large a gap.",
  },
  {
    situation: "Past a cutoff (hypothetical: a check-in only at 50% card utilization or more)",
    method: "Regression discontinuity",
    what: "Members just above against just below. Holds only near the cutoff.",
    assumes: "Members cannot place themselves precisely on one side, and nothing else changes at the cutoff.",
    probe: "No pile-up on either side. Traits measured before are smooth across it.",
  },
  {
    situation: "As an opt-in, with an invitation sent to a random half",
    method: "Encouragement design (instrumental variables)",
    what: "The gap between invited and not invited, scaled by the rise in coach use, estimates the coach's effect for members who use it because they were invited.",
    assumes: "The invitation acts only through coach use, and no one uses the coach less because of it.",
    probe: "The rise in use can be measured. Acting only through the coach can only be argued.",
  },
  {
    situation: "As an opt-in, with nothing random (turning on Rent Reporting)",
    method: "Propensity score matching or weighting",
    what: "Members who chose it against members who did not but had the same chance of choosing, judged from what was known before.",
    assumes: "No hidden confounders: every reason behind both the choice and the outcome is measured.",
    probe: "The groups match on measured traits. Members with no match are left out, so the result covers only those who remain. A sensitivity analysis asks how strong a hidden reason must be to erase the result.",
  },
];

const STEPS: { title: string; who: string; body: React.ReactNode }[] = [
  {
    title: "Offline gate",
    who: "Offline",
    body: (
      <>
        Rerun the cases the change can affect, as on{" "}
        <Link href="/skill-edits/framework" className={LINK}>
          Skill edits
        </Link>
        . Go on only with a Ship decision and no guardrail misses.
      </>
    ),
  },
  {
    title: "Canary",
    who: "About 1%",
    body: "A day or two, to catch crashes, slow replies, cost spikes and safety flags, with a quick rollback. It does not measure the effect.",
  },
  {
    title: "A/B test",
    who: "50/50",
    body: (
      <>
        By member, with every rule in{" "}
        <a href="#ab-test" className={LINK}>
          section 3
        </a>{" "}
        set in advance.
      </>
    ),
  },
  {
    title: "Readout",
    who: "Test over",
    body: "The split first: if it is more uneven than chance allows (a sample ratio mismatch), something is broken and the result is not read. Then the guardrails, then the primary metric with its confidence interval (the range of effects the data are consistent with). Segment cuts are ideas for the next test, not findings. Write the decision down: ship, change or drop.",
  },
  {
    title: "Rollout",
    who: "All but a holdout",
    body: "Everyone else, in steps if risky, while watching the guardrails. A small holdout stays on the old version for months.",
  },
  {
    title: "Monitoring",
    who: "Daily and weekly",
    body: "Code checks, a judge sample, latency and cost every day. A human audit every week. An alert on any guardrail breach.",
  },
];

const FEEDBACK: Entry[] = [
  {
    name: "Turn failures into cases",
    text: "A thumbs down, a repeated question, a judge or reviewer flag, or a safety catch becomes a new offline case, with personal details removed, a synthetic member attached and expected facts written by a reviewer.",
  },
  {
    name: "Check that offline predicts online",
    text: "Over many launches, offline wins should mostly become online wins, allowing for noise in both. If they do not, the eval set or the judge is measuring the wrong thing.",
  },
];

const LANE_STYLES = {
  decides: { box: "bg-ink text-white", eyebrow: "text-lime", title: "text-white", rule: "border-white/15", dd: "text-white/80" },
  plain: { box: "border border-line bg-white", eyebrow: "text-forest", title: "text-ink", rule: "border-line", dd: "text-slate" },
  later: {
    box: "border border-dashed border-field bg-white",
    eyebrow: "text-forest",
    title: "text-ink",
    rule: "border-line",
    dd: "text-slate",
  },
} as const;

const LABEL = "block text-[11px] font-semibold uppercase tracking-wide text-forest";

export default async function OnlineEvaluationPage() {
  const { cases, personas } = await getFrameworkData();
  const caseCount = cases.length ? `${cases.length} test cases` : "test cases";
  const personaCount = personas.length ? `${personas.length} synthetic members` : "synthetic members";

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Online evaluation · Framework" title="How the bots would be tested with real members">
        <p>
          Fynn Lab is not deployed, so there are no real chats and no online results. This page is the plan for the day it
          is.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      <section aria-labelledby="why" className="flex flex-col gap-4">
        <SectionHeader id="why" eyebrow="1 · Offline vs online" title="Real chats have no answer key">
          <p>
            Offline, each of the {caseCount} lists the facts a good reply must contain (
            <Link href="/before-after/framework#scoring" className={LINK}>
              scoring
            </Link>
            ). A real message arrives with no such list.
          </p>
        </SectionHeader>
        <div className="grid gap-3 md:grid-cols-3">
          {cards(personaCount).map((card) => (
            <div key={card.chip} className="rounded-2xl border border-line bg-white p-4 sm:p-5">
              <Chip tone={card.tone}>{card.chip}</Chip>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate marker:text-dim">
                {card.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="measure" className="flex flex-col gap-4">
        <SectionHeader id="measure" eyebrow="2 · What to measure" title="One metric decides, guardrails can stop it">
          <p>Each metric gets one job, set before the test starts.</p>
        </SectionHeader>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {LANES.map((lane) => {
            const s = LANE_STYLES[lane.style];
            return (
              <li key={lane.title} className={`flex flex-col rounded-2xl p-4 sm:p-5 ${s.box}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-wide ${s.eyebrow}`}>{lane.eyebrow}</p>
                <div className="mt-1 flex flex-wrap items-center gap-2">
                  <h3 className={`text-base font-semibold ${s.title}`}>{lane.title}</h3>
                  {lane.style === "decides" && <Chip tone="lime">Example</Chip>}
                </div>
                <dl className={`mt-3 space-y-2.5 border-t pt-3 ${s.rule}`}>
                  {lane.entries.map((entry) => (
                    <div key={entry.name}>
                      <dt className={`text-sm font-semibold ${s.title}`}>{entry.name}</dt>
                      <dd className={`text-sm leading-6 ${s.dd}`}>{entry.text}</dd>
                    </div>
                  ))}
                </dl>
                {lane.note && <p className="mt-3 rounded-xl bg-canvas px-3 py-2 text-xs leading-5 text-slate">{lane.note}</p>}
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="ab-test" className="flex flex-col gap-4">
        <SectionHeader id="ab-test" eyebrow="3 · A/B test" title="Split members at random, and fix the rules first">
          <p>
            An A/B test splits members at random between the current version (A) and a change (B), such as Before to After
            or one{" "}
            <Link href="/skill-edits/framework" className={LINK}>
              skill edit
            </Link>
            . Chance alone decides who gets which, so a gap bigger than noise is caused by the change.
          </p>
        </SectionHeader>
        <dl className="divide-y divide-line rounded-2xl border border-line bg-white">
          {RULES.map((rule) => (
            <div key={rule.name} className="grid gap-1 px-4 py-3 text-sm leading-6 sm:grid-cols-[15rem_minmax(0,1fr)] sm:gap-4">
              <dt className="font-semibold text-ink">{rule.name}</dt>
              <dd className="text-slate">{rule.text}</dd>
            </div>
          ))}
        </dl>
        <Expander tone="canvas" summary={<span className="text-sm font-semibold text-ink">How many members a test needs</span>}>
          <div className="max-w-3xl space-y-2 text-sm leading-6 text-slate">
            <p>
              Power is the chance a test detects a real change of the size that matters. Halving that size roughly
              quadruples the members needed.
            </p>
            <p className="rounded-xl border border-line bg-white px-3 py-2 text-xs leading-5">
              Illustration only, not a measured rate: if 20% of members asked again within a day, detecting a drop to 19%
              (80% power, 5% false-positive rate) would take about 25,000 members in each group.
            </p>
            <p>
              CUPED adjusts each member&apos;s result with the same metric from before the test. That data predates the
              split, so it cannot bias the result. A correlation of 0.5 cuts the variance, and the members needed, by about
              a quarter.
            </p>
          </div>
        </Expander>
      </section>

      <section aria-labelledby="causal" className="flex flex-col gap-4">
        <SectionHeader id="causal" eyebrow="4 · No random split" title="Match the method to how the change ships">
          <p>
            A plain before-and-after comparison mixes a change with everything else that changed. Each method below rests on
            assumptions that can be checked in part, never proven.
          </p>
        </SectionHeader>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-line bg-white px-4 py-3 text-sm">
          <Chip tone="dark">Start here</Chip>
          <span className="font-semibold text-ink">Can members be split at random?</span>
          <span className="text-slate">
            Yes: run an{" "}
            <a href="#ab-test" className={LINK}>
              A/B test
            </a>
            . No: find how the change ships below.
          </span>
        </div>
        <ul className="divide-y divide-line rounded-2xl border border-line bg-white">
          <li
            aria-hidden="true"
            className="hidden px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-forest lg:grid lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)] lg:gap-5"
          >
            <span>If the change ships</span>
            <span>Assumes</span>
            <span>Probe it by</span>
          </li>
          {METHODS.map((m) => (
            <li
              key={m.method}
              className="grid gap-2 px-4 py-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)] lg:gap-5"
            >
              <div className="flex flex-col gap-1.5">
                <p className="text-sm font-semibold text-ink">{m.situation}</p>
                <h3>
                  <Chip tone="lime">{m.method}</Chip>
                </h3>
                <p className="text-sm leading-6 text-slate">{m.what}</p>
              </div>
              <p className="text-sm leading-6 text-slate">
                <span className={`${LABEL} lg:sr-only`}>Assumes</span>
                {m.assumes}
              </p>
              <p className="text-sm leading-6 text-slate">
                <span className={`${LABEL} lg:sr-only`}>Probe it by</span>
                {m.probe}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="launch" className="flex flex-col gap-4">
        <SectionHeader id="launch" eyebrow="5 · Launch" title="Offline gates, online confirms">
          <p>
            Offline is cheap and repeatable, so it runs first and stops changes that break known cases. Only online shows
            whether members are better off.
          </p>
        </SectionHeader>
        <figure className="rounded-2xl border border-line bg-white p-4 sm:p-6">
          <ol className="ml-3 border-l-2 border-line">
            {STEPS.map((step, i) => (
              <li key={step.title} className="relative pb-5 pl-8 last:pb-0">
                <span className="absolute -left-[0.8rem] top-0">
                  <StepNumber n={i + 1} />
                </span>
                <div className="grid gap-1 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
                  <div className="flex flex-col items-start gap-1">
                    <h3 className="text-base font-semibold text-ink">{step.title}</h3>
                    <Chip>{step.who}</Chip>
                  </div>
                  <p className="text-sm leading-6 text-slate">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-5 rounded-xl border border-dashed border-field px-3.5 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-forest">
              <span aria-hidden="true">▲ </span>Back to step 1
            </p>
            <h3 className="mt-1 text-sm font-semibold text-ink">After every launch</h3>
            <ul className="mt-2 grid gap-3 md:grid-cols-2">
              {FEEDBACK.map((item) => (
                <li key={item.name} className="rounded-lg bg-canvas px-3 py-2.5">
                  <p className="text-sm font-semibold text-ink">{item.name}</p>
                  <p className="text-sm leading-6 text-slate">{item.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </figure>
      </section>
    </div>
  );
}
