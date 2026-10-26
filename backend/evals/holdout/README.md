# Held-out cases

24 cases (6 single-topic, 12 multi-part, 6 about the member's own data; 13 need a second domain) for checking the Before vs After result on questions the skills were never tuned to.

## How they were written (2026-10-26)

- The skills were frozen first: `skills/` has not changed since commit `2bc9c79` (2026-10-23), and the bot code, settings and models match the main run (`results/after.json`, same setup and skill fingerprints).
- One drafting agent per synthetic member wrote four cases from the skills, the member's profile and `docs/products.md`, without access to any eval result, the skill-edit scenarios or the existing multi-part and member-data cases. The brief: realistic questions, and expected facts that matter most to the member, not facts chosen to trip up a one-domain agent.
- A second agent per member checked every fact against its quoted source, the skill labels against the questions, and each message against the existing 64 cases (no duplicates or close paraphrases).
- A final pass removed facts the message does not ask for (keeping disclosures the skills require), so a correct reply is not failed over an extra detail.
- The cases and this plan were committed before either bot ran on them. The skills will not change in response to the results.

## Plan

```bash
cd backend
.venv/bin/python -m evals.run --bot before --cases evals/holdout --repeats 3 --out ../results/holdout/before.json
.venv/bin/python -m evals.run --bot after --cases evals/holdout --repeats 3 --out ../results/holdout/after.json
.venv/bin/python -m evals.report --baseline ../results/holdout/before.json --candidate ../results/holdout/after.json --out ../results/reports/holdout
```

Expected (written before running):

1. On the held-out cases that need a second domain, After passes more runs than Before, by less than on the main set's designed cases (After 76% against Before 3% of runs) and closer to its other multi-domain cases (85% against 52%).
2. On the one-domain held-out cases, the two are within about 10 points of each other.
3. After passes a smaller share of held-out runs than of main-set runs (86%), since the skill edits were made by reading main-set failures.

Whatever the runs show is reported as it is, including where these expectations fail.
