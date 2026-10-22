# Fynn Lab

An independent re-implementation of the architecture change described in Kikoff's engineering post ["Fynn at 100% scale"](https://about.kikoff.com/build/fynn-at-100-scale).

- **Built.** A before/after pair of credit-coach chatbots and a demo site that compares them side by side.
- **In progress.** A regression-eval loop that checks every skill change (see Status below).

It is a study project and is not affiliated with Kikoff. The products the bots talk about are fictional; see [docs/products.md](docs/products.md).

- **Before:** the earlier design in the post, which the post calls its beta. A small model routes each message to exactly one domain expert agent, so a question that spans several domains gets only one domain's expertise.
- **After:** the skill design the post moved to. A small model selects the topic skills the message needs. One agent answers with those skills plus always-on skills (tone, response rules, guardrails).

Both bots read the same skill files, see the same member profile and use the same answer model. They differ in routing and prompt composition.

**Fynn Lab additions, not from the post:**
- the After bot caps new skills at 3 per message;
- the After bot carries up to 2 of the previous turn's skills for one more turn;
- the products, personas and the four Before agents are this project's own.

## Status and roadmap

| Milestone | What | Status |
|---|---|---|
| M1 | Backend: skills, personas, both bots, FastAPI, tests | Done |
| M2 | Demo site: Before/After columns, routing display, architecture diagrams | Done |
| M3 | Eval set, code checks, LLM judge, parallel runner | Done |
| M4 | Regression report, dependent-test selection, three skill-edit scenarios | Done |
| Later | Batch API runner; compare skill budgets (cap 3/5/none) and answer models (Opus/Sonnet/Haiku) | Planned |
| M5 | Monitoring framework and results pages | Planned |
| M6 | Optional public deployment | Planned |

## Evaluation plan (M3 and M4)

"Monitoring" in this project means **offline regression testing before a skill change ships**, run on a fixed eval set. Production monitoring is out of scope for v1.

- **Eval set.** About 40 cases over 6 synthetic personas, in four datasets:
  - single-topic questions;
  - multi-part questions;
  - use of the member's own profile data;
  - basic safety, such as no promised score gains.
- **Scoring.** A case passes only if both checks pass:
  - code checks, such as banned promises and use of the member's figures;
  - an LLM judge that compares the answer with a list of expected facts and explains its verdict.
- **Before vs After.** Pass rates by dataset and by the number of questions in a message.
- **Regression report.** For each skill edit:
  - passed / not passed;
  - improved, regressed and unchanged cases;
  - a failure overview showing the old answer, the new answer and the judge's reason.
- **Dependent-test selection.** Each skill keeps separate hashes for its description, body and metadata.
  - A body edit reruns only the cases that use the skill.
  - A description or always-on edit reruns everything, because it can change routing or every prompt.
- **Three skill-edit scenarios on the After bot.** The hypothesis for each is written down before it runs:
  - a topic-skill body edit;
  - an always-on edit;
  - a description edit.

The detailed design notes are in [SPEC.md](SPEC.md), which is written in Korean.

## Running the evals

- **What it calls.** The runner calls the Anthropic API for the routers, the answer model and the Opus judge, so it needs `ANTHROPIC_API_KEY` in `backend/.env`. The tests never call the API.
- **Inputs.** The 40 cases are in `backend/evals/cases/` (four datasets). Each scenario in `scenarios/<id>/` has a `scenario.yaml` with its hypothesis and an edited copy of one skill. The copy is overlaid at run time; `skills/` is never modified.
- **Outputs.** Results go to `results/` at the repo root. Run the commands from `backend/`.

```bash
cd backend

# Full runs on both bots
.venv/bin/python -m evals.run --bot before --out ../results/before.json
.venv/bin/python -m evals.run --bot after --out ../results/after.json

# Skill-edit scenarios on the After bot. --baseline turns on dependent-test selection.
.venv/bin/python -m evals.run --bot after --scenario s1 --baseline ../results/after.json --out ../results/scenarios/s1.json
.venv/bin/python -m evals.run --bot after --scenario s2 --baseline ../results/after.json --out ../results/scenarios/s2.json
.venv/bin/python -m evals.run --bot after --scenario s3 --baseline ../results/after.json --out ../results/scenarios/s3.json

# Regression reports: report.json (for the site) and report.md in each directory
.venv/bin/python -m evals.report --baseline ../results/before.json --candidate ../results/after.json --out ../results/reports/before-vs-after
.venv/bin/python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s1.json --out ../results/reports/s1
.venv/bin/python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s2.json --out ../results/reports/s2
.venv/bin/python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s3.json --out ../results/reports/s3
```

