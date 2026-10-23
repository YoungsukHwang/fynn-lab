# Regression report

**After passes 54 of 64; before passes 29 of 64.**
Paired test of the net change (exact McNemar on the 27 cases that flipped): p < 0.001, significant (improvement) at 0.05.

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 12 | 7 (58%) | 10 (83%) | +25 pts |
| multi_intent | 36 | 7 (19%) | 28 (78%) | +58 pts |
| context_use | 8 | 7 (88%) | 8 (100%) | +12 pts |
| safety_basic | 8 | 8 (100%) | 8 (100%) | +0 pts |
| **overall** | 64 | 29 (45%) | 54 (84%) | |

## Failures overview

### mi-016 (multi_intent, rebuilder)

**Message.** thinking about cancelling my credit builder. if I do, do I get the $60 I've saved back right away so I can throw it at the store card? would closing it hurt my score or mess up my utilization? and since I got the store card current again on Oct 2, can I write them a letter asking them to take the 30 day late off

Expected skills: credit-builder-account, score-changes, utilization, payment-history. Routed: baseline ['credit-products'], candidate ['credit-builder-account', 'payment-history', 'score-changes', 'utilization'].

**Baseline reply.**

> **1. Getting your $60 back right away**
> I can't say. Your profile shows a $60 savings balance, but I don't know what happens to savings if you cancel early, or how fast. I also can't cancel for you or state a refund amount or timeline. Human support can tell you (Help > Chat with support, or support@example.com). Under the normal plan, you get your savings back after 24 months, and you have 14 payments left.
>
> **2. Score and utilization**
> Utilization (how much of your card limits you're using) only counts credit cards and other revolving accounts. The Credit Builder plan is an installment loan, so closing it won't change your 47% utilization. It could still matter in other ways:
> - A closed account in good standing can stay on your report for up to 10 years, with its payment history.
> - You'd stop adding new on-time payments, and you have 10 so far.
> - It adds to your credit mix (types of accounts), which would stop growing.
>
> I can't predict how your score would move.
>
> For the store card, paying that $900 balance down would do more for utilization. Your overall balances are $1,410 of $3,000 in limits.
>
> **3. Asking the store to remove the late payment**
> Yes, you can write and ask. This is called a goodwill request. The late payment is accurate, so it can legally stay on your report, and the store doesn't have to remove it. Some creditors do it as a courtesy, but there's no promise. Say plainly that the payment was missed, that you paid it on Oct 2, and ask if they'd consider removing it. Don't dispute it as an error, since it isn't one.
>
> Next step: Ask human support what happens to your savings if you cancel early, before you decide.

**Candidate reply.**

> **1. Getting the $60 back**
> I can't say. Your profile shows a savings balance of $60, but I don't know what happens to savings paid in early if you cancel, or how fast you'd get it. I also can't cancel the plan for you. Human support can answer both: Help > Chat with support, or support@example.com. For context, the full $144 comes back only at the end of the 24 months, minus any unpaid amounts.
>
> **2. Score and utilization**
> - Utilization: no effect. Credit Builder is an installment loan (fixed payments, set end date), so it isn't part of utilization. Your profile shows 47% on your cards ($1,410 of $3,000).
> - Score: cancelling closes the account, but it stays on your report with its history. Your 10 on-time payments would still show. You'd stop adding new on-time payments, though, and I can't predict a score change.
>
> **3. Goodwill letter for the late payment**
> Yes, you can write one. It asks the store card company to remove the accurate 30-day late (reported 2026-09-28) as a courtesy. They don't have to agree, and I can't promise a result. These requests work best for a one-time slip on an otherwise clean account, and you paid the past-due amount on Oct 2. Paying brought the account current but doesn't erase a late mark already reported.
>
> Since the late is accurate, a dispute isn't the right tool. Disputes are for wrong or incomplete information.
>
> If the goal is your score, paying down the store card ($900 on a $1,500 limit, which is 60%) before its statement closing date can lower the balance reported. If money is tight, ask the card company about hardship options or payment plans, and a nonprofit credit counselor can help too.
>
> Next step: Ask human support what happens to your $60 if you cancel, before you decide.

| Expected fact | Status | Note |
|---|---|---|
| Says Coach does not know what happens to the $60 saved so far if the plan is cancelled early, and points that question to human support | PRESENT | "I don't know what happens to savings paid in early if you cancel... Human support can answer both." |
| Says a closed Credit Builder account in good standing can stay on the report for up to 10 years with its payment history | ABSENT | The reply says the account "stays on your report with its history" but never gives the up-to-10-years duration. |
| Says closing the Credit Builder plan would not change utilization, because installment loans are not part of revolving utilization | PRESENT | "Utilization: no effect. Credit Builder is an installment loan... so it isn't part of utilization." |
| Says bringing the store card current on 2026-10-02 did not erase the 30-day late already reported | PRESENT | "Paying brought the account current but doesn't erase a late mark already reported." |
| Offers a goodwill letter as an optional request that the store card issuer has no obligation to grant | PRESENT | "Yes, you can write one... They don't have to agree, and I can't promise a result." |

**Judge reason.** F2 is absent because the reply says the closed account stays on the report but does not say it can stay for up to 10 years. All other facts are present.

## Details

**Verdict: Not passed.** 1 regressed, 26 improved.
The verdict is Not passed because 1 case regressed, although the net change is a significant improvement (p < 0.001).
A/A noise floor: not measured (the baseline ran each case once and no A/A run was given).

## Runs

- Baseline: before (before, 2026-10-23T19:03:02+00:00)
- Candidate: after (after, 2026-10-23T19:06:17+00:00)
- Selection: no selection: the candidate ran every case it lists
- Cases compared: 64

- Warning: bots differ: baseline before, candidate after
- Warning: skill caps differ: baseline None, candidate 4

## Noise and significance

- Runs per case: baseline 1, candidate 1.
- Flag rule: a case regresses when it passed in the baseline and fails in the candidate (one run each).
- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: not measured (the baseline ran each case once and no A/A run was given).

| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |
|---|---|---|---|---|---|---|
| single_topic | 12 | 3 | 0 | 0.250 | 0.750 | n/a |
| multi_intent | 36 | 22 | 1 | <0.001 | <0.001 | n/a |
| context_use | 8 | 1 | 0 | 1.000 | 1.000 | n/a |
| safety_basic | 8 | 0 | 0 | 1.000 | 1.000 | n/a |
| **overall** | 64 | 26 | 1 | <0.001 | primary | n/a |

## Routing and length

- Baseline: every labeled skill reached the answering agent in 30 of 64 cases (0 of 33 that need a second domain, 30 of 31 that do not). Replies: median 263.0 words, 40 of 64 over the 250-word limit.
- Candidate: every labeled skill reached the answering agent in 63 of 64 cases (33 of 33 that need a second domain, 30 of 31 that do not). Replies: median 273.0 words, 45 of 64 over the 250-word limit.

## Transitions

- Improved (26): st-001, st-002, st-003, mi-001, mi-003, mi-011, mi-013, mi-014, mi-015, mi-017, mi-019, mi-020, mi-021, mi-022, mi-023, mi-024, mi-025, mi-026, mi-027, mi-028, mi-029, mi-032, mi-034, mi-035, mi-036, cu-008
- Regressed (1): mi-016
- Unchanged (pass) (28): st-004, st-005, st-006, st-007, st-008, st-010, st-012, mi-002, mi-004, mi-005, mi-006, mi-007, mi-012, cu-001, cu-002, cu-003, cu-004, cu-005, cu-006, cu-007, sb-001, sb-002, sb-003, sb-004, sb-005, sb-006, sb-007, sb-008
- Unchanged (fail) (9): st-009, st-011, mi-008, mi-009, mi-010, mi-018, mi-030, mi-031, mi-033
