# Product Requirements Document — TravelShaper Travel Assistant

**Version:** 1.2
**Date:** April 2026
**Status:** Implementation phase
**Author:** [Your Name]

---

## 1. Purpose

This document defines the product requirements for TravelShaper, an AI-powered travel planning assistant built as a technical assessment. TravelShaper extends a LangGraph starter application into a functional travel agent that searches real flight and hotel data, provides cultural preparation guidance, and delivers synthesized trip recommendations — all instrumented with configurable OpenTelemetry tracing for observability and evaluation.

> **In one sentence:** TravelShaper is a single-turn, LLM-powered travel planning assistant that combines structured flight and hotel search with interest-based destination intelligence and cultural prep to deliver an explainable, personalized travel briefing for English-speaking American travelers.

---

## 2. Problem Statement

Planning international travel as an American requires navigating multiple disconnected tools: one site for flights, another for hotels, a travel blog for restaurant tips, a government site for visa info, and scattered forum posts for etiquette advice. The traveler does all the synthesis themselves — comparing options, cross-referencing reviews, and figuring out what to pack.

TravelShaper solves this by acting as a single conversational interface that searches across multiple sources, ranks results by the traveler's stated priorities, and delivers one cohesive recommendation that includes logistics, cultural preparation, and interest-based activity suggestions.

---

## 3. Target User

**Primary persona:** English-speaking American adult planning international or domestic leisure travel.

**Assumptions about the user:**
- Knows where they want to go (or has it narrowed to a region)
- Has rough dates or a travel window in mind
- Has a sense of budget preference (save money vs. full experience)
- Has specific interests they want the trip to cater to
- Does not have deep familiarity with the destination's language or customs
- Wants practical, actionable recommendations — not an overwhelming list of options

---

## 4. Jobs to Be Done

When a traveler comes to TravelShaper, they are trying to accomplish one or more of these jobs:

- **"Help me figure out the best way to get there."** — Compare flight options, understand tradeoffs between price, duration, and layovers.
- **"Help me choose where to stay based on my priorities."** — Match hotels to budget, location preferences, and trip style.
- **"Tell me what's worth doing for my interests."** — Surface destination-specific activities tailored to what the traveler actually cares about.
- **"Prepare me so I don't feel unprepared or awkward."** — Provide language basics, etiquette norms, dress expectations, and common mistakes to avoid.
- **"Summarize tradeoffs so I can make a decision faster."** — Explain *why* one option is better for this traveler, not just list options.

---

## 5. Non-goals

TravelShaper is explicitly **not** intended to:

- Complete bookings or process payments
- Manage airline loyalty accounts or hotel reward programs
- Guarantee real-time inventory accuracy or fare holds
- Provide persistent conversation memory across separate `/chat` requests
- Act as a comprehensive rail or ferry booking engine
- Replace dedicated travel agent services for complex multi-city itineraries

## 6. Future goals
- Highly stylized language support beyond English 
- Expanded UX functionality
- Deeper safety and security considerations


---

## 6. Scope

### 6.1 In scope (this implementation)

| Capability | Description |
|------------|-------------|
| Browser chat interface | Self-contained HTML/CSS/JS UI served at `http://localhost:8000` by FastAPI; calls the `/chat/stream` endpoint; coexists with the REST API |
| Flight search | Query Google Flights via SerpAPI; return structured results with prices, airlines, duration, layovers |
| Hotel search | Query Google Hotels via SerpAPI; return top 3 structured results with nightly rates, ratings, amenities |
| Cultural guide | Web-search-based research on language basics, etiquette, tipping, dress code, and common mistakes for American travelers |
| Interest discovery | Web search scoped to the traveler's stated interests (food, arts, events, fitness, nature, photography) |
| Synthesized briefing | LLM combines all tool results into a single opinionated travel recommendation |
| Budget-aware ranking | Recommendations are shaped by the traveler's budget preference |
| Configurable observability | OTel routing to Phoenix, Arize Cloud, both, or none — controlled by `OTEL_DESTINATION` in `.env` |
| Evaluation | Three LLM-as-judge metrics (user frustration, tool correctness, answer completeness) on traced queries |
| Tests | 25 unit tests covering tool schemas, agent graph construction, prompt routing, API endpoints, and OTel routing |
| Docker | Dockerfile for the application; docker-compose.yml including optional Phoenix |
| API | FastAPI server with `/chat`, `/chat/stream`, and `/health` endpoints |

### 6.2 Out of scope (this implementation)

| Capability | Rationale |
|------------|-----------|
| Booking or payment | TravelShaper recommends; it does not transact |
| Multi-turn conversation memory | Current implementation is single-turn; session management is a production enhancement |
| Dedicated train/ferry APIs | Train and ferry guidance is available via general web search but not through structured travel APIs |
| User accounts or saved trips | No persistence layer beyond Phoenix traces |
| Full frontend application | The browser UI is intentionally minimal — a single HTML file for demo and development use |
| Real-time price alerts | No background jobs or push notifications |
| Multi-language support | English for MVP |

### 6.3 Future roadmap (documented, not built)

