# TravelShaper

**AI travel planning assistant** — fill in a form, get an opinionated briefing with flights, hotels, cultural prep, and activity picks.

Every recommendation includes a hyperlink and an explanation of *why* it was chosen. The agent runs two distinct voices depending on budget mode, and the entire request flow is instrumented with Arize Phoenix for observability.

---

## Before You Begin

TravelShaper needs two things from the outside world: an OpenAI key to think with, and a SerpAPI key to search with. Everything else — the agent, the tools, the UI, the tracing stack — lives inside the project. Getting these keys configured correctly is the single most important step in setup, and the one most likely to cause confusion later if skipped.

### 1. Create your environment file

```bash
cd src
cp .env.example .env
```

Open `.env` in any editor and fill in your keys:

```
OPENAI_API_KEY=sk-...
SERPAPI_API_KEY=...
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

**Where to get keys:**

- **OpenAI** (required) — [platform.openai.com/api-keys](https://platform.openai.com/api-keys). The agent cannot function without this.
- **SerpAPI** (required for flights, hotels, and cultural guide) — [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). The free tier provides 250 searches per month, which supports roughly 60–125 full trip briefings. Without this key, the agent falls back to DuckDuckGo for everything — functional, but limited.
- **Phoenix endpoint** — leave the default. It points to the Phoenix container that Docker Compose starts automatically. Only change this if you are running Phoenix on a different host.

The `.env` file is listed in `.gitignore` and will never be committed. If you see an auth error later, this is the first place to check.

---

## Choose How to Run

There are two ways to run TravelShaper. Pick the one that fits your situation — they produce identical results.

### Option A: Docker Compose (recommended)

This is the fastest path. Docker handles Python versions, dependencies, and Phoenix in one command. You do not need a virtual environment.

```bash
cd src
./setup.sh
```

The setup script checks prerequisites, prompts for API keys if `.env` does not exist yet, builds the containers, and starts both services. When it finishes:

| Service | URL |
|---------|-----|
| TravelShaper (app + API) | [http://localhost:8000](http://localhost:8000) |
| Phoenix (tracing UI) | [http://localhost:6006](http://localhost:6006) |

To stop everything:

```bash
docker compose down
```

To rebuild after code changes (Docker caches aggressively — this ensures fresh containers):

```bash
docker compose build --no-cache
docker compose up -d
```

### Option B: Local virtual environment

Use this if you prefer working outside Docker, want hot-reload during development, or need to debug with local tools. A virtual environment is required — do not install into your system Python.

```bash
cd src
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows
pip install --upgrade pip
pip install poetry==1.8.2
poetry install -E dev
```

Start the server:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The app is now running at [http://localhost:8000](http://localhost:8000).

**Phoenix tracing** (optional in venv mode): the Phoenix packages have Python version constraints that conflict with Poetry's resolver. Install them directly with pip after Poetry finishes:

```bash
pip install arize-phoenix arize-phoenix-evals arize-phoenix-otel \
            openinference-instrumentation-langchain
