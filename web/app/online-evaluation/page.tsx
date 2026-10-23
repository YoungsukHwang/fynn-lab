import type { Metadata } from "next";
import Link from "next/link";

import { Chip, OnThisPage, PageHero, SectionHeader } from "@/components/evals/ui";
import { getFrameworkData } from "@/lib/evalData";

export const metadata: Metadata = { title: "Online evaluation framework" };

const SECTIONS = [
  { href: "#why", label: "Why offline is not enough" },
  { href: "#measure", label: "What to measure" },
  { href: "#ab-test", label: "A/B tests" },
  { href: "#causal", label: "Without randomization" },
  { href: "#linking", label: "Offline and online" },
  { href: "#launch", label: "How a launch would go" },
];

const CARRIES_OVER = [
  "The code checks. Banned patterns such as “I guarantee” or a repeated card number can run on every real reply, instantly and at almost no cost.",
  "The LLM judge, given a rubric (a fixed list of questions about any good reply) instead of expected facts: did the reply use the member's own figures correctly, follow the guardrails, and answer every part of the question? Grading by rubric is a new task for the judge, so its grades are checked against human reviewers before anyone relies on them.",
  "The skill files and guardrails themselves, which already spell out what a good reply says and must never say.",
  "The failure types the offline cases were written to catch, as a checklist for reading real chats.",
];

const DOES_NOT_CARRY = [
  "Expected facts, and with them the pass or fail verdict. A real message has no list of facts written in advance.",
  "The every-fact rule. Without a fact list, there is no fact to miss.",
  "A fixed set of members. Real members change from week to week, so two weeks of traffic are never quite the same test.",
  "Both bots answering the same message. Offline, every case goes to both bots; online, each member sees one bot, so the comparison is between groups of members.",
];

type Metric = { name: string; text: string };

const METRIC_GROUPS: { title: string; lead: string; metrics: Metric[] }[] = [
  {
    title: "Outcomes for members",
    lead: "Did the chat help? These come from what members do, not from grading the reply.",
    metrics: [
      {
        name: "Asked again within a day",
        text: "The member asks the same question again within 24 hours, a sign the first answer did not land. Questions are matched by meaning, not exact words, and a follow-up that builds on the answer does not count. Lower is better.",
      },
      {
        name: "Handed off to human support",
        text: "The member opens Help > Chat with support after a Coach chat. Some handoffs are right (a lost card, an account change Coach cannot make), so the useful count is handoffs Coach should have prevented, sorted by reason.",
      },
      {
        name: "Thumbs up or down",
        text: "Direct, but few members click, and those who do tend to feel strongly. A signal to read, not a rate for all members.",
      },
      {
        name: "What the member does next",
        text: "Actions in the app after the chat, such as paying down a high card balance before the statement date, or disputing a report error they asked about. This is what Coach is for, but it is slow and depends on far more than one chat.",
      },
    ],
  },
  {
    title: "Quality, sampled from real chats",
    lead: "Is the reply right? Real replies are graded, but only a sample, because grading costs money and reviewer time.",
    metrics: [
      {
        name: "LLM judge on a random sample",
        text: "Each day a random sample of chats is graded by the judge against the rubric. Random keeps the sample representative of all traffic.",
      },
      {
        name: "Human audit",
        text: "A reviewer grades a smaller sample each week without knowing which version wrote the reply. How often reviewer and judge agree shows whether the judge can be trusted, and the disagreements show where its instructions need work.",
      },
      {
        name: "Extra samples from risky topics",
        text: "More chats are drawn from hardship, collections and disputes, so rare but serious failures show up often enough to count. When an overall rate is reported, these extra chats are weighted back down to their real share of traffic.",
      },
      {
        name: "Privacy",
        text: "Chats are reviewed with personal details removed, by a small group with access.",
      },
    ],
  },
  {
    title: "Guardrails",
    lead: "Lines a change must not cross, whatever else it improves.",
    metrics: [
      {
        name: "Safety violations",
        text: "Promising a score gain or a number of points, suggesting a product to a member in hardship, repeating a card number, or recommending a Marketplace offer without saying partners may pay the app. Code checks catch the clear cases on every reply; the judge covers the rest on the sample.",
      },
      {
        name: "Latency",
        text: "How long a member waits, tracked at the 95th percentile (the time within which 95 of 100 replies arrive), because an average hides the slow ones.",
      },
      {
        name: "Cost per conversation",
        text: "Model usage for the router and the answer, per chat. Before and After put different skills in the prompt, so their cost differs and has to be measured, not assumed.",
      },
    ],
  },
];

