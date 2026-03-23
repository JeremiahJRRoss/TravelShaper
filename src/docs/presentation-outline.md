# Presentation Outline — TravelShaper Travel Assistant

**Total time: 20–25 minutes**
**Format: Screen share with live demo**

---

## Slide 1: Title (30 sec)
- "TravelShaper — AI Travel Planning Assistant"
- Your name, date
- One-liner: "A single-turn LLM agent that combines flight search, hotel search, and cultural intelligence into a personalized travel briefing."

---

## Slide 2: The Problem (1 min)
- Planning a trip means bouncing across 5+ sites
- Flights on Google Flights, hotels on Booking.com, etiquette on random blogs, "what to wear" on forums
- Three pain points: fragmentation, decision fatigue, missing cultural context
- "What if one agent did all of this and explained its reasoning?"

---

## Slide 3: Product Overview (1 min)
- 5 structured form inputs: departure city, destination, departure date, duration, budget mode
- Interests: 6 checkboxes (Food, Arts, Photography, Nature, Fitness, Nightlife)
- Optional free-form preferences field (500 chars, LLM-validated before use)
- 4 tools: flights, hotels, cultural guide, web search
- 1 output: a synthesised travel briefing with hyperlinks for every named recommendation
- Browser UI at `http://localhost:8000` — no curl required for the demo
- Target user: English-speaking American leisure traveller

---

## Slide 4: Agent Architecture (3 min)
- Show the LangGraph ReAct loop diagram
- START → llm_call → should_continue → tool_node → llm_call → END
- "The graph topology is unchanged from the starter app — I only added tools"
- Walk through the 4 tools: what each does, what API backs it
- Explain why SerpAPI: one key, three engines, structured JSON, free tier

**Key point:** The LLM decides which tools to call. No hardcoded routing.

---

## Slide 5: Tool Deep Dive (2 min)
- Show tool interface pattern: `@tool` decorator, typed args, docstring, error handling
- "The docstring is the prompt — GPT-4o reads it to decide when to invoke the tool"
- Show the adapter principle: tools return formatted strings, not raw JSON
- Show error handling: tools never raise into the agent loop

---

## Slide 6: System Prompt Design (1.5 min)
- **Two prompts, not one** — budget mode selects the voice at runtime via `get_system_prompt()`
- **Save money:** Bourdain's honesty + Billy Dee Williams' cool + Gladwell's narrative intelligence. Budget is philosophy, not compromise.
- **Full experience:** Robin Leach's spectacle + Pharrell's joy + Salman Rushdie's prose depth. Cities as mythology.
- Both prompts share: mandatory hyperlinks for every named recommendation, cinematic opener, memorable closing line
- Key insight: two separate prompts rather than one with conditional instructions — the model commits fully to one voice instead of blending

---

## Slide 7: Observability — OpenTelemetry & OpenInference (3 min)

**Explain the concepts:**
- **OpenTelemetry** — the industry standard for distributed tracing. Defines how to capture spans (units of work) and group them into traces (end-to-end requests).
- **OpenInference** — a semantic convention built on top of OpenTelemetry, specifically for AI/ML applications. Adds standard attributes for LLM calls (model, tokens, prompt/response) and tool calls (name, input, output).
- **Traces vs. Spans:**
  - A **trace** is the full lifecycle of one user request — from POST /chat to the final response
  - A **span** is a single step within that trace — one LLM call, one tool execution
  - Spans are nested: the root span contains child spans for each LLM call and tool call
- **Phoenix** consumes these traces and provides a UI for exploring, filtering, and evaluating them

**Show in Phoenix:**
- A real trace from the demo queries
- Point out the root span, LLM spans, tool spans
- Show token counts, latency per span, tool inputs/outputs

---

## Slide 8: Traces in Action (2 min)
- Show 2-3 different trace patterns:
  1. Full trip query (4 tool calls, 2 LLM calls)
  2. Cultural guide only (1 tool call)
  3. Vague query (web search fallback)
