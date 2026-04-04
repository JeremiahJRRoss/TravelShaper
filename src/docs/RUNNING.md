# TravelShaper — Running & Testing Guide

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required |
| pip | Any recent | Comes with Python |
| Docker + Docker Compose | Any recent | For containerised run |
| OpenAI API key | — | Required for the agent |
| SerpAPI key | — | Required for flights/hotels/cultural guide |

---

## 1. Local Setup

### 1a. Clone / unzip the project

```bash
unzip travelshaper-complete.zip
cd travelshaper/se-interview-main
```

### 1b. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 1c. Install Poetry inside the venv

```bash
pip install --upgrade pip
pip install poetry==1.8.2
```

### 1d. Install project dependencies

```bash
# Core dependencies + test runner
poetry install -E dev
```

#### Phoenix tracing (optional)

The Phoenix packages have Python version constraints that conflict with Poetry's resolver. Install them directly with pip:

```bash
pip install arize-phoenix arize-phoenix-evals arize-phoenix-otel \
            openinference-instrumentation-langchain
```

### 1e. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```
OPENAI_API_KEY=sk-...
SERPAPI_API_KEY=...

# Telemetry routing (phoenix | arize | otlp | both | all | none)
OTEL_DESTINATION=phoenix
PHOENIX_ENDPOINT=http://localhost:6006/v1/traces
# OTLP_ENDPOINT=http://localhost:4318/v1/traces    # only if OTEL_DESTINATION=otlp or all
# OTLP_HEADERS=                                    # comma-separated key=value pairs
```

---

## 2. Running the API Server

### Option A — Local (venv)

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### Option B — Docker Compose (recommended for full stack)

Starts TravelShaper and optionally Phoenix:

```bash
# With Phoenix (default):
docker compose --profile phoenix up --build -d

# Or use the Makefile (reads OTEL_DESTINATION from .env):
make up
```

| Service | URL |
|---------|-----|
| TravelShaper API | http://localhost:8000 |
| Phoenix Tracing UI | http://localhost:6006 |

### Option C — Docker only (no Phoenix)

```bash
docker build -t travelshaper .
docker run -p 8000:8000 --env-file .env travelshaper
```

---

## 3. Running the Tests

### All 26 tests (recommended)

```bash
pytest tests/ -v
```

Expected output:

```
tests/test_tools.py::test_search_flights_formats_results          PASSED
tests/test_tools.py::test_search_flights_handles_empty_results    PASSED
tests/test_tools.py::test_search_hotels_formats_results           PASSED
tests/test_tools.py::test_cultural_guide_returns_guidance         PASSED
tests/test_agent.py::test_agent_graph_has_expected_nodes          PASSED
tests/test_agent.py::test_agent_tools_registered                  PASSED
tests/test_agent.py::test_cultural_guide_tool_has_routing_docstring PASSED
tests/test_agent.py::test_voice_routing_selects_correct_prompt    PASSED
tests/test_agent.py::test_llm_call_uses_dispatch_prompt_before_tools PASSED
tests/test_agent.py::test_llm_call_uses_synthesis_prompt_after_tools PASSED
tests/test_api.py::test_health_endpoint                           PASSED
tests/test_api.py::test_chat_endpoint_accepts_message             PASSED
tests/test_api.py::test_chat_accepts_valid_preferences            PASSED
tests/test_api.py::test_chat_rejects_invalid_preferences          PASSED
tests/test_api.py::test_chat_skips_validation_for_empty_preferences PASSED
tests/test_api.py::test_chat_accepts_valid_places                 PASSED
tests/test_api.py::test_chat_rejects_invalid_place                PASSED
tests/test_api.py::test_chat_auto_corrects_misspelled_place       PASSED
tests/test_otel_routing.py::test_phoenix_destination_creates_one_exporter  PASSED
tests/test_otel_routing.py::test_phoenix_api_key_added_to_headers_when_present PASSED
tests/test_otel_routing.py::test_phoenix_no_api_key_sends_no_auth_header   PASSED
tests/test_otel_routing.py::test_arize_destination_calls_arize_register    PASSED
tests/test_otel_routing.py::test_arize_missing_credentials_skips_silently  PASSED
tests/test_otel_routing.py::test_both_destination_uses_arize_and_phoenix   PASSED
tests/test_otel_routing.py::test_otlp_destination_creates_one_exporter     PASSED
tests/test_otel_routing.py::test_otlp_headers_parsed_and_passed           PASSED
tests/test_otel_routing.py::test_otlp_missing_endpoint_skips_silently     PASSED
tests/test_otel_routing.py::test_all_destination_creates_all_exporters    PASSED
tests/test_otel_routing.py::test_none_destination_creates_no_exporters     PASSED
tests/test_otel_routing.py::test_project_name_sets_service_name            PASSED
tests/test_otel_routing.py::test_default_project_name_is_travelshaper      PASSED