const AB_CARDS: { title: string; body: React.ReactNode }[] = [
  {
    title: "Randomize by member, and keep it sticky",
    body: (
      <>
        <p>
          The unit of randomization is what gets assigned to A or B. Here it is the member, and the assignment is sticky:
          it is computed from the member ID, so a member gets the same version on every visit and every device.
        </p>
        <p className="mt-2">
          Per message would be wrong. One conversation could switch bots mid-way, the After bot&apos;s carry-over would
          act on turns the Before bot answered, and member outcomes such as asking again would belong to neither
          version.
        </p>
        <p className="mt-2">
          The analysis uses the same unit. Metrics counted per reply, such as latency, are first combined per member
          (for example each member&apos;s average), or analyzed with a method that treats one member&apos;s messages as
          a group, such as a bootstrap by member: one member&apos;s messages are alike, and treating each message as a
          separate data point makes the result look more certain than it is.
        </p>
        <p className="mt-2">
          Only members who open Coach during the test are counted, from their first chat. Members who never open it
          cannot be affected and only add noise. Leaving them out is fair because nobody sees a difference before
          opening Coach, so both groups open it at the same rate.
        </p>
      </>
    ),
  },
  {
    title: "One primary metric, plus guardrails",
    body: (
      <>
        <p>
          The primary metric is the single number that decides the test, chosen before it starts: for example, the
          share of members who ask again within a day.
        </p>
        <p className="mt-2">
          Guardrails (safety violations, unneeded handoffs, 95th-percentile latency, cost per chat) do not have to
          improve. They must not get worse by more than a margin set in advance. Every other metric is exploratory.
        </p>
      </>
    ),
  },
  {
    title: "How many members, and for how long",
    body: (
      <>
        <p>
          Power is the chance a test detects a change of the size that matters, if the change is real. It depends on
          how common the outcome is, how small a change should be detectable, and how many members take part. Small
          changes need many members: halving the smallest detectable change roughly quadruples the members needed.
        </p>
        <p className="mt-2 rounded-xl bg-canvas px-3 py-2 text-xs leading-5">
          Illustration only, not a measured rate: if 20% of members asked again within a day, detecting a drop to 19%
          with the usual settings (80% power, 5% false-positive rate) would take about 25,000 members in each group.
        </p>
        <p className="mt-2">
          The length is the time it takes for that many members to open Coach, rounded up to whole weeks, and at least
          one week. Members chat differently on weekdays and weekends, so a test from Monday to Thursday describes only
          how members behave from Monday to Thursday. Outcomes tied to card statements or paydays need a full monthly
          cycle.
        </p>
      </>
    ),
  },
  {
    title: "Less noise with CUPED",
    body: (
      <>
        <p>
          CUPED (controlled experiments using pre-experiment data) adjusts each member&apos;s result using the same
          metric from before the test, such as how often they asked again in the previous four weeks. Some members
          repeat themselves often and some rarely; removing that predictable part leaves less noise to see through.
          Any measure from before the test that predicts the result can be used, such as how often the member opens
          the app.
        </p>
        <p className="mt-2">
          It does not bias the result because the earlier weeks came before assignment, so the change cannot have
          touched them. The gain depends on how well the past predicts the test period: a correlation of 0.5 removes a
          quarter of the noise (measured as variance), so the test needs about a quarter fewer members. Members with
          no history gain nothing from it, but are not hurt by it either.
        </p>
      </>
    ),
  },
];

