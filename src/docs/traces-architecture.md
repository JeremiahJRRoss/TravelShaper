# Traces Architecture — TravelShaper

**Version:** 1.0 (v0.5.0)
**Date:** April 2026

This document explains how traces flow through TravelShaper — from the moment a request arrives, through span creation and export, to storage in Phoenix and evaluation by LLM-as-judge metrics. It covers the two-layer observability model, the trace lifecycle, span anatomy, the trace generator, and the evaluation pipeline.

---

## 1. Why Traces Matter in TravelShaper

TravelShaper is an LLM agent that calls multiple tools before synthesizing a response. A single user request can produce 5–8 internal operations: LLM calls for tool dispatch, parallel tool executions against external APIs, and a final LLM synthesis call. Without traces, you cannot see why a response was incomplete, which tool was slow, or whether the model chose the right tools.

Traces solve three problems: they make the agent's internal decisions visible, they provide the ground truth for automated evaluation, and they create a feedback loop between development and quality.

---

## 2. The Two-Layer Observability Model

TravelShaper's tracing uses two layers that work together. Understanding the distinction is essential for configuring, debugging, and extending the system.

### Layer 1: OpenTelemetry (Transport)

OpenTelemetry is a vendor-neutral standard for collecting and exporting telemetry data. It handles the mechanics of creating spans, assigning trace IDs, batching exports, and shipping data to a backend. In TravelShaper, this layer is configured by `otel_routing.py`, which reads `OTEL_DESTINATION` from `.env` and builds a `TracerProvider` with the appropriate exporters.

The transport layer does not know or care what is inside a span. It moves structured data from TravelShaper to a backend — Phoenix, Arize Cloud, Jaeger, or any OTLP-compatible receiver.

### Layer 2: Semantic Conventions (Meaning)

Without semantic conventions, an LLM call span would be indistinguishable from a database query span — both would just have a name, a duration, and some opaque attributes. Semantic conventions define what attributes LLM-specific spans should carry: the prompt text, the completion text, the model name, token counts, tool names, and tool parameters.

TravelShaper supports two convention sets, controlled by `OTEL_SEMCONV`:

| OTEL_SEMCONV | Convention | Package | Key Attributes | Best For |
|---|---|---|---|---|
| `openinference` (default) | OpenInference | `openinference-instrumentation-langchain` | `input.value`, `output.value`, `llm.model_name` | Phoenix, Arize |
| `genai` | OTel GenAI | `opentelemetry-instrumentation-langchain` (OpenLLMetry) | `gen_ai.request.model`, `gen_ai.usage.input_tokens` | Jaeger, Tempo, Datadog |

The instrumentor package auto-decorates every LangChain/LangGraph operation with the appropriate attributes. No manual span creation is needed for the agent's core loop — the instrumentor handles it.

### How They Connect

```
agent.py (startup)
    │
    ├── otel_routing.build_tracer_provider()     ← Layer 1: transport config
    │       reads OTEL_DESTINATION
    │       builds TracerProvider with exporters
    │
    ├── otel_routing.get_semconv()               ← Layer 2: convention selection
    │       reads OTEL_SEMCONV
    │
    └── Instrumentor.instrument(tracer_provider)  ← Connects both layers
            if genai: LangchainInstrumentor (OpenLLMetry)
            if openinference: LangChainInstrumentor (OpenInference)
```

**Analogy:** OpenTelemetry is like HTTP — it moves data from A to B. Semantic conventions are like HTML — they give that data structure and meaning that the receiver knows how to render.

---

## 3. Trace Lifecycle

### 3.1 Initialization (happens once at startup)

When `agent.py` is imported, it runs the observability initialization block:

```python
try:
    from otel_routing import build_tracer_provider, get_semconv

    _tracer_provider = build_tracer_provider()
    _semconv = get_semconv()

    if _semconv == "genai":
        from opentelemetry.instrumentation.langchain import LangchainInstrumentor
        LangchainInstrumentor().instrument(tracer_provider=_tracer_provider)
    else:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
except ImportError:
    pass  # tracing disabled, agent still works
```

