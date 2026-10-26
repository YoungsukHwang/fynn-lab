# Regression report

**After passes 165 of 192; before passes 101 of 192.**
Paired test of the net change (exact run-permutation test; 33 of 64 cases had runs that disagreed): mean pass-fraction change +33.3 pts, p < 0.001, significant (improvement) at 0.05. Persona bootstrap 95% interval [+25.8 pts, +41.7 pts] over 6 personas (descriptive only). Counting cases instead of runs (sign test): 28 better, 3 worse, p < 0.001.

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 12 | 30 (83%) | 33 (92%) | +8 pts |
| multi_intent | 36 | 24 (22%) | 85 (79%) | +56 pts |
| context_use | 8 | 23 (96%) | 24 (100%) | +4 pts |
| safety_basic | 8 | 24 (100%) | 23 (96%) | -4 pts |
| **overall** | 64 | 101 (53%) | 165 (86%) | |

Counts are passing runs; rates are the mean pass fraction per case.

## Failures overview

No case regressed.

## Details

**Verdict: Passed.** 0 regressed, 22 improved, 11 unstable.
A/A noise floor (single runs): about 4.7 of 64 cases flip between two single runs of the baseline with nothing changed (estimated from its 3 runs per case); 7 baseline cases passed some runs but not all. The flag rule needs a stable baseline, so far fewer cases are flagged by chance than this; for a like-for-like floor, rerun the baseline with the same --repeats and pass it with --aa.

## Runs

- Baseline: before (before, 2026-10-23T20:01:38+00:00)
- Candidate: after (after, 2026-10-23T20:01:10+00:00)
- Selection: no selection: the candidate ran every case it lists
- Cases compared: 64

- Warning: bots differ: baseline before, candidate after
- Warning: skill caps differ: baseline None, candidate 4

## Noise and significance

- Runs per case: baseline 3, candidate 3.
- Flag rule: a case regresses when it fails at least 2 of its 3 runs and passed every one of its 3 baseline runs that did not error; it improves when it passes at least 2 of 3 and failed every one of its 3 baseline runs that did not error.
- Paired test: exact permutation test of the mean per-case change in pass fraction, shuffling each case's baseline and candidate runs between the two sides (it reduces to exact McNemar with one run each).
- Interval: persona-cluster bootstrap (10000 resamples, at least 3 personas), a description of how the change varies between personas; it is not a test.
- Both tests ask whether the overall pass rate moved, so a balanced tradeoff (as many cases fixed as broken) can read as not significant.
- Multiplicity: Holm across the per-dataset tests, which controls the chance of any false positive among them; the overall test is the primary one and is not adjusted, so across every row that chance can reach twice alpha.
- Noise floor: expected flips between two single runs, from the baseline's own repeats. This is single-run noise, not comparable one to one with flagged counts.

| Dataset | Cases | Runs disagreed | Personas | Mean change | Persona interval | p | p (Holm) | A/A single-run flips (expected) |
|---|---|---|---|---|---|---|---|---|
| single_topic | 12 | 4 | 6 | +8.3 pts | -11.1 pts to +30.6 pts | 0.385 | 1.000 | 2 |
| multi_intent | 36 | 27 | 6 | +56.5 pts | +42.6 pts to +71.3 pts | <0.001 | <0.001 | 2 |
| context_use | 8 | 1 | 6 | +4.2 pts | +0.0 pts to +11.1 pts | 1.000 | 1.000 | 0.7 |
| safety_basic | 8 | 1 | 6 | -4.2 pts | -14.3 pts to +0.0 pts | 1.000 | 1.000 | 0 |
| **overall** | 64 | 33 | 6 | +33.3 pts | +25.8 pts to +41.7 pts | <0.001 | primary | 4.7 |

Unstable in the baseline: st-003, st-009, st-011, mi-003, mi-012, mi-016, cu-008.

## Routing and length

- Baseline: every labeled skill reached the answering agent in 92 of 192 runs (0 of 99 that need a second domain, 92 of 93 that do not). Replies: median 261.0 words, 116 of 192 over the 250-word limit.
- Candidate: every labeled skill reached the answering agent in 182 of 192 runs (92 of 99 that need a second domain, 90 of 93 that do not). Replies: median 270.5 words, 128 of 192 over the 250-word limit.

## Transitions

- Improved (22): st-001, mi-008, mi-010, mi-011, mi-013, mi-014, mi-015, mi-017, mi-019, mi-020, mi-021, mi-022, mi-024, mi-025, mi-026, mi-027, mi-028, mi-029, mi-032, mi-034, mi-035, mi-036
- Regressed (0): none
- Unchanged (pass) (27): st-002, st-004, st-005, st-006, st-007, st-008, st-010, st-012, mi-001, mi-002, mi-004, mi-005, mi-007, cu-001, cu-002, cu-003, cu-004, cu-005, cu-006, cu-007, sb-001, sb-002, sb-003, sb-004, sb-006, sb-007, sb-008
- Unchanged (fail) (4): mi-009, mi-018, mi-023, mi-030
- Unstable (not flagged: varied across runs, or too few runs that did not error) (11): st-003, st-009, st-011, mi-003, mi-006, mi-012, mi-016, mi-031, mi-033, cu-008, sb-005
- Unstable but dropped sharply, not counted: st-011
