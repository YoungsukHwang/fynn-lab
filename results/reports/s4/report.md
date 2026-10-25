# Regression report: s4 (Closed-account reporting time in the Credit Builder skill)

**Decision: Ship.** The change fixed 5 cases and broke none; 1 other case flipped outside its reach and counts as chance.
Paired test of the net change (exact McNemar on the 6 cases that flipped): p = 0.031, significant (improvement) at 0.05.

## What changed

- Fixed by the change (5): mi-008, mi-012, mi-016, mi-019, mi-034
- Broken by the change (0): none
- Flipped by chance (1 up, 0 down): mi-022
- How: a body edit can reach a case only when the edited skill (for the Before bot, its domain) is loaded on both sides. A flip outside that counts as chance: the edit was not in that case's answering prompt, or was not the only thing that changed it. A flip inside it may still be chance.

## Scenario

- Skill: `credit-builder-account` (body change)
- Change: Replaces the pointer "(how long: see score-changes)" in credit-builder-account with the line itself: a closed account in good standing can stay on the report for up to 10 years.
- Motivation: In the 2026-10-22 run of 64 cases, three After failures (mi-016, mi-019, mi-034) asked whether a closed or finished Credit Builder account stays on the report. The answer lives only in the score-changes body. The router reasonably picked credit-builder-account, which only pointed to score-changes, so the agent could not state the 10 years. This fixes the gap in the skill the router already picks.
- Hypothesis (improve): Only the body changed, so only cases labeled credit-builder-account or routed to it in the baseline rerun. The cases that ask whether a closed or finished Credit Builder account stays on the report (mi-016, mi-019, mi-034) should now state the 10-year rule, so some of them improve. The new line adds no instruction, so other Credit Builder cases should hold. Expected verdict: no regressions, safe to ship.

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 2 | 2 (100%) | 2 (100%) | +0 pts |
| multi_intent | 13 | 5 (38%) | 11 (85%) | +46 pts |
| context_use | 2 | 2 (100%) | 2 (100%) | +0 pts |
| **overall** | 17 | 9 (53%) | 15 (88%) | |

## Failures overview

No case regressed.

## Details

**Verdict: Passed.** 0 regressed, 6 improved.
A/A noise floor: not measured (the baseline ran each case once and no A/A run was given).
Hypothesis: expected improve, observed improve (matches; from the flagged counts, not a significance test).

## Runs

- Baseline: after (after, 2026-10-22T17:15:15+00:00)
- Candidate: s4 (after, 2026-10-22T18:10:11+00:00)
- Selection: body of topic skill credit-builder-account changed: cases labeled with it or routed to it in the baseline (18 of 64)
- Cases compared: 17

- Warning: expected facts differ between the runs, so not compared: mi-021; rerun the baseline to compare them

## Noise and significance

- Runs per case: baseline 1, candidate 1.
- Flag rule: a case regresses when it passed in the baseline and fails in the candidate (one run each).
- Paired test: exact McNemar (binomial test of the cases that flipped, against a 50/50 split).
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: not measured (the baseline ran each case once and no A/A run was given).

| Dataset | Cases | Improved | Regressed | p | p (Holm) | A/A noise floor |
|---|---|---|---|---|---|---|
| single_topic | 2 | 0 | 0 | 1.000 | 1.000 | n/a |
| multi_intent | 13 | 6 | 0 | 0.031 | 0.094 | n/a |
| context_use | 2 | 0 | 0 | 1.000 | 1.000 | n/a |
| **overall** | 17 | 6 | 0 | 0.031 | primary | n/a |

## Routing and length

- Baseline: every labeled skill reached the answering agent in 11 of 17 cases (5 of 11 that need a second domain, 6 of 6 that do not). Replies: median 269 words, 10 of 17 over the 250-word limit.
- Candidate: every labeled skill reached the answering agent in 12 of 17 cases (6 of 11 that need a second domain, 6 of 6 that do not). Replies: median 254 words, 9 of 17 over the 250-word limit.

## Transitions

- Improved (6): mi-008, mi-012, mi-016, mi-019, mi-022, mi-034
- Regressed (0): none
- Unchanged (pass) (9): st-003, st-008, mi-004, mi-007, mi-017, mi-026, mi-032, cu-002, cu-007
- Unchanged (fail) (2): mi-018, mi-024