const PITFALLS: Metric[] = [
  {
    name: "Novelty effect",
    text: "Members try something new more at first, or dislike a change at first, and both fade. Compare week one with week two, or split results by days since a member first saw the change.",
  },
  {
    name: "Peeking",
    text: "The p-value is the chance of a difference at least this large if the change did nothing. Checking it every day and stopping the first time it drops below 5% makes false wins far more common than 5%. Either fix the length and look once, or use sequential testing, a method built for repeated looks that keeps the false-win rate where it was set. Watching guardrails daily to stop a harmful change early is fine; stopping early for a win is the problem.",
  },
  {
    name: "Many metrics",
    text: "If a change does nothing, 20 metrics each tested at 5% will still show about one significant result by chance. Name the primary metric in advance, and correct the others for the number of tests, for example with the Holm method, which raises the bar for each metric so the chance of any false win stays at 5%.",
  },
  {
    name: "Interference",
    text: "If one member's chats land in both groups (a second account, assignment by device instead of by member, or a re-split mid-test), the groups blur and the difference shrinks toward zero. Sticky assignment by member ID prevents most of it. A subtler kind is spillover through something shared: if B sends fewer members to human support, the support queue gets shorter for A's members too, and A looks better than it would on its own.",
  },
  {
    name: "Lopsided groups",
    text: "If a 50/50 split comes out more uneven than chance allows, something is broken, such as a crash in one version or a logging bug. With many members even 51/49 can be too uneven to be chance. This check, called sample ratio mismatch, comes first in every readout; a failed one means the result is not read.",
  },
];

type Method = { name: string; what: string; when: string; assumption: string; check: string };

const METHODS: Method[] = [
  {
    name: "Difference-in-differences",
    what: "Compares how much an outcome changed in the group that got the change with how much it changed, over the same weeks, in a group that did not get it yet.",
    when: "The After bot rolls out to members in a few states first, or on one app platform first, and to everyone else a month later. With several rollout waves, each wave is compared only with members not yet switched.",
    assumption: "Parallel trends: without the change, both groups' outcomes would have moved the same way.",
    check: "Plot both groups for the weeks before launch; the lines should run parallel. Rerun the analysis with a fake launch date before the real one; it should find nothing. Passing both supports the assumption but cannot prove it.",
  },
  {
    name: "Interrupted time series and synthetic control",
    what: "Interrupted time series fits the trend before a launch date and asks whether the outcome jumped or bent at that date. Synthetic control builds a stand-in for the changed group from a weighted mix of unchanged ones.",
    when: "A change ships to all members on one date, such as an urgent guardrails fix, and the weeks before are the comparison. Synthetic control fits when the change reached one whole group at once, such as every member in one state, and other states never got it: their weighted mix stands in for what the changed state would have done.",
    assumption: "Without the change, the old trend would have continued (for synthetic control, the weighted mix would have kept tracking the changed group), and nothing else that moves the outcome changed on the same date.",
    check: "List everything else that happened that week: other launches, a marketing email, tax season, a holiday. Run the same model on fake dates and on a metric the change should not touch; neither should show a break. Use enough history that weekly and monthly cycles are part of the trend. For synthetic control, the mix should track the changed group closely before launch, and pretending each untouched state was the changed one should rarely give as large a gap.",
  },
  {
    name: "Propensity score matching or weighting",
    what: "Estimates each member's chance of making a choice from what was known about them beforehand (the propensity score), then compares members who chose with members who had the same chance but did not.",
    when: "Members choose to turn on a feature such as Rent Reporting, and the question is what it changed for them later. Those who turn it on already differ: they rent, have a linked bank account, and use the app more.",
    assumption: "No hidden confounders: every reason that drives both the choice and the outcome is in the data behind the score.",
    check: "After matching or weighting, the two groups should look alike on every measured trait. Every chooser needs comparable non-choosers; members with none are left out, and the result then describes only the members who remain. A sensitivity analysis asks how strong an unmeasured reason would have to be to erase the result.",
  },
  {
    name: "Regression discontinuity",
    what: "Compares members just above and just below a cutoff that decides who gets something.",
    when: "Suppose, as a hypothetical rule, Coach offered a check-in only to members whose card utilization is 50% or more. Members at 49% and 51% are nearly the same, so a jump in outcomes at 50% is the check-in's effect. It holds only for members near the cutoff and says little about members at 20% or 90%.",
    assumption: "Members cannot place themselves precisely on one side of the cutoff, and nothing else changes at it.",
    check: "Count members on each side; a pile-up just above or below suggests sorting. Traits measured before should be smooth across the cutoff. The estimate should hold for narrower and wider windows around it.",
  },
  {
    name: "Instrumental variables, as an encouragement design",
    what: "Uses something random that nudges a behavior, and has no other route to the outcome, to estimate the effect of the behavior itself. The random nudge is called the instrument.",
    when: "Coach cannot be forced on anyone, but an invitation to try it can be shown to a random half of members. The plain difference between the halves is already a clean randomized result: the effect of the invitation. Scaled by how much the invitation raised use, it estimates Coach's effect for members who use it because they were invited.",
    assumption: "The invitation changes outcomes only through Coach use; it does not, for example, remind members to pay a bill on its own. And no one uses Coach less because they were invited.",
    check: "The invitation must clearly raise Coach use, or the estimate is too noisy to trust; that part can be measured. That it acts only through Coach can only be argued, so read the invitation for anything that could act on its own.",
  },
];

