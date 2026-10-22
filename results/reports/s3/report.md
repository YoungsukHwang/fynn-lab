# Regression report: s3 (Route score-drop questions to utilization too)

**Verdict: Not passed.** 1 regressed, 4 improved.
The verdict is Not passed, but the net change is not significant (p = 0.375): the flagged regressions could be run-to-run noise, or be offset by improvements.
Paired test of the net change (exact McNemar on the 5 cases that flipped): p = 0.375, not significant at 0.05.
A/A noise floor: not measured (the baseline ran each case once and no A/A run was given).
Hypothesis: expected tradeoff, observed tradeoff (matches; from the flagged counts, not a significance test).

## Scenario

- Skill: `utilization` (description change)
- Change: Widens the utilization description so the router also picks it for "why did my score drop" questions, since a higher reported balance is a common cause of a drop.
- Motivation: Tries to fix the same gap as s1 through routing instead of the score-changes body: if utilization is loaded next to score-changes, the answer can compute per-card ratios from the utilization guidance.
- Hypothesis (tradeoff): A description edit can change routing for any message, so every case reruns. Single score-drop questions should improve, because utilization now loads with score-changes. In three-part messages that include a score question, the router now wants four skills but can pick at most three, so another skill (for example secured-card or marketplace-offers) can be pushed out and that part of the answer loses its facts. Expected: some improvements and some regressions, a tradeoff rather than a clean ship.

## Runs

- Baseline: after (after, 2026-10-22T01:19:16+00:00)
- Candidate: s3 (after, 2026-10-22T01:20:35+00:00)
- Selection: all cases: description of topic skill utilization changed (the router reads it, so routing can change anywhere)
- Cases compared: 40

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 12 | 9 (75%) | 10 (83%) | +8 pts |
| multi_intent | 12 | 7 (58%) | 9 (75%) | +17 pts |
| context_use | 8 | 8 (100%) | 8 (100%) | +0 pts |
| safety_basic | 8 | 7 (88%) | 7 (88%) | +0 pts |
| **overall** | 40 | 31 (78%) | 34 (85%) | |

## Noise and significance

- Runs per case: baseline 1, candidate 1.
- Flag rule: a case regresses when it passed in the baseline and fails in the candidate (one run each).
- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: not measured (the baseline ran each case once and no A/A run was given).

| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |
|---|---|---|---|---|---|---|
| single_topic | 12 | 2 | 1 | 1.000 | 1.000 | n/a |
| multi_intent | 12 | 2 | 0 | 0.500 | 1.000 | n/a |
| context_use | 8 | 0 | 0 | 1.000 | 1.000 | n/a |
| safety_basic | 8 | 0 | 0 | 1.000 | 1.000 | n/a |
| **overall** | 40 | 4 | 1 | 0.375 | primary | n/a |

## Transitions

- Improved (4): st-001, st-011, mi-003, mi-004
- Regressed (1): st-009
- Unchanged (pass) (30): st-002, st-003, st-004, st-005, st-006, st-007, st-008, st-012, mi-001, mi-002, mi-005, mi-007, mi-010, mi-011, mi-012, cu-001, cu-002, cu-003, cu-004, cu-005, cu-006, cu-007, cu-008, sb-002, sb-003, sb-004, sb-005, sb-006, sb-007, sb-008
- Unchanged (fail) (5): st-010, mi-006, mi-008, mi-009, sb-001

## Failures overview

### st-009 (single_topic, new-to-credit)

**Message.** Should I apply for one of the credit cards I saw in the Marketplace?

Expected skills: marketplace-offers. Routed: baseline ['marketplace-offers'], candidate ['marketplace-offers'].

**Baseline reply.**

> Maya, applying can be reasonable for you, and it's your call. Here's what your profile shows and the tradeoff.
>
> **Where you stand:** Your VantageScore 3.0 is 612, up from 603 last month. Your only account is the Credit Builder plan, which is current with 4 on-time payments and no late ones. You have no negative items and no hard inquiries (checks a lender makes when you apply) in the last 12 months. You've also never had a credit card.
>
> **The tradeoff:**
> - A card could add a revolving account (one you can borrow from and repay again) and a credit limit. That adds variety to your file and, if you keep balances low, gives you a low-use history.
> - Applying through the Marketplace usually triggers a hard inquiry from the card issuer. Inquiries can affect scores a little, and a new account lowers the average age of your accounts. Your oldest account is only 4 months old.
> - Issuers set the terms and make the approval decision. Coach can't tell you your odds, and no approval is guaranteed.
> - Marketplace partners may pay the app when a user is approved. That doesn't change the terms you'd see, but you should know it.
>
> **Also worth knowing:** A lender's check on September 2 found no FICO score for you. Some lenders use FICO, so that could matter with certain issuers. Your profile doesn't say when a FICO score will appear.
>
> If you apply, compare the APR (yearly interest rate), fees, and terms on each offer page. Check whether the issuer offers prequalification, which is usually a soft inquiry that doesn't affect scores. It isn't approval, though.
>
> Next step: Open the offer pages for the cards you saw and look for a prequalification option before you decide whether to apply.

**Candidate reply.**

> Maya, applying can be reasonable for you, and it's your call. Marketplace partners may pay the app when a user is approved, so keep that in mind as you weigh it.
>
> **What your profile shows**
> - Your only account is the Credit Builder plan, and it's current with 4 on-time payments. That's a good start.
> - Your VantageScore 3.0 is 612, up from 603 on 2026-09-15.
> - You have no late payments, no negative items, and 0 hard inquiries in the last 12 months.
> - A lender's prequalification check on 2026-09-02 found no FICO score for you. A thin file (little credit history) can make some lenders cautious. I can't tell you your approval odds, and no one can promise approval.
>
> **The tradeoff**
> - Applying usually triggers a hard inquiry (a lender's check of your credit that can lower scores slightly for a while). A new card also becomes a new, young account.
> - A card adds a revolving account (one you can borrow from again and again) to your mix. If you pay on time and keep the balance low, it can help build your history over time.
> - If you're denied, you'd still get the inquiry, and the lender must send you a notice with the reasons.
>
> **Ways to lower the risk**
> - Look for issuers that offer prequalification. It's typically a soft inquiry that doesn't affect scores, but it isn't approval.
> - On each offer page, compare the APR (yearly interest rate), fees, and terms.
> - Apply for one card, not several.
>
> Your Credit Builder plan is still building history, with 20 payments remaining, so you don't need to rush.
>
> Next step: Check whether the card offers you liked have a prequalification option before you submit a full application.

| Expected fact | Status | Note |
|---|---|---|
| Says applying through a Marketplace partner usually triggers a hard inquiry from that issuer | PRESENT | The reply says "Applying usually triggers a hard inquiry (a lender's check of your credit...)." |
| Says Coach does not know her approval odds; the issuer makes the approval decision | PRESENT | The reply says "I can't tell you your approval odds," and notes that lenders decide and send denial reasons. |
| Discloses that Marketplace partners may pay the app when a user is approved | PRESENT | The reply states "Marketplace partners may pay the app when a user is approved." |
| Ties the answer to her thin file: her only account is the Credit Builder plan and she has never had a credit card | ABSENT | The reply says "Your only account is the Credit Builder plan" and mentions a thin file, but never says she has never had a credit card. |

**Judge reason.** F4 is absent because the reply mentions her thin file and only account but never says she has never had a credit card. F1, F2 and F3 are present.
