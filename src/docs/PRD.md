# Product Requirements Document — TravelShaper Travel Assistant

**Version:** 1.1
**Date:** March 2026
**Status:** Implementation phase
**Author:** [Your Name]

---

## 1. Purpose

This document defines the product requirements for TravelShaper, an AI-powered travel planning assistant built as a technical assessment. TravelShaper extends a LangGraph starter application into a functional travel agent that searches real flight and hotel data, provides cultural preparation guidance, and delivers synthesized trip recommendations — all instrumented with Arize Phoenix for observability and evaluation.

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
- Deeper saftey and security considerations


---

## 6. Scope

### 6.1 In scope (this implementation)

| Capability | Description |
|------------|-------------|
| Browser chat interface | Self-contained HTML/CSS/JS UI served at `http://localhost:8000` by FastAPI; calls the `/chat` endpoint; coexists with the REST API |
| Flight search | Query Google Flights via SerpAPI; return structured results with prices, airlines, duration, layovers |
| Hotel search | Query Google Hotels via SerpAPI; return structured results with nightly rates, ratings, amenities |
| Cultural guide | Web-search-based research on language basics, etiquette, tipping, dress code, and common mistakes for American travelers |
| Interest discovery | Web search scoped to the traveler's stated interests (food, arts, events, fitness, nature, photography) |
| Synthesized briefing | LLM combines all tool results into a single opinionated travel recommendation |
| Budget-aware ranking | Recommendations are shaped by the traveler's budget preference |
| Phoenix observability | All LLM calls and tool invocations captured as OpenTelemetry traces |
| Evaluation | User frustration detection and tool usage correctness evaluation on traced queries |
| Tests | Unit tests covering tool schemas, agent graph construction, and API endpoints |
| Docker | Dockerfile for the application; docker-compose.yml including Phoenix |
| API | FastAPI server with `/chat` and `/health` endpoints |

### 6.2 Out of scope (this implementation)

