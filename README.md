# Fynn Lab

An independent re-implementation of the architecture change described in Kikoff's engineering post ["Fynn at 100% scale"](https://about.kikoff.com/build/fynn-at-100-scale), with an eval loop that checks when the change helps and whether each skill edit is safe to ship.

It is a study project and is not affiliated with Kikoff. The products the bots talk about are fictional; see [docs/products.md](docs/products.md).

- **Before:** the earlier design in the post, which the post calls its beta. A small model routes each message to exactly one domain expert agent, so a question that spans several domains gets only one domain's expertise.
- **After:** the skill design the post moved to. A small model selects the topic skills the message needs. One agent answers with those skills plus always-on skills (tone, response rules, guardrails).

Both bots read the same skill files, see the same member profile and use the same answer model. They differ only in routing and prompt composition.

**Fynn Lab additions, not from the post:** the After bot caps new skills at 4 per message (3 until the cap experiment below) and carries up to 2 of the previous turn's skills for one more turn; the products, personas and the four Before agents are this project's own.

## What it found

- **After wins where a question needs a second domain.** On the 33 eval cases whose skills span two or more Before domains, After passes 25 and Before 4: a Before agent holds only one domain's skills, and in none of those cases did its prompt have every labeled skill (After's had them in all 33). On the 31 cases that fit in one domain the gap is much smaller (29 against 25). Overall After passes 54 of 64 and Before 29 (exact McNemar test on the 27 cases that flipped, p < 0.001). The overall rate depends on how many multi-domain questions the set holds, so the per-group rates are the comparison. These are the 2026-10-23 runs, after S3, S5, S6 and the cap of 4 shipped; the 10-22 runs gave 42 against 31.
- **The shipped edits closed the cases every model failed.** Eight cases failed with Haiku, Sonnet and Opus answering, and seven of them were routing gaps no answer model can fix. With S3, S5, S6, the cap of 4 and three small skill-text fixes, all eight pass. Against the previous After run the bundle fixed 12 cases and broke 7 (p = 0.36), so outside its targets the flips are hard to tell from noise.
- **The same prompt does not always give the same result.** In cases where an edit left the prompt unchanged, about one in eight flipped between runs. So a skill edit's flips are split into fixed or broken by the edit (the edit could reach the case) and chance (it could not).
- **Skill edits:** a body edit that put a missing fact into the skill the router already picks (S4) fixed its targets and broke nothing, and shipped. Routing fixes through skill descriptions (S3, S5, S6) and a higher skill cap also fixed their targets, though less reliably, and shipped on 2026-10-23. Shortening the always-on response rules (S2) broke more than it fixed.
- **Answer model:** with the After bot as it was before the 10-23 edits shipped (cap of 3), and the same Opus judge, Sonnet passed 47 cases and Opus 46 (not distinguishable, p = 1.0) at about $9.50 against $22 per 1,000 conversations; Haiku cost $0.81 and passed 34 (p = 0.007 against Sonnet). The ranking also leans on a rule nothing grades: if replies over the response rules' length counted (over 300 words fails), Sonnet's lead over Haiku would not be significant (p = 0.14) and Opus would lead Sonnet 41 to 37 (p = 0.42).
- **The judge:** grading the same 192 replies again, Opus changed 6 verdicts (3%), so most run-to-run flips come from the answers. Sonnet and Haiku as judges each changed 17. Human labels on a blind sample are in progress.

| Edit | What changed | Decision |
|---|---|---|
| S1 | score-changes body: give per-card utilization on a score drop | Tradeoff |
| S2 | response-rules: answers under 120 words instead of 250 | Do not ship |
| S3 | utilization description: also route score-drop questions | Ship (shipped) |
| S4 | credit-builder-account body: closed accounts can stay up to 10 years | Ship (shipped) |
| S5 | payment-history description: free reports, score recovery | Ship (shipped) |
| S6 | score-changes description: how long closed accounts stay | Ship (shipped) |
| Cap 4 | the After router may pick 4 new skills instead of 3 | Ship (shipped) |

Every result is from one run per case. A decision is a lead to read: a case an edit could reach may still have flipped by chance.

## How it works