This runs exactly once. After this, every LangChain/LangGraph operation automatically produces spans. The `try/except ImportError` ensures the agent functions even when OTel packages are not installed.

### 3.2 Request arrives

When a request hits `POST /chat`, the API layer creates a custom request-level span in `api.py`:

```python
tracer = otel_trace.get_tracer("travelshaper")
with tracer.start_as_current_span("travelshaper.request") as span:
    # Set attributes based on OTEL_SEMCONV
    if _semconv_mode == "genai":
        span.set_attribute("gen_ai.system", "openai")
        span.set_attribute("gen_ai.request.model", "gpt-5.3-chat-latest")
        span.add_event("gen_ai.content.prompt", attributes={...})
    else:
        span.set_attribute(SpanAttributes.INPUT_VALUE, full_message)

    # Custom attributes (always set regardless of convention)
    span.set_attribute("travelshaper.destination", request.destination or "")
    span.set_attribute("travelshaper.departure", request.departure or "")
    span.set_attribute("travelshaper.budget_mode", ...)
    span.set_attribute("travelshaper.has_preferences", ...)

    # Agent runs inside this span context
    agent_result = agent.invoke(...)
```

This custom span provides request-level metadata that the auto-instrumentor cannot capture — departure city, destination, budget mode, and whether preferences were provided.

### 3.3 Agent execution produces child spans

Inside the `agent.invoke()` call, the instrumentor automatically creates child spans for each operation:

```
[travelshaper.request]                         ← custom span from api.py
  └── [agent.invoke]                           ← auto-instrumented chain span
        ├── [llm_call / ChatOpenAI]            ← dispatch phase LLM call
        │     model: gpt-5.3-chat-latest
        │     input: DISPATCH_PROMPT + user message
        │     output: tool_calls [search_flights, search_hotels, ...]
        │
        ├── [tool_node / search_flights]       ← tool execution span
        │     tool.name: search_flights
        │     tool.parameters: {departure_id: "SFO", arrival_id: "NRT", ...}
        │     tool.result: "Flight results: SFO → NRT ..."
        │
        ├── [tool_node / search_hotels]        ← tool execution span
        │     tool.name: search_hotels
        │     tool.parameters: {query: "Tokyo hotels", ...}
        │     tool.result: "Hotel results: ..."
        │
        ├── [tool_node / get_cultural_guide]   ← tool execution span
        │     tool.name: get_cultural_guide
        │     tool.parameters: {destination: "Tokyo, Japan"}
        │     tool.result: "Cultural and travel prep research ..."
        │
        └── [llm_call / ChatOpenAI]            ← synthesis phase LLM call
              model: gpt-5.3-chat-latest
              input: voice prompt + message history + tool results
              output: full travel briefing (markdown)
```

### 3.4 Span export

The `TracerProvider` is configured with a `BatchSpanProcessor`, which collects completed spans and exports them in batches to the configured destination(s). This is asynchronous — the export does not block the response to the user.

Export paths by destination:

| Destination | Exporter | Protocol | Endpoint |
|---|---|---|---|
| Phoenix (local) | `OTLPSpanExporter` | HTTP/protobuf | `http://localhost:6006/v1/traces` |
| Phoenix (Cloud) | `OTLPSpanExporter` + auth header | HTTP/protobuf | Phoenix Cloud URL |
| Arize Cloud | `arize.otel.register()` SDK | OTLP/HTTP | Arize-managed endpoint |
| Generic OTLP (HTTP) | `OTLPSpanExporter` | HTTP/protobuf | User-configured endpoint |
| Generic OTLP (gRPC) | `OTLPGrpcSpanExporter` | gRPC/protobuf | User-configured endpoint |