26 passed
```

> **No API keys are required to run tests.** All external calls are mocked.

### Run a specific test file

```bash
pytest tests/test_tools.py -v          # 4 tool tests
pytest tests/test_agent.py -v          # 6 agent graph + routing + dispatch tests
pytest tests/test_api.py -v            # 8 API + validation tests
pytest tests/test_otel_routing.py -v   # 13 OTel routing tests
```

### Run a single test by name

```bash
pytest tests/test_tools.py::test_search_flights_formats_results -v
```

---

## 4. Generating Phoenix Traces

Traces are generated by running real queries against the live API. Do this
**after** starting the full Docker Compose stack (Step 2, Option B).

### Run all 11 trace queries automatically

```bash
python -m traces.run_traces
```

You can optionally pass a count or custom base URL:

```bash
python -m traces.run_traces 3                          # first 3 queries only
python -m traces.run_traces all http://localhost:8000   # all queries, custom URL
```

View traces in the Phoenix UI at **http://localhost:6006** after running queries.

---

## 5. Running Evaluations

Evaluations use Phoenix's LLM-as-judge pipeline to score traces against three metrics.

### Prerequisites

- Phoenix packages installed (see Step 1d)
- Phoenix is running: `docker compose --profile phoenix up`
- Traces exist: run `python -m traces.run_traces` first

### Run evaluations

```bash
python -m evaluations.run_evals
```

Results are logged back to Phoenix and visible in the **Evaluations** tab.

---

## 6. Interactive API Docs

| Page | URL |
|------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

## 7. Project Structure Reference

```
src/
├── agent.py                        # LangGraph agent — three system prompts, dispatch + voice routing
├── api.py                          # FastAPI server (POST /chat, /chat/stream, GET /health)
├── otel_routing.py                 # OTel config routing (OTEL_DESTINATION in .env)
├── tools/
│   ├── __init__.py                 # SerpAPI helper (serpapi_request)
│   ├── flights.py                  # search_flights tool
│   ├── hotels.py                   # search_hotels tool
│   └── cultural_guide.py          # get_cultural_guide tool
├── tests/
│   ├── test_tools.py               # 4 tool unit tests (mocked)
│   ├── test_agent.py               # 6 agent graph, routing + dispatch tests
│   ├── test_api.py                 # 8 API + validation tests
│   └── test_otel_routing.py        # 13 OTel routing tests
├── evaluations/
│   ├── run_evals.py                # Phoenix evaluation runner — 3 metrics
│   └── metrics/
│       ├── frustration.py          # USER_FRUSTRATION_PROMPT
│       ├── answer_completeness.py  # ANSWER_COMPLETENESS_PROMPT
│       └── tool_correctness.py     # TOOL_CORRECTNESS_PROMPT
├── traces/
│   └── run_traces.py               # 11 trace queries for Phoenix tracing
├── Dockerfile                      # Container build
├── docker-compose.yml              # TravelShaper + optional Phoenix
├── Makefile                        # Build/test/demo automation
├── pyproject.toml                  # Dependencies
└── .env.example                    # Environment variable template
```

---

## 8. Troubleshooting

**`SERPAPI_API_KEY is not set` error**
Copy `.env.example` to `.env` and add your SerpAPI key, then restart.

**`OPENAI_API_KEY` auth error**
Check your `.env` file.

**Tests fail to collect**
Make sure you are running from `src/` with the venv active. Run `pytest tests/ -v`.

**Phoenix UI shows no traces**
Traces are only generated when real queries hit the live API. Run `python -m traces.run_traces`.

**Phoenix container not starting**
Check that `OTEL_DESTINATION` in `.env` is set to `phoenix`, `both`, or `all`. Phoenix only starts with the `phoenix` Docker Compose profile.

**`ModuleNotFoundError: No module named 'phoenix'`**
Install Phoenix packages:
```bash
pip install arize-phoenix arize-phoenix-evals arize-phoenix-otel \
            openinference-instrumentation-langchain
```

**Docker build fails at `poetry install`**
A `poetry.lock` file is required for reproducible builds. Generate it
with `poetry lock` and commit it before building the image.
