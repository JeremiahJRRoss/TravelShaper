# Software Architecture Document — TravelShaper Travel Assistant

**Version:** 2.2 (v0.5.0)
**Date:** April 2026
**Status:** Implementation phase

---

## 1. Overview

TravelShaper is a LangGraph-based travel planning agent exposed via a FastAPI HTTP API. It accepts a natural-language travel request, dispatches specialized tools to gather flight, hotel, and cultural intelligence, and returns a synthesized travel briefing. All LLM and tool activity is traced via configurable OpenTelemetry routing that supports Arize Phoenix, Arize Cloud, any OTLP-compatible backend, or combinations thereof. Semantic conventions are configurable between OpenInference (Phoenix/Arize native) and OTel GenAI (standard backends).

This document describes the software architecture: component design, data flow, external dependencies, deployment topology, and the decisions behind each choice.

---

## 2. Architecture Goals

TravelShaper's architecture is optimized for five goals:

1. **Deliver useful trip briefings in one request.** The system accepts a single natural-language prompt and returns a synthesized travel briefing with flights, hotels, cultural prep, and interest-based suggestions. No multi-step wizard, no session required.

2. **Keep the agent workflow simple and explainable.** The design preserves the starter app's ReAct-style graph and adds tools without introducing unnecessary orchestration complexity. The graph topology does not change — only the tool registry expands.

3. **Make tool use observable and evaluable.** Configurable OTel routing captures LLM calls, tool calls, and full request traces. The destination is controlled by `OTEL_DESTINATION` in `.env` — Phoenix, Arize Cloud, any OTLP-compatible backend (Jaeger, Tempo, Honeycomb, etc.), combinations of all three, or none. Semantic conventions are controlled by `OTEL_SEMCONV` — OpenInference for Phoenix/Arize, GenAI for standard backends. Evaluation metrics (user frustration, tool correctness, answer completeness) are runnable against collected traces.

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
                         │ GPT    │ │Flights │ │Hotels  │ │Google  │ │ Search │
                         └────────┘ └────────┘ └────────┘ └────────┘ └────────┘

                              ▲
                              │ traces (OTLP)
                              ▼
                    ┌────────────┐    ┌─────────────┐    ┌──────────┐
                    │   Phoenix  │    │ Arize Cloud │    │ Generic  │
                    │   (local)  │    │ (managed)   │    │  OTLP    │
                    └────────────┘    └─────────────┘    └──────────┘
```

**External dependencies:**

| Service | Purpose | Auth | Failure mode |
|---------|---------|------|-------------|
| OpenAI API | LLM reasoning and synthesis | API key | Fatal — agent cannot function |
| SerpAPI | Flights, hotels, scoped web search | API key | Degraded — falls back to DuckDuckGo |
| DuckDuckGo | General web search | None | Degraded — agent relies on LLM knowledge |
| Phoenix | Trace collection and evaluation (optional) | None (local) or API key (Cloud) | Silent — app functions, traces lost |
| Arize Cloud | Managed trace collection (optional) | API key + Space ID | Silent — app functions, traces lost |

---

## 4. Component Architecture

### 4.1 Component overview

```
src/
├── api.py                     # HTTP layer — REST + SSE endpoints + validation
├── agent.py                   # Agent graph + three system prompts + voice routing
├── otel_routing.py            # OTel config routing (OTEL_DESTINATION + OTEL_SEMCONV in .env)
├── static/
│   └── index.html             # Browser chat UI (Bebas Neue / Cormorant Garamond / DM Sans)
├── tools/
│   ├── __init__.py            # SerpAPI helper (serpapi_request)
│   ├── flights.py             # search_flights
│   ├── hotels.py              # search_hotels
│   └── cultural_guide.py      # get_cultural_guide
├── evaluations/
│   ├── run_evals.py           # Evaluation runner — 3 LLM-as-judge metrics, trace-level
│   ├── export_spans.py        # Export Phoenix spans to CSV
│   └── metrics/
│       ├── frustration.py     # USER_FRUSTRATION_PROMPT (reference)
│       ├── answer_completeness.py # ANSWER_COMPLETENESS_PROMPT
│       └── tool_correctness.py# TOOL_CORRECTNESS_PROMPT
├── traces/
│   └── run_traces.py          # Trace generator — 11 queries
├── tests/
│   ├── test_tools.py          # 4 tool tests
│   ├── test_agent.py          # 6 agent graph, routing + dispatch tests
│   ├── test_api.py            # 8 API + validation tests
│   └── test_otel_routing.py   # 21 OTel routing + semconv tests
├── Dockerfile
├── docker-compose.yml
├── Makefile                   # Build/test/demo automation
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
1. **Place validation** — `validate_place()` calls `gpt-4o-mini` to verify departure and destination are real, recognisable places. Corrects misspellings; rejects ambiguous or fictional names.
2. **Preference validation** — `validate_preferences()` calls `gpt-4o-mini` to safety-classify free-form user text. Rejects illegal requests, prompt injection, and off-topic content.

