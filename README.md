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
| M5 | Eval pages built from the committed results: Before vs After, Skill edits, Noise & A/A, each with Framework and Results tabs | Done |
| Stats | Repeated runs, A/A noise floor, paired tests, flag rule, Holm correction (see Noise and significance) | Built; the committed results are still single runs |
| M6 | Optional public deployment | Planned |

## Evaluation plan (M3 and M4)

"Monitoring" in this project means **offline regression testing before a skill change ships**, run on a fixed eval set. Production monitoring is out of scope for v1.

- **Eval set.** 64 cases over 6 synthetic personas, in four datasets:
  - single-topic questions;
  - multi-part questions (36 cases). Real member messages often mix several intents, so 24 of these were added on 2026-10-22, each needing skills from two or more Before domains (see Eval set expansion below);
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
- **Noise and significance.** LLM replies vary from run to run, so a case can flip with nothing changed. Each report adds a paired test of the net change, an A/A noise floor when one can be measured and, with repeated runs, a stricter flag rule (see below).

The detailed design notes are in [SPEC.md](SPEC.md), which is written in Korean.

## Running the evals

- **What it calls.** The runner calls the Anthropic API for the routers, the answer model and the Opus judge, so it needs `ANTHROPIC_API_KEY` in `backend/.env`. The tests never call the API.
- **Inputs.** The 64 cases are in `backend/evals/cases/` (four datasets). Each scenario in `scenarios/<id>/` has a `scenario.yaml` with its hypothesis and an edited copy of one skill. The copy is overlaid at run time; `skills/` is never modified.
- **Outputs.** Results go to `results/` at the repo root. Run the commands from `backend/`.

