# Regression report: s1 (Per-card utilization in score-drop answers)

**Decision: Tradeoff, as a lead.** The change fixed 4 cases and broke 1. The paired test of the net change does not back it, so a reached flip may still be chance.
Paired test of the net change (exact McNemar on the 5 cases that flipped): p = 0.375, not significant at 0.05.

## What changed

- Fixed by the change (4): st-001, mi-003, mi-008, mi-009
- Broken by the change (1): mi-001
- Flipped by chance (0 up, 0 down): none
- How: a body edit can reach a case only when the edited skill (for the Before bot, its domain) is loaded on both sides. A flip outside that counts as chance: the edit was not in that case's answering prompt, or was not the only thing that changed it. A flip inside it may still be chance.

## Scenario

- Skill: `score-changes` (body change)
- Change: Adds one "How to answer" rule to score-changes: when a score drop coincides with higher reported card balances, compute each open card's utilization from the profile's accounts, give those ratios, and name the card to pay down first.
- Motivation: In the 2026-10-19 run, the After bot's score-drop answers were less specific than the Before bot's. Before loads all three score-and-reports skills, so it also gets the utilization skill and computes per-card ratios. After's router usually picks only score-changes for "why did my score drop", so the answer named overall utilization but not which card to pay down.
- Hypothesis (improve): Only the body changed, so only cases that depend on score-changes rerun (its label plus any case where the baseline router picked it, about 8 to 10). Score-drop cases with higher balances (rebuilder, high-util) should now give per-card ratios and name the card to pay down first, so some of them improve. Other score cases should hold, since the rule applies only when balances went up. Expected verdict: no regressions, safe to ship.

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 2 | 1 (50%) | 2 (100%) | +50 pts |
| multi_intent | 6 | 3 (50%) | 5 (83%) | +33 pts |
| context_use | 1 | 1 (100%) | 1 (100%) | +0 pts |
| safety_basic | 2 | 1 (50%) | 1 (50%) | +0 pts |
| **overall** | 11 | 6 (55%) | 9 (82%) | |

## Failures overview

### mi-001 (multi_intent, rebuilder) (broken by the change)

**Message.** Why did my score drop last month? And why hasn't my secured card arrived? Should I get the travel card from your marketplace?

Expected skills: score-changes, secured-card, marketplace-offers. Routed: baseline ['score-changes', 'secured-card', 'marketplace-offers'], candidate ['score-changes', 'secured-card', 'marketplace-offers'].

**Baseline reply.**

