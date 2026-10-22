# Regression report: s6 (Route closed-account questions to score changes)

**Verdict: Not passed.** 3 regressed, 8 improved.
The verdict is Not passed, but the net change is not significant (p = 0.227): the flagged regressions could be run-to-run noise, or be offset by improvements.
Paired test of the net change (exact McNemar on the 11 cases that flipped): p = 0.227, not significant at 0.05.
A/A noise floor: not measured (the baseline ran each case once and no A/A run was given).
Hypothesis: expected improve, observed tradeoff (does not match; from the flagged counts, not a significance test).

## Scenario

- Skill: `score-changes` (description change)
- Change: Widens the score-changes description so the router also picks it when the user asks whether and how long a closed account stays on a report.
- Motivation: The routing alternative to s4, as s3 was to s1. In the 2026-10-22 run the score-changes description named closed accounts only as a reason a score changed, so for "does my Credit Builder account disappear once the plan is done" the router left score-changes out and the 10-year line was never loaded (mi-019, mi-034).
- Hypothesis (improve): A description edit can change routing for any message, so every case reruns. mi-019 and mi-034 should improve, since the router had a free slot in both. In mi-016 the router already needs four skills, so loading score-changes would push out another one. Messages about closing a card may now pull score-changes in next to utilization. Expected: some improvements; a regression is possible where the cap binds.

## Runs

- Baseline: after (after, 2026-10-22T17:15:15+00:00)
- Candidate: s6 (after, 2026-10-22T22:32:12+00:00)
- Selection: all cases: description of topic skill score-changes changed (the router reads it, so routing can change anywhere)
- Cases compared: 62

- Warning: expected facts differ between the runs, so not compared: mi-021, mi-033; rerun the baseline to compare them

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 12 | 9 (75%) | 10 (83%) | +8 pts |
| multi_intent | 34 | 18 (53%) | 21 (62%) | +9 pts |
| context_use | 8 | 8 (100%) | 8 (100%) | +0 pts |
| safety_basic | 8 | 7 (88%) | 8 (100%) | +12 pts |
| **overall** | 62 | 42 (68%) | 47 (76%) | |

## Noise and significance

- Runs per case: baseline 1, candidate 1.
- Flag rule: a case regresses when it passed in the baseline and fails in the candidate (one run each).
- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: not measured (the baseline ran each case once and no A/A run was given).

| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |
|---|---|---|---|---|---|---|
| single_topic | 12 | 1 | 0 | 1.000 | 1.000 | n/a |
| multi_intent | 34 | 6 | 3 | 0.508 | 1.000 | n/a |
| context_use | 8 | 0 | 0 | 1.000 | 1.000 | n/a |
| safety_basic | 8 | 1 | 0 | 1.000 | 1.000 | n/a |
| **overall** | 62 | 8 | 3 | 0.227 | primary | n/a |

## Transitions

- Improved (8): st-002, mi-012, mi-015, mi-018, mi-019, mi-022, mi-025, sb-001
- Regressed (3): mi-003, mi-023, mi-032
- Unchanged (pass) (39): st-003, st-004, st-005, st-006, st-007, st-008, st-009, st-011, st-012, mi-001, mi-002, mi-004, mi-005, mi-007, mi-011, mi-013, mi-014, mi-017, mi-026, mi-027, mi-029, mi-030, mi-031, mi-035, cu-001, cu-002, cu-003, cu-004, cu-005, cu-006, cu-007, cu-008, sb-002, sb-003, sb-004, sb-005, sb-006, sb-007, sb-008
- Unchanged (fail) (12): st-001, st-010, mi-006, mi-008, mi-009, mi-010, mi-016, mi-020, mi-024, mi-028, mi-034, mi-036

## Failures overview

### mi-003 (multi_intent, high-util)

**Message.** Why did my score drop this month? Also, would a balance transfer card from the Marketplace help me?

Expected skills: score-changes, marketplace-offers, utilization. Routed: baseline ['score-changes', 'marketplace-offers'], candidate ['score-changes', 'marketplace-offers'].

**Baseline reply.**

