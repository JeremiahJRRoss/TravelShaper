# Software Architecture Document — TravelShaper Travel Assistant

**Version:** 2.0 (v0.1.4)
**Date:** March 2026
**Status:** Implementation phase

---

## 1. Overview

TravelShaper is a LangGraph-based travel planning agent exposed via a FastAPI HTTP API. It accepts a natural-language travel request, dispatches specialized tools to gather flight, hotel, and cultural intelligence, and returns a synthesized travel briefing. All LLM and tool activity is traced via Arize Phoenix.

This document describes the software architecture: component design, data flow, external dependencies, deployment topology, and the decisions behind each choice.

---

## 2. Architecture Goals

TravelShaper's architecture is optimized for five goals:

1. **Deliver useful trip briefings in one request.** The system accepts a single natural-language prompt and returns a synthesized travel briefing with flights, hotels, cultural prep, and interest-based suggestions. No multi-step wizard, no session required.

2. **Keep the agent workflow simple and explainable.** The design preserves the starter app's ReAct-style graph and adds tools without introducing unnecessary orchestration complexity. The graph topology does not change — only the tool registry expands.

3. **Make tool use observable and evaluable.** Phoenix must capture LLM calls, tool calls, and full request traces. Evaluation metrics (user frustration, tool correctness) must be runnable against collected traces.

4. **Support local demo and production discussion.** The architecture must run locally with Docker and also support a credible production deployment story with scaling, latency, and cost considerations for the presentation.

5. **Stay within deliberate product boundaries.** TravelShaper is a planning assistant, not a booking system. It is single-turn, API-only, English-only, and does not include persistent user accounts or saved trips. These are non-goals, not gaps.

---

## 3. System Context

```
┌──────────┐       HTTP POST /chat        ┌──────────────────┐
│  Client   │ ──────────────────────────▶  │  TravelShaper API     │
│  (curl,   │                              │  (FastAPI)       │
│  browser, │  ◀──────────────────────────  │                  │
│  frontend)│       JSON response          └────────┬─────────┘
└──────────┘                                        │
                                                    │ invokes
                                                    ▼
                                           ┌──────────────────┐
                                           │  LangGraph Agent │
                                           │  (ReAct loop)    │
                                           └────────┬─────────┘
                                                    │
                              ┌──────────┬──────────┼──────────┬──────────┐
                              │          │          │          │          │
                              ▼          ▼          ▼          ▼          ▼
                         ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
                         │ OpenAI │ │SerpAPI │ │SerpAPI │ │SerpAPI │ │ DDG    │
                         │ GPT-4o │ │Flights │ │Hotels  │ │Google  │ │ Search │
                         └────────┘ └────────┘ └────────┘ └────────┘ └────────┘

                              ▲
                              │ traces (OTLP)
                              ▼
                         ┌────────────┐
                         │   Phoenix  │
                         │   (local)  │
                         └────────────┘
```

**External dependencies:**

| Service | Purpose | Auth | Failure mode |
|---------|---------|------|-------------|
| OpenAI API | LLM reasoning and synthesis | API key | Fatal — agent cannot function |
| SerpAPI | Flights, hotels, scoped web search | API key | Degraded — falls back to DuckDuckGo |
| DuckDuckGo | General web search | None | Degraded — agent relies on LLM knowledge |
| Phoenix | Trace collection and evaluation | None (local) | Silent — app functions, traces lost |

---

## 4. Component Architecture

### 4.1 Component overview

```
src/
├── api.py                     # HTTP layer — REST + SSE endpoints + validation
├── agent.py                   # Agent graph + dual system prompts + voice routing
├── static/
│   └── index.html             # Browser chat UI (Bebas Neue / Cormorant Garamond / DM Sans)
├── tools/
│   ├── __init__.py            # SerpAPI helper (serpapi_request)
│   ├── flights.py             # search_flights
│   ├── hotels.py              # search_hotels
│   └── cultural_guide.py      # get_cultural_guide
├── evaluations/
│   ├── run_evals.py           # Evaluation runner
│   └── metrics/
│       ├── frustration.py     # USER_FRUSTRATION_PROMPT
│       └── tool_correctness.py# TOOL_CORRECTNESS_PROMPT
├── tests/
│   ├── test_tools.py          # 4 tool tests
│   ├── test_agent.py          # 2 agent graph tests
│   └── test_api.py            # 8 API + validation tests
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env
```

