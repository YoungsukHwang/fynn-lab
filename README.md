# Fynn Lab

An independent re-implementation of the architecture change described in Kikoff's engineering post ["Fynn at 100% scale"](https://about.kikoff.com/build/fynn-at-100-scale), with an eval loop that checks when the change helps and whether each skill edit is safe to ship.

It is a study project and is not affiliated with Kikoff. The products the bots talk about are fictional; see [docs/products.md](docs/products.md).

**Site:** [youngsukhwang.github.io/fynn-lab](https://youngsukhwang.github.io/fynn-lab/). It has the eval framework and results pages. Its Demo page chats with both bots through a hosted backend with a small daily allowance (see "Hosted backend" below). Recorded replies from the committed eval run are one click away, and the page switches to them when that backend is asleep or not set up.

- **Before:** the earlier design in the post, which the post calls its beta. A small model routes each message to exactly one domain expert agent, so a question that spans several domains gets only one domain's expertise.
- **After:** the skill design the post moved to. A small model selects the topic skills the message needs. One agent answers with those skills plus always-on skills (tone, response rules, guardrails).

Both bots read the same skill files, see the same member profile and use the same answer model. They differ only in routing and prompt composition.

**Fynn Lab additions, not from the post:** the After bot caps new skills at 4 per message (3 until the cap experiment below) and carries up to 2 of the previous turn's skills for one more turn; the products, personas and the four Before agents are this project's own.

## What it found

Before vs After and the answer models ran three times per case, on the skills shipped 2026-10-23.

- **After wins where a question needs a second domain, and only there.** On the 33 cases whose skills span two or more Before domains, After passes 78 of 99 runs and Before 16. A Before agent holds only one domain's skills: in none of those runs did its prompt hold every labeled skill, and After's did in 92 of 99. On the 31 cases one domain covers, the two are about even (85 and 87 of 93).
- **Most of that gap comes from cases built to show it.** 24 of the 33 multi-domain cases (`mi-013` to `mi-036`) were written for this comparison: every question beyond the Before router's likely pick was built around a fact only another domain's skill held. There Before passes 2 of 72 runs and After 55. Both Before passes are `mi-016`, whose fact a later skill edit (S4) copied into a skill the Before agent loads. On the other 9 multi-domain cases, which were not built around the Before domains, the gap is smaller but still there (14 and 23 of 27).
- **On real traffic the gain depends on the mix.** Nobody has measured how often members ask a question that needs a second domain. If 10% do, the expected gain is about 5 points using the 9 multi-domain cases not built for the comparison, or 8 using all 33; at 30% it is about 12 or 20. The total on this eval set (After 165 of 192 runs, Before 101; a mean gain of 33 points per case, p < 0.001 on a run-permutation test) reflects this set's mix, which leans on multi-domain cases by design, so it is not a forecast.
- **After costs about 9% less per reply.** $9.57 against $10.50 per 1,000 replies with Sonnet answering, router included, at list prices and assuming a warm prompt cache. Its prompt holds only the picked skills rather than a whole domain's. Answers run at low effort; latency was not recorded.
- **The same prompt does not always give the same result.** Two runs of the same bot disagree on 10% of cases with Sonnet or Opus answering and 27% with Haiku. The judge alone accounts for about 3%: grading the same replies again changed 6 of 192 verdicts. So a skill edit's flips are split into fixed or broken by the edit (the edit could reach the case) and chance (it could not).
- **Only one skill edit is backed by its test.** A body edit that put a missing fact into the skill the router already picks (S4) fixed 5 cases and broke none, and its net change is significant (p = 0.031). The test counts every flip, including one the reach rule calls chance; on the five reached cases alone it would give p = 0.0625. The routing fixes through skill descriptions (S3, S5, S6) and the cap of 4 fixed 1 to 3 cases each and broke none, but none of their net changes is significant, so they are leads: a case they reached may still have flipped by chance. They shipped as leads, and a rerun afterwards showed that together they closed the cases every model failed (next point). Shortening the always-on response rules (S2) broke 7 cases and fixed 1.
- **The shipped edits closed the cases every model failed.** Eight cases failed with Haiku, Sonnet and Opus answering, and seven of them were routing gaps no answer model can fix. With S3, S5, S6, the cap of 4 and three small skill-text fixes, they pass in 23 of 24 runs with Sonnet answering and 24 of 24 with Opus (Haiku: 15). In single runs against the previous After run the bundle fixed 12 cases and broke 7 (p = 0.36), so outside its targets the flips are hard to tell from noise. Two of the eight (`st-001`, `mi-003`) had an expected fact reworded in between, so that comparison leaves them out.
- **Answer model:** the After bot with each model, the same Opus judge. Haiku passed 129 of 192 runs (67%) at $0.82 per 1,000 replies, Sonnet 165 (86%) at $9.57, Opus 174 (91%) at $23.49. Sonnet against Opus is not significant (p = 0.10); Haiku is clearly behind both (p < 0.001). Nothing grades reply length, though the response rules ask for about 250 words, and the ranking depends on where a cap would sit: counting replies over 250 words as failures, Haiku passes the most runs (79, 58 and 50); over 300 words, Opus does (102, 137 and 161).
- **The judge:** Opus grading the same 192 replies again changed 6 verdicts; Sonnet and Haiku as judges each changed 17 and cost $0.50 and $0.04 per 64 replies, against $1.16 for Opus. Human labels on a blind sample are in progress.

| Edit | What changed | Decision |
|---|---|---|
| S1 | score-changes body: give per-card utilization on a score drop | Lead: tradeoff |
| S2 | response-rules: answers under 120 words instead of 250 | Lead: do not ship |
| S3 | utilization description: also route score-drop questions | Lead: ship (shipped) |
| S4 | credit-builder-account body: closed accounts can stay up to 10 years | Ship (shipped) |
| S5 | payment-history description: free reports, score recovery | Lead: ship (shipped) |
| S6 | score-changes description: how long closed accounts stay | Lead: ship (shipped) |
| Cap 4 | the After router may pick 4 new skills instead of 3 | Lead: ship (shipped) |

Skill-edit results are from one run per case. A decision is backed when the paired test of the net change is significant in its direction (a gain for Ship, a loss for Do not ship); otherwise it is a lead to read, not proof. A tradeoff is always a lead.

## Limitations

- **Single-turn only.** Every case is one message, so carrying skills between turns is not evaluated.
- **No held-out set.** The cases, the expected facts and the skill fixes were all written by one person looking at the same eval set, so the gap includes tuning. Before the shipped edits, a single run on 2026-10-22 gave After 42 and Before 31 of 64 (p = 0.019); a single run after them gave 54 and 29.
- **The judge is not yet checked against people.** One LLM judge (Opus) grades every reply; the human labels on a blind sample are not finished.
- **Synthetic setting.** Six fictional members, fictional products, and a Before domain split that is this project's own; a different split would change which cases need a second domain. No real members use the bots (the hosted demo is anonymous and rate-limited), so the Online evaluation page is a plan with no data.

## How it works

- **Eval set.** 64 single-message cases over 6 synthetic members, in four datasets: single-topic questions, multi-part questions (36, of which 32 need a second domain, 24 of them written for this comparison), use of the member's own data, and basic safety. Cases live in `backend/evals/cases/`; the written-for-the-comparison ones are marked `designed: true`.
- **Scoring.** A case passes only if both checks pass: code checks (for example no promised score gains, using the member's own figures) and an LLM judge (Opus) that looks for every expected fact in the reply.
- **Judge check.** `evals.judge_validation` draws a blind sample of graded replies for a person to label with the judge's own rules, regrades stored replies with other judge models, and reports how often each judge agrees with the person and with the original judge.
- **Before vs After.** Both bots answer every case; the report pairs the cases and tests the net change.
- **Skill edits.** A scenario in `scenarios/<id>/` holds an edited copy of one skill, laid over `skills/` for the run. Only the cases the edit can affect rerun: a body edit reruns the cases labeled with that skill or routed to it; a description edit, an always-on edit or a cap change reruns all. The report then counts a flip for the edit only when the edit could reach that case's prompt:
  - a body edit, when the edited skill was loaded on both sides (when only one side loaded it, the router changed the prompt too);
  - a description edit, when the edited skill entered or left the case's routing (a reordering alone does not count);
  - a cap change, when the routing changed and the cap mattered: the run with the lower cap filled it, or the run with the higher cap went past it;
  - an always-on edit, always.

  When the two runs also differ in skill cap, a body or description edit also reaches the cases where the cap mattered. With the Before bot, the edited skill's domain stands in for the skill. Descriptions and the cap are also in the router's instructions, so these rules assume such an edit acts only through the skills it adds or removes. A decision (ship, do not ship) is backed when the paired test of the net change is significant in its direction, and is a lead otherwise.
- **Answer model and judge.** The After bot is run with each answer model (Haiku, Sonnet, Opus 5.5) and the stored replies are regraded by other judge models; `evals.models_report` sums up cost, cases passed, reply length and judge agreement. Every report also says whether each case's answering agent had every labeled skill and how long the replies are (`evals/quality.py`).
- **Online evaluation.** The site has a framework page for evaluating the bots on real traffic: metrics, A/B tests, and causal inference when a change cannot be randomized. It has no data.

The detailed design notes are in [SPEC.md](SPEC.md), which is written in Korean.

## Running the evals

The runner calls the Anthropic API for the routers, the answer model and the judge, so it needs `ANTHROPIC_API_KEY` in `backend/.env`. The tests never call the API. Run the commands from `backend/`; results go to `results/` at the repo root. The runner overwrites `--out`, so move a results file a committed report still compares to `results/archive/` first.

```bash
cd backend

# Both bots on every case, three runs each (how results/before.json and after.json were made)
.venv/bin/python -m evals.run --bot before --repeats 3 --out ../results/before.json
.venv/bin/python -m evals.run --bot after --repeats 3 --out ../results/after.json

# A skill edit on the After bot; --baseline picks the cases it can affect. A shipped scenario no longer runs.
.venv/bin/python -m evals.run --bot after --scenario s1 --baseline ../results/after.json --out ../results/scenarios/s1-new.json

# The After bot with another skill cap (the default is 4 since the cap experiment); every case reruns
.venv/bin/python -m evals.run --bot after --max-skills 5 --baseline ../results/after.json --out ../results/cap5.json

# Reports: report.json (for the site) and report.md. A report refuses to replace one of other runs,
# or to use a baseline that does not fit the scenario, without --force.
.venv/bin/python -m evals.report --baseline ../results/before.json --candidate ../results/after.json --out ../results/reports/before-vs-after
.venv/bin/python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s1-new.json --out ../results/reports/s1-new

# After a fatal API error (a bad key, no credit) the run stops and writes <out>.partial.json; rerun only what errored
.venv/bin/python -m evals.run --bot after --repeats 3 --rerun-errors ../results/after.partial.json --out ../results/after.json

# The After bot with Haiku and with Opus answering, three runs each
FYNN_AGENT_MODEL=claude-haiku-5-5 .venv/bin/python -m evals.run --bot after --repeats 3 --out ../results/models/k3/after-haiku.json
FYNN_AGENT_MODEL=claude-opus-5-5 .venv/bin/python -m evals.run --bot after --repeats 3 --out ../results/models/k3/after-opus.json

# The answer model and judge report (no API). The regrades graded earlier single runs, passed with --regraded-runs.
.venv/bin/python -m evals.models_report --runs ../results/models/k3/after-haiku.json ../results/after.json \
  ../results/models/k3/after-opus.json --regraded-runs ../results/models/after-*.json \
  --regrades ../results/validation/regrades --out ../results/reports/models

# Judge check: draw a blind sample to label and its page (no API), regrade stored replies with another judge
# model (API), then compare (no API). A sample file is not overwritten without --force.
.venv/bin/python -m evals.judge_validation sample --runs ../results/models/after-*.json \
  --include after-sonnet:mi-023 --out ../results/validation/sample-new.json
.venv/bin/python -m evals.judge_validation page --sample ../results/validation/sample.json \
  --translations ../results/validation/translations.ko.json --out judge-check.html
.venv/bin/python -m evals.judge_validation regrade --results ../results/models/after-sonnet.json \
  --judge-model claude-sonnet-5-5 --out ../results/validation/regrades/sonnet-on-after-sonnet.json
# --labels is optional; without it, or before the file exists, the report has only the judge-to-judge comparison
.venv/bin/python -m evals.judge_validation agreement --sample ../results/validation/sample.json \
  --labels ../results/validation/human-labels.json --regrades ../results/validation/regrades \
  --runs ../results/models/after-*.json --out ../results/validation/agreement
```

### Reproduce the committed reports

The reports need no API. Each skill edit compares the After run its scenario was run against, which has since moved to `results/archive/`. Rerunning a scenario itself needs the commit it was run at (`ac8ccae` for S1 to S3, `f303797` for S4 to S6 and the cap), since S3 to S6 have shipped and the skills have changed.

```bash
cd backend
.venv/bin/python -m evals.report --baseline ../results/before.json --candidate ../results/after.json --out ../results/reports/before-vs-after
.venv/bin/python -m evals.report --baseline ../results/archive/after-2026-10-22T17-15-15.json --candidate ../results/cap4.json --out ../results/reports/cap4
for s in s1 s2 s3; do
  .venv/bin/python -m evals.report --baseline ../results/archive/after-2026-10-22T01-19-16.json \
    --candidate ../results/scenarios/$s.json --out ../results/reports/$s
done
for s in s4 s5 s6; do
  .venv/bin/python -m evals.report --baseline ../results/archive/after-2026-10-22T17-15-15.json \
    --candidate ../results/scenarios/$s.json --out ../results/reports/$s
done
```

- **Models report:** the `evals.models_report` command above.
- **Bundle comparison** (12 fixed, 7 broken): `--baseline ../results/models/after-sonnet.json --candidate ../results/archive/after-2026-10-23T19-06-17.json`, the single runs before and after the shipped edits.
- **Judge sample:** the committed `results/validation/sample.json` (seed 0, `sample_id` 524a504be8710b63) comes out of the `sample` command at commit `53832be`, with the arguments it records in `args`: the three `results/models/after-*.json` runs and one `--include` for each of the eight targeted replies. The facts of `st-001` were reworded since, so at later commits that command refuses the `st-001` includes.

### Notes

- **Cost.** One run of the 64 cases cost about $1.70 to $1.85 per bot at list prices with Sonnet answering and Opus judging, as recorded in the committed results; the judge is about two thirds of it. Three runs per case cost three times as much (Before $5.54, After $5.18). Each case's result records the router's, the answering model's and the judge's tokens apart (`routing.usage`, `usage`, `judge.usage`); older results files add the router's tokens to the answer's. The billing console is the final word, and the runner does not ask before spending.
- **Safety nets.** Results record fingerprints of the skills, the bot and judge code, and the settings, so a run against a baseline reruns every case when any of those or the models changed. A report leaves out cases whose expected facts were reworded between the two runs.
- **More statistics.** `backend/evals/stats.py` handles repeated runs: `--repeats K` gives a stricter flag rule and the run-permutation test, which the site uses for Before vs After and the answer models. Its A/A noise floor and Holm correction appear only in the report Markdown. In simulations of the original 40-case set where nothing changed, the test calls about 3% of comparisons significant at 0.05; when eight cases truly drop, it catches the drop in roughly 75% to 95% of simulations with three runs per case, against 20% to 30% with one. See SPEC.md.

## Layout

```
skills/      skill files (Markdown + YAML frontmatter), shared by both bots
personas/    synthetic member profiles (JSON, no real data)
scenarios/   skill-edit scenarios: an edited copy of one skill and what it should do
results/     committed eval results and reports (archive/ holds runs a report still compares)
docs/        product fact sheet for the fictional app
backend/     Python: fynn core package, FastAPI app, eval runner and reports, tests
web/         Next.js site: the demo and the eval pages
```

## Backend

Requires Python 3.12 or newer.

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env        # then add your ANTHROPIC_API_KEY

.venv/bin/python -m pytest                                  # tests use a fake LLM, no key needed
.venv/bin/python -m fynn.chat --persona rebuilder           # chat with both bots in the terminal

# HTTP API for the demo site. The extra flags also reload when skills or personas change.
.venv/bin/uvicorn api.main:app --port 8000 --reload --reload-dir . --reload-dir ../skills \
  --reload-dir ../personas --reload-include '*.md' --reload-include '*.json'
```

Settings in `backend/.env` are loaded before anything else, and variables exported in your shell take precedence over them. The skill caps are in `backend/fynn/config.py`; `evals.run --max-skills N` overrides the new-skill cap for one run.

| Role | Model |
|---|---|
| Routers (both bots) | `claude-haiku-5-5` |
| Answering agent | `claude-sonnet-5-5`, low effort |
| Eval judge | `claude-opus-5-5` |

You can override each model with an environment variable; see `backend/.env.example`.

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Takes `{bot, persona_id, messages, carry_skills?}`. Returns the reply, the model, the routing decision and token usage. Errors come back as JSON `{detail, retryable}`. |
| `GET /personas` | Synthetic member profiles |
| `GET /architecture` | Domains, skills, models, skill budgets and request limits, for the site's diagrams |

`FYNN_CHAT_LIMIT_PER_VISITOR_PER_HOUR` and `FYNN_CHAT_LIMIT_PER_DAY` cap `/chat` requests for a public demo (`api/limits.py`); they are unset locally, so there is no limit. A refused request gets a 429 with `Retry-After`. The counts live in memory and reset when the server restarts.

### Hosted backend

The public demo's backend runs as a Hugging Face Docker Space. `.github/workflows/space.yml` assembles it from `space/` (Dockerfile and Space README), `backend/`, `skills/` and `personas/`, and pushes it to the Space on every push to `main` that touches them. The Space allows 20 chat requests per visitor per hour and 400 a day in all (10 and 200 questions to both bots, at most about $4 to $5 a day with Sonnet answering), and only the GitHub Pages origin. The free Space sleeps after two days without visitors; the site then shows recorded replies until it wakes.

One-time setup:

1. Create a Docker Space on Hugging Face (blank template, free CPU, public), for example `fynn-lab-api`.
2. In the Space's settings, add the secret `ANTHROPIC_API_KEY`. A key used only for this demo, with a monthly spend limit set in the Anthropic Console, is the backstop if the in-memory limits reset.
3. Create a Hugging Face access token that can write to the Space.
4. In this GitHub repo's Actions settings, add the secret `HF_TOKEN` (that token) and the variables `HF_SPACE` (for example `<hf-user>/fynn-lab-api`) and `FYNN_API_URL` (the Space's address, `https://<hf-user>-fynn-lab-api.hf.space`).
5. Run the "Deploy API" workflow, then "Deploy site", so the site is rebuilt with the API address.

## Web

Requires Node.js 20.9 or newer. The demo needs the backend on port 8000, and chatting needs `ANTHROPIC_API_KEY` in `backend/.env`.

```bash
cd web
npm install
npm run dev                 # http://localhost:3000
```

- **Demo** (`/`): pick a synthetic member and send one message to both bots; each column shows the reply, the router's decision and the skills used.
- **Before vs After** and **Skill edits**: each has a Framework tab (how it is measured) and a Results tab (what was found), built from the committed results and reports.
- **Models**: the answer-model comparison (cost against cases passed, reply length) and the judge check.
- **Online evaluation**: a framework page for evaluating the bots on real traffic.
- `NEXT_PUBLIC_API_URL` points the site at another backend (read at build time); `FYNN_CORS_ORIGINS` in `backend/.env` allows other origins. In `npm run dev`, reload a page to pick up new results files.
- **Static site.** `FYNN_STATIC_SITE=1 FYNN_BASE_PATH=/fynn-lab npm run build` writes plain files to `web/out/`; `.github/workflows/pages.yml` does this on every push to `main` and publishes to GitHub Pages, with `NEXT_PUBLIC_API_URL` from the repository variable `FYNN_API_URL`. Its Demo page also offers recorded replies, and switches to them when the backend does not answer within 15 seconds; with no API address it shows only those. They are `results/demo/recorded.json`, which `.venv/bin/python -m evals.demo_snapshot --before ../results/before.json --after ../results/after.json --out ../results/demo/recorded.json` (from `backend/`, no API) rebuilds from the committed runs.
- **Checks.** `npm run typecheck` and `npm run lint`.
