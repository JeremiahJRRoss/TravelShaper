# Software Architecture Document — TravelShaper Travel Assistant

**Version:** 2.1 (v0.3.2)
**Date:** April 2026
**Status:** Implementation phase

---

## 1. Overview

TravelShaper is a LangGraph-based travel planning agent exposed via a FastAPI HTTP API. It accepts a natural-language travel request, dispatches specialized tools to gather flight, hotel, and cultural intelligence, and returns a synthesized travel briefing. All LLM and tool activity is traced via configurable OpenTelemetry routing that supports Arize Phoenix, Arize Cloud, or both.

This document describes the software architecture: component design, data flow, external dependencies, deployment topology, and the decisions behind each choice.

---

## 2. Architecture Goals

TravelShaper's architecture is optimized for five goals:

1. **Deliver useful trip briefings in one request.** The system accepts a single natural-language prompt and returns a synthesized travel briefing with flights, hotels, cultural prep, and interest-based suggestions. No multi-step wizard, no session required.

2. **Keep the agent workflow simple and explainable.** The design preserves the starter app's ReAct-style graph and adds tools without introducing unnecessary orchestration complexity. The graph topology does not change — only the tool registry expands.

3. **Make tool use observable and evaluable.** Configurable OTel routing captures LLM calls, tool calls, and full request traces. The destination is controlled by `OTEL_DESTINATION` in `.env` — Phoenix, Arize Cloud, both, or none. Evaluation metrics (user frustration, tool correctness, answer completeness) are runnable against collected traces.

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
                    ┌────────────┐    ┌─────────────┐
                    │   Phoenix  │    │ Arize Cloud │
                    │   (local)  │    │ (managed)   │
                    └────────────┘    └─────────────┘
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
├── otel_routing.py            # OTel config routing (OTEL_DESTINATION in .env)
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
│   └── test_otel_routing.py   # 8 OTel routing tests
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

Does not contain business logic beyond validation.

**agent.py — Agent orchestration**

Owns the LangGraph state graph, three system prompts (dispatch + two voice-matched synthesis prompts), and the tool registry.

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

The extension adds three new tools to the registry. The graph structure itself does not change — the LLM decides which tools to call based on the system prompt and user message.

**otel_routing.py — Telemetry configuration**

Owns all OpenTelemetry configuration. Reads `OTEL_DESTINATION` from `.env` and builds a `TracerProvider` with a `Resource` whose `service.name` is set from `OTEL_PROJECT_NAME` (default: `travelshaper`) and the appropriate OTLP exporters attached.

Valid values for `OTEL_DESTINATION`:
- `phoenix` — sends traces to local Phoenix or Phoenix Cloud
- `arize` — sends traces to Arize Cloud (requires `ARIZE_API_KEY` + `ARIZE_SPACE_ID`)
- `both` — sends traces to Phoenix and Arize simultaneously
- `none` — disables all telemetry

Called once at startup from `agent.py`:
```python
from otel_routing import build_tracer_provider
from openinference.instrumentation.langchain import LangChainInstrumentor

_tracer_provider = build_tracer_provider()
LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
```

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

25 unit tests across four test files that validate tool schemas, agent graph construction, prompt routing (including phase detection), API endpoint behavior, and OTel routing logic. Tests mock external API calls — they never require live SerpAPI or OpenAI keys.

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

All tools return strings. For structured sources (SerpAPI flights/hotels), the tool formats the JSON response into a readable summary with the top 3 results. For web search tools, the raw search snippets are returned. The LLM handles final synthesis.

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

### 6.3 GPT-4o-mini as the validation model

gpt-4o-mini is used for the place validation and preference validation classifiers in `api.py` because:
- Faster and cheaper than gpt-4o for simple classification tasks
- Sufficient accuracy for binary/categorical decisions (valid/invalid, allow/deny)
- Switched from gpt-4o in v0.3.1 as part of token reduction work

### 6.4 SerpAPI as the data layer

SerpAPI was chosen because:
- One API key powers three tool types (flights, hotels, general search)
- Google Flights and Google Hotels engines return structured JSON — not raw HTML scraping
- Free tier (250 searches/month) is sufficient for development and demo
- Python `requests` library is the only dependency — no SDK required

### 6.5 DuckDuckGo as fallback