### 4.2 Component responsibilities

**api.py — HTTP layer**

Owns the FastAPI application, request/response models, endpoint routing, and input validation.
Delegates intelligence to the agent. Stateless — no session management.

Endpoints:
- `POST /chat` — synchronous; accepts `{"message": str, "preferences": str|null, "departure": str|null, "destination": str|null}`; returns `{"response": str}`. Used by curl and tests.
- `POST /chat/stream` — SSE streaming; same request body; emits real-time `status`, `place_corrected`, `place_error`, `validation_error`, `done`, and `error` events. Used by the browser UI.
- `GET /health` — returns `{"status": "ok"}`
- `GET /` — serves the browser chat UI (`static/index.html`)

Validation pipeline (runs before agent invocation):
1. **Place validation** — `validate_place()` calls `gpt-4o` to verify departure and destination are real, recognisable places. Corrects misspellings; rejects ambiguous or fictional names.
2. **Preference validation** — `validate_preferences()` calls `gpt-4o` to safety-classify free-form user text. Rejects illegal requests, prompt injection, and off-topic content.

Does not contain business logic beyond validation.

**agent.py — Agent orchestration**

Owns the LangGraph state graph, two voice-matched system prompts, and the tool registry.

Two system prompts selected at runtime by `get_system_prompt(message)`:
- `SYSTEM_PROMPT_SAVE_MONEY` — Bourdain / Billy Dee Williams / Gladwell voice; activated when message contains "save money", "budget", "cheapest", or "spend as little"
- `SYSTEM_PROMPT_FULL_EXPERIENCE` — Robin Leach / Pharrell Williams / Salman Rushdie voice; the default

Graph nodes:
- `llm_call` — invokes gpt-5.3-chat-latest with the appropriate system prompt, message history, and bound tools
- `tool_node` — executes tool calls, returns `ToolMessage` results
- `should_continue` — routes to `tool_node` if tool calls present, otherwise to `END`

The graph topology is unchanged from the starter app:

```
START → llm_call → should_continue?
                     ├── tool calls present → tool_node → llm_call
                     └── no tool calls     → END
```

The extension adds three new tools to the registry. The graph structure itself does not change — the LLM decides which tools to call based on the system prompt and user message.

**tools/ — Tool modules**

Each tool is a self-contained module that:
1. Defines a function decorated with `@tool` (LangChain tool interface)
2. Has a clear docstring that the LLM reads to decide when to invoke it
3. Accepts typed parameters
4. Returns a string (tool output that becomes a `ToolMessage`)
5. Handles its own errors and returns a descriptive message on failure

Tools do not call each other. Tools do not access agent state. Tools are independently testable.

**evaluations/ — Phoenix evaluation scripts**

Standalone scripts that run after traces are collected. Not part of the request path. Read spans from Phoenix, apply evaluation logic, and write results back to Phoenix as annotations.

**tests/ — Test suite**

Unit tests that validate tool schemas, agent graph construction, and API endpoint behavior. Tests mock external API calls — they never require live SerpAPI or OpenAI keys.

---

## 5. Data Flow

### 5.1 Request lifecycle

```
1. Client sends POST /chat {"message": "..."}
      │
2. api.py wraps message as HumanMessage, invokes agent
      │
3. agent.build_agent() returns compiled graph
      │
4. Graph executes: START → llm_call
      │
5. GPT-4o reads system prompt + message + tool descriptions
      │
6. GPT-4o decides: call tools or respond directly
      │
      ├── [Tools needed] → returns AIMessage with tool_calls
      │     │
      │  7. should_continue routes to tool_node
      │     │
      │  8. tool_node executes each tool call:
      │     ├── search_flights(departure, arrival, date, ...)
      │     │     └── HTTP GET to SerpAPI → structured JSON → string
      │     ├── search_hotels(destination, check_in, check_out, ...)
      │     │     └── HTTP GET to SerpAPI → structured JSON → string
      │     ├── get_cultural_guide(destination)
      │     │     └── HTTP GET to SerpAPI → web results → string
      │     └── web_search(query)
      │           └── DuckDuckGo → string
      │     │
      │  9. tool_node returns list of ToolMessages
      │     │
      │  10. Graph loops back to llm_call
      │     │
      │  11. GPT-4o reads tool results, synthesizes briefing
      │     │
      │  12. should_continue → END (no more tool calls)
      │
      └── [No tools needed] → returns AIMessage with content
            │
13. api.py extracts final message content
      │
14. Client receives {"response": "..."}
```

