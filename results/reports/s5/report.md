# Regression report: s5 (Route free-report and recovery questions to payment history)

**Verdict: Not passed.** 3 regressed, 7 improved.
The verdict is Not passed, but the net change is not significant (p = 0.344): the flagged regressions could be run-to-run noise, or be offset by improvements.
Paired test of the net change (exact McNemar on the 10 cases that flipped): p = 0.344, not significant at 0.05.
A/A noise floor: not measured (the baseline ran each case once and no A/A run was given).
Hypothesis: expected improve, observed tradeoff (does not match; from the flagged counts, not a significance test).

## Scenario

- Skill: `payment-history` (description change)
- Change: Widens the payment-history description so the router also picks it when the user asks how to get free credit reports, or whether or when a score will recover or reach a target.
- Motivation: In the 2026-10-22 run, the free-reports line sits in the payment-history body but its description never mentions credit reports, so the After router judged that no skill covered "is there a free way to look at my credit reports" (mi-024). In sb-001, a "back above 600 by December" question, the router left payment-history out, so the reply could not say how the recent late fades.
- Hypothesis (improve): A description edit can change routing for any message, so every case reruns. mi-024 and sb-001 should improve once payment-history loads. Recovery questions inside three-part messages could now take a slot from another skill, but the new triggers are narrow, so few cases should lose a skill. Expected: improvements and no regressions, or at most one.

## Runs

- Baseline: after (after, 2026-10-22T17:15:15+00:00)
- Candidate: s5 (after, 2026-10-22T22:32:15+00:00)
- Selection: all cases: description of topic skill payment-history changed (the router reads it, so routing can change anywhere)
- Cases compared: 62

- Warning: expected facts differ between the runs, so not compared: mi-021, mi-033; rerun the baseline to compare them

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 12 | 9 (75%) | 8 (67%) | -8 pts |
| multi_intent | 34 | 18 (53%) | 22 (65%) | +12 pts |
| context_use | 8 | 8 (100%) | 8 (100%) | +0 pts |
| safety_basic | 8 | 7 (88%) | 8 (100%) | +12 pts |
| **overall** | 62 | 42 (68%) | 46 (74%) | |

## Noise and significance

- Runs per case: baseline 1, candidate 1.
- Flag rule: a case regresses when it passed in the baseline and fails in the candidate (one run each).
- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: not measured (the baseline ran each case once and no A/A run was given).

| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |
|---|---|---|---|---|---|---|
| single_topic | 12 | 0 | 1 | 1.000 | 1.000 | n/a |
| multi_intent | 34 | 6 | 2 | 0.289 | 1.000 | n/a |
| context_use | 8 | 0 | 0 | 1.000 | 1.000 | n/a |
| safety_basic | 8 | 1 | 0 | 1.000 | 1.000 | n/a |
| **overall** | 62 | 7 | 3 | 0.344 | primary | n/a |

## Transitions

- Improved (7): mi-008, mi-010, mi-012, mi-015, mi-022, mi-024, sb-001
- Regressed (3): st-011, mi-003, mi-030
- Unchanged (pass) (39): st-003, st-004, st-005, st-006, st-007, st-008, st-009, st-012, mi-001, mi-002, mi-004, mi-005, mi-007, mi-011, mi-013, mi-014, mi-017, mi-023, mi-026, mi-027, mi-029, mi-031, mi-032, mi-035, cu-001, cu-002, cu-003, cu-004, cu-005, cu-006, cu-007, cu-008, sb-002, sb-003, sb-004, sb-005, sb-006, sb-007, sb-008
- Unchanged (fail) (13): st-001, st-002, st-010, mi-006, mi-009, mi-016, mi-018, mi-019, mi-020, mi-025, mi-028, mi-034, mi-036

## Failures overview

### st-011 (single_topic, multi-product)

**Message.** My phone, electric and internet bills don't show up on my Experian report. Is Bill Reporting broken?

Expected skills: bill-reporting. Routed: baseline ['bill-reporting'], candidate ['bill-reporting'].

**Baseline reply.**

> No, this is most likely not a glitch. Bill Reporting sends your on-time payments to Equifax only. It does not send them to Experian or TransUnion, so they won't show on an Experian report.
>
> Your profile shows Bill Reporting is active, and it covers all three bills you mentioned. Each one (phone, electric, and internet) has 8 months reported so far.
>
> A few things to keep in mind:
>
> - **Check Equifax.** Your bill history should appear there, not on Experian.
> - **Your score may not reflect it.** Whether these payments affect a score depends on the scoring model and on whether a lender pulls Equifax data. I can't say how much they will or won't matter for you.
> - **Rent is different.** Rent and bills can reach different bureaus, so one report may look more complete than another.
>
> Your profile doesn't say which bureau your 702 VantageScore 3.0 comes from, so I can't tell you whether it includes this data.
>
> If your Equifax report doesn't show the bills either, that could be a detection problem with your linked bank account. Human support can look into that. Go to Help > Chat with support, or email support@example.com.
>
> Next step: Pull your free Equifax report and look for your phone, electric, and internet accounts. If they're missing there, contact human support.