Already present in the starter code. No API key needed. Provides general web search coverage for interest discovery, cultural questions, and edge cases that SerpAPI doesn't cover.

### 6.6 FastAPI for the HTTP layer

Already present in the starter code. Async-capable, automatic OpenAPI docs at `/docs`, Pydantic validation on request/response models. No reason to change it.

### 6.7 Configurable OTel routing for observability

Phoenix was the original choice (required by the assessment). In v0.3.0, observability was generalized to support multiple destinations via `otel_routing.py`:
- Local-first development with Phoenix
- Production transition to Arize Cloud without code changes
- Dual-destination mode for migration overlap
- Disable mode for environments where tracing is not needed

---

## 7. Observability Architecture

### 7.1 Instrumentation

Telemetry is initialized at application startup before the agent is built. The `otel_routing` module reads `OTEL_DESTINATION` from `.env` and builds a `TracerProvider` with a `Resource` whose `service.name` is set from `OTEL_PROJECT_NAME` (default: `travelshaper`) and the appropriate OTLP exporters. The LangChain/LangGraph instrumentor adds OpenInference semantic attributes to every span.

```python
from otel_routing import build_tracer_provider
from openinference.instrumentation.langchain import LangChainInstrumentor

_tracer_provider = build_tracer_provider()
LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
```

This is wrapped in a `try/except ImportError` block in agent.py so the app functions without the OTel packages installed.

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
        ├── [LLM] gpt-5.3 (dispatch — decides which tools to call)
        ├── [Tool] search_flights
        ├── [Tool] search_hotels
        ├── [Tool] get_cultural_guide
        └── [LLM] gpt-5.3 (synthesis — produces final briefing with voice)
```

Total spans per query: typically 5–8 depending on how many tools are dispatched and whether the LLM loops more than once.

### 7.4 Evaluation pipeline

Evaluations run as a separate batch process after traces are collected:

```
Phoenix (stored traces)
    │
    ▼
evaluations/run_evals.py
    ├── Fetch spans from Phoenix
    ├── Apply frustration evaluator
    ├── Apply tool correctness evaluator
    ├── Apply answer completeness evaluator
    └── Write annotations back to Phoenix
```

Evaluators are LLM-as-judge functions: they send the trace data to GPT-4o with an evaluation prompt and receive a label plus an explanation.

Three metrics were chosen based on failure modes observed during development and trace analysis:

* **User Frustration** catches the most common end-user-visible failure: the agent silently omitting requested information when a tool returns empty results, or contradicting the user's stated budget preference.
* **Tool Usage Correctness** catches the most common agent-level failure: incorrect IATA codes passed to `search_flights`, skipped `get_cultural_guide` calls for international trips, and unnecessary tool calls on vague queries.
* **Answer Completeness** fills a gap the other two metrics can't cover: distinguishing intentionally scoped responses (user asked for flights only) from unintentionally incomplete ones (agent failed to search hotels).

### 7.5 OpenTelemetry vs OpenInference — Two Layers of Observability

TravelShaper's observability stack has two distinct layers that work together:

**OpenTelemetry (OTLP) — The Transport Layer**

OpenTelemetry is a vendor-neutral standard for collecting and exporting telemetry data (traces, metrics, logs). In TravelShaper:
- `otel_routing.build_tracer_provider()` configures a `TracerProvider` with a `Resource` (`service.name` from `OTEL_PROJECT_NAME`), `BatchSpanProcessor`, and `OTLPSpanExporter` targeting the configured destinations
- Every span carries a trace ID, parent ID, start/end timestamps, and arbitrary attributes
- The transport is agnostic — it works identically whether the destination is Phoenix, Jaeger, Datadog, or Arize Cloud

**OpenInference — The Semantic Convention Layer**

OpenInference is an open-source standard (created by Arize) that defines what attributes LLM-specific spans should carry. Without it, an LLM call span would just be a generic function call with a duration. With OpenInference:
- `input.value` contains the prompt text
- `output.value` contains the completion text
- `llm.model_name` identifies which model was called
- `llm.token_count.prompt` and `llm.token_count.completion` track token usage
- Tool spans carry `tool.name`, `tool.parameters`, and `tool.result`

The `openinference-instrumentation-langchain` package automatically adds these attributes to every LangChain/LangGraph span. This is why Phoenix can display our traces in a purpose-built LLM UI (with prompt/response columns, token counts, and tool call trees) rather than as generic distributed tracing data.

**In TravelShaper's code:**

```python
# agent.py — both layers initialized together
from otel_routing import build_tracer_provider           # Layer 1: OTLP transport
from openinference.instrumentation.langchain import LangChainInstrumentor  # Layer 2: semantic conventions