### 5.2 Data shapes

**Agent state:**

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
```

The state is a flat list of messages. Each graph node appends to it. LangGraph's `operator.add` reducer handles concatenation.

**Tool inputs (Pydantic or typed args):**

```python
# search_flights
{
    "departure_id": "SFO",        # IATA airport code
    "arrival_id": "NRT",          # IATA airport code
    "outbound_date": "2026-10-15", # YYYY-MM-DD
    "return_date": "2026-10-25",   # YYYY-MM-DD
    "currency": "USD",
    "type": 1                      # 1=round trip, 2=one way
}

# search_hotels
{
    "q": "Tokyo hotels",
    "check_in_date": "2026-10-15",
    "check_out_date": "2026-10-25",
    "adults": 2,
    "currency": "USD",
    "sort_by": 3                   # 3=lowest price, 13=highest rating
}

# get_cultural_guide
{
    "destination": "Tokyo, Japan"
}
```

**Tool outputs:**

All tools return strings. For structured sources (SerpAPI flights/hotels), the tool formats the JSON response into a readable summary. For web search tools, the raw search snippets are returned. The LLM handles final synthesis.

### 5.3 Partial-input behavior

Users will not always provide all five expected inputs (origin, destination, dates, budget, interests). The architecture handles this gracefully:

- **Missing dates:** The agent searches without date constraints or uses a reasonable near-future window. Flight and hotel tools degrade to less specific results, not errors.
- **Missing budget preference:** The agent defaults to a balanced approach — showing a range of options without strong ranking bias.
- **Missing interests:** The agent skips interest-based web search and focuses on flights, hotels, and cultural prep.
- **Missing origin:** The agent cannot search flights but can still search hotels, cultural info, and interests for the destination.

The guiding principle: provide the best possible partial briefing rather than refuse to act or depend on follow-up state that doesn't exist in a single-turn system.

---

## 6. Technology Decisions

### 6.1 LangGraph over plain LangChain

The starter app uses LangGraph's `StateGraph` rather than LangChain's `AgentExecutor`. This gives explicit control over the agent loop: we can see exactly which nodes fire, in what order, and with what state. Phoenix traces map cleanly to graph nodes, making observability richer.

The ReAct loop (llm → tool → llm → ... → end) is the simplest useful agent pattern and matches the assessment's scope.

### 6.2 GPT-5.3 as the reasoning model

gpt-5.3-chat-latest is used for the agent because:
- Strong agentic reasoning and synthesis capability
- Strong tool-calling support (parallel tool calls, reliable structured arguments)
- Good at synthesis tasks (combining multiple tool results into a coherent briefing)
- Temperature is passed via `model_kwargs={"temperature": 1}` — the only value gpt-5.3-chat-latest accepts

### 6.3 SerpAPI as the data layer

SerpAPI was chosen because:
- One API key powers three tool types (flights, hotels, general search)
- Google Flights and Google Hotels engines return structured JSON — not raw HTML scraping
- Free tier (250 searches/month) is sufficient for development and demo
- Python `requests` library is the only dependency — no SDK required

The alternative was direct web scraping or dedicated APIs (Amadeus, Booking.com). Scraping is brittle. Dedicated APIs require separate accounts and approval processes that conflict with the time constraint.

### 6.4 DuckDuckGo as fallback

Already present in the starter code. No API key needed. Provides general web search coverage for interest discovery, cultural questions, and edge cases that SerpAPI doesn't cover.

### 6.5 FastAPI for the HTTP layer

Already present in the starter code. Async-capable, automatic OpenAPI docs at `/docs`, Pydantic validation on request/response models. No reason to change it.

### 6.6 Phoenix for observability

Phoenix was chosen because:
- Required by the assessment
- OpenTelemetry-native — traces capture LLM calls, tool usage, and latency automatically
- Local-first — runs as a local server, no cloud account needed
- Built-in evaluation framework for user frustration and custom metrics
- LangGraph integration via `openinference-instrumentation-langchain`

---

## 7. Observability Architecture

### 7.1 Instrumentation

Phoenix is initialized at application startup before the agent is built. The LangChain/LangGraph instrumentor auto-captures:

```python
from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor

