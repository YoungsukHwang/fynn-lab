import type { Metadata } from "next";
import Link from "next/link";

import { AbTestFlow } from "@/components/evals/AbTestFlow";
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
// In order from the eval set to real members: what stays behind, what carries over, what only members show.
const CARDS: { chip: string; tone: ChipTone; items: string[] }[] = [
  {
    chip: "Stays offline",
    tone: "neutral",
    items: [
      "Expected facts and the pass or fail verdict: a real message comes with no list of facts.",
      "The same synthetic members on every run.",
    ],
  },
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
    chip: "Only online",
    tone: "dark",
    items: [
      "Whether a reply helped: what the member did next.",
      "Follow-up turns that build on the new version's own replies.",
      "Effects at real load, such as on the human support queue.",
    ],
  },
];

type Stage = { chip: string; title: string; dark: boolean; rows: { label: string; text: string }[] };

function stages(personaCount: string): Stage[] {
  return [
    {
      chip: "Offline",
      title: "Backtest on logged chats",
      dark: false,
      rows: [
        {
          label: "How",
          text: "Replay past real messages, with personal details removed, through the current version and the change, and grade both replies with the code checks and the rubric judge.",
        },
        {
          label: "Measures",
          text: "Rubric pass rate; which reply the judge prefers on the same message (shown in random order, since judges favor a position); safety flags per 1,000 replies; cost and latency per reply; which skills the router picks.",
        },
        {
          label: "Adds",
          text: `Real typos, new topics and credit files unlike those of the ${personaCount}, in far larger numbers. Both versions still answer the same message, so the comparison stays paired.`,
        },
        {
          label: "Cannot tell",
          text: "Whether the facts are right (there is no answer key), how later turns would go (they were written in reply to the old version), or what members do next.",
        },
      ],
    },
    {
      chip: "Online",
      title: "A/B test with members",
      dark: true,
      rows: [
        { label: "How", text: "Split members at random, so each sees one version (section 3)." },
        {
          label: "Measures",
          text: "What members do: asking the same question again, handoffs to human support, and later outcomes (section 2).",
        },
        { label: "Adds", text: "Whether members are better off, including follow-up turns and effects at real load." },
        {
          label: "Costs",
          text: "Weeks of traffic, with real members exposed to the change, so it runs only after the backtest finds nothing wrong.",
        },
      ],
    },
  ];
}

type Entry = { name: string; text: string };

const LANES: { title: string; job: string; entries: Entry[]; style: "decides" | "plain" | "later"; note?: string }[] = [
  {
    title: "Primary metric",
    job: "Decides whether the change ships.",
    style: "decides",
    entries: [
      {
        name: "Asked again within a day",
        text: "The same question within 24 hours, matched by meaning. A follow-up that builds on the answer does not count. Lower is better.",
      },
    ],
  },
  {
    title: "Guardrails",
    job: "Can block a launch even when the primary metric improves: each must not get worse by more than a margin set in advance.",
    style: "plain",
    entries: [
      { name: "Safety violations", text: "Promising a score gain, suggesting a product to a member in hardship, repeating a card number." },
      { name: "Preventable handoffs", text: "Chats sent to human support that the coach should have solved." },
      {
        name: "Still using the app a week later",
        text: "Members active in the app 7 days after their first coach chat. It must not fall: a change that drives members away would also lower asking again.",
      },
      { name: "Latency, 95th percentile", text: "95 of 100 replies arrive within it. An average hides the slow ones." },
      { name: "Cost per chat", text: "Before and After load different skills, so cost is measured." },
    ],
  },
  {
    title: "Diagnostics",
    job: "Explain why the primary metric moved. They never decide on their own.",
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
    title: "Long-term outcomes",
    job: "What the coach is for, but they move over months, too slowly to decide one test.",
    style: "later",
    entries: [
      {
        name: "What members do next",
        text: "Paying a card down before the statement date, on-time payments, staying with the app.",
      },
    ],
    note: "A small holdout kept on the old version for months shows whether gains on the primary metric reach these. If they never do, the primary metric is the wrong target.",
  },
];

type Fit = { mark: "yes" | "partly" | "no"; note?: string };
type Candidate = { name: string; fits: [Fit, Fit, Fit, Fit]; role: string };

const CRITERIA = ["Every chat", "Moves within days", "Clear direction", "From members"] as const;