These are described in the architecture design and presentation but not implemented in this version.

**Phase 2 — Conversational depth:**
- Session-based conversation memory for multi-turn planning
- Weather API integration for data-driven packing guidance
- Richer hotel filtering (neighborhood, amenity preferences)
- Caching layer to reduce SerpAPI calls for repeated queries

**Phase 3 — Expanded coverage:**
- Dedicated rail APIs (Trainline, Amtrak) for structured train search
- Structured event search for concerts, festivals, exhibitions
- Destination comparison mode ("Barcelona vs. Lisbon in October")
- Rate limiting and authentication on the API

**Phase 4 — Product maturity:**
- Saved trips and user preference profiles
- Collaborative itinerary planning
- Horizontal scaling with load balancer
- Persistent message store (Redis or PostgreSQL)
- Highly stylized support for multiple languages with nuanced / localized UX

---

## 7. Functional Requirements

### 7.1 User input

The system accepts a single chat message containing some or all of the following:

| Field | Required | Example |
|-------|----------|---------|
| Origin city | Yes | "Flying from San Francisco" |
| Destination | Yes | "Want to go to Tokyo" |
| Travel dates | Recommended | "Mid-October, about 10 days" |
| Budget preference | Recommended | "Trying to save money" or "Full experience" |
| Interests | Recommended | "Food, photography, and art" |
| Optional constraints | No | "Direct flights only," "Under $100/night," "Solo traveler" |

If required fields are missing, the agent should still attempt a useful response using reasonable defaults rather than refusing to act.

### 7.2 Tool behavior

**search_flights**