import os
endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
tracer_provider = register(project_name="travelshaper", endpoint=endpoint)
LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
```

This is wrapped in a `try/except ImportError` block in agent.py so the app functions without Phoenix installed.

### 7.2 What gets traced

| Span type | Captured data |
|-----------|---------------|
| LLM span | Model name, input messages, output message, token counts (prompt + completion), latency, tool call decisions |
| Tool span | Tool name, input arguments, output content, execution duration |
| Chain span | End-to-end trace from `/chat` request to response, linking all child spans |

### 7.3 Trace structure

A typical travel briefing query produces this trace:

```
[Chain] POST /chat
  └── [Chain] agent.invoke
        ├── [LLM] gpt-4o (initial — decides to call tools)
        ├── [Tool] search_flights
        ├── [Tool] search_hotels
        ├── [Tool] get_cultural_guide
        └── [LLM] gpt-4o (synthesis — produces final briefing)
```

Total spans per query: typically 5–8 depending on how many tools are dispatched and whether the LLM loops more than once.

### 7.4 Evaluation pipeline

Evaluations run as a separate batch process after traces are collected:

```
Phoenix (stored traces)
    │
    ▼
run_evals.py
    ├── Fetch spans from Phoenix
    ├── Apply frustration evaluator
    ├── Apply tool correctness evaluator
    └── Write annotations back to Phoenix
```

Evaluators are LLM-as-judge functions: they send the trace data to GPT-4o with an evaluation prompt and receive a label (e.g., `frustrated: true/false`, `tool_correct: true/false`) plus an explanation.

---

## 8. Tool Design Patterns

### 8.1 Tool interface contract

Every tool follows the same pattern:

```python
from langchain_core.tools import tool

@tool
def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str,
) -> str:
    """Search for flights between two airports.
    
    Use this tool when the user wants to find flights.
    departure_id and arrival_id should be IATA airport codes (e.g., SFO, NRT, CDG).
    Dates should be YYYY-MM-DD format.
    """
    # 1. Build SerpAPI request
    # 2. Execute HTTP call
    # 3. Parse response
    # 4. Format as readable string
    # 5. Return string (or error message)
```

**The docstring is critical.** GPT-4o reads it to decide when to invoke the tool and what arguments to pass. A vague docstring means unreliable tool selection.

### 8.2 Error handling strategy

Tools never raise exceptions into the agent loop. On failure, they return a descriptive error string that the LLM can work with:

```python
try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.Timeout:
    return "Flight search timed out. Please try again."
except requests.HTTPError as e:
    return f"Flight search failed: {e}"
```

This lets the agent gracefully degrade: "I couldn't find flight data, but here's what I know about Tokyo from web search..."

### 8.3 SerpAPI call pattern

All SerpAPI tools follow the same HTTP pattern:

```python
import os
import requests

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_URL = "https://serpapi.com/search"

def _serpapi_request(params: dict) -> dict:
    params["api_key"] = SERPAPI_KEY
    response = requests.get(SERPAPI_URL, params=params, timeout=15)
    response.raise_for_status()
    return response.json()
```

Each tool sets the `engine` parameter to the appropriate SerpAPI engine:
- `search_flights` → `engine=google_flights`
- `search_hotels` → `engine=google_hotels`
- `get_cultural_guide` → `engine=google` (with scoped queries)

### 8.4 Response formatting

SerpAPI returns large JSON payloads. Tools extract and format the relevant fields rather than passing raw JSON to the LLM (which would waste tokens and reduce synthesis quality).

Example for flights:
```python
def _format_flights(data: dict) -> str:
    flights = data.get("best_flights", []) + data.get("other_flights", [])
    if not flights:
        return "No flights found for these dates."
    
    results = []
    for f in flights[:5]:  # Top 5 only
        legs = f.get("flights", [])
        airline = legs[0].get("airline", "Unknown") if legs else "Unknown"
        price = f.get("price", "N/A")
        duration = f.get("total_duration", "N/A")
        stops = len(legs) - 1
        results.append(f"- {airline}: ${price}, {duration}min, {stops} stop(s)")
    
    return "Flight options:\n" + "\n".join(results)