const yes: Fit = { mark: "yes" };

// The four tests a primary metric must pass, applied to metrics a team could pick instead.
const CANDIDATES: Candidate[] = [
  { name: "Asked again within a day", fits: [yes, yes, { mark: "yes", note: "lower" }, yes], role: "Primary metric" },
  { name: "Thumbs up or down", fits: [{ mark: "no", note: "few click" }, yes, yes, yes], role: "Diagnostic" },
  {
    name: "Handoffs to human support",
    fits: [yes, yes, { mark: "partly", note: "some chats belong with a person" }, yes],
    role: "Guardrail (preventable ones)",
  },
  {
    name: "Judge-graded quality of live replies",
    fits: [{ mark: "partly", note: "a sample" }, yes, yes, { mark: "no", note: "a model grading a model" }],
    role: "Diagnostic",
  },
  {
    name: "Still using the app a week later",
    fits: [yes, { mark: "partly", note: "a week, and one reply barely moves it" }, { mark: "yes", note: "higher" }, yes],
    role: "Guardrail (must not fall)",
  },
  {
    name: "Messages per chat",
    fits: [yes, yes, { mark: "no", note: "more can mean engaged or confused" }, yes],
    role: "Not used",
  },
  {
    name: "Paid down before the statement date",
    fits: [{ mark: "no", note: "only members with a card balance" }, { mark: "no", note: "a month or more" }, yes, yes],
    role: "Long-term outcome",
  },
];

const MARKS = {
  yes: { label: "Yes", box: "bg-lime-soft text-forest" },
  partly: { label: "Partly", box: "bg-mist text-ink" },
  no: { label: "No", box: "border border-line bg-white text-slate" },
} as const;

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
        , then backtest it on logged chats (
        <a href="#why" className={LINK}>
          section 1
        </a>
        ). Go on only with a Ship decision, no guardrail misses and nothing wrong in the backtest.
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

/** The arrow from one card to the next: down on phones, right on wide screens. Decorative. */
function FlowArrow() {
  return (
    <span
      aria-hidden="true"
      className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-sm leading-none text-dim md:-right-[1.15rem] md:bottom-auto md:left-auto md:top-1/2 md:translate-x-0 md:-translate-y-1/2"
    >
      <span className="md:hidden">▼</span>
      <span className="hidden md:inline">▶</span>
    </span>
  );
}