- "You can see exactly what the agent decided to do and why"
- Show how latency breaks down: most time is in external API calls

---

## Slide 9: Evaluation (3 min)
- Two metrics: User Frustration and Tool Usage Correctness
- Both use LLM-as-judge pattern: send trace data to GPT-4o with an evaluation prompt
- **User Frustration:** detects incomplete answers, ignored requests, fabricated details
- **Tool Correctness:** checks if the right tools were called with valid parameters
- Show evaluation results in Phoenix: labels, scores, explanations
- Show the frustrated interactions dataset (filtered from evaluation results)
- "This is how you'd build a feedback loop — identify failure cases, create a dataset, fine-tune or adjust prompts"

---

## Slide 10: Deployment Architecture Design (3 min)
- Show the production architecture diagram:
  - Load balancer → N stateless TravelShaper instances → external APIs
  - Redis for caching + future session memory
  - Phoenix/OTEL collector for async trace export
- **Scaling strategy:** horizontal scaling is easy because the app is stateless. Each request is independent.
- **Latency optimization:** parallel tool dispatch, response caching, async trace export, capped tool output length
- **Cost considerations:** OpenAI is the dominant cost (~$0.02-$0.08/query), SerpAPI free tier supports ~60-125 briefings/month, production would use paid tier + caching

---

## Slide 11: Live Demo (5 min)
1. Show the app running (curl to /health)
2. Send a full trip planning query (Query 1 from trace-queries.md)
3. Walk through the response — point out flights, hotels, cultural prep, interest suggestions
4. Switch to Phoenix UI — show the trace that was just created
5. Show spans: LLM calls, tool calls, latency breakdown
6. Show evaluation results from the pre-run evaluation batch
7. Optionally: send a second query (cultural-only or budget trip) to show different tool dispatch

**Demo options:**

Option A — Browser UI (recommended for presentation):
```
Open http://localhost:8000 in browser
Fill in the form: San Francisco → Tokyo, 2 weeks, save money, food + photography
Click "Plan my trip →" and watch the live SSE status feed
```

Option B — curl (for showing the API directly):
```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool

# Full trip query with place validation
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Flying from San Francisco to Tokyo, mid-October, 10 days, save money, love food and photography.",
    "departure": "San Francisco, CA",
    "destination": "Tokyo, Japan"
  }' | python3 -m json.tool
```

---

## Slide 12: What I'd Do Next (1 min)
- Multi-turn conversation memory (Redis-backed session state)
- Weather API for data-driven packing advice
- Dedicated train/ferry search (Trainline, Omio)
- Response caching to reduce SerpAPI cost and latency
- Replace SerpAPI with direct Amadeus/Booking.com APIs for production ToS compliance
- Google Places Autocomplete as a client-side layer on top of LLM place validation

---

## Slide 13: Q&A
- "Happy to dig into any part of the architecture, evaluation approach, or tool design"

---

## Timing summary

| Section | Minutes |
|---------|---------|
| Title + Problem + Overview | 2.5 |
| Agent Architecture + Tools | 5 |
| System Prompt | 1 |
| Observability (OTEL/OpenInference/Traces) | 5 |
| Evaluation | 3 |
| Deployment Architecture | 3 |
| Live Demo | 5 |
| What's Next + Q&A | 1.5 |
| **Total** | **~25 min** |

---

## Preparation checklist

Before the presentation:
- [ ] TravelShaper running: `docker-compose up -d` from `src/`
- [ ] Browser open at `http://localhost:8000` — confirm UI loads
- [ ] Phoenix running at `http://localhost:6006` with traces from 10 queries
- [ ] Evaluations already run (results visible in Phoenix)
- [ ] Terminal with curl commands ready as backup
- [ ] Architecture diagram ready (screenshot or SVG)
- [ ] No API keys visible on screen
- [ ] Run `./run_traces.sh` beforehand if traces are empty
