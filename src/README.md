# TravelShaper — AI Travel Assistant

An intelligent travel planning assistant powered by LLM agents. TravelShaper helps you find flights, hotels, and cultural insights for your destination — all through a single conversation.

Built with LangGraph, FastAPI, and instrumented with Arize Phoenix for observability and evaluation. Accessible via a browser chat interface at `http://localhost:8000` or directly through the REST API.

---

## What TravelShaper Does

You tell TravelShaper where you're coming from, where you want to go, your rough travel dates, and what matters to you. It searches live flight and hotel data, gathers cultural and destination intelligence from the web, and delivers a curated travel briefing — not a wall of links, but an opinionated recommendation.

### The Conversation Flow

**1. You share your trip details**

TravelShaper asks for five things through natural conversation:

| Detail | Example |
|--------|---------|
| **Origin** | "I'm flying out of San Francisco" |
| **Destination** | "I want to go to Tokyo" |
| **Dates** | "Sometime in mid-October, about 10 days" |
| **Budget style** | "I want the full experience" or "I'm trying to save money" |
| **Interests** | "I'm into food, photography, and art" |

TravelShaper works best when you include all five details in a single message. For the richest results, be specific — "I'm flying from SFO to Tokyo in mid-October for 10 days, budget-friendly, and I love food and photography" gives TravelShaper everything it needs in one shot.

> **Note:** The current implementation is single-turn — each `/chat` request is independent. In a production version, conversation memory would allow multi-turn back-and-forth where TravelShaper asks follow-ups across messages. For now, include as much detail as possible in your initial request.

You can also include optional details, and TravelShaper will factor them in:

- Direct flights only
- Hotel budget cap (e.g., "under $100/night")
- Solo traveler, couple, or family
- Preferred neighborhood style (walkable, quiet, nightlife-friendly)
- Accessibility needs
- Walking tolerance ("I can walk all day" vs. "I prefer short distances")
- Interest in trains or day trips from the destination

**2. TravelShaper searches on your behalf**

Once it understands your trip, TravelShaper dispatches specialized tools:

- **Flight search** — Queries Google Flights via SerpAPI for structured results: real prices, airlines, layovers, and duration.
- **Hotel search** — Queries Google Hotels via SerpAPI for structured results: nightly rates, ratings, amenities, and images.
- **Cultural guide** — Searches the web for destination-specific etiquette, language phrases, dress codes, and tipping customs. Results are web-sourced and synthesized by the LLM — useful and practical, but not from a structured travel database.
- **General web search** — Fills in gaps with open web results for your specific interests (restaurants, events, photo spots, etc.). Coverage and quality vary by destination.

**3. You receive a travel briefing**

TravelShaper synthesizes everything into a single conversational response covering:

- **Getting there** — Best flight options ranked by your budget preference, with a note on the best value.
- **Where to stay** — Hotel recommendations matched to your budget and neighborhood preferences.
- **What to know before you go** — Key phrases in the local language, etiquette tips, what to wear for the season and culture, and things to avoid.
- **What to do** — Recommendations tailored to your stated interests (food spots, photo locations, art scenes, nature hikes, nightlife, fitness activities).

TravelShaper explains *why* it recommends something, not just *what*. For example: "This hotel is recommended because it's walkable to the food district and under your budget" or "This flight is cheaper but has a 4-hour layover — worth it if you're saving money, skip it if you want to arrive rested."

---

## Your Interests

When TravelShaper asks what you care about, choose from these categories (or combine them):

| Interest | What TravelShaper finds for you |
|----------|---------------------------|
| **Food & Dining** | Local restaurants, street food, food markets, dining customs, must-try dishes |
| **Parties & Events** | Nightlife, live music, festivals, local events happening during your dates |
| **The Arts** | Museums, galleries, street art, architecture, local craft scenes, underground culture |
| **Fitness** | Hiking trails, running routes, local gyms, outdoor activities, cycling |
| **Nature** | National parks, scenic views, beaches, gardens, day trips into the outdoors |
| **Photography** | Photogenic spots, golden hour locations, iconic views, hidden gems worth shooting |

You can pick as many as you want. TravelShaper adjusts its research and recommendations accordingly.

---

## Budget Modes

TravelShaper tailors every recommendation to one of two modes:

**"Save money"** — Prioritizes budget airlines, hostels and guesthouses, free attractions, street food, and public transit tips. TravelShaper will flag when spending a little more is genuinely worth it.