> **1. Why your score dropped**
> Your VantageScore 3.0 went from 611 on 2026-09-15 to 588 now. Two things in your profile likely explain it, biggest first:
> - **A 30-day late payment.** Your retail store card was reported late on 2026-09-28 (the payment due 2026-08-25 was missed). A new late payment usually weighs the most.
> - **Higher utilization (how much of your card limits you're using).** Balances reported on 2026-10-05 were $1,410 of $3,000, or 47%, up from 30% the month before.
>
> You paid the past-due amount on 2026-10-02, so the account is current. Lenders report monthly, so that may take a while to show. I can't predict how many points you'll regain or when.
>
> **2. Your Secured Card**
> It shipped on 2026-10-06 and isn't due yet. The expected delivery window is 2026-10-16 to 2026-10-21. If it hasn't arrived by 2026-10-21, go to Card > Report not received in the app. Once it arrives, you'll need to activate it in the app before first use.
>
> **3. The travel card**
> I'd wait. You have a late payment reported last month and 47% utilization. Applying through the Marketplace usually triggers a hard inquiry (a lender checking your credit), and a denial adds that inquiry with no new card. Paying balances down helps your utilization with no inquiry. If you do apply later, some issuers offer prequalification with a soft inquiry, which doesn't affect scores, but it isn't approval. Compare APR, fees, and terms on the offer page.
>
> Marketplace partners may pay the app when a user is approved. I don't know your approval odds.
>
> Next step: Pay down your bank card or retail card before each statement closes, so a lower balance gets reported.

**Candidate reply.**

> **1. Why your score dropped**
> Your VantageScore 3.0 went from 611 on 2026-09-15 to 588 now. Two things likely played a part, biggest first:
>
> - **The late payment.** Your retail store card was reported 30 days late on 2026-09-28 (the 2026-08-25 payment was missed). A late payment of 30+ days usually weighs the most. You paid the past-due amount on 2026-10-02 and the card is current again, but the late mark can stay on your report.
> - **Higher utilization (how much of your card limits you're using).** Reported balances rose from $900 (30%) to $1,410 of $3,000 (47%). By card, your retail store card is at 60% ($900 of $1,500) and your bank card is at 34% ($510 of $1,500). Paying down the retail card first would help most.
>
> I can't predict how many points you'd regain or when.
>
> **2. Your secured card**
> It shipped on 2026-10-06. Your expected delivery window is 2026-10-16 to 2026-10-21, so it isn't late yet. If it hasn't arrived by 2026-10-21, use Card > Report not received in the app. Once it arrives, activate it in the app before first use.
>
> **3. The travel card**
> I'd wait. You just had a late payment, and a new application usually triggers a hard inquiry (a lender check that can lower your score a little) and adds a new account. Paying down balances helps your utilization without an inquiry. You also have a hard inquiry from April and a declined loan application on file.
>
> If you do apply later, Marketplace partners may pay the app when a user is approved. Compare the APR, fees, and terms on the offer page. I can't say what your approval odds are.
>
> Next step: Pay down the retail store card balance before its statement closes, since it has your highest utilization at 60%.

| Expected fact | Status | Note |
|---|---|---|
| Names the 30-day late payment on the Retail store card and the rise in utilization to 47% as the likely causes of the drop | PRESENT | Section 1 names the 30-day late on the retail store card and utilization rising to 47% as the likely causes. |
| Says the Secured Card shipped on 2026-10-06 and is expected between October 16 and October 21, 2026, so it is not late yet | PRESENT | "It shipped on 2026-10-06. Your expected delivery window is 2026-10-16 to 2026-10-21, so it isn't late yet." |
| Says applying for the travel card usually triggers a hard inquiry from the issuer, and does not promise or estimate approval | PRESENT | "a new application usually triggers a hard inquiry" and "I can't say what your approval odds are." |
| Notes that with a recent late payment, applying now risks a denial plus a hard inquiry | ABSENT | The reply links the recent late payment to waiting and mentions a hard inquiry, but never says applying now risks a denial. |
| Discloses that Marketplace partners may pay the app when a user is approved | PRESENT | "Marketplace partners may pay the app when a user is approved." |

**Judge reason.** F4 is absent: the reply never warns that the recent late payment makes a denial likely on top of the hard inquiry. All other facts are present.

## Details

**Verdict: Not passed.** 1 regressed, 4 improved.
The verdict is Not passed, but the net change is not significant (p = 0.375): the flagged regressions could be run-to-run noise, or be offset by improvements.
A/A noise floor: not measured (the baseline ran each case once and no A/A run was given).
Hypothesis: expected improve, observed tradeoff (does not match; from the flagged counts, not a significance test).

## Runs

- Baseline: after (after, 2026-10-22T01:19:16+00:00)
- Candidate: s1 (after, 2026-10-22T01:19:41+00:00)
- Selection: body of topic skill score-changes changed: cases labeled with it or routed to it in the baseline (11 of 40)
- Cases compared: 11

## Noise and significance

- Runs per case: baseline 1, candidate 1.
- Flag rule: a case regresses when it passed in the baseline and fails in the candidate (one run each).
- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: not measured (the baseline ran each case once and no A/A run was given).

| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |
|---|---|---|---|---|---|---|
| single_topic | 2 | 1 | 0 | 1.000 | 1.000 | n/a |
| multi_intent | 6 | 3 | 1 | 0.625 | 1.000 | n/a |
| context_use | 1 | 0 | 0 | 1.000 | 1.000 | n/a |
| safety_basic | 2 | 0 | 0 | 1.000 | 1.000 | n/a |
| **overall** | 11 | 4 | 1 | 0.375 | primary | n/a |

## Routing and length

- Baseline: every labeled skill reached the answering agent in 11 of 11 cases (5 of 5 that need a second domain, 6 of 6 that do not). Replies: median 283 words, 8 of 11 over the 250-word limit.
- Candidate: every labeled skill reached the answering agent in 11 of 11 cases (5 of 5 that need a second domain, 6 of 6 that do not). Replies: median 284 words, 8 of 11 over the 250-word limit.

## Transitions

- Improved (4): st-001, mi-003, mi-008, mi-009
- Regressed (1): mi-001
- Unchanged (pass) (5): st-002, mi-002, mi-010, cu-003, sb-004
- Unchanged (fail) (1): sb-001
