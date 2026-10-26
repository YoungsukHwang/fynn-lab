# Regression report

**After passes 69 of 72; before passes 43 of 72.**
Paired test of the net change (exact run-permutation test; 11 of 24 cases had runs that disagreed): mean pass-fraction change +36.1 pts, p < 0.001, significant (improvement) at 0.05. Persona bootstrap 95% interval [+27.8 pts, +45.8 pts] over 6 personas (descriptive only). Counting cases instead of runs (sign test): 9 better, 1 worse, p = 0.021.

## Pass rates

| Dataset | Cases | Baseline | Candidate | Change |
|---|---|---|---|---|
| single_topic | 6 | 16 (89%) | 15 (83%) | -6 pts |
| multi_intent | 12 | 9 (25%) | 36 (100%) | +75 pts |
| context_use | 6 | 18 (100%) | 18 (100%) | +0 pts |
| **overall** | 24 | 43 (60%) | 69 (96%) | |

Counts are passing runs; rates are the mean pass fraction per case.

## Failures overview

No case regressed.

## Details

**Verdict: Passed.** 0 regressed, 9 improved, 2 unstable.
A/A noise floor (single runs): about 1.3 of 24 cases flip between two single runs of the baseline with nothing changed (estimated from its 3 runs per case); 2 baseline cases passed some runs but not all. The flag rule needs a stable baseline, so far fewer cases are flagged by chance than this; for a like-for-like floor, rerun the baseline with the same --repeats and pass it with --aa.

## Runs

- Baseline: before (before, 2026-10-26T01:17:23+00:00)
- Candidate: after (after, 2026-10-26T01:17:19+00:00)
- Selection: no selection: the candidate ran every case it lists
- Cases compared: 24

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
| single_topic | 6 | 2 | 6 | -5.6 pts | -16.7 pts to +0.0 pts | 1.000 | 1.000 | 1.3 |
| multi_intent | 12 | 9 | 6 | +75.0 pts | +58.3 pts to +91.7 pts | <0.001 | <0.001 | 0 |
| context_use | 6 | 0 | 6 | +0.0 pts | +0.0 pts to +0.0 pts | 1.000 | 1.000 | 0 |
| **overall** | 24 | 11 | 6 | +36.1 pts | +27.8 pts to +45.8 pts | <0.001 | primary | 1.3 |

Unstable in the baseline: st-103, st-105.

## Routing and length

- Baseline: every labeled skill reached the answering agent in 33 of 72 runs (0 of 39 that need a second domain, 33 of 33 that do not). Replies: median 243.5 words, 28 of 72 over the 250-word limit.
- Candidate: every labeled skill reached the answering agent in 70 of 72 runs (37 of 39 that need a second domain, 33 of 33 that do not). Replies: median 265.0 words, 45 of 72 over the 250-word limit.

## Transitions

- Improved (9): mi-101, mi-103, mi-104, mi-105, mi-106, mi-108, mi-109, mi-110, mi-112
- Regressed (0): none
- Unchanged (pass) (13): st-101, st-102, st-104, st-106, mi-102, mi-107, mi-111, cu-101, cu-102, cu-103, cu-104, cu-105, cu-106
- Unchanged (fail) (0): none
- Unstable (not flagged: varied across runs, or too few runs that did not error) (2): st-103, st-105