```

This keeps tool output concise and focused. The LLM adds context, ranking, and explanation during synthesis.

### 8.5 Adapter design principle

Tools return TravelShaper-owned output formats, not raw vendor JSON. This protects the agent from upstream response drift — if SerpAPI changes a field name or nesting structure, only the tool adapter changes, not the system prompt or synthesis logic. It also makes evaluation easier, since tool outputs have a consistent shape regardless of which provider backs them.

In the current implementation, this means each tool extracts relevant fields and formats them into a readable string. In a future version, tools could return structured Pydantic models that the synthesis layer consumes directly.

---

## 9. System Prompt Design

TravelShaper uses two system prompts, selected at runtime based on the budget keyword in the user's message.

### 9.1 Voice routing

```python
def get_system_prompt(message: str) -> str:
    lower = message.lower()
    if "save money" in lower or "budget" in lower or "cheapest" in lower:
        return SYSTEM_PROMPT_SAVE_MONEY
    return SYSTEM_PROMPT_FULL_EXPERIENCE
```

### 9.2 SYSTEM_PROMPT_SAVE_MONEY — Bourdain / Billy Dee / Gladwell

Activated for budget-preference queries. Muscular, direct prose with strong opinions and zero tourist-trap tolerance. Saving money is framed as intelligence, not compromise. Every recommendation comes with a Gladwell-style non-obvious insight. DuckDuckGo searches are phrased like a journalist on a beat.

### 9.3 SYSTEM_PROMPT_FULL_EXPERIENCE — Leach / Pharrell / Rushdie

The default. Robin Leach's theatrical grandeur fused with Pharrell's warm, groovy inclusivity, underpinned by Rushdie's narrative depth. Cities are mythology. Sentences earn their length. Luxury is elevated without being intimidating.

### 9.4 Shared instructions (both prompts)

Both prompts require:
- Cinematic opening hook before any sections
- Four named sections: Getting There · Where to Stay · Before You Go · What to Do
- Mandatory markdown hyperlinks for every named place, restaurant, hotel, and attraction
- No fabricated facts — only tool-grounded data for logistics
- Parallel tool dispatch in a single turn
- One memorable closing line

See `docs/system-prompt-spec.md` for the full prompt text and design rationale.

---

## 10. Deployment Architecture

### 10.1 Local development

```
┌─────────────────────────────────────────────┐
│  Developer machine                          │
│                                             │
│  ┌──────────┐     ┌──────────┐              │
│  │ TravelShaper  │     │ Phoenix  │              │
│  │ :8000    │────▶│ :6006    │              │
│  └────┬─────┘     └──────────┘              │
│       │                                     │
└───────┼─────────────────────────────────────┘
        │
        ▼ (outbound HTTPS)
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ OpenAI  │  │ SerpAPI │  │  DDG    │
   └─────────┘  └─────────┘  └─────────┘
```

### 10.2 Docker Compose

```yaml
# docker-compose.yml
services:
  travelshaper:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - phoenix

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
```

### 10.3 Production architecture (proposed)

This architecture is presented in the assessment but not implemented.

```
                        ┌──────────────┐
                        │ Load Balancer│
                        │  (ALB/NLB)   │
                        └──────┬───────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
          ┌──────▼──────┐ ┌───▼────┐ ┌──────▼──────┐
          │  TravelShaper    │ │TravelShaper │ │  TravelShaper    │
          │  Instance 1 │ │Inst. 2 │ │  Instance 3 │
          └──────┬──────┘ └───┬────┘ └──────┬──────┘
                 │            │             │
                 └─────────┬──┘─────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──┐  ┌──────▼──┐  ┌─────▼─────┐
       │ OpenAI  │  │ SerpAPI │  │  Redis    │
       │  API    │  │         │  │  (cache + │
       └─────────┘  └─────────┘  │  sessions)│
                                 └─────┬─────┘
                                       │
                                 ┌─────▼─────┐
                                 │ Phoenix / │
                                 │ OTEL      │
                                 │ Collector │
                                 └───────────┘