Custom spans in `api.py` branch on `OTEL_SEMCONV` to set convention-appropriate request-level attributes (see §7.5).

Does not contain business logic beyond validation.

**agent.py — Agent orchestration**

Owns the LangGraph state graph, three system prompts (dispatch + two voice-matched synthesis prompts), and the tool registry. At startup, initializes the observability stack by calling `otel_routing.build_tracer_provider()` and `otel_routing.get_semconv()`, then instruments LangChain with the appropriate instrumentor package.

Three system prompts:
- `DISPATCH_PROMPT` — minimal (~150 tokens) tool-routing instructions; used on the first `llm_call` before tools have run
- `SYSTEM_PROMPT_SAVE_MONEY` — Bourdain / Billy Dee Williams / Gladwell voice; activated during synthesis when message contains "save money", "budget", "cheapest", or "spend as little"
- `SYSTEM_PROMPT_FULL_EXPERIENCE` — Robin Leach / Pharrell Williams / Salman Rushdie voice; the default synthesis prompt

Graph nodes:
- `llm_call` — invokes gpt-5.3-chat-latest with the appropriate system prompt (dispatch or synthesis), message history, and bound tools
- `tool_node` — executes tool calls, returns `ToolMessage` results
- `should_continue` — routes to `tool_node` if tool calls present, otherwise to `END`

The graph topology is unchanged from the starter app:

```
START → llm_call → should_continue?
                     ├── tool calls present → tool_node → llm_call
                     └── no tool calls     → END
```

**otel_routing.py — Telemetry configuration**

Owns all OpenTelemetry configuration. Reads `OTEL_DESTINATION` and `OTEL_SEMCONV` from `.env` and builds a `TracerProvider` with a `Resource` whose `service.name` is set from `OTEL_PROJECT_NAME` (default: `travelshaper`) and the appropriate OTLP exporters attached.

Valid values for `OTEL_DESTINATION`:
- `phoenix` — sends traces to local Phoenix or Phoenix Cloud
- `arize` — sends traces to Arize Cloud (requires `ARIZE_API_KEY` + `ARIZE_SPACE_ID`)
- `otlp` — sends traces to any OTLP-compatible backend; `OTLP_PROTOCOL` selects transport (`http` default or `grpc`)
- `both` — sends traces to Phoenix and Arize simultaneously
- `all` — sends traces to Phoenix, Arize, and generic OTLP simultaneously
- `none` — disables all telemetry

Valid values for `OTEL_SEMCONV`:
- `openinference` (default) — OpenInference conventions for Phoenix/Arize
- `genai` — OTel GenAI conventions for standard backends

Called once at startup from `agent.py`:
```python
from otel_routing import build_tracer_provider, get_semconv

_tracer_provider = build_tracer_provider()
_semconv = get_semconv()

if _semconv == "genai":
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    LangchainInstrumentor().instrument(tracer_provider=_tracer_provider)
else:
    from openinference.instrumentation.langchain import LangChainInstrumentor
    LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
```

**tools/ — Tool modules**

Each tool is a self-contained module that defines a function decorated with `@tool`, has a clear docstring for LLM routing, accepts typed parameters, returns a string, and handles its own errors. Tools do not call each other, do not access agent state, and are independently testable. Each tool returns the top 3 results.

**evaluations/ — Phoenix evaluation scripts**

Standalone scripts that run after traces are collected. Not part of the request path. Read spans from Phoenix, apply evaluation logic, and write results back to Phoenix as annotations.

**tests/ — Test suite**

39 unit tests across four test files that validate tool schemas, agent graph construction, prompt routing (including phase detection), API endpoint behavior, OTel routing logic, and semantic convention selection. Tests mock external API calls — they never require live SerpAPI or OpenAI keys.

---

## 5. Data Flow

### 5.1 Request lifecycle