| Capability | Rationale |
|------------|-----------|
| Booking or payment | TravelShaper recommends; it does not transact |
| Multi-turn conversation memory | Current implementation is single-turn; session management is a production enhancement |
| Dedicated train/ferry APIs | Train and ferry guidance is available via general web search but not through structured travel APIs |
| User accounts or saved trips | No persistence layer beyond Phoenix traces |
| Full frontend application | The browser UI is intentionally minimal — a single HTML file for demo and development use. A production-grade frontend (React app, mobile app, etc.) is out of scope |
| Real-time price alerts | No background jobs or push notifications |
| Multi-language support | English only |

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
| Output | List of flight options with: airline, price, duration, number of stops, layover details, departure/arrival times |
| Budget behavior | "Save money" → sort by price ascending; "Full experience" → sort by top flights (Google's default ranking favoring convenience) |
| Error handling | Return a message indicating flights could not be found if SerpAPI returns empty or errors |

**search_hotels**

| Property | Specification |
|----------|---------------|
| Input | Destination query, check-in date, check-out date, number of adults, optional price ceiling |
| Source | SerpAPI `google_hotels` engine |
| Output | List of properties with: name, nightly rate, overall rating, review count, amenities, neighborhood |
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
2. Provides 2–4 options per category, not exhaustive lists
3. Explains *why* each recommendation fits the traveler's stated preferences
4. Includes cultural preparation (language, etiquette, dress) when a cultural guide was retrieved
5. Includes interest-based suggestions (food spots, photo locations, etc.) when relevant
6. Notes tradeoffs honestly ("cheaper but longer layover," "great location but noisy street")
7. Acknowledges limitations when data is thin ("I couldn't find specific event listings for those dates")

### 7.4 API contract

**GET /**

Serves the browser chat interface (`static/index.html`). Returns HTTP 200 with the HTML page. The REST API endpoints take routing priority — this mount only activates for paths not claimed by `/chat` or `/health`.

**POST /chat**

Request:
```json
{
  "message": "string (required)"
}
```

Response:
```json
{
  "response": "string"
}
```

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

These are best-effort targets, not SLAs. Response time depends on SerpAPI latency and OpenAI API load.

### 8.2 Reliability

- The agent must not crash on malformed input. Invalid or incomplete messages should produce a helpful response or a clear error message.
- If a tool call fails (SerpAPI timeout, rate limit), the agent should continue with available results rather than failing entirely.
- The `/health` endpoint must always respond, even if external APIs are down.

### 8.3 Observability

- Every LLM invocation must produce a Phoenix span capturing: input prompt, output response, model name, token usage, and latency.
- Every tool invocation must produce a Phoenix span capturing: tool name, input parameters, output data, and execution time.
- Spans must be organized into traces that represent a complete user interaction from request to response.

### 8.4 Cost

| Resource | Estimated cost per query |
|----------|------------------------|
| OpenAI GPT-4o | ~$0.02–$0.08 (depends on tool call count and response length) |
| SerpAPI | Free tier: 250 searches/month; ~2–4 searches per query |
| Total per briefing | ~$0.02–$0.08 (OpenAI dominates; SerpAPI is free tier) |

At free-tier SerpAPI, the system supports roughly 60–125 full briefings per month before hitting search limits.

### 8.5 Security

- API keys are stored in `.env` and never committed to version control.
- `.env` is listed in `.gitignore`.
- No user authentication is implemented in this version (out of scope).
- No personally identifiable information is stored or logged beyond Phoenix traces.

---

## 9. Agent Architecture

### 9.1 Graph structure

```
START → llm_call → should_continue?
                     ├── tool calls present → tool_node → llm_call (loop)
                     └── no tool calls     → END
```

This is the standard LangGraph ReAct pattern from the starter code. The extension adds three new tools to the tool registry without changing the graph topology.

### 9.2 System prompt

The agent's system prompt instructs it to:

1. Act as a travel planning assistant for American travelers
2. Collect trip details from the user's message (origin, destination, dates, budget, interests)
3. Use `search_flights` when it has enough info to query flights
4. Use `search_hotels` when it has enough info to query hotels
5. Use `get_cultural_guide` for international destinations
6. Use `web_search` for interest-specific discovery and general questions
7. Synthesize all results into a structured but conversational briefing
8. Explain reasoning behind recommendations
9. Acknowledge when information is limited or uncertain

### 9.3 Tool dispatch logic

The LLM decides which tools to call based on the user's message. Expected behavior:

| User message contains | Tools the agent should call |
|----------------------|----------------------------|
| Origin + destination + dates | `search_flights`, `search_hotels`, `get_cultural_guide` |
| Destination + interests only | `get_cultural_guide`, `web_search` |
| General travel question | `web_search` |
| "Find me flights from X to Y" | `search_flights` |
| "What should I know before visiting Japan?" | `get_cultural_guide` |

The agent may call multiple tools in a single turn. Tool selection is handled by the LLM, not hardcoded routing.

---

## 10. Evaluation Requirements

### 10.1 User frustration evaluation

Using Phoenix's evaluation framework, assess each traced interaction for signals of user frustration:

- Agent failed to use available tools when they were clearly relevant
- Agent returned generic advice when structured data was available
- Response was incomplete (e.g., flights but no hotels when both were expected)
- Agent hallucinated information not grounded in tool results

### 10.2 Tool usage correctness evaluation

Assess whether the agent selected appropriate tools and passed valid parameters:

- Did the agent call `search_flights` when the user asked about flights?
- Did the agent pass valid airport codes, dates, and parameters?
- Did the agent call `get_cultural_guide` for international destinations?
- Did the agent avoid calling tools with missing or malformed inputs?

### 10.3 Trace volume

A minimum of 10 diverse queries must be traced in Phoenix, covering:

- Full trip planning requests (all five inputs provided)
- Partial requests (destination only, or just "find flights")
- Interest-heavy requests ("best food in Barcelona")
- Cultural questions ("what should I know about Japan?")
- Edge cases (vague destinations, missing dates, unusual requests)

---

## 11. Testing Requirements

### 11.1 Unit tests (minimum 2, target 4+)

| Test | What it validates |
|------|-------------------|
| Tool schema test | Each tool's input parameters and output format match their Pydantic schemas |
| Agent graph test | The compiled graph has the expected nodes (`llm_call`, `tool_node`) and edges |
| API health test | `GET /health` returns `{"status": "ok"}` with status 200 |
| API chat test | `POST /chat` with a valid message returns a response with a non-empty `response` field |

### 11.2 Test execution

```bash
poetry run pytest tests/ -v
```

All tests must pass without requiring external API keys (mock external calls where needed).

---

## 12. Deployment Requirements

### 12.1 Local development

```bash
poetry install
cp .env.example .env
# Add API keys to .env
poetry run uvicorn api:app --reload
```

### 12.2 Docker

```bash
docker build -t travelshaper .
docker run -p 8000:8000 --env-file .env travelshaper
```

### 12.3 Docker Compose (with Phoenix)

```bash
docker-compose up
```

Exposes:
- TravelShaper API on port 8000
- Phoenix UI on port 6006

---

## 13. Success Criteria

This implementation is successful if:

1. The agent responds to travel planning queries with flight, hotel, and cultural recommendations sourced from real APIs
2. At least one new tool (`search_flights`, `search_hotels`, or `get_cultural_guide`) is integrated into the LangGraph agent and returns structured output
3. Phoenix captures traces for all LLM calls and tool invocations
4. At least 10 diverse queries are traced and exported
5. Two evaluation metrics (user frustration + tool correctness) are configured and run against traces
6. At least two unit tests pass
7. A Dockerfile is included and builds successfully
8. A browser chat interface is served at `http://localhost:8000` and coexists with the REST API
9. The README documents setup, usage, architecture, and design decisions
10. A 20–25 minute presentation covers architecture, observability, evaluation, deployment design, and a live demo

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SerpAPI free tier exhausted during development | No flight/hotel search results | Use mock responses for development; reserve live queries for demo |
| SerpAPI returns empty results for niche destinations | Incomplete briefing | Agent gracefully notes missing data; DuckDuckGo fills gaps |
| OpenAI API latency spikes | Slow responses | Set reasonable timeouts; note in presentation that latency depends on provider |
| Cultural guide returns low-quality web results | Inaccurate etiquette advice | Agent falls back to LLM training knowledge; README notes this is practical guidance, not authoritative |
| Phoenix instrumentation adds overhead | Slightly slower responses | Acceptable for assessment; note in architecture that production would use async export |

---

## 15. Open Questions

These are unresolved design decisions that would be addressed in subsequent iterations:

- Should train and ferry guidance remain best-effort web search, or become a dedicated API integration?
- Should the first release return one "best bundle" recommendation, or present separate budget / balanced / premium bundles?
- Should cultural/packing guidance be a standalone tool response, or always embedded in the main briefing?
- How much structured validation should be applied to user inputs (airport codes, date formats) before tool dispatch, vs. letting the LLM handle interpretation?
- At what point does the response become too long, and should TravelShaper offer a summary with "ask me for more detail on any section" follow-up?

---

## Appendix A: Interest Category Definitions

| Interest | Search strategy | Example queries |
|----------|----------------|-----------------|
| Food & Dining | Web search for restaurants, street food, food markets, must-try dishes at destination | "best restaurants Tokyo," "Tokyo street food guide" |
| Parties & Events | Web search for nightlife, live music, festivals, events during travel dates | "Tokyo nightlife October 2026," "events Tokyo October" |
| The Arts | Web search for museums, galleries, street art, architecture, underground culture | "Tokyo contemporary art museums," "Tokyo architecture walks" |
| Fitness | Web search for hiking trails, running routes, gyms, outdoor activities | "hiking near Tokyo," "running routes Tokyo" |
| Nature | Web search for parks, scenic views, gardens, day trips into nature | "day trips from Tokyo nature," "Tokyo gardens parks" |
| Photography | Web search for photogenic spots, iconic views, golden hour locations | "best photo spots Tokyo," "Tokyo photography locations" |

---

## Appendix B: Budget Mode Behavior

| Decision point | Save money | Full experience |
|----------------|-----------|-----------------|
| Flight ranking | Sort by price ascending | Sort by Google's "best flights" (convenience + price) |
| Hotel ranking | Sort by price; include hostels and guesthouses | Sort by rating; prefer 4-star+ properties |
| Restaurant suggestions | Street food, markets, local cheap eats | Top-rated restaurants, notable dining experiences |
| Activity suggestions | Free attractions, walking tours, public parks | Skip-the-line options, guided tours, signature experiences |
| Transport advice | Public transit tips, budget airlines | Direct flights, convenience-first routing |
| Tone | "Here's how to do Tokyo for under $100/day" | "Here's how to make the most of Tokyo" |