### 3.5 Storage and visualization

Once spans arrive at the backend, they are stored and made available for querying. In Phoenix (the default backend), traces appear in the UI at `http://localhost:6006` within seconds of the request completing. Each trace can be expanded to show the full span tree — every LLM call, every tool execution, with inputs, outputs, and durations.

---

## 4. Span Anatomy

### 4.1 What each span type captures

| Span Type | Captured Data |
|-----------|---------------|
| Request span (`travelshaper.request`) | User message, destination, departure, budget mode, preferences flag, full response |
| LLM span (auto-instrumented) | Model name, system prompt, user messages, assistant response, token counts (prompt + completion), latency, tool call decisions |
| Tool span (auto-instrumented) | Tool name, input arguments, output content, execution duration, error status |
| Chain span (auto-instrumented) | End-to-end trace linking all child spans, total duration |

### 4.2 Custom vs auto-instrumented attributes

**Auto-instrumented** (by the LangChain instrumentor): model name, input/output text, token counts, tool names, tool parameters, tool results, span durations, trace/span IDs, parent-child relationships.

**Custom** (set explicitly in `api.py`): `travelshaper.destination`, `travelshaper.departure`, `travelshaper.budget_mode`, `travelshaper.has_preferences`. These domain-specific attributes are not part of any standard convention — they encode business context that is useful for filtering and analysis.

### 4.3 Convention-specific differences

When `OTEL_SEMCONV=openinference`, the request span sets:
- `SpanAttributes.INPUT_VALUE` — the user's message
- `SpanAttributes.OUTPUT_VALUE` — the agent's response
- `SpanAttributes.INPUT_MIME_TYPE` / `OUTPUT_MIME_TYPE` — `text/plain`

When `OTEL_SEMCONV=genai`, the request span sets:
- `gen_ai.system` — `"openai"`
- `gen_ai.request.model` — `"gpt-5.3-chat-latest"`
- Span events: `gen_ai.content.prompt` (with prompt text) and `gen_ai.content.completion` (with response text)

The auto-instrumented child spans follow whichever convention the instrumentor package uses — OpenInference attributes for the `openinference-instrumentation-langchain` package, GenAI attributes for the `opentelemetry-instrumentation-langchain` package.

---

## 5. The Trace Generator

### 5.1 Purpose

The trace generator (`traces/run_traces.py`) is a standalone Python script that fires 11 curated queries against the running TravelShaper server. Its purpose is to populate Phoenix with a representative set of traces for analysis and evaluation.

### 5.2 Query design

The 11 queries were designed to cover every meaningful combination of tools, voices, input patterns, and edge cases:

| # | Scenario | Expected Tools | Voice | Special Test |
|---|----------|---------------|-------|-------------|
| 1 | Full trip, SFO→Tokyo | All 4 | Save money | Full schema |
| 2 | Full trip, NYC→Barcelona | All 4 | Full experience | Birthday trip |
| 3 | Budget, Chicago→"Roam" | 3 (no DDG) | Save money | Auto-correction |
| 4 | Japan etiquette only | Cultural + DDG | Full experience | No origin/dates |
| 5 | Lisbon, already there | Cultural + DDG | Save money | No transport |
| 6 | LAX→London, flights only | Flights only | Save money | Single tool |
| 7 | Bangkok, hotels only | Hotels only | Save money | Single tool |
| 8 | Miami→Queenstown | All 4 | Full experience | Long-haul, S. hemisphere |
| 9 | "Somewhere warm" | DDG only | Default | Vague/open-ended |
| 10 | Seattle→Austin (SXSW) | 3 (no cultural) | Full experience | Domestic |
| 11 | Boston→Paris, past dates | Flights + Hotels | Save money | Error handling |

### 5.3 Date arithmetic

All dates in the queries are computed relative to `date.today()` using `timedelta`. This means the script never goes stale — Query 1 always searches 30 days from now, Query 11 always uses dates 30 days in the past, and so on.