**"Full experience"** — Prioritizes comfort, quality, and memorable experiences. Direct flights, well-reviewed hotels, top-rated restaurants, and skip-the-line suggestions. TravelShaper will still flag obvious overpriced tourist traps.

---

## Cultural & Travel Prep

Every briefing includes a preparation section tailored for American travelers:

### Language Basics
- Essential phrases: hello, thank you, please, excuse me, how much?, where is...?
- Pronunciation tips
- Whether English is widely spoken at your destination

### Etiquette
- Greeting customs (bowing, handshakes, cheek kisses)
- Tipping expectations
- Table manners and dining norms
- Religious site protocols
- Common faux pas to avoid

### What to Wear
- Weather-appropriate clothing for your travel dates
- Cultural dress expectations (covering shoulders for temples, modest dress in conservative areas)
- Practical footwear advice (cobblestones, hiking, temple visits requiring shoe removal)
- Packing suggestions for the season

---

## Running the Application

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation)
- A [SerpAPI](https://serpapi.com) API key (free tier: 250 searches/month)
- An [OpenAI](https://platform.openai.com) API key

### Setup

1. Clone the repository:

```bash
git clone <your-repo-url>
cd se-interview
```

2. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
# .venv\Scripts\activate    # Windows
```

3. Install Poetry inside the venv and install dependencies:

```bash
pip install --upgrade pip
pip install poetry==1.8.2
poetry install -E dev
```

4. *(Optional)* Install Phoenix tracing packages:

```bash
pip install arize-phoenix arize-phoenix-evals arize-phoenix-otel \
            openinference-instrumentation-langchain
```

> **Note:** Phoenix packages are installed with `pip` rather than via a Poetry
> extra because `arize-phoenix-otel` has Python version constraints that conflict
> with Poetry's resolver on Python 3.11/3.12.

5. Configure environment variables:

```bash
cp .env.example .env
```

Edit `.env` and add your keys:

```
OPENAI_API_KEY=your_openai_key_here
SERPAPI_API_KEY=your_serpapi_key_here
```

4. Start the API server:

```bash
poetry run uvicorn api:app --reload
```

The API is now available at `http://localhost:8000`.

### Using Docker

Build and run:

```bash
docker build -t travelshaper .
docker run -p 8000:8000 --env-file .env travelshaper
```

Or with Docker Compose (includes Phoenix):

```bash
docker-compose up
```

This starts both the TravelShaper API on port 8000 and Phoenix UI on port 6006.

> **Note:** The `docker-compose.yml` is included in the repository. If running Phoenix separately, see the Observability section below.

---

## Using the Web Interface

Once the server is running, open your browser and go to:

```
http://localhost:8000
```

You'll see a chat interface where you can type travel queries directly. The interface talks to the same `/chat` endpoint as curl — no difference in behaviour, just a friendlier way to interact during development and demos.

The API endpoints remain fully available alongside the UI. curl, pytest, and any other HTTP client work exactly as before.

---

## API Endpoints

### GET /

Serves the browser-based chat interface. Open in any browser — no curl needed.

```
http://localhost:8000
```

### POST /chat

Send a message to TravelShaper and receive a response.

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to plan a trip to Barcelona from San Francisco in October. I love food and photography and want the full experience."}'
```

Response:

```json
{
  "response": "Great choice! Barcelona in October is ideal — warm enough for outdoor dining but past the summer crowds. Let me search for flights, hotels, and local recommendations for you..."
}
```

### POST /chat (additional queries)

Each request is independent (no session memory). To ask about a different aspect of your trip, include the relevant context again:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the nightlife like in Barcelona in October? Are there any art exhibitions?"}'
```

> **Production enhancement:** Adding session-based conversation memory would allow true multi-turn planning where TravelShaper remembers earlier context across requests.

### GET /health

Health check endpoint.

```bash
curl http://localhost:8000/health
```

Returns `{"status": "ok"}`.

---

## Architecture

```
User
  │
  ▼
FastAPI (/chat)
  │
  ▼
LangGraph Agent
  │
  ├── llm_call (GPT-4o with system prompt + tools)
  │     │
  │     ├── Needs more info? → Ask user follow-up
  │     │
  │     └── Ready to search? → Dispatch tools
  │           │
  │           ├── search_flights    (SerpAPI → Google Flights)
  │           ├── search_hotels     (SerpAPI → Google Hotels)
  │           ├── get_cultural_guide (SerpAPI → Google Search, scoped)
  │           └── duckduckgo_search  (DuckDuckGo, general fallback)
  │
  ├── tool_node (executes tool calls, returns results)
  │
  └── llm_call (synthesizes results into travel briefing)
        │
        ▼
      Response to user
```

The agent runs in a loop: the LLM decides whether to call tools or respond. It may call multiple tools in a single turn, then synthesize all results into one cohesive briefing.

### Tools

| Tool | API | What it returns |
|------|-----|-----------------|
| `search_flights` | SerpAPI (google_flights engine) | Airlines, prices, durations, layovers, booking links |
| `search_hotels` | SerpAPI (google_hotels engine) | Hotel names, nightly rates, ratings, amenities, images |
| `get_cultural_guide` | SerpAPI (google engine, scoped) | Language phrases, etiquette, dress code, local customs |
| `duckduckgo_search` | DuckDuckGo (no key needed) | General search results for interests and open questions |

---

## Observability with Arize Phoenix

TravelShaper is instrumented with Arize Phoenix for full observability of every agent interaction.

### Starting Phoenix

```bash
phoenix serve
```

Phoenix UI is available at `http://localhost:6006`.

### What Phoenix Captures

- **LLM calls** — Every GPT-4o invocation with full prompt, response, token usage, and latency.
- **Tool usage** — Every tool call with input parameters, output data, and execution time.
- **Agent traces** — End-to-end traces showing the full conversation loop: intake → tool dispatch → synthesis.

### Running Evaluations

```bash
poetry run python evaluations/run_evals.py
```

This runs two evaluation metrics on captured traces:

1. **User Frustration** — Detects traces where the user had to repeat themselves, got incomplete answers, or expressed dissatisfaction.
2. **Tool Usage Correctness** — Evaluates whether the agent selected the right tools for the user's query and passed valid parameters.

---

## Testing

Run the test suite:

```bash
poetry run pytest tests/ -v
```

Tests cover:

- Tool schema validation (correct input/output types)
- Agent graph construction (nodes and edges wired correctly)
- API endpoint responses (health check, chat request/response format)

---

## Project Structure

Target layout for the completed project:

```
se-interview/
├── api.py                  # FastAPI server with /chat, /health, and static UI
├── agent.py                # LangGraph agent — graph definition and system prompt
├── static/
│   └── index.html          # Browser chat interface (served at http://localhost:8000)
├── tools/
│   ├── __init__.py
│   ├── flights.py          # search_flights — SerpAPI Google Flights
│   ├── hotels.py           # search_hotels — SerpAPI Google Hotels
│   └── cultural_guide.py   # get_cultural_guide — scoped web search + synthesis
├── evaluations/
│   ├── run_evals.py        # Phoenix evaluation runner
│   └── metrics/
│       ├── frustration.py  # User frustration evaluator
│       └── tool_correctness.py
├── tests/
│   ├── test_tools.py       # Tool unit tests
│   ├── test_agent.py       # Agent graph tests
│   └── test_api.py         # API endpoint tests
├── Dockerfile
├── docker-compose.yml      # App + Phoenix
├── pyproject.toml           # Poetry dependencies
├── .env.example
└── README.md               # This file
```

---

## Example Session

The following is an illustrative example of the kind of response TravelShaper produces. Actual output depends on live search results at query time and will vary.

```
You:     Hey, I'm planning a trip to Japan. Flying from SFO,
         sometime in April, about 2 weeks. I love food and
         photography. Trying to save money where I can.

TravelShaper: Great timing — April is cherry blossom season in Japan,
         which is perfect for photography. Let me search for
         flights, hotels, and local intel for you.

         ✈ FLIGHTS (SFO → Tokyo)
         I found several options for mid-April:
         - ANA via LAX: $687 round trip, 14h — best value
         - JAL direct: $892 round trip, 11h — worth it if you
           want to arrive rested
         - United direct: $845 round trip, 11.5h

         🏨 HOTELS
         For budget-conscious stays in Tokyo:
         - Khaosan Tokyo Kabuki: $35/night, Asakusa — great
           location for temples and street food
         - Hotel Graphy Nezu: $62/night, Bunkyo — quiet area,
           near Ueno Park for cherry blossoms

         🗾 BEFORE YOU GO
         Language: "Sumimasen" (excuse me) and "Arigatou
         gozaimasu" (thank you) will get you far. English is
         limited outside Tokyo station and tourist areas.

         Etiquette: Don't tip — it's considered rude. Remove
         shoes indoors (socks without holes!). Don't eat while
         walking. Bow slightly when greeting.

         What to wear: April averages 55-65°F. Layers are key —
         warm midday, cool mornings. Comfortable walking shoes
         essential (you'll walk 10+ miles/day). Temples require
         covered shoulders.

         📸 PHOTOGRAPHY & FOOD
         - Meguro River and Chidorigafuchi for cherry blossoms
         - Tsukiji Outer Market for street food photography
         - Golden Gai in Shinjuku — tiny atmospheric bars
         - Yanaka district — old Tokyo, great for street shots
         - Fuunji ramen in Shinjuku (cash only, expect a line)
```

A separate query like "How do I get from Tokyo to Kyoto on a budget?" would produce a focused response about the Shinkansen, Japan Rail Pass options, and travel tips for that route.

---

## User Experience Principles

**Clear** — TravelShaper does not dump raw search results. It synthesizes, ranks, and explains so the user gets a recommendation, not a research project.

**Personalized** — Every recommendation reflects the traveler's stated budget, interests, and constraints. Two users asking about the same city get different briefings.

**Explainable** — TravelShaper states the reason behind each major recommendation. "This hotel is near the food district and within budget" is more useful than "here's a hotel."

**Actionable** — The user should leave with a workable travel plan: specific flights, named hotels, concrete restaurant picks, and practical packing advice.

**Honest** — If search coverage is thin, data is uncertain, or a recommendation has tradeoffs, TravelShaper says so. It flags when prices may have changed and when its guidance is general rather than verified.

---

## Known Limitations

- TravelShaper is a planning assistant, not a booking engine. It recommends options but does not complete purchases.
- Flight and hotel prices change frequently. Results reflect the time of search, not guaranteed availability.
- Train and ferry data is less structured than flight and hotel data. Coverage varies by region.
- Cultural etiquette and dress guidance is practical advice based on common norms, not absolute rules. Local customs vary within countries.
- Weather-based packing guidance is strongest for trips within the next 1–2 weeks. Seasonal averages are used for trips further out.
- The app is designed for English-speaking American travelers. Guidance assumes U.S. norms as the baseline.

---

## Troubleshooting

**The server does not start**
- Confirm Python 3.11+ is installed: `python --version`
- Confirm the venv is active: your prompt should show `(.venv)`
- Confirm Poetry is installed in the venv: `poetry --version`
- Run `poetry install -E dev` to ensure dependencies are present
- Confirm `.env` exists and contains valid keys

**The app returns an authentication error**
- Check that `OPENAI_API_KEY` is set correctly in `.env`
- Check that `SERPAPI_API_KEY` is set correctly in `.env`
- Verify your SerpAPI key at [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key)

**The app responds but results are poor or incomplete**
- Make sure your message includes origin, destination, timeline, and budget preference
- Check SerpAPI usage — the free tier allows 250 searches/month
- Try a well-known destination (Tokyo, Barcelona, Rome) for the most reliable results

**Traces are missing in Phoenix**
- Confirm Phoenix is running: `phoenix serve`
- Check that the Phoenix endpoint is configured in the app's instrumentation
- Run at least one `/chat` query after Phoenix is started, then refresh the Phoenix UI

---

---

## Design Decisions

**Browser chat interface** — A single self-contained HTML file served directly by FastAPI at `http://localhost:8000`. No separate frontend server, no npm, no build step. The UI calls the same `/chat` endpoint as curl, so the REST API remains fully available for testing and automation alongside it.

**SerpAPI as single data provider** — One API key powers flights, hotels, and scoped web searches. The Google Flights and Google Hotels engines return structured JSON with real pricing data. Cultural and interest searches use SerpAPI's general Google engine — useful and practical, but less structured than the dedicated travel endpoints.

**Cultural guide as a first-class tool** — Most travel chatbots skip cultural preparation entirely. For American travelers especially, etiquette and language guidance prevents real-world embarrassment and shows the agent adds value beyond price comparison.

**DuckDuckGo as fallback** — The original codebase's search tool remains available for general queries that don't fit the specialized tools. No API key required.

**Single-turn design** — Each `/chat` request is currently independent. The user gets the best results by including all trip details in one message. Multi-turn conversation memory (session-based chat history) is a natural production enhancement but is out of scope for this implementation.

**Budget as a lens, not a filter** — Budget preference affects ranking and tone, not hard cutoffs. A budget traveler still sees the occasional splurge-worthy option; a full-experience traveler still gets warned about tourist traps.