**Candidate reply.**

> No, this is most likely how Bill Reporting is designed to work. It sends on-time phone, electric and internet payments to Equifax only. It does not send them to Experian or TransUnion, so they won't show on your Experian report.
>
> Your profile shows Bill Reporting is active, with your mobile phone, electric utility and home internet bills each reported for 8 months. Those payments should be on your Equifax report. It's worth checking there.
>
> A few other points:
> - Only on-time payments are reported. Late bills are never reported through the app.
> - Your profile lists your score as VantageScore 3.0 but doesn't say which bureau's data it uses, so I can't say whether it includes these bills.
> - A lender's view depends on which bureau they pull. I can't say whether a given lender will see or count these payments.
> - Your rent reporting goes through a different path than bills, so what shows on each bureau can differ.
>
> If your Equifax report doesn't show these bills after you check, or you think the app isn't detecting a payment from your linked bank account, human support can look into it. Use Help > Chat with support, or email support@example.com.
>
> Next step: Pull your Equifax report and look for the phone, electric and internet accounts. If they're missing there, contact human support.

| Expected fact | Status | Note |
|---|---|---|
| Says Bill Reporting sends bill payments only to Equifax, not to Experian or TransUnion, so not seeing them on Experian is expected | PRESENT | The reply says it "sends on-time phone, electric and internet payments to Equifax only. It does not send them to Experian or TransUnion." |
| Uses the profile: the mobile phone, electric utility and home internet bills have each been reported for 8 months | PRESENT | The reply says the "mobile phone, electric utility and home internet bills [are] each reported for 8 months." |
| Says the effect on a score depends on the scoring model and on whether a lender pulls Equifax | ABSENT | The reply covers which bureau a lender pulls, but it ties score inclusion only to bureau data and never says the effect depends on the scoring model. |