### 5.4 Output

Each run produces a timestamped JSON file (e.g. `trace-results_2026-04-04_14-05-32.json`) containing the request body, response text, and status for each query. Traces are simultaneously recorded in Phoenix for visual analysis.

### 5.5 Usage

```bash
python -m traces.run_traces              # all 11 queries
python -m traces.run_traces 3            # first 3 only (quick test)
python -m traces.run_traces all http://localhost:8000   # explicit URL
```

---

## 6. The Evaluation Pipeline

### 6.1 From traces to scores

The evaluation runner (`evaluations/run_evals.py`) reads collected traces from Phoenix and scores each one against three LLM-as-judge metrics. The pipeline works at the trace level, not the span level — it groups all spans by trace ID, identifies the root span (with user input and agent output), and identifies child spans (with actual tool calls).

```
Phoenix (stored traces)
    │
    ▼
evaluations/run_evals.py
    │
    ├── Connect to Phoenix at localhost:6006
    ├── Pull all spans via client.spans.get_spans_dataframe()
    ├── Group spans by trace_id
    ├── For each trace:
    │     ├── Find the span with the longest output (agent briefing)
    │     ├── Extract tool spans by matching span names against known tools
    │     └── Assemble {input, output, tools_called} record
    │
    ├── Score each record against three metrics (gpt-4o as judge)
    │     ├── User Frustration
    │     ├── Tool Usage Correctness
    │     └── Answer Completeness
    │
    ├── Write annotations back to Phoenix (SpanEvaluations)
    ├── Create 'frustrated_interactions' dataset from flagged traces
    └── Save local JSON summary file
```

### 6.2 Why trace-level, not span-level

A naive approach would evaluate individual spans — "was this LLM call good?" But the quality of a TravelShaper response depends on the relationship between spans: did the agent call the right tools (tool spans) given the user's request (root span), and did it synthesize a complete response (output) from the tool results? This requires assembling a composite view across the entire trace.

### 6.3 Tool call extraction

The evaluation pipeline extracts actual tool calls from child spans, not from the response text. This is critical for the Tool Usage Correctness metric, which needs to know what tools were called (the decision) independently of what the response says (the output). The extraction works by matching child span names against the four known tool names: `search_flights`, `search_hotels`, `get_cultural_guide`, `duckduckgo_search`.

### 6.4 The three metrics

**User Frustration** catches the most common end-user-visible failure: the agent silently omitting requested information, contradicting stated preferences, or producing a response that is technically correct but experientially poor. Uses Phoenix's built-in `USER_FRUSTRATION_PROMPT_TEMPLATE`.

**Tool Usage Correctness** catches the most common agent-level failure: incorrect IATA codes, skipped cultural guide calls for international trips, unnecessary tool calls on vague queries. The custom prompt receives the actual list of tools called (from trace child spans) alongside the user's request.

**Answer Completeness** fills a gap the other two metrics cannot cover: distinguishing intentionally scoped responses (user asked for flights only) from unintentionally incomplete ones (agent failed to search hotels). The custom prompt has scope awareness — it first determines what the user actually asked for, then evaluates coverage.

### 6.5 Reading results together

A trace that scores correct on tools, complete on answers, but frustrated on experience tells you the system is mechanically sound but tonally off — the system prompt needs voice tuning.

A trace that scores correct on tools but incomplete on answers tells you the LLM is gathering the right data but dropping information during synthesis — the structural instructions need reinforcement.

A trace that scores incorrect on tools will almost always also score incomplete on answers, because missing tool calls produce missing data. The tool correctness flag identifies the root cause; the completeness flag shows the user-facing consequence.

---

## 7. Configuration Reference