```

**Scaling strategy:**

| Component | Scaling approach | Rationale |
|-----------|-----------------|-----------|
| TravelShaper API | Horizontal — multiple stateless instances behind a load balancer | Each request is independent; no shared state |
| OpenAI API | Managed by OpenAI; scale via API tier and rate limits | No self-hosting required |
| SerpAPI | Managed by SerpAPI; scale via plan tier | Free tier is sufficient for demo; paid plans for production |
| Redis | Single instance or cluster for session cache | Stores conversation history for multi-turn; caches repeated SerpAPI queries |
| Phoenix / OTEL | Separate collector service; async export from app instances | Decouples observability from request latency |

**Latency optimization:**

- Parallel tool execution: LangGraph can dispatch multiple tool calls in a single turn. SerpAPI calls execute concurrently.
- Response caching: Redis caches SerpAPI responses keyed by query parameters. Identical queries within a TTL window skip the API call.
- Async trace export: OTLP spans are exported asynchronously so tracing does not block the response path.
- Model selection: GPT-4o-mini for simpler queries (intent parsing), GPT-4o for synthesis. Reduces cost and latency for straightforward requests.

**Cost optimization:**

| Cost driver | Optimization |
|-------------|-------------|
| OpenAI tokens | Cap tool output length in formatting functions; avoid passing raw SerpAPI JSON |
| SerpAPI calls | Cache responses; batch related queries where possible |
| Compute | Stateless containers scale to zero when idle (ECS Fargate, Cloud Run) |
| Phoenix | Self-hosted; no per-trace cost |

---

## 11. Security Considerations

### 11.1 Current implementation

| Concern | Status |
|---------|--------|
| API key storage | `.env` file, excluded from git via `.gitignore` |
| API authentication | None — open endpoint. Acceptable for local demo. |
| Input validation | Pydantic model validates request shape; LLM handles content interpretation |
| Prompt injection | System prompt is hardcoded; user message is treated as untrusted input by the LLM |
| Data persistence | No user data stored beyond Phoenix traces |
| HTTPS | Not configured — local HTTP only |

### 11.2 Production additions

- API key or JWT authentication on `/chat`
- Rate limiting per client
- HTTPS via load balancer TLS termination
- Input sanitization before tool dispatch
- Audit logging for all tool calls
- Phoenix traces redacted of PII before long-term storage

---

## 12. Testing Strategy

### 12.1 Test categories

| Category | What it validates | External calls |
|----------|-------------------|----------------|
| Tool schema tests | Input types, output format, docstring presence | Mocked |
| Agent graph tests | Correct nodes, edges, and compilation | Mocked |
| API endpoint tests | HTTP status codes, response shapes | Mocked |
| Integration tests (manual) | Full request with live APIs during demo | Live |

### 12.2 Mocking approach

Tests use `unittest.mock.patch` to replace external API calls:

```python
@patch("tools.flights._serpapi_request")
def test_search_flights_returns_formatted_string(mock_request):
    mock_request.return_value = {
        "best_flights": [{
            "flights": [{"airline": "ANA"}],
            "price": 687,
            "total_duration": 840
        }]
    }
    result = search_flights("SFO", "NRT", "2026-10-15", "2026-10-25")
    assert "ANA" in result
    assert "687" in result