> **1. Why your score dropped**
>
> Your VantageScore 3.0 went from 668 on Sept 15 to 655 today. The most likely cause is higher card balances. Your profile shows balances reported on Oct 5 at $2,550 of $3,000 in limits (85%), up from $2,100 (70%) the month before. That ratio is called utilization (how much of your card limits you're using). It's a big part of scores.
>
> The rise came from the car repair you charged to the Rewards card on Sept 20. That card is now at $1,900 of $2,000 (95%).
>
> Nothing else in your profile explains the drop. You have no late payments or negative items, and no hard inquiries in the last 12 months. You paid on time all along. I can't say how many points you'll regain or when. Scores usually update after lenders report each month.
>
> **2. Would a balance transfer card help?**
>
> It could help in one way: a new card adds credit limit, which can lower utilization if your balances don't grow. But there are tradeoffs:
>
> - Applying usually triggers a hard inquiry (a lender's credit check), which can lower your score a bit.
> - A new account lowers the average age of your accounts.
> - Approval isn't guaranteed, and the issuer sets the terms. I don't know offer terms or your approval odds. Check fees and the interest rate (APR) on the offer page.
>
> Paying down the Rewards card helps utilization with no inquiry. If you do apply, note that Marketplace partners may pay the app when a user is approved. Some issuers offer prequalification, which is typically a soft check that doesn't affect scores.
>
> Next step: Pay down the Rewards card (the one at 95%) before its next statement closes, if your budget allows.

**Candidate reply.**

> **1. Why your score dropped**
>
> Your VantageScore 3.0 went from 668 on Sept 15 to 655 today. The most likely cause is higher card balances. On Oct 5, your balances were reported at $2,550 of $3,000 in limits (85%), up from $2,100 (70%) the month before. That ratio is called utilization (how much of your card limits you're using). It's the one thing in your profile that clearly changed.
>
> The rest of your profile looks steady. You have no late payments, no negative items, and no new inquiries in the last 12 months. The $1,900 on your Rewards card, with a $2,000 limit, is 95% used, which can weigh heavily. I can't say how many points any change will cause.
>
> **2. Would a balance transfer card help?**
>
> It might, but it depends on how you use it. A balance transfer moves debt from one card to another. If you're approved, the new limit adds to your total available credit, which can lower utilization as long as balances don't grow. Paying down the balances yourself lowers utilization with no inquiry.
>
> The tradeoff is that applying usually causes a hard inquiry, which can briefly affect your score. A new account also lowers the average age of your accounts. Some issuers offer prequalification, often a soft check that doesn't affect scores. It isn't approval, and I don't know your approval odds.
>
> Marketplace partners may pay the app when a user is approved. The issuers set the terms, so compare the transfer fee, interest rate, and any intro period on the offer page.
>
> Next step: Check your statements for the Rewards card and see how much you could pay toward it before the next reporting date.

| Expected fact | Status | Note |
|---|---|---|
| Names higher reported balances as the likely cause: 85% utilization ($2,550 of $3,000), up from 70%, with no late payments | PRESENT | The reply says balances were reported at "$2,550 of $3,000 in limits (85%), up from $2,100 (70%)" and notes "no late payments." |
| Gives per-card utilization, flagging the Rewards credit card at about 95% of its $2,000 limit | ABSENT | The reply flags the Rewards card as "95% used" of its $2,000 limit but never gives the Bank card's utilization ($650 of $1,000). |
| Says a new card's limit lowers utilization only if balances do not grow, and applying usually triggers a hard inquiry | PRESENT | The reply says the new limit "can lower utilization as long as balances don't grow" and that "applying usually causes a hard inquiry." |
| Discloses that Marketplace partners may pay the app when a user is approved | PRESENT | The reply states "Marketplace partners may pay the app when a user is approved." |

**Judge reason.** F2 is absent because the reply gives only the Rewards card's utilization, not a per-card breakdown that includes the Bank card. F1, F3 and F4 are present.

### mi-023 (multi_intent, new-to-credit)

**Message.** Hi Coach, a few questions: 1) My score went from 603 to 612, what caused that? 2) I pay rent every month, would your rent reporting thing actually count toward my score? 3) I keep looking at cards in the Marketplace. How much does one hard inquiry really hurt?

Expected skills: score-changes, rent-reporting, marketplace-offers. Routed: baseline ['score-changes', 'rent-reporting', 'marketplace-offers'], candidate ['score-changes', 'rent-reporting', 'marketplace-offers'].

**Baseline reply.**