```bash
cd backend

# Full runs on both bots. --repeats 3 runs every case three times (default 1).
.venv/bin/python -m evals.run --bot before --repeats 3 --out ../results/before.json
.venv/bin/python -m evals.run --bot after --repeats 3 --out ../results/after.json

# Skill-edit scenarios on the After bot. --baseline turns on dependent-test selection.
.venv/bin/python -m evals.run --bot after --repeats 3 --scenario s1 --baseline ../results/after.json --out ../results/scenarios/s1.json
.venv/bin/python -m evals.run --bot after --repeats 3 --scenario s2 --baseline ../results/after.json --out ../results/scenarios/s2.json
.venv/bin/python -m evals.run --bot after --repeats 3 --scenario s3 --baseline ../results/after.json --out ../results/scenarios/s3.json

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
- **Other options.** `--dataset NAME` runs one dataset, `--limit N` runs the first N cases, and `--workers N` sets parallel case runs (default 8).
- **Cost.** The token usage recorded in the committed results comes to at most about $1.30 per 40 case runs (Sonnet 5.5 answering and an Opus 5.5 judge, at list prices), so about $2.10 for a single-run round of the current 64 cases. `--repeats K` multiplies that by K: the set of commands above with K=3 is about 816 case runs (before, after, S2 and S3 on 64 cases each, S1 on about 16), roughly $27. Usage inside the SDK's own retries is not recorded, so the billing console is the final word. The runner does not ask before spending, so check the cost first.

## Noise and significance

The first real run had several scenario flips that could be run-to-run variation rather than an effect of the edit. The statistics layer in `backend/evals/stats.py` separates the two. It never calls the API; it only reads results files.

- **Repeated runs.** `run.py --repeats K` runs each case K times. A case keeps every run under `runs`, its pass count `passes` and its `pass_fraction`. Its top-level fields come from a run with the majority outcome. Summary buckets count runs, so a rate is the mean pass fraction. K=1 writes the same files as before, plus `repeats`, `passes` and `pass_fraction`.
- **Flag rule.** A case regresses only when it fails at least m of its K runs and passed every baseline run; it improves when it passes at least m and failed every baseline run. m defaults to a strict majority (2 of 3) and is set with `report.py --min-fails M`. Anything else that varied is listed as unstable and is not counted; unstable cases that still moved by at least m of K (for example 2 of 3 to 0 of 3) are listed separately as sharp drops or rises. With one run per side this is the plain flip, so the verdict means what it did before.
- **Errored runs.** An API error says nothing about the bot, so a report leaves errored runs out of a case's counts (flag rule, test, rates, noise floor) whenever that side of the case has other runs. This applies to the baseline, the candidate and an A/A run alike, so partly errored cases on both sides do not read as a regression. When every run on a side errored (always the case for an errored run at K=1), the flag rule counts that side as failing, as before, so it can still flag the case; the paired test and the noise floor leave such a case out and say so. Reports list and warn about cases with errored runs on either side. A results file's own summary still counts errored runs as failures and shows how many errored.
- **Paired test of the net change.** Cases are paired with their baseline.
  - With one run per side: an exact McNemar test, a binomial test of the flipped cases against a 50/50 split.
  - With repeated runs: an exact permutation test of the mean per-case change in pass fraction. If the change did nothing, a case's baseline and candidate runs are interchangeable, so the test shuffles each case's runs between the two sides and computes the exact null distribution (no resampling, no seed). With one run each it gives exactly the McNemar p-value. It does not depend on how many personas there are.
  - P-values are exact fractions, so a p of exactly 0.05 counts as significant. The JSON keeps 6 decimals.
  - A persona-cluster bootstrap interval (95%, 10,000 resamples, fixed seed, at least 3 personas) of the same mean change is shown next to it. It describes how much the change varies between personas and is not a test: with 6 personas it can sit entirely on one side of zero by chance.
  - Both tests ask whether the overall pass rate moved. A balanced tradeoff, with as many cases fixed as broken, can read as not significant.
- **Verdict and test.** The verdict (Passed only when no case is flagged as regressed) is unchanged. When it and the paired test tell different stories, the report adds a sentence next to it: for example a Not passed verdict with a net change that is not significant, or a Passed verdict next to a significant net regression hidden in unstable cases. Hypothesis matches come from the flagged counts and are not a significance test.
- **A/A noise floor.** How many cases flip between two runs of the baseline with nothing changed.
  - With K of at least 2 it comes free from the baseline's own repeats: the expected number of flips between two single runs is the sum over cases of 2k(K-k)/(K(K-1)), where k is the case's passing runs. That is single-run noise. The flag rule needs a stable baseline and m failing runs, so far fewer cases are flagged by chance, and the report labels the two differently.
  - A second baseline run passed as `report.py --aa PATH` gives an observed count under the flag rule instead. It should have the candidate's K; when it does not, the report warns and says which rule it used instead.
  - A report whose two runs share the bot, skills and models is marked as an A/A report. Code, the judge and the cases are not fingerprinted, so it is only pure noise if nothing else changed.
- **Multiplicity.** The per-dataset p-values are Holm-corrected together, which controls the chance of any false positive among them. The overall test is the primary one at 0.05 and is not adjusted, so across every row of the table that chance can reach 0.10. Significant means p at or below 0.05.
- **Calibration.** In A/A simulations on the original 40-case layout (6 personas, K=3), the permutation test flags about 3% of no-change runs at 0.05, and 0 to 4% depending on how noisy the cases are. It never went above 5%, because an exact test on coarse pass fractions is a little conservative. When 8 cases really drop (from passing 95% of the time to 30%), the overall test catches it roughly 75 to 95% of the time at K=3 and 20 to 30% at K=1, depending on how noisy the other cases are. That gap is the case for K=3. With nothing changed, the per-case verdict still reads Not passed in about 93 to 99.7% of comparisons at K=1 and 53 to 70% at K=3, and at K=1 a real 10-point gain is caught only about one time in five. These figures come from one-off simulations that are not committed.
- **Caveats.** A few dozen cases cannot detect small effects, and a non-significant result is not evidence of no change.

## Eval set expansion

The first Before vs After run could not show much difference, because 31 of the 40 cases fit inside one Before domain, where the Before agent already holds every skill the case needs. On 2026-10-22, 24 multi-question cases were added (`mi-013` to `mi-036`, four per persona, 11 with two questions and 13 with three):

- **Each needs a second domain.** Its labeled skills span two or more Before domains (13 span two, 11 span three, covering every domain pair).
- **Each extra question hinges on a skill-only fact**: a price, fee, bureau list, threshold or how-to-answer rule found only in that topic skill, not in the profile, the always-on skills or general credit knowledge. A Before agent routed elsewhere should miss it.
- **Facts are single claims**, and a comment above each one names the skill line or profile field it comes from. A separate reviewer checked every fact against its source, and dropped facts the message never asked for.
- **Four cases need four topic skills** (`mi-016`, `mi-020`, `mi-028`, `mi-036`), one more than the After bot's cap of 3 new skills (a Fynn Lab setting). They test raising the cap to 4.
- **Labels on five existing cases were completed** (`st-001`, `st-002`, `mi-003` and `mi-008` gain utilization, `sb-001` gains payment-history), because a fact in each relied on that skill. With the added label, `mi-008` also needs four skills.

The committed results predate the expansion and cover the original 40 cases. The new cases need a rerun: about $4.20 to run both bots once on all 64 cases, or the K=3 set above.

```bash
# A/A: a second baseline run with nothing changed and the same --repeats, then a report against it
.venv/bin/python -m evals.run --bot after --repeats 3 --out ../results/aa/after.json
.venv/bin/python -m evals.report --baseline ../results/after.json --candidate ../results/aa/after.json --out ../results/reports/aa-after

# Use it as the noise floor of a scenario report, with a stricter flag rule
.venv/bin/python -m evals.report --baseline ../results/after.json --candidate ../results/scenarios/s2.json \
    --aa ../results/aa/after.json --min-fails 3 --out ../results/reports/s2
```

`report.json` gains `flag_rule`, `paired_test` (with `by_dataset`, `p_holm`, `family` and the descriptive `ci`), `noise_floor` (with its `unit`), `noise_floor_note`, `verdict_note`, `kind`, `improvements`, `sharp_changes`, `baseline_errors` and an `unstable` transition. `report.md` gives the test, the noise floor and any verdict note next to the verdict, plus a "Noise and significance" section.

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
- **Eval pages.** Three sections, each with a Framework tab and a Results tab, all built from the committed results and reports:
  - `/before-after`: how the two bots are compared (designs, the domain map, the eval set, scoring), and what the eval found, split by whether a case needs a second domain, by number of questions and by dataset;
  - `/skill-edits`: the regression loop and dependent-test selection, and the three scenario reports;
  - `/noise`: the statistics (repeats, flag rule, net-change tests, A/A noise floor, calibration and power), and every comparison's noise check with the runs behind it.
  The old `/framework` and `/results` paths redirect to the Before vs After tabs.
- **Checks.** `npm run typecheck` (generates route types, then runs `tsc`) and `npm run lint`.