function NumberedCard({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex flex-col rounded-2xl border border-line bg-white p-4 sm:p-5">
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-lime-soft text-xs font-semibold text-forest"
        >
          {n}
        </span>
        <h3 className="text-base font-semibold text-ink">{title}</h3>
      </div>
      <div className="mt-2 flex-1 text-sm leading-6 text-slate">{children}</div>
    </li>
  );
}

function BulletCard({ chip, title, items }: { chip: React.ReactNode; title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
      {chip}
      <h3 className="mt-2 text-base font-semibold text-ink">{title}</h3>
      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate marker:text-dim">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default async function OnlineEvaluationPage() {
  const { cases, personas } = await getFrameworkData();
  const caseCount = cases.length ? `${cases.length} test cases` : "test cases";
  const personaCount = personas.length ? `${personas.length} synthetic members` : "synthetic members";

  return (
    <div className="flex flex-col gap-8 sm:gap-10">
      <PageHero eyebrow="Online evaluation · Framework" title="How the bots would be tested with real members">
        <p>
          Fynn Lab is not deployed, so there are no real chats and no online results. This page is the plan for the day
          it is: what to measure, how to test a change such as Before to After on live traffic, what to do when a test
          is not possible, and how online results would feed back into the offline evals.
        </p>
      </PageHero>

      <OnThisPage links={SECTIONS} />

      {/* 1. Why offline is not enough */}
      <section aria-labelledby="why" className="flex flex-col gap-4">
        <SectionHeader id="why" eyebrow="1 · Why offline is not enough" title="Real chats have no answer key">
          <p>
            Offline, each of the {caseCount} comes with a list of facts a good reply must contain, written in advance,
            and the judge checks the reply against that list (
            <Link href="/before-after/framework#scoring" className="font-medium text-ink underline underline-offset-2">
              scoring
            </Link>
            ). A real member&apos;s message arrives with no such list.
          </p>
          <p>
            Real traffic is also different in kind: typos, follow-up turns, topics the eval set never covers, and credit
            files unlike those of the {personaCount}. Every offline case is a single turn, so the After bot&apos;s
            carry-over of skills to the next turn is never exercised offline.
          </p>
          <p>
            And a correct reply is not always a helpful one. A reply can contain every expected fact and still be too
            long to read, or leave the member unsure what to do next.
          </p>
        </SectionHeader>
        <div className="grid gap-3 lg:grid-cols-2">
          <BulletCard chip={<Chip tone="lime">Carries over</Chip>} title="What still works online" items={CARRIES_OVER} />
          <BulletCard chip={<Chip>Does not carry over</Chip>} title="What only offline has" items={DOES_NOT_CARRY} />
        </div>
      </section>

      {/* 2. What to measure */}
      <section aria-labelledby="measure" className="flex flex-col gap-4">
        <SectionHeader id="measure" eyebrow="2 · What to measure" title="Member outcomes, sampled quality, guardrails">
          <p>
            Outcome metrics say whether Coach helped. Quality metrics grade a sample of real replies. Guardrail metrics
            are limits a change must stay within.
          </p>
        </SectionHeader>
        <ul className="grid gap-3 lg:grid-cols-3">
          {METRIC_GROUPS.map((group) => (
            <li key={group.title} className="rounded-2xl border border-line bg-white p-4 sm:p-5">
              <h3 className="text-base font-semibold text-ink">{group.title}</h3>
              <p className="mt-1 text-sm leading-6 text-slate">{group.lead}</p>
              <dl className="mt-3 space-y-3 border-t border-line pt-3">
                {group.metrics.map((metric) => (
                  <div key={metric.name}>
                    <dt className="text-sm font-semibold text-ink">{metric.name}</dt>
                    <dd className="mt-0.5 text-sm leading-6 text-slate">{metric.text}</dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ul>
        <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
          <h3 className="text-base font-semibold text-ink">Leading and lagging metrics</h3>
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            <div className="rounded-xl bg-canvas px-3 py-2.5">
              <Chip tone="dark">Leading</Chip>
              <p className="mt-1.5 text-sm leading-6 text-slate">
                Move within hours or days: asking again, handoffs, thumbs, sampled quality. A two-week test can only
                decide on these.
              </p>
            </div>
            <div className="rounded-xl bg-canvas px-3 py-2.5">
              <Chip>Lagging</Chip>
              <p className="mt-1.5 text-sm leading-6 text-slate">
                Take weeks or months: utilization at the next statement, months of on-time payments, whether a member
                keeps using the app. Closer to what matters, too slow for most tests.
              </p>
            </div>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate">
            So it is worth checking that changes which move the leading metrics also move the lagging ones. A long-term
            holdout (a small group kept on the old version for months) makes that possible: comparing it with everyone
            else shows the lagging effect. A leading metric whose gains do not show up there is the wrong thing to
            optimize.
          </p>
        </div>
      </section>

      {/* 3. A/B tests */}
      <section aria-labelledby="ab-test" className="flex flex-col gap-4">
        <SectionHeader id="ab-test" eyebrow="3 · A/B tests" title="Randomize members, pick one metric, fix the length">
          <p>
            An A/B test is a randomized experiment: members are split at random between the current version (A) and the
            change (B), and the two groups are compared. Because chance alone decides who gets which, a difference
            larger than noise is caused by the change. The change could be Before to After, or a single{" "}
            <Link href="/skill-edits/framework" className="font-medium text-ink underline underline-offset-2">
              skill edit
            </Link>
            .
          </p>
        </SectionHeader>
        <ol className="grid gap-3 md:grid-cols-2">
          {AB_CARDS.map((card, i) => (
            <NumberedCard key={card.title} n={i + 1} title={card.title}>
              {card.body}
            </NumberedCard>
          ))}
        </ol>
        <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
          <h3 className="text-base font-semibold text-ink">Pitfalls to plan for</h3>
          <dl className="mt-3 grid gap-x-8 gap-y-3 md:grid-cols-2">
            {PITFALLS.map((pitfall) => (
              <div key={pitfall.name}>
                <dt className="text-sm font-semibold text-ink">{pitfall.name}</dt>
                <dd className="mt-0.5 text-sm leading-6 text-slate">{pitfall.text}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* 4. Causal inference without randomization */}
      <section aria-labelledby="causal" className="flex flex-col gap-4">
        <SectionHeader id="causal" eyebrow="4 · Without randomization" title="When a clean A/B test is not possible">
          <p>
            Some changes cannot be randomized: they must ship to everyone at once, they roll out region by region, or
            members choose them. Comparing before with after, or users with non-users, then mixes the change with
            everything else that differs. Each method below separates the two under one key assumption. That
            assumption can never be fully proven, only probed, so each card says how to probe it.
          </p>
        </SectionHeader>
        <ul className="grid gap-3 lg:grid-cols-2">
          {METHODS.map((method) => (
            <li key={method.name} className="rounded-2xl border border-line bg-white p-4 sm:p-5">
              <h3 className="text-base font-semibold text-ink">{method.name}</h3>
              <p className="mt-1 text-sm leading-6 text-slate">{method.what}</p>
              <dl className="mt-3 space-y-2.5 border-t border-line pt-3">
                {(
                  [
                    ["When it fits here", method.when],
                    ["Key assumption", method.assumption],
                    ["How to check it", method.check],
                  ] as const
                ).map(([label, text]) => (
                  <div key={label}>
                    <dt className="text-[11px] font-semibold uppercase tracking-wide text-forest">{label}</dt>
                    <dd className="mt-0.5 text-sm leading-6 text-slate">{text}</dd>
                  </div>
                ))}
              </dl>
            </li>
          ))}
        </ul>
      </section>

      {/* 5. Linking offline and online */}
      <section aria-labelledby="linking" className="flex flex-col gap-4">
        <SectionHeader id="linking" eyebrow="5 · Offline and online" title="Offline gates, online confirms">
          <p>
            The two are one loop, not rivals. Offline is cheap, fast and repeatable; online is slow and costly but is
            the only place members show whether a change helped.
          </p>
        </SectionHeader>
        <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <NumberedCard n={1} title="Offline gates the launch">
            A change reaches members only after it passes the offline regression test: the cases it can affect are
            rerun and the edit breaks none of the cases it could reach (flips it could not reach count as chance) (
            <Link href="/skill-edits/framework" className="font-medium text-ink underline underline-offset-2">
              Skill edits
            </Link>
            ). Changes that break known cases stop here, before any member sees them.
          </NumberedCard>
          <NumberedCard n={2} title="Online confirms">
            Passing offline means the right facts for known questions. Only the online test shows whether members are
            better off.
          </NumberedCard>
          <NumberedCard n={3} title="Check that offline predicts online">
            For each launch, record the offline change and the online change side by side. Over many launches, offline
            wins should mostly become online wins, allowing for noise in both. If they do not, the eval set or the
            judge is measuring the wrong thing.
          </NumberedCard>
          <NumberedCard n={4} title="Feed failures back">
            Real chats that fail (a thumbs down, a repeated question, a judge or reviewer flag, a safety catch) become
            new offline cases: personal details removed, attached to a synthetic member, expected facts written by a
            reviewer. The eval set then grows where the bot actually fails.
          </NumberedCard>
        </ol>
      </section>

      {/* 6. How a launch would go */}
      <section aria-labelledby="launch" className="flex flex-col gap-4">
        <SectionHeader id="launch" eyebrow="6 · Launch checklist" title="How a launch would go">
          <p>Each step has to pass before the next one starts.</p>
        </SectionHeader>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <NumberedCard n={1} title="Offline gate">
            Rerun the affected cases. The decision is Ship, no guardrail misses, and cost and latency are checked on
            the eval set.
          </NumberedCard>
          <NumberedCard n={2} title="Small canary">
            A canary is a small first release, about 1% of members for a day or two. It does not measure the effect; it
            catches crashes, slow replies, cost spikes and safety flags, with a quick rollback.
          </NumberedCard>
          <NumberedCard n={3} title="A/B test">
            Split members 50/50, sticky by member ID. Fix the primary metric, the guardrail margins and the length in
            whole weeks before it starts.
          </NumberedCard>
          <NumberedCard n={4} title="Readout">
            Check the split first (sample ratio mismatch), then the guardrails, then the primary metric with its confidence interval (the range
            of effects the data are consistent with). Segment cuts are ideas for the next test, not findings. Write the
            decision down: ship, change, or drop.
          </NumberedCard>
          <NumberedCard n={5} title="Rollout">
            Move the remaining members over, in steps if the change is risky, while watching the guardrails. Keep a
            small long-term holdout on the old version to measure the lagging metrics.
          </NumberedCard>
          <NumberedCard n={6} title="Monitoring">
            Every day: code checks on every reply, the judge on a sample, latency and cost. Every week: a human audit.
            Alerts on any guardrail breach, and new failures added to the offline set.
          </NumberedCard>
        </ol>
      </section>
    </div>
  );
}