```

You will also need to run the Phoenix server separately. The simplest way is Docker:

```bash
docker run -p 6006:6006 arizephoenix/phoenix:latest
```

---

## Running Tests

Here is the thing about the tests that matters most: they are entirely self-contained. All 14 tests use mocked external calls. They do not need API keys, a running server, or Docker. They need only the right Python packages available to import.

The principle is simple: every command that runs Python code should execute inside either a container or an activated virtual environment. Never bare system Python.

### If you are using Docker

```bash
cd src
docker compose run --rm test
```

This spins up a temporary container, installs test dependencies, runs pytest, and removes the container when finished. Your running app and Phoenix are unaffected.

### If you are using a local virtual environment

Run tests in the same venv where you installed dependencies — there is no reason to create a separate one:

```bash
cd src
source .venv/bin/activate
pytest tests/ -v
```

Expected output: **14 tests passing**.

---

## What It Does

TravelShaper takes a departure city, destination, dates, budget preference, and interests, then dispatches four tools to gather live data:

- **search_flights** — Google Flights via SerpAPI (prices, airlines, layovers)
- **search_hotels** — Google Hotels via SerpAPI (rates, ratings, amenities)
- **get_cultural_guide** — scoped Google search for etiquette, language, dress code
- **duckduckgo_search** — open web search for interests and gaps (no key needed)

It synthesises the results into a single briefing covering getting there, where to stay, cultural prep, and what to do — tailored to your budget mode and selected interests.

The agent runs two distinct voices depending on budget mode. "Save money" activates a Bourdain / Billy Dee Williams / Gladwell voice — muscular prose, insider knowledge, budget as philosophy. "Full experience" activates a Robin Leach / Pharrell / Rushdie voice — theatrical, joyful, literary. Both are instructed to include a markdown hyperlink for every named place, hotel, restaurant, and attraction.

---

## API Endpoints

**`GET /`** — Browser UI. Open [http://localhost:8000](http://localhost:8000) in any browser. No curl required.

**`POST /chat`** — Synchronous chat. Returns the full JSON response when the agent finishes. Useful for curl, scripts, and tests.

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from NYC to Rome, September, save money, food and history."}' \
  | python3 -m json.tool
```

**`POST /chat/stream`** — SSE streaming. Same request body as `/chat`. The browser UI uses this to show real-time status updates as each tool executes.

**`GET /health`** — Returns `{"status": "ok"}`. Used by Docker's health check and useful for verifying the server is alive.

---

## Running Traces and Evaluations

Traces are generated by running real queries against the live API. Do this after starting the full Docker Compose stack (or after starting both the app and Phoenix in venv mode).

### Generate traces

```bash
cd src
chmod +x run_traces.sh
./run_traces.sh
```