| Property | Specification |
|----------|---------------|
| Input | Departure airport code, arrival airport code, outbound date, return date, travel class (default economy) |
| Source | SerpAPI `google_flights` engine |
| Output | Top 3 flight options with: airline, price, duration, number of stops, layover details, departure/arrival times |
| Budget behavior | "Save money" → sort by price ascending; "Full experience" → sort by top flights (Google's default ranking favoring convenience) |
| Error handling | Return a message indicating flights could not be found if SerpAPI returns empty or errors |

**search_hotels**

| Property | Specification |
|----------|---------------|
| Input | Destination query, check-in date, check-out date, number of adults, optional price ceiling |
| Source | SerpAPI `google_hotels` engine |
| Output | Top 3 properties with: name, nightly rate, overall rating, review count, amenities, neighborhood |
| Budget behavior | "Save money" → sort by price; "Full experience" → sort by rating/review quality |
| Error handling | Return a message indicating hotels could not be found if SerpAPI returns empty or errors |

**get_cultural_guide**

| Property | Specification |
|----------|---------------|
| Input | Destination country/city |
| Source | SerpAPI `google` engine with queries scoped to etiquette, language, dress code, and tipping for the destination |
| Output | Structured summary covering: 5–10 useful phrases with pronunciation, greeting customs, tipping norms, dress expectations, common faux pas for American visitors |
| Data quality | Web-sourced and LLM-synthesized; practical but not authoritative. Quality varies by destination popularity |
| Error handling | Fall back to LLM's training knowledge if web search returns thin results |

**web_search (existing)**

| Property | Specification |
|----------|---------------|
| Input | Free-text search query |
| Source | DuckDuckGo |
| Output | Search result snippets |
| Usage | General fallback for interest-based discovery, event lookup, and questions not covered by specialized tools |

### 7.3 Response synthesis

After all tools return, the LLM produces a single response that:

1. Leads with the most decision-relevant information (flights and hotels)
2. Provides 2–3 options per category, not exhaustive lists
3. Explains *why* each recommendation fits the traveler's stated preferences
4. Includes cultural preparation (language, etiquette, dress) when a cultural guide was retrieved
5. Includes interest-based suggestions (food spots, photo locations, etc.) when relevant
6. Notes tradeoffs honestly ("cheaper but longer layover," "great location but noisy street")
7. Acknowledges limitations when data is thin ("I couldn't find specific event listings for those dates")

### 7.4 API contract

**GET /**

Serves the browser chat interface (`static/index.html`).

**POST /chat**

Request:
```json
{
  "message": "string (required)",
  "departure": "string or null",
  "destination": "string or null",
  "preferences": "string or null (max 500 chars)"
}
```

Response:
```json
{
  "response": "string"
}
```

**POST /chat/stream**

Same request body. Returns SSE events: `status`, `place_corrected`, `place_error`, `validation_error`, `done`, `error`.

**GET /health**

Response:
```json
{
  "status": "ok"
}
```

---

## 8. Non-Functional Requirements

### 8.1 Performance

| Metric | Target |
|--------|--------|
| End-to-end response time | Under 30 seconds for a full briefing (multiple tool calls + synthesis) |
| Individual tool call | Under 5 seconds per SerpAPI query |
| LLM synthesis | Under 10 seconds for final response generation |

### 8.2 Reliability

- The agent must not crash on malformed input.
- If a tool call fails, the agent should continue with available results.
- The `/health` endpoint must always respond.

### 8.3 Observability

- Every LLM invocation must produce a span capturing: input prompt, output response, model name, token usage, and latency.
- Every tool invocation must produce a span capturing: tool name, input parameters, output data, and execution time.
- Spans must be organized into traces that represent a complete user interaction.
- Trace destination is configurable via `OTEL_DESTINATION` environment variable.

### 8.4 Cost

| Resource | Estimated cost per query |
|----------|------------------------|
| OpenAI GPT-5.3 (agent) | ~$0.02–$0.08 (depends on tool call count and response length) |
| OpenAI GPT-4o-mini (validation) | ~$0.001–$0.003 per validation call |
| SerpAPI | Free tier: 250 searches/month; ~2–4 searches per query |
| Total per briefing | ~$0.02–$0.08 (agent LLM dominates) |

### 8.5 Security

- API keys are stored in `.env` and never committed to version control.
- No user authentication is implemented in this version.
- No personally identifiable information is stored beyond Phoenix traces.

---

## 9. Agent Architecture

### 9.1 Graph structure

```
START → llm_call (dispatch) → should_continue?
                                ├── tool calls → tool_node → llm_call (synthesis) → END
                                └── no tool calls → END
```

### 9.2 System prompts

Three prompts selected at runtime by `get_system_prompt(message, phase)`:
1. `DISPATCH_PROMPT` — minimal tool routing (dispatch phase)
2. `SYSTEM_PROMPT_SAVE_MONEY` — Bourdain/Billy Dee/Gladwell voice (synthesis, budget)
3. `SYSTEM_PROMPT_FULL_EXPERIENCE` — Leach/Pharrell/Rushdie voice (synthesis, default)

### 9.3 Tool dispatch logic

The LLM decides which tools to call based on the user's message. Expected behavior:

| User message contains | Tools the agent should call |
|----------------------|----------------------------|
| Origin + destination + dates | `search_flights`, `search_hotels`, `get_cultural_guide` |
| Destination + interests only | `get_cultural_guide`, `web_search` |
| General travel question | `web_search` |
| "Find me flights from X to Y" | `search_flights` |
| "What should I know before visiting Japan?" | `get_cultural_guide` |

---

## 10. Evaluation Requirements

### 10.1 User frustration evaluation

Assess each traced interaction for signals of user frustration — incomplete responses, ignored preferences, generic advice when structured data was available.

### 10.2 Tool usage correctness evaluation

Assess whether the agent selected appropriate tools and passed valid parameters, using actual tool calls extracted from trace child spans.

### 10.3 Answer completeness evaluation

Assess whether the response covers everything the user asked for, with scope awareness for intentionally scoped requests.

### 10.4 Trace volume

11 diverse queries are traced in Phoenix, covering: full trip planning, partial requests, interest-heavy queries, cultural questions, edge cases (vague input, past dates, misspelled destinations), and both budget voices.

---

## 11. Testing Requirements

### 11.1 Unit tests (25 implemented)

| File | Count | What it validates |
|------|-------|-------------------|
| test_tools.py | 4 | Tool input/output format, empty result handling |
| test_agent.py | 6 | Graph structure, tool registration, voice routing, dispatch phase detection |
| test_api.py | 8 | HTTP endpoints, place validation, preference validation |
| test_otel_routing.py | 7 | OTel destination selection, credential handling, exporter creation |

### 11.2 Test execution

```bash
pytest tests/ -v    # 25 passed
```

All tests pass without requiring external API keys.

---

## 12. Deployment Requirements

### 12.1 Docker Compose (with optional Phoenix)

```bash
# Default — with Phoenix:
docker compose --profile phoenix up -d --build

# Without Phoenix (Arize-only or no telemetry):
docker compose up -d --build
```

Exposes:
- TravelShaper API on port 8000
- Phoenix UI on port 6006 (when profile active)

---

## 13. Success Criteria

This implementation is successful if:

1. The agent responds to travel planning queries with flight, hotel, and cultural recommendations sourced from real APIs
2. Three new tools (`search_flights`, `search_hotels`, `get_cultural_guide`) are integrated into the LangGraph agent
3. Configurable OTel tracing captures traces for all LLM calls and tool invocations
4. 11 diverse queries are traced and exportable
5. Three evaluation metrics are configured and run against traces
6. 25 unit tests pass
7. A Dockerfile is included and builds successfully
8. A browser chat interface is served at `http://localhost:8000`
9. The README documents setup, usage, architecture, and design decisions
10. A 20–25 minute presentation covers architecture, observability, evaluation, deployment design, and a live demo

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SerpAPI free tier exhausted | No flight/hotel results | Use mock responses for dev; reserve live queries for demo |
| SerpAPI returns empty results | Incomplete briefing | Agent gracefully notes missing data; DuckDuckGo fills gaps |
| OpenAI API latency spikes | Slow responses | Set reasonable timeouts |
| Cultural guide returns low-quality results | Inaccurate advice | Agent falls back to LLM training knowledge |
| Phoenix instrumentation adds overhead | Slightly slower responses | Acceptable for assessment; production uses async export |

---

## Appendix A: Interest Category Definitions

(Unchanged from previous version.)

---

## Appendix B: Budget Mode Behavior

(Unchanged from previous version.)
