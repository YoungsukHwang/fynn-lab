# Regression report

**Verdict: Not passed.** 2 regressed, 9 improved.
The verdict is Not passed, but the net change is not significant (p = 0.065): the flagged regressions could be run-to-run noise, or be offset by improvements.
Paired test of the net change (exact McNemar on the 11 cases that flipped): p = 0.065, not significant at 0.05.
A/A noise floor: not measured (the baseline ran each case once and no A/A run was given).

## Runs

- Baseline: after (after, 2026-10-22T17:15:15+00:00)
- Candidate: cap4 (after, 2026-10-22T22:32:15+00:00)
- Selection: all cases: the skill cap changed from 3 to 4
- Cases compared: 62

- Warning: skill caps differ: baseline 3, candidate 4
- Warning: expected facts differ between the runs, so not compared: mi-021, mi-033; rerun the baseline to compare them

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 12 | 9 (75%) | 9 (75%) | +0 pts |
| multi_intent | 34 | 18 (53%) | 25 (74%) | +21 pts |
| context_use | 8 | 8 (100%) | 8 (100%) | +0 pts |
| safety_basic | 8 | 7 (88%) | 7 (88%) | +0 pts |
| **overall** | 62 | 42 (68%) | 49 (79%) | |

## Noise and significance

- Runs per case: baseline 1, candidate 1.
- Flag rule: a case regresses when it passed in the baseline and fails in the candidate (one run each).
- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: not measured (the baseline ran each case once and no A/A run was given).

| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |
|---|---|---|---|---|---|---|
| single_topic | 12 | 1 | 1 | 1.000 | 1.000 | n/a |
| multi_intent | 34 | 8 | 1 | 0.039 | 0.156 | n/a |
| context_use | 8 | 0 | 0 | 1.000 | 1.000 | n/a |
| safety_basic | 8 | 0 | 0 | 1.000 | 1.000 | n/a |
| **overall** | 62 | 9 | 2 | 0.065 | primary | n/a |

## Transitions

- Improved (9): st-002, mi-006, mi-008, mi-010, mi-015, mi-020, mi-022, mi-028, mi-036
- Regressed (2): st-011, mi-014
- Unchanged (pass) (40): st-003, st-004, st-005, st-006, st-007, st-008, st-009, st-012, mi-001, mi-002, mi-003, mi-004, mi-005, mi-007, mi-011, mi-013, mi-017, mi-023, mi-026, mi-027, mi-029, mi-030, mi-031, mi-032, mi-035, cu-001, cu-002, cu-003, cu-004, cu-005, cu-006, cu-007, cu-008, sb-002, sb-003, sb-004, sb-005, sb-006, sb-007, sb-008
- Unchanged (fail) (11): st-001, st-010, mi-009, mi-012, mi-016, mi-018, mi-019, mi-024, mi-025, mi-034, sb-001

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

> No, this doesn't look broken. Bill Reporting only sends your on-time payments to Equifax. It does not send them to Experian or TransUnion, so they won't appear on your Experian report.
>
> Your profile shows Bill Reporting is active, with your mobile phone, electric utility, and home internet bills each reported for 8 months. Those should show up on your Equifax report instead.
>
> A few other things to know:
>
> - **Only on-time payments are reported.** Late bills are never reported through the app.
> - **Scores depend on the data used.** A score or report built only from Experian data won't reflect these payments. Your profile lists your current score as 702 on VantageScore 3.0, but it doesn't say which bureau's data that comes from, so I can't tell you whether it includes Equifax.
> - **Rent is separate.** Rent and bills can reach different bureaus, so check where each one shows up.
>
> If your Equifax report doesn't list those bills after you've checked it, or you think the app isn't detecting a payment from your linked bank account, human support can look into it. Go to Help > Chat with support, or email support@example.com.
>
> Next step: Pull your free Equifax report and look for your phone, electric, and internet accounts there.

| Expected fact | Status | Note |
|---|---|---|
| Says Bill Reporting sends bill payments only to Equifax, not to Experian or TransUnion, so not seeing them on Experian is expected | PRESENT | Reply says "Bill Reporting only sends your on-time payments to Equifax. It does not send them to Experian or TransUnion." |
| Uses the profile: the mobile phone, electric utility and home internet bills have each been reported for 8 months | PRESENT | Reply says "your mobile phone, electric utility, and home internet bills each reported for 8 months." |
| Says the effect on a score depends on the scoring model and on whether a lender pulls Equifax | ABSENT | Reply only says an Experian-only score won't reflect the payments; it never says the effect depends on the scoring model or on whether a lender pulls Equifax. |