const LANE_STYLES = {
  decides: { box: "bg-ink text-white", job: "text-lime", title: "text-white", rule: "border-white/15", dd: "text-white/80" },
  plain: { box: "border border-line bg-white", job: "text-forest", title: "text-ink", rule: "border-line", dd: "text-slate" },
  later: {
    box: "border border-dashed border-field bg-white",
    job: "text-forest",
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
          No real members use the bots: the public demo is anonymous and rate-limited, so there are no online results.
          This page is the plan for testing the bots with real members.
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
        <ol className="grid gap-7 md:grid-cols-3 md:gap-6">
          {CARDS.map((card, i) => (
            <li key={card.chip} className="relative rounded-2xl border border-line bg-white p-4 sm:p-5">
              <Chip tone={card.tone}>{card.chip}</Chip>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate marker:text-dim">
                {card.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {i < CARDS.length - 1 && <FlowArrow />}
            </li>
          ))}
        </ol>
        <div className="flex flex-col gap-3">
          <div className="max-w-3xl">
            <h3 className="text-base font-semibold text-ink">Real chats in two steps: backtest, then test online</h3>
            <p className="mt-1 text-sm leading-6 text-slate">
              Logged chats can test a change before any member sees it. What a backtest measures differs from the eval
              set, since there is no answer key, and from the online test, since no member reacts.
            </p>
          </div>
          <ol className="grid gap-7 md:grid-cols-2 md:gap-6">
            {stages(personaCount).map((stage, i, all) => (
              <li
                key={stage.title}
                className={`relative rounded-2xl p-4 sm:p-5 ${stage.dark ? "bg-ink text-white" : "border border-line bg-white"}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={stage.dark ? "lime" : "neutral"}>{stage.chip}</Chip>
                  <h4 className={`text-base font-semibold ${stage.dark ? "text-white" : "text-ink"}`}>{stage.title}</h4>
                </div>
                <dl className={`mt-3 space-y-2.5 border-t pt-3 text-sm leading-6 ${stage.dark ? "border-white/15" : "border-line"}`}>
                  {stage.rows.map((row) => (
                    <div key={row.label}>
                      <dt className={`text-[11px] font-semibold uppercase tracking-wide ${stage.dark ? "text-lime" : "text-forest"}`}>
                        {row.label}
                      </dt>
                      <dd className={stage.dark ? "text-white/80" : "text-slate"}>{row.text}</dd>
                    </div>
                  ))}
                </dl>
                {i < all.length - 1 && <FlowArrow />}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section aria-labelledby="measure" className="flex flex-col gap-4">
        <SectionHeader id="measure" eyebrow="2 · What to measure" title="One metric decides, the others guard or explain">
          <p>
            Each metric gets one job, set before the test starts: only the primary metric decides, a guardrail can block
            the launch, and the rest explain the result or are checked later.
          </p>
        </SectionHeader>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {LANES.map((lane) => {
            const s = LANE_STYLES[lane.style];
            return (
              <li key={lane.title} className={`flex flex-col rounded-2xl p-4 sm:p-5 ${s.box}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className={`text-base font-semibold ${s.title}`}>{lane.title}</h3>
                  {lane.style === "decides" && <Chip tone="lime">Example</Chip>}
                </div>
                <p className={`mt-1 text-sm leading-6 ${s.job}`}>{lane.job}</p>
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
        <div className="flex flex-col gap-3">
          <div className="max-w-3xl">
            <h3 className="text-base font-semibold text-ink">Why asking again within a day</h3>
            <p className="mt-1 text-sm leading-6 text-slate">
              A primary metric needs four things: it is measured on every chat without asking the member, it moves
              within days so a test of a few weeks can read it, one direction is plainly better, and it comes from what
              members do rather than from a model&apos;s opinion. Of these candidates, only asking again has all four.
            </p>
          </div>
          {/* Focusable so keyboard users can scroll the table sideways on narrow screens. */}
          <div
            tabIndex={0}
            role="region"
            aria-label="Candidate primary metrics"
            className="overflow-x-auto rounded-2xl border border-line bg-white"
          >
            <table className="w-full min-w-[46rem] text-left text-sm">
              <caption className="sr-only">Candidate primary metrics against the four tests, and the role each gets</caption>
              <thead className="border-b border-line text-xs text-slate">
                <tr>
                  <th scope="col" className="px-4 py-2.5 font-semibold">
                    Candidate
                  </th>
                  {CRITERIA.map((c) => (
                    <th key={c} scope="col" className="px-3 py-2.5 font-semibold">
                      {c}
                    </th>
                  ))}
                  <th scope="col" className="px-4 py-2.5 font-semibold">
                    Used here as
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {CANDIDATES.map((c, i) => (
                  <tr key={c.name} className={`align-top ${i === 0 ? "bg-lime-soft/40" : ""}`}>
                    <th scope="row" className="px-4 py-2.5 font-semibold text-ink">
                      {c.name}
                    </th>
                    {c.fits.map((fit, j) => (
                      <td key={CRITERIA[j]} className="px-3 py-2.5">
                        <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${MARKS[fit.mark].box}`}>
                          {MARKS[fit.mark].label}
                        </span>
                        {fit.note && <span className="mt-0.5 block text-xs leading-5 text-slate">{fit.note}</span>}
                      </td>
                    ))}
                    <td className={`px-4 py-2.5 ${i === 0 ? "font-semibold text-ink" : "text-slate"}`}>{c.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="max-w-3xl text-sm leading-6 text-slate">
            It has weak spots too. Matching &ldquo;the same question&rdquo; takes a model (an LLM or text embeddings),
            which needs checking against human labels, as the judge did. And a member who gives up and leaves never asks
            again, so a change that drives members away could look like a win. The guardrail on members still using the app
            catches that during the test, and the long-term holdout later.
          </p>
        </div>
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
        <AbTestFlow />
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
              CUPED adjusts each member&apos;s result with data from before the test: the same metric for members who used
              the coach before, and something every member has, such as app activity, for those new to it. That data
              predates the split, so it cannot bias the result. A correlation of 0.5 cuts the variance, and the members
              needed, by about a quarter; members with weaker data from before gain less.
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