```
1. Client sends POST /chat {"message": "..."}
      │
2. api.py validates place names + preferences (gpt-4o-mini)
      │
3. api.py wraps message as HumanMessage, invokes agent
      │
4. agent.build_agent() returns compiled graph
      │
5. Graph executes: START → llm_call (DISPATCH phase)
      │
6. GPT-5.3 reads DISPATCH_PROMPT + message + tool descriptions
      │
7. GPT-5.3 decides which tools to call, returns AIMessage with tool_calls
      │
8. should_continue routes to tool_node
      │
9. tool_node executes each tool call:
      │   ├── search_flights → SerpAPI → structured JSON → string
      │   ├── search_hotels → SerpAPI → structured JSON → string
      │   ├── get_cultural_guide → SerpAPI → web results → string
      │   └── duckduckgo_search → DuckDuckGo → string
      │
10. tool_node returns list of ToolMessages
      │
11. Graph loops back to llm_call (SYNTHESIS phase)
      │
12. GPT-5.3 reads voice prompt (save-money or full-experience) + tool results
      │
13. GPT-5.3 synthesizes briefing, returns AIMessage with content
      │
14. should_continue → END (no more tool calls)
      │
15. api.py extracts final message content
      │
16. Client receives {"response": "..."}
```

### 5.2 Data shapes