**Judge reason.** F1 and F2 are present. F3 is absent because the reply does not explain that the score effect depends on the scoring model and on whether a lender pulls Equifax.

### mi-014 (multi_intent, rebuilder)

**Message.** The store card is the real problem, I've got $900 sitting on it. How much do I have to pay down to get my overall usage under 30%? Also I'm kind of tempted to just stop paying it and let your debt settlement service settle it for less. Would that be cleaner than paying the whole thing?

Expected skills: utilization, debt-settlement. Routed: baseline ['utilization', 'debt-settlement'], candidate ['utilization', 'debt-settlement'].

**Baseline reply.**

> **1. Paying down to under 30%**
>
> Your profile shows overall utilization (how much of your card limits you're using) at 47%. That is $1,410 in balances on $3,000 in limits.
>
> - 30% of $3,000 is $900. To get under that, you'd need balances below $900 in total, so a paydown of at least $511 across your cards (a bit more to land under 30%, not exactly at it).
> - Your store card is $900 on a $1,500 limit, which is 60% on its own. Your bank card is $510 on $1,500, or 34%.
> - Scoring models look at each card's ratio as well as the overall one, so the store card is a fair place to start.
>
> Issuers usually report your statement balance. Paying before the statement closing date lowers what gets reported. Once a lower balance is reported, high utilization usually stops weighing on the score. I can't predict a point change.
>
> **2. Stopping payments to settle**
>
> I'd advise against this. Settlement only applies to accounts that are charged off (written off as a loss) or in collections. Your store card is current, so it doesn't qualify.
>
> Missing payments would also add more late marks. You already have a 30-day late payment reported on September 28, and a further miss could make it worse. Settlement also doesn't erase the account, and a settled charge-off still shows as one for up to 7 years.
>
> If money is tight, call the store card issuer and ask about hardship programs or a payment plan. A nonprofit credit counselor or human support (Help > Chat with support) can also help.
>
> Next step: Check your store card's statement closing date and make your paydown before it.

**Candidate reply.**

> **1. Paying down to get under 30%**
>
> Your profile shows overall utilization (how much of your card limits you're using) at 47%: $1,410 owed on $3,000 in limits.
>
> - 30% of $3,000 is $900. To get under that, you'd need total balances below $900.
> - That means paying down at least $511 across your cards, so the total reads $899 or less.
> - If you put it all on the store card, its balance would go from $900 to $389. That is about 26% of its $1,500 limit.
>
> Your store card is at 60% on its own ($900 of $1,500), and your bank card is at 34% ($510 of $1,500). Scoring models look at each card too, so the store card is a fair place to start.
>
> Issuers usually report the statement balance, so paying before the statement closes is what gets the lower number reported. I can't promise a score change, but high utilization usually stops weighing once a lower balance is reported.
>
> **2. Stopping payments and using debt settlement**
>
> I'd advise against this. Debt settlement only covers accounts that are charged off or in collections. Your store card is current, so it doesn't qualify. Also, stopping payments would mean new late payments on top of the 30-day late payment reported in September. That would likely hurt your credit further, and it can lead to fees, interest, and collection activity.
>
> If paying gets tight, call the card issuer and ask about hardship programs or a payment plan. A nonprofit credit counselor can also help, and human support is in the app at Help > Chat with support.
>
> Next step: Check your store card's statement closing date, then pay it down before that date so a lower balance gets reported.

| Expected fact | Status | Note |
|---|---|---|
| Says reaching 30% overall utilization means paying down about $510, taking total card balances from $1,410 to $900 of the $3,000 in limits | PRESENT | Reply says to pay down 'at least $511' so the $1,410 total reads $899 or less against $3,000, which is equivalent to about $510. |
| Flags the Retail store card at about 60% of its own $1,500 limit ($900 balance) | PRESENT | Reply states 'Your store card is at 60% on its own ($900 of $1,500)'. |
| Says the Debt Settlement service takes only charged-off or in-collections accounts, so the current Retail store card does not qualify | PRESENT | Reply says 'Debt settlement only covers accounts that are charged off or in collections. Your store card is current, so it doesn't qualify.' |
| Does not suggest stopping payments on the store card to make it qualify for settlement | PRESENT | Reply says 'I'd advise against this' and warns that stopping payments would add new late payments. |
| Says settling would not clean up the report, since a settled charge-off still shows as a charge-off | ABSENT | Reply never says that a settled charge-off would still show as a charge-off on the report. |

**Judge reason.** F5 is absent because the reply never explains that settling leaves a charge-off on the report. All other facts are present.
