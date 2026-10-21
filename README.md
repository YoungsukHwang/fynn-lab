# Fynn Lab

An independent re-implementation of the architecture change described in Kikoff's engineering post ["Fynn at 100% scale"](https://about.kikoff.com/build/fynn-at-100-scale). The project has two parts: a before/after pair of credit-coach chatbots, and a regression-eval loop that checks every skill change. It is a study project and is not affiliated with Kikoff. The products the bots talk about are fictional (see [docs/products.md](docs/products.md)).

- **Before:** a small model routes each message to exactly one domain expert agent. A three-part question gets one domain's expertise.
- **After:** a small model selects every topic skill the message needs. One agent answers with those skills plus always-on skills (tone, response rules, guardrails).

Both bots read the same skill files and the same member profile. The only difference is routing and prompt composition.

The design notes and roadmap are in [SPEC.md](SPEC.md), which is written in Korean.

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

Both limits are design choices that M3 will compare. They are set in `backend/fynn/config.py`.

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
| `GET /architecture` | Domains, skills, and models, used to draw the diagrams |

## Web demo

The demo needs the backend running on port 8000 (see above).

```bash
cd web
npm install
npm run dev                 # http://localhost:3000
```

- **Pages.** `/` is the demo: pick a synthetic member, then send one message to both bots. Each column shows the reply, the router's decision and reason, and the architecture diagram with the agent or skills that were used.
- **Different backend.** To point the site at a different backend, set `NEXT_PUBLIC_API_URL`. It is read at build time.
- **CORS.** The API allows `localhost:3000` and `127.0.0.1:3000`. Set `FYNN_CORS_ORIGINS` in `backend/.env` for any other origin.
- **Placeholders.** `/framework` and `/results` stay placeholders until M5.