- **Eval set.** 64 single-message cases over 6 synthetic members, in four datasets: single-topic questions, multi-part questions (36, of which 32 need a second domain), use of the member's own data, and basic safety. Cases live in `backend/evals/cases/`.
- **Scoring.** A case passes only if both checks pass: code checks (for example no promised score gains, using the member's own figures) and an LLM judge (Opus) that looks for every expected fact in the reply.
- **Judge check.** `evals.judge_validation` draws a blind sample of graded replies for a person to label with the judge's own rules, regrades stored replies with other judge models, and reports how often each judge agrees with the person and with the original judge.
- **Before vs After.** Both bots answer every case; the report pairs the cases and tests the net change.
- **Skill edits.** A scenario in `scenarios/<id>/` holds an edited copy of one skill, laid over `skills/` for the run. Only the cases the edit can affect rerun: a body edit reruns the cases labeled with that skill or routed to it, a description edit, an always-on edit or a cap change reruns all. The report then counts a flip for the edit only when the edit could reach that case's prompt: the edited skill was loaded (body edit), the routing changed (description or cap), or always (always-on edit).
- **Answer model and judge.** The After bot is run with each answer model (Haiku, Sonnet, Opus 5.5) and the stored replies are regraded by other judge models; `evals.models_report` sums up cost, cases passed, reply length and judge agreement. Every report also says whether each case's answering agent had every labeled skill and how long the replies are (`evals/quality.py`).
- **Online evaluation.** The site has a framework page for evaluating the bots on real traffic: metrics, A/B tests, and causal inference when a change cannot be randomized. It has no data.

The detailed design notes are in [SPEC.md](SPEC.md), which is written in Korean.

## Running the evals

The runner calls the Anthropic API for the routers, the answer model and the judge, so it needs `ANTHROPIC_API_KEY` in `backend/.env`. The tests never call the API. Run the commands from `backend/`; results go to `results/` at the repo root.

```bash
cd backend

# Both bots on every case (--repeats K runs each case K times; default 1)
.venv/bin/python -m evals.run --bot before --out ../results/before.json
.venv/bin/python -m evals.run --bot after --out ../results/after.json

# A skill edit on the After bot; --baseline picks the cases it can affect
.venv/bin/python -m evals.run --bot after --scenario s5 --baseline ../results/after.json --out ../results/scenarios/s5.json

# The After bot with another skill cap (the default is 4 since the cap experiment); every case reruns
.venv/bin/python -m evals.run --bot after --max-skills 5 --baseline ../results/after.json --out ../results/cap5.json

# Reports: report.json (for the site) and report.md
.venv/bin/python -m evals.report --baseline ../results/before.json --candidate ../results/after.json --out ../results/reports/before-vs-after
.venv/bin/python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s5.json --out ../results/reports/s5

# After a fatal API error (a bad key, no credit) the run stops and writes <out>.partial.json; rerun only what errored
.venv/bin/python -m evals.run --bot after --rerun-errors ../results/after.partial.json --out ../results/after.json

# The After bot with another answer model, then the answer model and judge report (no API for the report)
FYNN_AGENT_MODEL=claude-haiku-5-5 .venv/bin/python -m evals.run --bot after --out ../results/models/after-haiku.json
.venv/bin/python -m evals.models_report --runs ../results/models/after-*.json --router-from ../results/after.json \
  --regrades ../results/validation/regrades --out ../results/reports/models

# Judge check: draw a blind sample to label and its page (no API), regrade stored replies with another judge
# model (API), then compare. The committed sample's exact arguments are in its "args"; it is not overwritten without --force.
.venv/bin/python -m evals.judge_validation sample --runs ../results/models/after-*.json \
  --include after-sonnet:mi-023 --out ../results/validation/sample.json
.venv/bin/python -m evals.judge_validation page --sample ../results/validation/sample.json \
  --translations ../results/validation/translations.ko.json --out judge-check.html
.venv/bin/python -m evals.judge_validation regrade --results ../results/models/after-sonnet.json \
  --judge-model claude-sonnet-5-5 --out ../results/validation/regrades/sonnet-on-after-sonnet.json
.venv/bin/python -m evals.judge_validation agreement --sample ../results/validation/sample.json \
  --labels ../results/validation/human-labels.json --regrades ../results/validation/regrades \
  --runs ../results/models/after-*.json --out ../results/validation/agreement
```

- **Cost.** At most about $2.20 per bot for one run of the 64 cases at list prices (Sonnet answering, Opus judging, roughly half each). Older results files add the router's tokens to the answer's, so that figure prices them at Sonnet rates. Each case's result now records the router's, the answering model's and the judge's tokens apart (`routing.usage`, `usage`, `judge.usage`), since the three run on different models. The billing console is the final word, and the runner does not ask before spending.
- **Safety nets.** Results record fingerprints of the skills, the bot and judge code, and the settings, so a run against a baseline reruns every case when any of those or the models changed. A report leaves out cases whose expected facts were reworded between the two runs. The runner overwrites `--out`, so move an old results file to `results/archive/` first if a committed report still compares it.
- **More statistics.** `backend/evals/stats.py` also has repeated runs with a stricter flag rule, an A/A noise floor, a permutation test and Holm correction. They are kept for later and are not shown on the site; see SPEC.md.

## Layout

```
skills/      skill files (Markdown + YAML frontmatter), shared by both bots
personas/    synthetic member profiles (JSON, no real data)
scenarios/   skill-edit scenarios: an edited copy of one skill and what it should do
results/     committed eval results and reports
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
| Answering agent | `claude-sonnet-5-5` |
| Eval judge | `claude-opus-5-5` |

You can override each model with an environment variable; see `backend/.env.example`.

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Takes `{bot, persona_id, messages, carry_skills?}`. Returns the reply, the model, the routing decision and token usage. Errors come back as JSON `{detail, retryable}`. |
| `GET /personas` | Synthetic member profiles |
| `GET /architecture` | Domains, skills, models, skill budgets and request limits, for the site's diagrams |

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
- `NEXT_PUBLIC_API_URL` points the site at another backend (read at build time); `FYNN_CORS_ORIGINS` in `backend/.env` allows other origins. In `npm run dev`, hard-reload a page to pick up new results files.
- **Checks.** `npm run typecheck` and `npm run lint`.