_tracer_provider = build_tracer_provider()  # reads OTEL_DESTINATION from .env
LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
```

Custom spans in `api.py` also set OpenInference standard attributes (`SpanAttributes.INPUT_VALUE`, `SpanAttributes.OUTPUT_VALUE`) so the request-level span renders properly in Phoenix's UI columns alongside the auto-instrumented LangChain spans.

**Analogy:** OpenTelemetry is like HTTP — it moves data from A to B. OpenInference is like HTML — it gives that data structure and meaning that the receiver (Phoenix) knows how to render.

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

**The docstring is critical.** GPT-5.3 reads it to decide when to invoke the tool and what arguments to pass. A vague docstring means unreliable tool selection.

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

All SerpAPI tools follow the same HTTP pattern via the shared `serpapi_request()` helper in `tools/__init__.py`.

### 8.4 Response formatting

SerpAPI returns large JSON payloads. Tools extract and format the relevant fields rather than passing raw JSON to the LLM (which would waste tokens and reduce synthesis quality).

Each tool returns the top 3 results (reduced from 5 in v0.3.1 to save tokens). The LLM adds context, ranking, and explanation during synthesis.

### 8.5 Adapter design principle

Tools return TravelShaper-owned output formats, not raw vendor JSON. This protects the agent from upstream response drift — if SerpAPI changes a field name or nesting structure, only the tool adapter changes, not the system prompt or synthesis logic.

---

## 9. System Prompt Design

TravelShaper uses three system prompts: one for tool dispatch and two for synthesis, selected at runtime. This section explains what they contain, why they are written the way they are, and how the selection decision is made.

### 9.1 Why two voice prompts instead of one

The naive approach is a single prompt with an instruction like "if the user wants to save money, write like Bourdain; if they want the full experience, write like Robin Leach." This does not work reliably. The model reads the entire prompt before generating and blends registers rather than committing to one. Two separate prompts solve this by giving the model complete, unambiguous instructions with no competing voice.

### 9.2 Voice routing

```python
def get_system_prompt(message: str, phase: str = "synthesis") -> str:
    if phase == "dispatch":
        return DISPATCH_PROMPT
    lower = message.lower()
    if "save money" in lower or "budget" in lower \
       or "cheapest" in lower or "spend as little" in lower:
        return SYSTEM_PROMPT_SAVE_MONEY
    return SYSTEM_PROMPT_FULL_EXPERIENCE