**Agent state:**

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
```

The state is a flat list of messages. Each graph node appends to it. LangGraph's `operator.add` reducer handles concatenation.

**Tool inputs and outputs:**

All tools return strings. For structured sources (SerpAPI flights/hotels), the tool formats the JSON response into a readable summary with the top 3 results. For web search tools, the raw search snippets are returned. The LLM handles final synthesis.

### 5.3 Partial-input behavior

Users will not always provide all five expected inputs. The architecture handles this gracefully by providing the best possible partial briefing rather than refusing to act.

---

## 6. Technology Decisions

### 6.1 LangGraph over plain LangChain

The starter app uses LangGraph's `StateGraph` rather than LangChain's `AgentExecutor`. This gives explicit control over the agent loop: we can see exactly which nodes fire, in what order, and with what state.

### 6.2 GPT-5.3 as the reasoning model

gpt-5.3-chat-latest is used for the agent for strong agentic reasoning, tool-calling support, and synthesis capability.

### 6.3 GPT-4o-mini as the validation model

gpt-4o-mini is used for place validation and preference validation classifiers — faster and cheaper than gpt-4o for simple classification tasks.

### 6.4–6.7

SerpAPI as data layer (one key, three tool types), DuckDuckGo as fallback (no key needed), FastAPI for HTTP (already in starter), configurable OTel routing for observability (vendor-neutral, supports any backend).

---

## 7. Observability Architecture

For the full trace lifecycle, span anatomy, and evaluation pipeline, see [docs/traces-architecture.md](traces-architecture.md).

### 7.1 Instrumentation

Telemetry is initialized at application startup before the agent is built. The `otel_routing` module reads `OTEL_DESTINATION` and `OTEL_SEMCONV` from `.env` and builds a `TracerProvider` with the appropriate exporters and instrumentor.

### 7.2 What gets traced

| Span type | Captured data |
|-----------|---------------|
| LLM span | Model name, input messages, output message, token counts, latency, tool call decisions |
| Tool span | Tool name, input arguments, output content, execution duration |
| Chain span | End-to-end trace from `/chat` request to response, linking all child spans |
| Request span | Custom: destination, departure, budget mode, preferences flag |

### 7.3 Trace structure

A typical travel briefing query produces 5–8 spans depending on how many tools are dispatched.

### 7.4 Evaluation pipeline

Evaluations run as a separate batch process after traces are collected. Three LLM-as-judge metrics: User Frustration, Tool Usage Correctness, and Answer Completeness.

### 7.5 OpenTelemetry vs OpenInference — Two Layers of Observability

TravelShaper's observability stack has two distinct layers: OpenTelemetry (transport) and semantic conventions (meaning). The semantic convention layer is configurable via `OTEL_SEMCONV`:

| OTEL_SEMCONV | Package | Key attributes | Best for |
|---|---|---|---|
| `openinference` (default) | `openinference-instrumentation-langchain` | `input.value`, `output.value`, `llm.model_name` | Phoenix, Arize |
| `genai` | `opentelemetry-instrumentation-langchain` | `gen_ai.request.model`, `gen_ai.usage.input_tokens` | Jaeger, Tempo, Datadog, Honeycomb |

Custom spans in `api.py` also branch on `OTEL_SEMCONV`: OpenInference mode sets `SpanAttributes.INPUT_VALUE` and `SpanAttributes.OUTPUT_VALUE`; GenAI mode uses standard span events (`gen_ai.content.prompt`, `gen_ai.content.completion`) and attributes (`gen_ai.system`, `gen_ai.request.model`).

---

## 8–13. Tool Design, System Prompts, LLM Decisions, Validation, Deployment, Security

These sections are unchanged from v0.3.2. Key points: tools return top 3 results, three system prompts (dispatch + two voices), gpt-4o-mini for validation (fail-open for places, fail-closed for preferences), Docker Compose with optional Phoenix profile.

---

## 14. Testing Strategy

### 14.1 Test categories

| Category | File | Count | What it validates | External calls |
|----------|------|-------|-------------------|----------------|
| Tool schema tests | test_tools.py | 4 | Input types, output format, docstring presence | Mocked |
| Agent graph tests | test_agent.py | 6 | Nodes, edges, routing, dispatch vs synthesis phase | Mocked |
| API endpoint tests | test_api.py | 8 | HTTP status codes, response shapes, validation pipeline | Mocked |
| OTel routing tests | test_otel_routing.py | 21 | Exporter creation, credential handling, destination selection, generic OTLP, headers parsing, gRPC protocol, fallback, project name, semantic convention selection | Mocked |
| Integration tests (manual) | — | — | Full request with live APIs during demo | Live |

### 14.2 Mocking approach

Tests use `unittest.mock.patch` to replace external API calls. OTel routing tests additionally use `patch.dict(os.environ)` to control environment variables. No test requires a live API key.

### 14.3 Test execution

```bash
pytest tests/ -v    # 39 passed
```

---

## 15. Evolution Path

**Completed (v0.3.0–v0.5.0):**
- Configurable OTel routing (phoenix / arize / otlp / both / all / none)
- Token reduction via condensed prompts and phase-based dispatch
- Validation model optimization (gpt-4o → gpt-4o-mini)
- Generic OTLP destination with HTTP and gRPC transport
- Configurable semantic conventions (openinference / genai)

**Near-term (next iteration):**
- Structured preference extraction
- Bounded result ranking
- Timeout and fallback policies

**Medium-term (production readiness):**
- Redis-backed session memory
- Response caching
- LangGraph subgraphs for larger tool sets

**Long-term (product expansion):**
- Authenticated users and saved trips
- Destination comparison mode
- Multi-agent specialization

---

## 16. Key Architectural Decisions Log

| Decision | Choice | Alternatives considered | Rationale |
|----------|--------|------------------------|-----------|
| Agent framework | LangGraph StateGraph | LangChain AgentExecutor, raw OpenAI function calling | Explicit graph control, better trace visibility |
| Reasoning model | GPT-5.3-chat-latest | Anthropic Claude, local models | Strong tool-calling, starter code uses OpenAI |
| Validation model | GPT-4o-mini | GPT-4o, keyword blocklist | Faster/cheaper for classification; sufficient accuracy |
| Travel data source | SerpAPI | Amadeus, Booking.com, web scraping | Single key for 3 tool types; structured JSON |
| General search | DuckDuckGo | Google Custom Search | No API key needed; already in starter code |
| Observability | Configurable OTel (Phoenix/Arize/OTLP/both/all/none) | Phoenix-only, LangSmith | Vendor-neutral; supports production transition to any OTLP backend |
| Semantic conventions | Configurable (OpenInference/GenAI) | OpenInference-only | Supports both LLM-native and standard OTel backends |
| HTTP framework | FastAPI | Flask, Django | Already in starter code; async-capable |
| Deployment | Docker + Docker Compose | Bare Python, Kubernetes | Docker is assessment requirement |
| Test runner | pytest | unittest | Cleaner syntax; standard in ecosystem |
| Prompt strategy | 3 prompts (dispatch + 2 voice) | 1 prompt, 2 prompts | Dispatch saves ~300-600 tokens; voices prevent blending |

---

## 17. Constraints and Assumptions

(Unchanged from previous version.)

---

## 18. Glossary

| Term | Definition |
|------|-----------|
| Agent | A LangGraph state machine that loops between LLM reasoning and tool execution |
| ReAct | Reasoning + Acting — the pattern where an LLM reasons about what to do, acts (calls a tool), observes the result, and repeats |
| Tool | A Python function registered with LangChain's `@tool` decorator, callable by the LLM |
| Span | A single unit of work in a trace (one LLM call, one tool execution) |
| Trace | An end-to-end record of a user request, composed of multiple spans |
| Phoenix | Arize's open-source observability platform for LLM applications |
| OpenInference | An open-source semantic convention defining what attributes LLM spans carry |
| GenAI semantic conventions | OTel-standard attributes for LLM spans (gen_ai.request.model, etc.) |
| SerpAPI | A web API that returns structured Google search results |
| OTEL / OTLP | OpenTelemetry / OpenTelemetry Protocol — vendor-neutral standard for telemetry transport |
| Arize Cloud | Arize's managed observability platform — production-grade alternative to self-hosted Phoenix |
| Dispatch prompt | Minimal prompt (~150 tokens) used during tool selection phase before tools run |
| Synthesis prompt | Full voice prompt used after tools return results, for writing the final briefing |