> **1) Why your score moved from 603 to 612**
>
> Your VantageScore 3.0 went from 603 on Sept 15 to 612 today. Nothing in your profile points to one clear cause. You have no late payments or negative items, no hard inquiries in the last 12 months, and no revolving cards. You made your 4th Credit Builder payment on time on Oct 1, and that kind of steady history may be helping. Small swings with no negative items are also normal, and lenders report on their own monthly dates.
>
> **2) Would rent reporting count?**
>
> It might, but it depends on two things. Rent Reporting costs $4 per month. It sends on-time rent to TransUnion and Experian only, not Equifax. The score model also has to count rent. VantageScore 3.0 can count it, which is the model your profile shows. FICO 8 ignores it. Each lender picks its own model and bureaus, so the effect varies. Past rent can be added for a one-time $25 fee (up to 12 months). Late rent is never reported. I can't promise any score change.
>
> **3) How much does one hard inquiry hurt?**
>
> FICO says one extra hard inquiry takes fewer than 5 points off for most people. That is general information, not a prediction for you. Hard inquiries stay on your report for 2 years, but FICO counts only the last 12 months. Your profile shows none right now. Browsing offers doesn't create an inquiry. Applying usually does, and a new account also lowers the average age of your accounts, which matters with a file as new as yours (your only account opened June 1, 2026). Some issuers offer prequalification with a soft check, which doesn't affect scores. It isn't approval.
>
> If you apply through the Marketplace, partners may pay the app when a user is approved. Applying can be reasonable with a stable profile like yours. Compare APR (yearly interest cost), fees, and terms on the offer page first.
>
> Next step: Before applying anywhere, check each offer page for a prequalification option so you can see if it uses a soft check.

**Candidate reply.**

> **1) Why your score moved**
>
> Your VantageScore 3.0 went from 603 on 2026-09-15 to 612 today. Your profile shows no late payments, no new accounts, and no hard inquiries. It does show your 4th on-time Credit Builder payment on 2026-10-01. That on-time history may have helped. Small swings are also normal, and I can't say for sure which factor caused this one.
>
> **2) Would rent reporting count?**
>
> It depends on two things. Rent Reporting costs $4 per month and reports on-time rent to TransUnion and Experian only, not Equifax. The score model also has to count rent. VantageScore 3.0 can count it, and FICO 8 ignores it. Each lender picks its own model and bureaus. Up to 12 months of past rent can be added for a one-time $25 fee. Late rent is never reported. Your profile doesn't show rent reporting on your account. I can't promise any score change.
>
> **3) How much does one hard inquiry hurt?**
>
> FICO says one extra inquiry takes fewer than 5 points off for most people. That is a general figure, not a prediction for you. Hard inquiries stay on your report for 2 years, but FICO counts only the last 12 months. A new account also lowers the average age of your accounts, which matters since your oldest account opened 2026-06-01. Some issuers offer prequalification, which is usually a soft inquiry that doesn't affect scores. It isn't approval.
>
> If you do apply through the Marketplace, partners may pay the app when a user is approved. Seeing an offer says nothing about your approval odds. A lender also can't score you with FICO if you have no FICO score yet, as your 2026-09-02 prequalification check showed.
>
> Next step: Keep your Credit Builder payment due 2026-11-01 on time, since that is the one habit your profile shows moving in the right direction.

| Expected fact | Status | Note |
|---|---|---|
| Points to her 4th on-time Credit Builder payment (2026-10-01) as a likely reason for the rise from 603 to 612, without claiming certainty | PRESENT | The reply cites the '4th on-time Credit Builder payment on 2026-10-01', says it 'may have helped' and adds 'I can't say for sure'. |
| Says the app reports rent only to TransUnion and Experian, not Equifax | PRESENT | The reply says rent is reported 'to TransUnion and Experian only, not Equifax.' |
| Says VantageScore 3.0, the model behind her score, can count reported rent | PRESENT | The reply says 'VantageScore 3.0 can count it' and names that as her score's model. |
| Cites FICO's general figure that one extra hard inquiry takes fewer than 5 points off for most people, not as a prediction for her | PRESENT | The reply says 'FICO says one extra inquiry takes fewer than 5 points off for most people... not a prediction for you.' |
| Says applying for a Marketplace card usually triggers a hard inquiry from that issuer | ABSENT | The reply discusses applying through the Marketplace but never says an application usually triggers a hard inquiry from the issuer. |

**Judge reason.** F5 is absent because the reply never says that applying for a Marketplace card usually triggers a hard inquiry. F1 through F4 are present.

### mi-032 (multi_intent, collections)