```

This runs inside `llm_call()` on every node invocation. Phase detection determines whether to send the dispatch prompt or a voice prompt — see §9.6.

### 9.3 SYSTEM_PROMPT_SAVE_MONEY — Bourdain / Billy Dee / Gladwell

Condensed in v0.3.1 from ~90 lines to ~20 lines. Preserves all functional instructions: voice identity, tool usage rules, section structure, hyperlink requirements, and closing line instruction.

**Hotel sort:** `sort_by=3` (lowest price).

### 9.4 SYSTEM_PROMPT_FULL_EXPERIENCE — Leach / Pharrell / Rushdie

Also condensed in v0.3.1. Same structure as the save-money prompt with the luxury voice and editorial section titles.

**Hotel sort:** `sort_by=13` (highest rating).

### 9.5 Shared prompt instructions (both voice prompts)

Both prompts share hard requirements: mandatory hyperlinks for every named entity, parallel tool dispatch, no fabricated facts, four-section structure, and a closing line.

### 9.6 DISPATCH_PROMPT — tool routing (v0.3.2)

A separate ~150-token prompt used only during the dispatch phase (the first `llm_call` before tools have run). Contains only tool routing instructions: how to convert city names to IATA codes, when to use each tool, sort_by rules by budget mode, and the instruction to call all relevant tools in a single turn.

**Why a separate dispatch prompt?**
Sending the full voice prompt (~200+ tokens of prose style instructions) before tools run wastes tokens on instructions the model cannot act on yet. The dispatch prompt focuses the model on one job: decide which tools to call. Estimated savings: ~300–600 tokens per full-trip request.

**Phase detection in `llm_call`:**
```python
last_message = state["messages"][-1] if state["messages"] else None
is_synthesis = isinstance(last_message, ToolMessage)
phase = "synthesis" if is_synthesis else "dispatch"
```

If the last message is a `ToolMessage`, tools have just returned and we are in the synthesis phase. Otherwise we are in the dispatch phase.

---

## 10. LLM Decision Making

### 10.1 The decision surface

The LLM makes three types of decisions on each `llm_call` invocation:

1. **Which tools to call, and with what arguments.** During the dispatch phase, the model reads the DISPATCH_PROMPT, the user's message, and tool descriptions, then decides which tools are relevant.

2. **Whether to call tools at all, or respond directly.** If the model determines it has enough information to produce a useful response without additional tool calls, it returns a plain `AIMessage` with no `tool_calls`.

3. **How to synthesise tool results into prose.** During the synthesis phase, the model has factual grounding from the tools and is asked to write about it in a specific voice register.

### 10.2 Tool selection logic

The DISPATCH_PROMPT and tool docstrings are the primary mechanisms for shaping tool selection. Each tool has three signal sources the model uses: the `@tool` docstring, the dispatch prompt's tool guidance section, and conversation history.

### 10.3 Parallel tool dispatch

When the model determines multiple tools are needed, it returns a single `AIMessage` with multiple entries in `tool_calls`. LangGraph's `tool_node` executes these concurrently.

### 10.4 Hotel sort_by routing

Both the dispatch prompt and voice prompts instruct the model to set `sort_by` differently based on budget mode: `sort_by=3` for save money, `sort_by=13` for full experience.

---

## 11. Input Validation Architecture

TravelShaper validates two types of user input before the agent runs: place names and free-form preference text. Both use `gpt-4o-mini` as a classifier. This section explains what the prompts do, why each decision was made, and how failures are handled.

### 11.1 Place name validation

**Purpose:** Prevent the agent from spending 20–30 seconds searching for a fictional or misspelled city, only to return empty results or hallucinated data.

**The classifier prompt instructs `gpt-4o-mini` to return one of four outcomes:**

| Outcome | Condition | Agent behaviour |
|---------|-----------|-----------------|
| `valid=true, corrected=null` | Recognisable real place, correctly spelled | Agent proceeds with input as-is |
| `valid=true, corrected="Tokyo, Japan"` | Misspelling of an identifiable place | Agent proceeds with corrected name; UI shows teal correction banner |
| `valid=false` (ambiguous) | Multiple places match — "Springfield", "Georgia" | Request rejected with disambiguation prompt; user corrects and resubmits |
| `valid=false` (invalid) | Unrecognisable, fictional, or injected | Request rejected with user-friendly message; field highlighted red |

**Why `gpt-4o-mini` and not a geocoding API?**

A geocoding API (Google Places, Mapbox) would be more authoritative for exact matching but has three drawbacks: it requires another API key, it fails on natural-language inputs, and it cannot handle the nuanced "I know what you mean, let me correct it" case. `gpt-4o-mini` handles all three cases in one call. The tradeoff is that it is probabilistic — a sufficiently unusual real city name could be rejected.

**Fail-open on transient errors.** If the `gpt-4o-mini` call itself fails, `validate_place()` returns `valid=True` and lets the agent proceed.

### 11.2 Preference text validation

**Purpose:** The `preferences` field is free-form text up to 500 characters that gets appended to the agent's message. Without validation, this is a prompt injection surface.

**The classifier uses `gpt-4o-mini` with a safety classifier prompt.** The prompt instructs the model to lean toward ALLOW for ambiguous cases.

**Fail-safe on errors.** Unlike place validation, preference validation fails closed: if the `gpt-4o-mini` call fails, `validate_preferences()` returns `valid=False`.

### 11.3 Validation in the SSE stream

The `/chat/stream` endpoint runs validation before opening the SSE connection.

### 11.4 Validation cost and latency

Each validation call to `gpt-4o-mini` costs approximately 0.3–0.5 seconds and a few hundred tokens — faster and cheaper than the gpt-4o calls used in versions prior to v0.3.1. A full request with both place fields and a preferences field makes three sequential validation calls before the agent starts. This adds roughly 1–2 seconds to the total request time.

---

## 12. Deployment Architecture

### 12.1 Local development

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

### 12.2 Docker Compose

```yaml
services:
  travelshaper:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - OTEL_DESTINATION=${OTEL_DESTINATION:-phoenix}
      - PHOENIX_ENDPOINT=http://phoenix:6006/v1/traces
      - ARIZE_ENDPOINT=${ARIZE_ENDPOINT:-}
      - ARIZE_API_KEY=${ARIZE_API_KEY:-}
      - ARIZE_SPACE_ID=${ARIZE_SPACE_ID:-}
    depends_on:
      phoenix:
        condition: service_started
    restart: unless-stopped

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    restart: unless-stopped
    profiles:
      - phoenix