```

No test requires a live API key. The CI pipeline can run tests without secrets configured.

### 12.3 Test execution

```bash
poetry run pytest tests/ -v
```

---

## 13. Evolution Path

The architecture is designed to evolve without rewrites. Each phase extends the existing structure.

**Near-term (next iteration):**
- Structured preference extraction — parse user input into a typed preferences object before tool dispatch, rather than relying entirely on the LLM to interpret freeform text
- Bounded result ranking — score and sort tool results deterministically before passing to the LLM for synthesis
- Timeout and fallback policies — per-tool timeout budgets with graceful degradation

**Medium-term (production readiness):**
- Redis-backed session memory — enables multi-turn conversation without changing the graph topology (messages are loaded from Redis into state at the start of each request)
- Response caching — cache SerpAPI results by query parameters with a TTL, reducing cost and latency for repeated queries
- LangGraph subgraphs — split the single ReAct loop into nested subgraphs for transport, lodging, and destination research if the tool set grows beyond 6–8 tools

**Long-term (product expansion):**
- Authenticated users and saved trips
- Destination comparison mode ("Barcelona vs. Lisbon in October")
- Itinerary generation with day-by-day scheduling
- Multi-agent specialization — separate planning agents for transport, activities, and cultural prep, coordinated by a supervisor agent

Each phase is additive. The current graph, tools, and API surface remain stable through all three phases.

---

## 14. Key Architectural Decisions Log

| Decision | Choice | Alternatives considered | Rationale |
|----------|--------|------------------------|-----------|
| Agent framework | LangGraph StateGraph | LangChain AgentExecutor, raw OpenAI function calling | LangGraph provides explicit graph control, better trace visibility, matches starter code |
| LLM provider | OpenAI GPT-4o | Anthropic Claude, local models | Starter code uses it; strong tool-calling support; well-documented |
| Travel data source | SerpAPI | Amadeus, Booking.com, web scraping | Single API key for flights + hotels + search; structured JSON; free tier sufficient |
| General search | DuckDuckGo | Google Custom Search, Bing | Already in starter code; no API key needed |
| Observability | Arize Phoenix | LangSmith, Datadog, custom logging | Required by assessment; local-first; built-in evaluation framework |
| HTTP framework | FastAPI | Flask, Django | Already in starter code; async-capable; auto-generated docs |
| Deployment | Docker + Docker Compose | Bare Python, Kubernetes | Docker is assessment requirement; Compose simplifies Phoenix co-deployment |
| Test runner | pytest | unittest | Cleaner syntax; better fixture support; standard in Python ecosystem |
| Tool output format | Formatted strings | Structured Pydantic models | LLM consumes strings naturally; structured models add complexity without benefit in single-turn design |

**Explicitly deferred:**

| Decision | Why deferred |
|----------|-------------|
| Booking engine | Out of product scope; TravelShaper recommends, it does not transact |
| Persistent conversation memory | Single-turn is sufficient for assessment; Redis-backed memory is a Phase 2 addition |
| Dedicated rail/ferry APIs | Coverage is thin and approval processes are slow; general web search covers this adequately for now |
| Frontend application | API-only is cleaner for assessment; frontend adds no architectural insight |
| Multi-language support | English-only matches the target user; i18n is a product decision, not an architecture blocker |

---

## 15. Constraints and Assumptions

**Constraints:**
- 4–6 hour implementation window
- Single API key for travel data (SerpAPI free tier, 250 searches/month)
- Starter code uses Poetry, LangGraph, FastAPI — these are fixed
- Assessment requires Phoenix specifically, not alternative observability tools

**Assumptions:**
- The user provides enough context in a single message for useful tool dispatch
- SerpAPI free tier is sufficient for development and a live demo (~60–125 full queries)
- GPT-4o reliably selects the correct tools given a well-crafted system prompt
- Phoenix local server is stable enough for trace collection during the demo
- The evaluator (interviewer) has access to OpenAI and SerpAPI keys for running the project

---

## 16. Glossary

| Term | Definition |
|------|-----------|
| Agent | A LangGraph state machine that loops between LLM reasoning and tool execution |
| ReAct | Reasoning + Acting — the pattern where an LLM reasons about what to do, acts (calls a tool), observes the result, and repeats |
| Tool | A Python function registered with LangChain's `@tool` decorator, callable by the LLM |
| Span | A single unit of work in a trace (one LLM call, one tool execution) |
| Trace | An end-to-end record of a user request, composed of multiple spans |
| Phoenix | Arize's open-source observability platform for LLM applications |
| OpenInference | The semantic convention for LLM observability spans, built on OpenTelemetry |
| SerpAPI | A web API that returns structured Google search results (flights, hotels, general search) |
| OTEL / OTLP | OpenTelemetry / OpenTelemetry Protocol — the standard for exporting traces |
