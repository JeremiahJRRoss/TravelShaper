# TravelShaper

AI travel planning assistant — fill in a form, get an opinionated briefing with flights, hotels, cultural prep, and activity picks.

## Quick Start

```bash
git clone <your-repo-url>
cd src
./setup.sh
```

This checks prerequisites, configures API keys, and starts the app and Phoenix via Docker Compose.

When it finishes:

- **App:** [http://localhost:8000](http://localhost:8000)
- **Phoenix:** [http://localhost:6006](http://localhost:6006)

Tests run without API keys or Docker:

```bash
poetry install -E dev
pytest tests/ -v
```

For alternative methods (local venv, standalone Docker), see [RUNNING.md](src/RUNNING.md).

## What It Does

TravelShaper takes a departure city, destination, dates, budget preference, and interests, then dispatches four tools to gather live data:

- **search_flights** — Google Flights via SerpAPI (prices, airlines, layovers)
- **search_hotels** — Google Hotels via SerpAPI (rates, ratings, amenities)
- **get_cultural_guide** — scoped Google search for etiquette, language, dress code
- **duckduckgo_search** — open web search for interests and gaps (no key needed)

It synthesizes the results into a single briefing covering getting there, where to stay, cultural prep, and what to do — tailored to your budget mode ("save money" or "full experience") and selected interests.

The agent runs two distinct voices depending on budget mode. Every recommendation includes a hyperlink and an explanation of *why* it was chosen. The entire request flow is instrumented with Arize Phoenix for observability.

## Running Tests

```bash
poetry run pytest tests/ -v
```

14 tests, all mocked — no API keys required.

CI runs automatically on push and PR — see `.github/workflows/ci.yml`.

## Running Traces + Evaluations

```bash
./run_traces.sh                        # fires 10 queries, generates Phoenix traces
python -m evaluations.run_evals        # runs 3 evaluation metrics against traces
```

See [docs/trace-queries.md](src/docs/trace-queries.md) for query details and [docs/evaluation-prompts.md](src/docs/evaluation-prompts.md) for evaluation methodology.

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
├── run_traces.sh                   # 10 trace queries + span export
├── RUNNING.md                      # Full setup guide (venv, Docker, Phoenix)
└── CHANGELOG.md
```

## Architecture

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

### Tools

| Tool | API | What it returns |
|------|-----|-----------------|
| `search_flights` | SerpAPI (google_flights engine) | Airlines, prices, durations, layovers, booking links |
| `search_hotels` | SerpAPI (google_hotels engine) | Hotel names, nightly rates, ratings, amenities, images |
| `get_cultural_guide` | SerpAPI (google engine, scoped) | Language phrases, etiquette, dress code, local customs |
| `duckduckgo_search` | DuckDuckGo (no key needed) | General search results for interests and open questions |

For the full architecture narrative, see [docs/ARCHITECTURE.md](src/docs/ARCHITECTURE.md).

## API Endpoints

`GET /` — Browser UI

`POST /chat` — Sync chat, returns full JSON response:
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from NYC to Rome, September, save money, food and history."}' \
  | python3 -m json.tool
```

`POST /chat/stream` — SSE streaming (used by the browser UI). Same request body as `/chat`.

`GET /health` — Returns `{"status": "ok"}`

Full API contract (request fields, SSE event types, validation errors) in [docs/ARCHITECTURE.md](src/docs/ARCHITECTURE.md).

## Design Decisions

- **Single HTML file UI** — no npm, no build step; served directly by FastAPI alongside the REST API.
- **SerpAPI as single data provider** — one key powers flights, hotels, and scoped web searches with structured JSON.
- **Cultural guide as a first-class tool** — etiquette and language prep adds value beyond price comparison.
- **DuckDuckGo as fallback** — covers general queries without requiring an additional API key.
- **Single-turn design** — each request is independent; include all trip details in one submission.
- **Budget as a lens, not a filter** — affects ranking and tone, not hard cutoffs.
- **Place validation before agent** — gpt-4o catches misspellings and rejects fake places before the expensive agent runs.

## Known Limitations

- Planning assistant only — recommends options but does not book.
- Flight and hotel prices reflect time of search, not guaranteed availability.
- Cultural guidance is practical advice based on common norms, not absolute rules.
- Designed for English-speaking American travelers; guidance assumes U.S. norms as baseline.
- Single-turn: no conversation memory between requests.

## Troubleshooting

**Server won't start** — Confirm Python 3.11+, venv is active, `.env` exists with valid keys. Run `poetry install -E dev`.

**Auth error** — Check `OPENAI_API_KEY` and `SERPAPI_API_KEY` in `.env`. Verify SerpAPI key at [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key).

**Poor or incomplete results** — Include origin, destination, dates, and budget. Check SerpAPI usage (free tier: 250 searches/month). Try well-known destinations first.

**Missing traces in Phoenix** — Confirm Phoenix is running (`docker-compose up`). Run at least one `/chat` query, then refresh the Phoenix UI at `http://localhost:6006`.

---

MIT License — see [LICENSE](LICENSE).