```

Phoenix is optional — it only starts when the `phoenix` profile is active. The Makefile reads `OTEL_DESTINATION` from `.env` and activates the profile when needed.

### 12.3 Production architecture (proposed)

(Unchanged from previous version — see original document.)

### 12.4 Observability — Production Path

The local development stack runs Phoenix as a Docker container. In production, the observability layer transitions through stages, controlled entirely by environment variables:

**Stage 1 — Self-hosted Phoenix (current default)**

`OTEL_DESTINATION=phoenix` in `.env`. Phoenix runs as a Docker container. Traces are stored locally.

**Stage 2 — Phoenix Cloud**

Set `PHOENIX_API_KEY` in `.env`. The same `phoenix` destination routes traces to Arize's managed Phoenix instance. No application code changes.

**Stage 3 — Arize Cloud**

Set `OTEL_DESTINATION=arize` with `ARIZE_ENDPOINT`, `ARIZE_API_KEY`, and `ARIZE_SPACE_ID`. Replace self-hosted Phoenix with Arize's managed platform. Benefits: persistent storage, team access, scheduled evaluations, drift monitoring.

**Migration overlap:** Set `OTEL_DESTINATION=both` to send traces to both Phoenix and Arize during the transition. Remove Phoenix when confident in Arize.

All transitions require only `.env` changes — no application code modifications. This is possible because `otel_routing.py` uses standard OpenTelemetry (transport) with OpenInference (semantic conventions), both of which all three destinations natively support.

---

## 13. Security Considerations

(Unchanged — see original document. Note: validation classifiers now use gpt-4o-mini.)

---

## 14. Testing Strategy

### 14.1 Test categories

| Category | File | Count | What it validates | External calls |
|----------|------|-------|-------------------|----------------|
| Tool schema tests | test_tools.py | 4 | Input types, output format, docstring presence | Mocked |
| Agent graph tests | test_agent.py | 6 | Nodes, edges, routing, dispatch vs synthesis phase | Mocked |
| API endpoint tests | test_api.py | 8 | HTTP status codes, response shapes, validation pipeline | Mocked |
| OTel routing tests | test_otel_routing.py | 8 | Exporter creation, credential handling, destination selection, project name | Mocked |
| Integration tests (manual) | — | — | Full request with live APIs during demo | Live |

### 14.2 Mocking approach

Tests use `unittest.mock.patch` to replace external API calls. OTel routing tests additionally use `patch.dict(os.environ)` to control environment variables. No test requires a live API key.

### 14.3 Test execution

```bash
pytest tests/ -v    # 26 passed
```

---

## 15. Evolution Path

The architecture is designed to evolve without rewrites. Each phase extends the existing structure.

**Completed (v0.3.0–v0.3.2):**
- Configurable OTel routing (phoenix / arize / both / none)
- Token reduction via condensed prompts and phase-based dispatch
- Validation model optimization (gpt-4o → gpt-4o-mini)

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
| Observability | Configurable OTel (Phoenix/Arize/both/none) | Phoenix-only, LangSmith | Vendor-neutral; supports production transition |
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
| SerpAPI | A web API that returns structured Google search results |
| OTEL / OTLP | OpenTelemetry / OpenTelemetry Protocol — vendor-neutral standard for telemetry transport |
| Arize Cloud | Arize's managed observability platform — production-grade alternative to self-hosted Phoenix |
| Dispatch prompt | Minimal prompt (~150 tokens) used during tool selection phase before tools run |
| Synthesis prompt | Full voice prompt used after tools return results, for writing the final briefing |