- **Passing.** A case passes only if the code checks and the judge both pass. A case that errors is recorded with status `error` and counts as not passed; the rest of the run continues.
- **Selection.** With `--baseline`, a body edit to a topic skill (s1) reruns only the cases labeled with that skill or routed to it in the baseline. An always-on edit (s2) or a description edit (s3) reruns every case.
- **Baseline freshness.** Run the scenarios against an `after.json` made from the current `skills/`. The runner warns when the baseline's skill hashes differ.
- **Reports.** A report compares only the cases in the candidate. The verdict is Passed when no case regressed. A scenario report also says whether the result matches the hypothesis in `scenario.yaml`.
- **Other options.** `--dataset NAME` runs one dataset, `--limit N` runs the first N cases, and `--workers N` sets parallel cases (default 8).

## Layout

```
skills/      skill files (Markdown + YAML frontmatter), shared by both bots
personas/    synthetic member profiles (JSON, no real data)
docs/        product fact sheet for the fictional app
backend/     Python: fynn core package, FastAPI app, tests
web/         Next.js demo site: Before/After chat, routing display, architecture diagrams
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

Settings in `backend/.env` are loaded before anything else, and variables exported in your shell take precedence over them.

### Skill budget (After bot)

- The router picks up to `MAX_NEW_SKILLS_PER_TURN` (3) topic skills for the latest message.
- Skills picked on the previous turn stay loaded for one more turn, up to `MAX_CARRIED_SKILLS` (2). This keeps a follow-up question from losing the guidance behind the answer it follows. The CLI tracks this for you. API clients pass the previous reply's `routing.selected` back as `carry_skills`.

Both limits are this project's design choices; the post does not mention them. M3 will compare settings. They are set in `backend/fynn/config.py`.

### Models

| Role | Model |
|---|---|
| Routers (both bots) | `claude-haiku-5-5` |
| Answering agent | `claude-sonnet-5-5` |
| Eval judge (M3) | `claude-opus-5-5` |

You can override each model with an environment variable; see `backend/.env.example`.

### API

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Takes `{bot, persona_id, messages, carry_skills?}`. Messages must alternate, starting and ending with the user. `carry_skills` applies to the After bot only; the Before bot ignores it, and unknown names are dropped. Returns `bot`, `reply`, `model`, `stop_reason`, the routing decision (`strategy`, `selected`, `carried`, `reason`, `error`), and token usage including cache reads and writes. Every error comes back as JSON `{detail, retryable}` with CORS headers. |
| `GET /personas` | Synthetic member profiles |
| `GET /architecture` | Domains, skills, models, skill budgets and request `limits` (`max_messages`, `max_user_message_chars`); the site uses them to draw the diagrams and to cap its input |

## Web demo

Requires Node.js 20.9 or newer. The demo needs the backend running on port 8000 (see above), and chatting needs `ANTHROPIC_API_KEY` in `backend/.env`.

```bash
cd web
npm install
npm run dev                 # http://localhost:3000
```

- **Pages.** `/` is the demo: pick a synthetic member, then send one message to both bots. Each column shows the reply, the router's decision and reason, and the architecture diagram with the agent or skills that were used.
- **Different backend.** To point the site at a different backend, set `NEXT_PUBLIC_API_URL`. It is read at build time.
- **CORS.** The API allows `localhost:3000` and `127.0.0.1:3000`. Set `FYNN_CORS_ORIGINS` in `backend/.env` for any other origin.
- **Placeholders.** `/framework` and `/results` stay placeholders until M5.
- **Checks.** `npm run typecheck` (generates route types, then runs `tsc`) and `npm run lint`.