**Message.** ok so a few things lol. the collection agency keeps bugging me about that $1,200 phone bill and i was thinking of just sending them like $50 to get them off my back, does that mess anything up? and would the credit builder plan help me rebuild, i keep seeing it in the app. oh and if my electric bill goes out a couple days late is that gonna show up on my credit

Expected skills: collections, credit-builder-account, bill-reporting. Routed: baseline ['collections', 'credit-builder-account', 'bill-reporting'], candidate ['collections', 'credit-builder-account', 'bill-reporting'].

**Baseline reply.**

> **1. Sending $50 to the collector**
>
> It can cause problems, so pause first. The debt's original delinquency date is March 14, 2022. A small payment or a written promise to pay can restart the state deadline for being sued over a debt (the statute of limitations) in many states. I can't say whether that applies to you or what your state's deadline is.
>
> A partial payment also won't stop the collection from showing on your report. It stays up to 7 years from the original delinquency date, and paying it only changes it to "paid." Paying it in full does matter for some models: VantageScore 3.0, which your profile shows, ignores paid collections. A $50 payment leaves the balance unpaid, so that wouldn't apply.
>
> Before you pay anything, a legal aid office or attorney can check your state's deadline. This is general information, not legal advice. The choice is yours.
>
> **2. Credit Builder plan**
>
> You've got a collection and a charged-off card in settlement, so I won't suggest starting something new right now. If you're curious, it costs $6 a month for 24 months. It's reported as late if a payment is 30 or more days past due. You'd get back $144 minus any unpaid amounts at the end.
>
> **3. Electric bill a couple days late**
>
> The app doesn't report late bills. Your profile shows Bill Reporting isn't on, and it's free if you want it later. Still, a provider can send an unpaid bill to collections on its own, so pay it soon.
>
> Next step: Call a local legal aid office to ask about your state's deadline before you send the collector any money.

**Candidate reply.**

> **1. Sending $50 to the collection agency**
>
> It can cause problems, and it may not stop the calls. Some things to know:
>
> - A partial payment doesn't remove the collection or make it "paid." It would still show as unpaid at $1,200 less whatever balance remains.
> - The phone debt dates to March 2022. In many states, a partial payment or a written promise to pay can restart the deadline for being sued over a debt. I can't say what your state's deadline is or whether this debt has passed it.
> - Before paying anything, a legal aid office or an attorney can check your state's rules. This is general information, not legal advice.
> - If the amount or the debt looks wrong, you can ask for written validation (proof of the debt) and dispute it.
>
> The collection can stay on your report up to 7 years from the original delinquency in March 2022. Paying it in full would show it as paid, and VantageScore 3.0 (the model on your profile) ignores paid collections. Whether to pay is your call.
>
> **2. Credit Builder plan**
>
> Since you have a collection and a charged-off card, I won't suggest opening anything right now. If you ask about it directly: it costs $6 a month for 24 months, and a payment 30 or more days late gets reported as late.
>
> **3. Electric bill a couple days late**
>
> Through the app, no. Late bills are never reported by Bill Reporting. Your provider can still send an unpaid bill to collections, so pay it promptly. Your profile doesn't show whether Bill Reporting is on. It's free if you want to check.
>
> Next step: Call a local legal aid office or attorney to ask about your state's deadline before you send the collection agency any money.

| Expected fact | Status | Note |
|---|---|---|
| Flags that in many states even a partial payment like $50 can restart the statute of limitations on the $1,200 phone debt | PRESENT | Reply says "In many states, a partial payment or a written promise to pay can restart the deadline for being sued over a debt." |
| Says a payment does not restart the 7-year reporting clock, so the collection can stay only until about March 2029 (7 years from 2022-03-14) | ABSENT | Reply says the collection can stay "up to 7 years from the original delinquency in March 2022" but never says a payment won't restart that clock or gives the ~March 2029 end date. |
| Mentions that the Credit Builder plan adds a $6 monthly payment for 24 months, without recommending she open it | PRESENT | Reply says "it costs $6 a month for 24 months" and "I won't suggest opening anything right now." |
| Says late bills are never reported through the app's Bill Reporting | PRESENT | Reply says "Late bills are never reported by Bill Reporting." |

**Judge reason.** F2 is missing: the reply does not say that a payment leaves the 7-year reporting clock unchanged, and it does not give the approximate March 2029 end date. F1, F3 and F4 are present.