**Judge reason.** F1 and F2 are present. F3 is absent because the reply mentions lender bureau pulls but not that the score effect depends on the scoring model.

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
> Your VantageScore 3.0 moved from 668 on Sept 15 to 655 today. The most likely cause is higher card balances. Your profile shows balances reported on Oct 5 at $2,550 against $3,000 in limits (85%), up from $2,100 (70%) the month before. That's after the $ car repair charged to your Rewards card on Sept 20.
>
> Utilization (how much of your card limits you're using) is a common reason scores move. Your Rewards card is the highest, at $1,900 of $2,000 (95%).
>
> Nothing else in your profile explains it. You have no late payments, no negative items, and no new hard inquiries. Your on-time payments are helping, so this looks like a balance effect rather than a problem with your payment record. I can't say how many points you'll regain or when.
>
> **2. Would a balance transfer card help?**
>
> It might, but it comes with tradeoffs. Applying usually causes a hard inquiry (a lender check that can lower scores slightly) and adds a new account, which lowers the average age of your accounts. A new limit would lower your utilization only if your balances don't grow. Paying down balances helps without any inquiry.
>
> I don't have offer terms, such as transfer fees or the promotional rate, so check those on the offer page. Some issuers offer prequalification, which is usually a soft inquiry, but it isn't approval. Marketplace partners may pay the app when a user is approved, and I can't predict your approval odds.
>
> Next step: Pay down the Rewards card first, since it's at 95%, before deciding on any new card.

| Expected fact | Status | Note |
|---|---|---|
| Names higher reported balances as the likely cause: 85% utilization ($2,550 of $3,000), up from 70%, with no late payments | PRESENT | Reply says balances were reported at "$2,550 against $3,000 in limits (85%), up from $2,100 (70%)" and notes "no late payments." |
| Gives per-card utilization, flagging the Rewards credit card at about 95% of its $2,000 limit | ABSENT | Reply flags only the Rewards card at "$1,900 of $2,000 (95%)" and never gives the Bank card's utilization, so it does not give per-card figures. |
| Says a new card's limit lowers utilization only if balances do not grow, and applying usually triggers a hard inquiry | PRESENT | Reply says "A new limit would lower your utilization only if your balances don't grow" and "Applying usually causes a hard inquiry." |
| Discloses that Marketplace partners may pay the app when a user is approved | PRESENT | Reply states "Marketplace partners may pay the app when a user is approved." |

**Judge reason.** F2 is absent because the reply gives only the Rewards card's utilization and omits the Bank card's. F1, F3 and F4 are present.

### mi-030 (multi_intent, collections)

**Message.** The collection agency's letter from September says I owe $1,200 on the old phone account, but I think part of that is fees I never agreed to. How do I push back on the amount? Also, I've kept my store card paid on time and I really don't want to slip on it now. What's the best way to make sure that never happens?

Expected skills: collections, payment-history. Routed: baseline ['collections', 'payment-history'], candidate ['collections', 'payment-history'].

**Baseline reply.**

> **1. Pushing back on the amount**
>
> Since you think part of the $1,200 is fees you never agreed to, you can question it. Here is how:
>
> - **Check the letter.** A validation notice should list the creditor, an itemized balance, and a validation period end date. That date is 30 days after you received the letter. Your profile shows the letter arrived around September 22, so that window may be closing or already closed. Check the date on the letter.
> - **Dispute in writing.** If you do it within that period, the collector must stop collecting the disputed amount until it sends proof of the debt. Ask for an itemized breakdown of the fees.
> - **Dispute with the credit bureaus too.** If the reported amount looks wrong, you can dispute it with each bureau. They generally have 30 days to investigate. Keep copies of everything.
>
> If the period has passed, you can still ask for an itemized breakdown and dispute with the bureaus. Only dispute what you believe is inaccurate.
>
> Also, the debt dates to March 2022. Before you make any payment or sign a promise to pay, talk to a legal aid office or attorney. In many states, a partial payment or written promise can restart the deadline for being sued. This is general information, not legal advice.
>
> **2. Keeping your store card on time**
>
> Your profile shows you paid it on time on October 1. To keep that going:
>
> - Set up autopay for at least the minimum payment.
> - Add a calendar reminder a few days before the due date.
> - Keep your balance low. Yours is $280 on an $800 limit, which is 35% utilization (how much of your limit you're using).
>
> A payment is generally reported late only when it is 30 or more days past due, so catching a missed one fast matters.
>
> Next step: Turn on autopay for at least the minimum payment on your store card.

**Candidate reply.**

> **1. Pushing back on the $1,200**
>
> If you think the amount is wrong, you can ask for validation and dispute it. Here is how:
>
> - Look at the letter for the validation notice. It should list the creditor, an itemized balance, and a validation period end date. That date is 30 days after you received the letter.
> - If you dispute in writing before that date, the collector must stop collecting the disputed amount until it sends proof of the debt. Your profile shows the letter arrived around September 22, so check the date now. It may be close or already passed.
> - Ask for an itemized breakdown of the $1,200, so you can see which part is fees.
> - You can also dispute the entry with the credit bureaus, since you believe the amount is inaccurate. Keep copies of everything you send.
>
> Because this debt dates to March 2022, be careful before you make any payment or sign anything that promises payment. In many states that can restart the deadline for being sued. A legal aid office or attorney can check your state's rules. This is general information, not legal advice.
>
> **2. Keeping your store card on time**
>
> Your profile shows you paid the store card on time on October 1. Good habits to lock that in:
>
> - Set up autopay for at least the minimum payment, so a missed date can't happen.
> - Add a calendar reminder a few days before the due date as a backup.
> - Keep enough in your bank account to cover the autopay.
>
> Lenders usually report a payment as late only once it is 30 or more days past due, but a fee can still apply sooner. Autopay helps you avoid both.
>
> Next step: Find the validation period end date on the September letter and, if it hasn't passed, send a written dispute asking for an itemized breakdown of the $1,200.

| Expected fact | Status | Note |
|---|---|---|
| Suggests requesting debt validation from the collection agency, which lists an itemized balance she can check for the fees | PRESENT | Reply says to "ask for validation" and get "an itemized breakdown of the $1,200, so you can see which part is fees." |
| Says that if she disputes in writing within the validation period (30 days after she receives the notice), the collector must stop collecting the disputed amount until it sends verification | PRESENT | Reply says "If you dispute in writing before that date, the collector must stop collecting the disputed amount until it sends proof," with the period being 30 days after receipt. |
| Says the credit bureau generally has 30 days to investigate a dispute of the collection entry | ABSENT | Reply suggests disputing with the credit bureaus but gives no investigation timeframe. |
| Uses her profile: the Store card is open and current, with an on-time payment on 2026-10-01 | PRESENT | Reply says "Your profile shows you paid the store card on time on October 1." |
| Suggests autopay or reminders for at least the minimum payment on the Store card | PRESENT | Reply says "Set up autopay for at least the minimum payment" and add a calendar reminder. |

**Judge reason.** F3 is absent because the reply never mentions the bureau's roughly 30-day investigation window; all other facts are present.