### 7.1 Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OTEL_DESTINATION` | `phoenix` | Where traces are sent (phoenix, arize, otlp, both, all, none) |
| `OTEL_SEMCONV` | `openinference` | Span attribute format (openinference, genai) |
| `OTEL_PROJECT_NAME` | `travelshaper` | Service name in `TracerProvider` resource; project name in dashboards |
| `PHOENIX_ENDPOINT` | — | OTLP endpoint for Phoenix (local or Cloud) |
| `PHOENIX_API_KEY` | — | Auth token for Phoenix Cloud |
| `ARIZE_API_KEY` | — | API key for Arize Cloud |
| `ARIZE_SPACE_ID` | — | Space ID for Arize Cloud |
| `OTLP_ENDPOINT` | — | Endpoint for generic OTLP backend |
| `OTLP_PROTOCOL` | `http` | Transport for generic OTLP (http or grpc) |
| `OTLP_HEADERS` | — | Auth headers for generic OTLP (comma-separated key=value) |

### 7.2 Failure modes

| Scenario | Behavior |
|----------|----------|
| OTel packages not installed | Agent works normally, no traces generated |
| Phoenix not reachable | Spans are batched and eventually dropped; no crash |
| Arize credentials missing | Warning logged, destination skipped |
| OTLP endpoint missing | Warning logged, destination skipped |
| gRPC package not installed | Falls back to HTTP exporter with warning |
| GenAI instrumentor not installed | Warning logged, tracing disabled |

All failure modes are non-fatal. The agent always functions regardless of telemetry state.

### 7.3 Production path

| Stage | Configuration | Backend |
|-------|--------------|---------|
| Local development | `OTEL_DESTINATION=phoenix` | Self-hosted Phoenix container |
| Phoenix Cloud | `OTEL_DESTINATION=phoenix` + `PHOENIX_API_KEY` | Managed Phoenix |
| Arize Cloud | `OTEL_DESTINATION=arize` | Arize managed platform |
| Standard backends | `OTEL_DESTINATION=otlp` + `OTEL_SEMCONV=genai` | Jaeger, Tempo, Datadog, Honeycomb |
| Migration overlap | `OTEL_DESTINATION=both` or `all` | Multiple backends simultaneously |
| Disabled | `OTEL_DESTINATION=none` | No traces |

All transitions require only `.env` changes — no code modifications.

---

## 8. Testing the Trace System

The `test_otel_routing.py` file contains 21 tests that validate every routing path, credential handling, and failure mode. Tests mock environment variables and OTLP exporters — no live endpoints are required.

Key test categories:

- **Phoenix tests (3):** Exporter creation, API key passthrough, no-auth case
- **Arize tests (2):** SDK registration call, missing credentials graceful skip
- **Both/All tests (2):** Multi-destination exporter wiring
- **Generic OTLP tests (4):** HTTP exporter, header parsing, missing endpoint, combined destinations
- **gRPC tests (4):** gRPC exporter selection, header passthrough, fallback to HTTP, explicit HTTP
- **None test (1):** No exporters created
- **Project name tests (2):** Custom and default service names
- **Semconv tests (4):** Default selection, genai selection, explicit openinference, missing package resilience

---

## 9. Extending the Trace System

### Adding a new tool

When adding a new tool to the agent, no trace configuration changes are needed. The LangChain instrumentor automatically creates spans for any tool registered in the `tools` list. The evaluation pipeline's `KNOWN_TOOLS` set in `run_evals.py` should be updated to include the new tool name for correct Tool Usage Correctness scoring.

### Adding a new metric

Create a new prompt template in `evaluations/metrics/`, add a `run_metric()` call in `run_evals.py`, and include the results in the Phoenix annotation and JSON summary output. The existing heartbeat timer and error handling patterns apply to any new metric.

### Adding a new backend

Add a new case to `build_tracer_provider()` in `otel_routing.py`. The pattern is always the same: create an exporter, wrap it in a `BatchSpanProcessor`, and attach it to the `TracerProvider`. Add corresponding tests in `test_otel_routing.py`.