This fires 11 queries covering every tool combination, both budget voices, auto-correction, vague inputs, and edge cases. Each query generates a trace visible in Phoenix at [http://localhost:6006](http://localhost:6006).

### Run evaluations

```bash
python -m evaluations.run_evals
```

This runs three LLM-as-judge metrics against the collected traces: user frustration (Phoenix built-in template), tool usage correctness, and answer completeness. Results are logged back to Phoenix and visible in the Evaluations tab.

See [docs/trace-queries.md](src/docs/trace-queries.md) for the full query list and [docs/evaluation-prompts.md](src/docs/evaluation-prompts.md) for evaluation methodology.

---

## Project Structure

```
src/
├── api.py                          # FastAPI server — /chat, /chat/stream, /health, static UI
├── agent.py                        # LangGraph agent — dual system prompts, voice routing
├── static/index.html               # Browser UI — Bebas Neue / Cormorant Garamond / DM Sans
├── tools/
│   ├── __init__.py                 # serpapi_request() helper
│   ├── flights.py                  # search_flights (SerpAPI Google Flights)
│   ├── hotels.py                   # search_hotels (SerpAPI Google Hotels)
│   └── cultural_guide.py          # get_cultural_guide (scoped Google search)
├── evaluations/
│   ├── run_evals.py                # Phoenix evaluation runner (3 metrics)
│   └── metrics/
│       ├── frustration.py          # USER_FRUSTRATION_PROMPT
│       ├── answer_completeness.py  # ANSWER_COMPLETENESS_PROMPT
│       └── tool_correctness.py     # TOOL_CORRECTNESS_PROMPT
├── scripts/
│   └── export_spans.py             # Export Phoenix spans to JSON
├── tests/
│   ├── test_tools.py               # 4 tool tests
│   ├── test_agent.py               # 2 agent graph tests
│   └── test_api.py                 # 8 endpoint + validation tests
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PRD.md
│   ├── system-prompt-spec.md
│   ├── test-specification.md
│   ├── docker-spec.md
│   ├── evaluation-prompts.md
│   ├── trace-queries.md
│   ├── implementation-plan.md
│   └── presentation-outline.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── run_traces.sh                   # 11 trace queries + span export
├── setup.sh                        # One-command setup (Docker path)
├── RUNNING.md                      # Extended setup guide
└── CHANGELOG.md
```

---

## Architecture

The agent uses a standard LangGraph ReAct loop. The graph topology is unchanged from the starter app — the extension adds tools, not complexity.

```
Browser / curl
  │
  ├── POST /chat/stream  (SSE — browser UI)
  └── POST /chat         (sync — curl / tests)
           │
           ▼
     Place + Preference Validation (gpt-4o)
           │
           ▼
     LangGraph Agent
           │
     get_system_prompt(message)
           ├── "save money" → Bourdain / Billy Dee / Gladwell voice
           └── default     → Leach / Pharrell / Rushdie voice
           │
     llm_call (gpt-5.3-chat-latest)
           │
           ├── search_flights       (SerpAPI → Google Flights)
           ├── search_hotels        (SerpAPI → Google Hotels)
           ├── get_cultural_guide   (SerpAPI → Google Search)
           └── duckduckgo_search    (DuckDuckGo, no key needed)
           │
     tool_node → llm_call (synthesis)
           │
     SSE stream / JSON response → browser / client
```

For the full architecture narrative — component design, data flow, LLM decision making, prompt design rationale, deployment topology, and security considerations — see [docs/ARCHITECTURE.md](src/docs/ARCHITECTURE.md).

---

## Design Decisions

There is a pattern in how TravelShaper makes its choices, and the pattern is worth naming: every decision optimises for the shortest path to a working demo that is still architecturally honest.

- **Single HTML file UI** — no npm, no build step; served directly by FastAPI alongside the REST API. The constraint produced a better result: one file that loads instantly and has zero deployment friction.
- **SerpAPI as single data provider** — one key powers flights, hotels, and scoped web searches with structured JSON. The alternative was three separate APIs with three approval processes.
- **Cultural guide as a first-class tool** — etiquette and language prep is what separates a useful travel briefing from a price comparison. Most travel tools skip this entirely.
- **DuckDuckGo as fallback** — covers general queries without requiring an additional API key. Already present in the starter code.
- **Two system prompts, not one** — a single prompt with conditional voice instructions produces blended, inconsistent output. Two separate prompts let the model commit fully to one register.
- **Place validation before agent** — gpt-4o catches misspellings and rejects fictional places before the expensive agent runs. A 1-second validation call saves 30 seconds of wasted agent time.
- **Single-turn design** — each request is independent. This is a deliberate product boundary, not a gap.

---

## Known Limitations

- Planning assistant only — recommends options but does not book.
- Flight and hotel prices reflect time of search, not guaranteed availability.
- Cultural guidance is practical advice based on common norms, not absolute rules.
- Designed for English-speaking American travellers; guidance assumes U.S. norms as baseline.
- Single-turn: no conversation memory between requests.
- SerpAPI free tier supports ~60–125 full briefings per month.

---

## Troubleshooting

**Server won't start** — confirm your `.env` exists with valid keys. If running locally, confirm the venv is activated and you have run `poetry install -E dev`. If running Docker, try `docker compose build --no-cache`.

**Auth error from OpenAI or SerpAPI** — check your `.env` file. Verify the SerpAPI key at [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). Verify the OpenAI key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

**Tests fail with ModuleNotFoundError** — you are running pytest outside of an isolated environment. Either activate your venv (`source .venv/bin/activate`) or use the Docker test service (`docker compose run --rm test`). Confirm that `pyproject.toml` contains `[tool.pytest.ini_options]` with `pythonpath = ["."]`.

**Poor or incomplete results** — include origin, destination, dates, and budget in your request. Check SerpAPI usage (free tier: 250 searches/month). Try well-known destinations first.

**Missing traces in Phoenix** — confirm Phoenix is running. If using Docker Compose, both services start together. If using a venv, you need to start Phoenix separately. Run at least one `/chat` query, then refresh the Phoenix UI at [http://localhost:6006](http://localhost:6006).

**`ModuleNotFoundError: No module named 'phoenix'`** — the Phoenix packages are not installed. In venv mode, install them with pip (see the venv setup section above). In Docker mode, they are pre-installed in the container.

---

MIT License — see [LICENSE](LICENSE).
