# TravelShaper

**AI travel planning assistant** — fill in a form, get an opinionated briefing with flights, hotels, cultural prep, and activity picks.

Every recommendation includes a hyperlink and an explanation of *why* it was chosen. The agent runs two distinct voices depending on budget mode, and the entire request flow is instrumented with Arize Phoenix for observability.

---

## What It Does

TravelShaper takes a departure city, destination, dates, budget preference, and interests, then dispatches four tools to gather live data:

- **search_flights** — Google Flights via SerpAPI (prices, airlines, layovers)
- **search_hotels** — Google Hotels via SerpAPI (rates, ratings, amenities)
- **get_cultural_guide** — scoped Google search for etiquette, language, dress code
- **duckduckgo_search** — open web search for interests and gaps (no key needed)

It synthesises the results into a single briefing covering getting there, where to stay, cultural prep, and what to do — tailored to your budget mode and selected interests.

The agent runs two distinct voices depending on budget mode. "Save money" activates a Bourdain / Billy Dee Williams / Gladwell voice — muscular prose, insider knowledge, budget as philosophy. "Full experience" activates a Robin Leach / Pharrell / Rushdie voice — theatrical, joyful, literary. Both are instructed to include a markdown hyperlink for every named place, hotel, restaurant, and attraction.

Voice routing works by keyword matching on the assembled message string. The browser UI always includes the exact phrase "save money" or "full experience" in the message it constructs, so routing is reliable from the form. When using curl or the API directly, include one of these keywords in your message: `save money`, `budget`, `cheapest`, or `spend as little` to trigger the budget voice. Any message without these keywords defaults to the full-experience voice.

---

## Before You Begin

TravelShaper needs two API keys: an OpenAI key (powers the agent and validation classifiers) and a SerpAPI key (powers flight, hotel, and cultural guide searches). Everything else lives inside the project.

**Where to get keys:**

- **OpenAI** (required) — [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **SerpAPI** (required for flights, hotels, cultural guide) — [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). Free tier: 250 searches/month (~60–125 full briefings). Without this key, the agent falls back to DuckDuckGo for everything — functional, but limited.

You will create a `.env` file with these keys during setup. The `.env` file is listed in `.gitignore` and will never be committed.

---

## Prerequisites

You need **Docker** (with Docker Compose) to run the app, and **Python 3.11+** to run tests and traces locally.

**macOS:** Install Docker Desktop for Mac from [docs.docker.com/desktop/install/mac-install](https://docs.docker.com/desktop/install/mac-install/). Python 3.11+ ships with macOS or can be installed via [python.org](https://www.python.org/downloads/) or `brew install python`.

**Windows 10/11:** Install Docker Desktop for Windows from [docs.docker.com/desktop/install/windows-install](https://docs.docker.com/desktop/install/windows-install/) with WSL 2 backend enabled. Install Python 3.11+ from [python.org/downloads](https://www.python.org/downloads/) — check "Add Python to PATH" during install.

**Linux (Desktop):** Install Docker Engine and the Docker Compose plugin from [docs.docker.com/engine/install](https://docs.docker.com/engine/install/). Python 3.11+ ships with most distributions. On Ubuntu/Debian, if missing: `sudo apt install python3 python3-venv python3-pip`.

Verify both are available:

```
docker compose version
python3 --version
```

On Windows, use `python --version` instead of `python3 --version`. If `python` is not recognized, the installer's "Add to PATH" checkbox was likely not checked — reinstall or add it manually.

If `docker compose` (with a space) does not work but `docker-compose` (hyphenated) does, you have the legacy v1 CLI — that works too, just substitute `docker-compose` wherever you see `docker compose` below.

On Linux, if you get a permission error from Docker, either prefix commands with `sudo` or add yourself to the docker group: `sudo usermod -aG docker $USER` (requires logout/login to take effect).

---

## Start the App

All commands in this section are run from inside the `src/` directory.

**Step 1.** Create your `.env` file:

On macOS or Linux:

```
cd src
cp .env.example .env
```

On Windows:

```
cd src
copy .env.example .env
```

Open `.env` in any text editor and add your OpenAI and SerpAPI keys.

**Step 2.** Build and start the stack:

```
docker compose up -d --build
```

This builds the TravelShaper container with all dependencies and starts both the app and Phoenix. Takes 1–3 minutes on first build.

**Step 3.** Verify both containers are running:

```
docker ps
```

You should see two containers — one on port 8000 (TravelShaper) and one on port 6006 (Phoenix), both with `Up` status.

When the stack is running:

| Service | URL |
|---------|-----|
| TravelShaper (app + API) | [http://localhost:8000](http://localhost:8000) |
| Phoenix (tracing UI) | [http://localhost:6006](http://localhost:6006) |

To stop the stack: `docker compose down`. To rebuild after code changes: `docker compose down && docker compose up -d --build`.

---

## Quick Reference

Once the Docker stack is running and your venv is set up, these are the things you will do most often.

### Access the browser UI

Open [http://localhost:8000](http://localhost:8000) in any browser. The form collects departure, destination, dates, budget mode, interests, and optional preferences. Click "Plan my trip →" to get a full briefing streamed in real time. No login, no setup — the browser talks directly to the same API that curl uses.

### Access Phoenix (tracing UI)

Open [http://localhost:6006](http://localhost:6006) in any browser. Every request to `/chat` or `/chat/stream` generates a trace. Click into any trace to see the full tool call chain — which tools were called, what arguments were passed, how long each step took, and the agent's final response. Phoenix runs as a separate container started by Docker Compose and requires no additional setup.


### Test the API with a single curl request

```
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from San Francisco, CA (please identify the nearest major international airport). Destination: Tokyo, Japan. Departure: 2026-06-15. Return: 2026-06-29 (2 weeks). Budget preference: save money. Interests: food and dining, photography. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "San Francisco, CA",
    "destination": "Tokyo, Japan"
  }' | python3 -m json.tool
```

On Windows, replace `python3` with `python` and use double quotes for the outer shell quoting (or run the command inside WSL or Git Bash). The response is a JSON object with a `response` field containing the full travel briefing in markdown.

To verify the server is alive without triggering a full agent run:

```
curl http://localhost:8000/health
```

Expected output: `{"status":"ok"}`


### Query trace information from the terminal

Phoenix exposes a REST API at `localhost:6006`. To fetch recent spans:

```
curl -s http://localhost:6006/v1/spans?limit=10 | python3 -m json.tool
```

To fetch traces:

```
curl -s http://localhost:6006/v1/traces?limit=5 | python3 -m json.tool
```

---

## Set Up Python for Traces and Evaluations

Traces and evaluations both run on your local machine, outside Docker. They use a Python virtual environment inside `src/`. You only need to set this up once.

**Step 1.** Open a second terminal and navigate to `src/`:

```
cd src
```

**Step 2.** Create the virtual environment:

On macOS or Linux:

```
python3 -m venv .venv
```

On Windows:

```
python -m venv .venv
```

This creates a `.venv/` directory inside `src/` that isolates all project dependencies from your system Python (and from other distributions like Anaconda). The `.venv/` directory is listed in `.gitignore` and will not be committed.

**Step 3.** Activate the virtual environment:

On macOS or Linux:

```
source .venv/bin/activate
```

On Windows (Command Prompt):

```
.venv\Scripts\activate.bat
```

On Windows (PowerShell):

```
.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script with a security error, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` first, then try again.

Your terminal prompt should now show `(.venv)` at the beginning. This tells you the venv is active. If you open a new terminal, you will need to activate it again — the activation only applies to the current shell session.

**Step 4.** Install dependencies:

```
pip install requests arize-phoenix arize-phoenix-evals pandas openai
```

The `requests` package is all that `run_traces.py` needs. The remaining packages are for `run_evals.py`, which uses the Phoenix client to pull traces and the Phoenix evals library to score them with gpt-4o. If your system has Anaconda installed, make sure your venv is not inheriting Anaconda's packages — run `conda deactivate` before activating your venv if you see `ValueError: numpy.dtype size changed`.

You only need to install these once. In future terminal sessions, just activate the venv:

On macOS or Linux: `cd src && source .venv/bin/activate`

On Windows: `cd src` then `.venv\Scripts\activate.bat` or `.venv\Scripts\Activate.ps1`


---

## Generate Traces and Run Evaluations

This is the core observability workflow: generate traces by sending real queries to the agent, then score those traces with three LLM-as-judge metrics. Both scripts run from the same venv in the same terminal session.

Make sure you are in the `src/` directory with the venv active and the Docker stack is running.

If you prefer to work with trace data offline, `run_traces.py` run traces and save each query's input and response to a timestamped JSON file in the `src/` directory.

### Generate traces

```
python run_traces.py
```

This fires 11 real queries against the server at `localhost:8000`, covering every tool combination, both budget voices, auto-correction, vague inputs, past-date error handling, and edge cases. All dates are computed dynamically relative to today so the script never goes stale.

Results are saved to a timestamped JSON file in `src/` (e.g. `trace-results_2026-03-23_14-05-32.json`). Traces are also recorded in Phoenix at [http://localhost:6006](http://localhost:6006).

You can limit the number of queries for a quick smoke test:

```
python run_traces.py 3            # run first 3 queries only
python run_traces.py all          # run all 11 (the default)
```

### Run evaluations

Once traces exist in Phoenix, score them:

```
python run_evals.py
```

The script connects to Phoenix at `localhost:6006`, pulls the most recent traces, groups all spans by trace ID to identify the root span (user input + agent output) and child spans (actual tool calls), and scores each trace against three metrics. The tool correctness evaluator receives the real list of tools that were called — extracted from the trace data, not inferred from the response text.

Each trace is scored by three separate gpt-4o calls (one per metric). The script reads your `OPENAI_API_KEY` from the `.env` file in `src/`. A typical run against the 11 traces from `run_traces.py` takes 1–3 minutes. A heartbeat prints every 10 seconds so you know it hasn't hung.

You can limit how many traces to evaluate:

```
python run_evals.py              # evaluate 11 most recent traces (default)
python run_evals.py 5            # evaluate 5 most recent traces
python run_evals.py all          # evaluate all traces in Phoenix
```

Results are written back to Phoenix as annotations on the root spans and saved to a local JSON summary file (e.g. `eval-results_2026-03-23_14-08-12.json`).

### The typical session

The intended sequence is: generate traces, then immediately score them. Both commands run from the same venv, same directory, same terminal:

```
python run_traces.py
python run_evals.py
```

Then open [http://localhost:6006](http://localhost:6006) and click the **Evaluations** tab to see scores alongside traces.

### What the three metrics measure

**User Frustration** detects responses that are technically correct but experientially poor — curt, dismissive, or structured in a way that forces extra work. Any traces flagged as frustrated are worth investigating for system prompt adjustments.

**Tool Usage Correctness** evaluates whether the agent called the right tools for the request. Unlike a naive approach that infers tool usage from the response text, this metric extracts the actual tool calls from the trace's child spans and passes them to the evaluator. This means it can correctly distinguish between "the right tool was called but failed" and "the wrong tool was called" — two very different problems with very different fixes.

**Answer Completeness** checks whether the response covers everything the user asked for, with scope awareness. A flights-only response is complete for a flights-only request. A full-trip query that's missing hotel recommendations is incomplete. The evaluator first determines what the user actually asked for, then checks each element.

For the full evaluation prompt text and design rationale, see [docs/evaluation-prompts.md](src/docs/evaluation-prompts.md).


---

## API Endpoints and the Browser UI

TravelShaper exposes a REST API and serves a browser UI from the same server. The browser UI is a single HTML file that calls the streaming endpoint under the hood — everything the UI can do, curl can do too. This section explains both interfaces and how to craft requests that get the best results from the agent.

### The browser UI

Open [http://localhost:8000](http://localhost:8000) in any browser. The form collects seven pieces of information:

| Field | Required | Default | What it does |
|-------|----------|---------|-------------|
| Departing from | Yes | — | Free text. City or region — the agent resolves the nearest major airport. Examples: "San Francisco, CA", "London", "SFO". |
| Destination | Yes | — | Free text. City, region, or country. Examples: "Tokyo, Japan", "Barcelona", "New Zealand". |
| Departure date | Yes | Today | Date picker. Must be today or later. |
| Duration | No | 2 weeks | Dropdown: 1 week, 2 weeks, 3 weeks, or 4 weeks. The return date is calculated automatically. |
| Budget | No | Save money | Toggle between "Save money" and "Full experience". This controls which system prompt and writing voice the agent uses, and affects how hotels are sorted (lowest price vs. highest rating). |
| Interests | No | Food checked | Six checkboxes: Food, Arts, Photo, Nature, Fitness, Nightlife. Checked interests are included in the message and drive DuckDuckGo search queries for destination-specific recommendations. |
| Additional preferences | No | Empty | Free-text field, up to 500 characters. Used to refine web search queries — things like dietary restrictions, mobility needs, travel companions, or style preferences. This field is safety-checked by gpt-4o before the agent sees it. |

When you click "Plan my trip →", the UI assembles these fields into a structured natural-language message and sends it to `POST /chat/stream`. The SSE stream shows real-time status updates (which tools are being called, when the briefing is being written) before rendering the final result as a formatted report with numbered sections.

### How the UI constructs its message

Understanding how the UI builds the message is useful if you want to replicate its behaviour from curl or a script. The form fields are joined into a single string that looks like this:

```
I am planning a trip departing from San Francisco, CA (please identify the
nearest major international airport). Destination: Tokyo, Japan. Departure:
2026-10-15. Return: 2026-10-29 (2 weeks). Budget preference: save money.
Interests: food and dining, photography. Please provide a complete travel
briefing with hyperlinks for every named place, restaurant, hotel, and
attraction.
```

The `departure` and `destination` values are also sent as separate fields in the JSON body, which triggers place validation before the agent runs. If the user typed something in the preferences box, it is sent as a separate `preferences` field — the API appends it to the message internally, framed as DuckDuckGo search context.

### Request schema

All endpoints that accept a body use the same schema. The `message` field is the only required field — everything else is optional but improves the quality of the response and enables validation.

```json
{
  "message": "string (required) — the trip planning request",
  "departure": "string or null — raw departure place name, triggers validation",
  "destination": "string or null — raw destination place name, triggers validation",
  "preferences": "string or null — free-form text, max 500 chars, safety-checked"
}
```

### Response schema

`POST /chat` returns a single JSON object:

```json
{
  "response": "string — the full travel briefing in markdown"
}
```

### Crafting a complete request with curl

A minimal request works — the agent will do its best with whatever you provide. But a complete request gives the agent everything it needs to call all four tools and produce a full briefing. Here is the difference.

**Minimal request** — the agent receives only the message and infers what it can. No place validation runs. Results are usable but less reliable:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from NYC to Rome, September, save money, food and history."}' \
  | python3 -m json.tool
```

**Complete request** — mirrors exactly what the browser UI sends. Place validation catches misspellings, the budget keyword triggers the correct voice, dates are explicit so the flight and hotel tools get precise parameters, and interests guide DuckDuckGo queries:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from New York City, NY (please identify the nearest major international airport). Destination: Rome, Italy. Departure: 2026-09-10. Return: 2026-09-24 (2 weeks). Budget preference: save money. Interests: food and dining, arts and culture. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "New York City, NY",
    "destination": "Rome, Italy",
    "preferences": "I want to eat in Trastevere, not near the Vatican. Allergic to shellfish."
  }' | python3 -m json.tool
```

**What makes the message effective for the agent:**

The agent reads the `message` field as natural language and decides which tools to call based on what information is present. Including all of these elements gives it the clearest signal:

An explicit departure city with the phrase "please identify the nearest major international airport" tells the agent to convert the city name to an IATA code for the flight search tool. Without this, the agent sometimes passes city names instead of airport codes, which causes SerpAPI to return empty results.

Dates in `YYYY-MM-DD` format are passed directly to the flight and hotel tools. Vague dates like "mid-September" work but force the agent to pick specific dates on its own, which may not match your intent.

The phrase `Budget preference: save money` (or `full experience`) triggers voice routing. The agent checks for the exact keywords `save money`, `budget`, `cheapest`, or `spend as little` to select the budget voice. Any other phrasing defaults to the full-experience voice. This also affects hotel sorting — `save money` sets `sort_by=3` (lowest price) while `full experience` sets `sort_by=13` (highest rating).

Listing interests by name ("food and dining, photography") gives the agent specific terms to search for with DuckDuckGo. Without interests, the agent skips interest-based search and focuses on flights, hotels, and cultural prep.

The closing instruction "Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction" reinforces the system prompt's hyperlink requirement. The agent is already instructed to include links, but this explicit request in the user message improves compliance.

The `preferences` field is appended to the message internally as "Additional context for web search queries (use when calling duckduckgo_search to refine results): ..." — so it specifically influences the DuckDuckGo tool, not the flight or hotel searches.

### UI option values for API use

The browser UI presents dropdown menus, toggles, and checkboxes. Under the hood, each option maps to a specific string value that gets embedded in the `message` field. When crafting curl requests, use these exact strings to replicate what the UI sends.

**Budget modes** — the UI sends one of these two phrases inside the message as `Budget preference: <value>`. The value controls both the writing voice and the hotel sort order:

| UI label | Value in message | Voice | Hotel sort |
|----------|-----------------|-------|------------|
| 💰 Save money | `save money` | Bourdain / Billy Dee / Gladwell | `sort_by=3` (lowest price) |
| ✨ Full experience | `full experience` | Leach / Pharrell / Rushdie | `sort_by=13` (highest rating) |

**Interests** — the UI sends checked interests as a comma-separated list inside the message as `Interests: <value>, <value>.` Each checkbox maps to a specific string. You can combine any number of them. When no interests are checked, the UI sends "No specific interests — general recommendations welcome." instead:

| UI label | Value in message |
|----------|-----------------|
| 🍜 Food | `food and dining` |
| 🎨 Arts | `arts and culture` |
| 📸 Photo | `photography` |
| 🌿 Nature | `nature and outdoors` |
| 🏃 Fitness | `fitness and sports` |
| 🎶 Nightlife | `nightlife and events` |

For example, a message with food, photography, and nightlife selected would contain: `Interests: food and dining, photography, nightlife and events.`

**Trip duration** — the UI sends the duration as part of the date range in the message. The return date is calculated by adding the selected number of weeks to the departure date. The duration dropdown maps to these values:

| UI label | Weeks added | Example in message |
|----------|------------|-------------------|
| 1 week | 7 days | `Return: 2026-10-22 (1 week)` |
| 2 weeks | 14 days | `Return: 2026-10-29 (2 weeks)` |
| 3 weeks | 21 days | `Return: 2026-11-05 (3 weeks)` |
| 4 weeks | 28 days | `Return: 2026-11-12 (4 weeks)` |

**Putting it all together** — here is a curl request that uses all six interests, the full-experience budget mode, a 3-week duration, and a preferences field:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Miami, FL (please identify the nearest major international airport). Destination: Buenos Aires, Argentina. Departure: 2026-11-01. Return: 2026-11-22 (3 weeks). Budget preference: full experience. Interests: food and dining, arts and culture, photography, nature and outdoors, fitness and sports, nightlife and events. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "Miami, FL",
    "destination": "Buenos Aires, Argentina",
    "preferences": "I am a serious amateur photographer and want to find street markets and tango venues that are not staged for tourists. I am also training for a marathon and need running routes."
  }' | python3 -m json.tool
```

### Scoped requests

You do not have to ask for everything. The agent handles partial requests gracefully and only calls the tools that are relevant:

```bash
# Flights only — agent calls search_flights, skips hotels and cultural guide
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Los Angeles, CA (please identify the nearest major international airport). Destination: London, United Kingdom. Departure: 2026-12-15. Return: 2026-12-28. Budget preference: save money. Please focus only on flight options — I have accommodation sorted.",
    "departure": "Los Angeles, CA",
    "destination": "London, United Kingdom"
  }' | python3 -m json.tool

# Cultural guide only — no flights, no hotels
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am visiting Japan for the first time next month. What should I know about etiquette, language, what to wear, and what not to do?",
    "destination": "Japan"
  }' | python3 -m json.tool

# Already at destination — interest-based recommendations only
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am already in Lisbon, Portugal. I do not need flights or hotels. I want to know the best photography spots and where to eat that is not a tourist trap.",
    "destination": "Lisbon, Portugal",
    "preferences": "I shoot film, not digital. Looking for texture — peeling tiles, old men playing cards, laundry across alleys."
  }' | python3 -m json.tool
```

### `POST /chat/stream` — SSE streaming

Same request body as `/chat`. The browser UI uses this endpoint. Instead of waiting for the full response, it streams Server-Sent Events as the agent works. Each event has a `type` and a JSON `data` payload:

| Event type | When it fires | Data shape |
|------------|---------------|------------|
| `status` | Each time a tool is called or the agent changes state | `{"message": "✈️  Searching flights"}` |
| `place_corrected` | A misspelled place name was auto-corrected | `{"field": "destination", "original": "Roam", "canonical": "Rome, Italy"}` |
| `place_error` | A place name was rejected (fictional, ambiguous) | `{"field": "destination", "message": "We couldn't find a place called 'Fakeville'."}` |
| `validation_error` | The preferences field was rejected by safety check | `{"message": "Your additional preferences could not be used: ..."}` |
| `done` | The agent finished — contains the full briefing | `{"response": "full markdown text..."}` |
| `error` | Something went wrong during agent execution | `{"message": "error description"}` |

Status messages cycle through tool-specific labels as the agent works: "✈️  Searching flights", "🏨  Finding hotels", "🗺️  Gathering cultural guide", "🔍  Searching the web", "📊  Processing search results", and "✍️  Writing your personalised briefing". The final status before `done` is always "🎉 Your briefing is ready".

### `GET /health`

Returns `{"status": "ok"}` with a 200 status code. Used by Docker's health check (configured in the Dockerfile to poll every 30 seconds) and useful for verifying the server is alive from scripts or monitoring tools:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

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
│   ├── run_evals.py                # Legacy evaluation runner (prefer run_evals.py at project root)
│   └── metrics/
│       ├── frustration.py          # Reference frustration prompt
│       ├── answer_completeness.py  # ANSWER_COMPLETENESS_PROMPT
│       └── tool_correctness.py     # TOOL_CORRECTNESS_PROMPT
├── scripts/
│   └── export_spans.py             # Export Phoenix spans to CSV
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
├── run_traces.py                   # Trace generator — 11 queries, cross-platform Python
├── run_evals.py                    # Evaluation runner — 3 LLM-as-judge metrics, trace-level
├── run_traces.sh                   # Trace generator (bash, legacy — prefer run_traces.py)
├── setup.sh                        # One-command setup (Docker path, macOS/Linux only)
├── RUNNING.md                      # Extended setup guide (some sections outdated — prefer this README)
└── CHANGELOG.md
```

---

## Documentation

The `docs/` directory contains the full design record for the project. Each document covers a specific dimension of the system and is written to be self-contained — you can read any one of them without needing the others first.

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](src/docs/ARCHITECTURE.md) | Software architecture document covering component design, data flow, LLM decision making, system prompt rationale, tool design patterns, input validation architecture, deployment topology, and the decision log for every major technical choice. The most comprehensive single document in the project. |
| [PRD.md](src/docs/PRD.md) | Product requirements document defining the target user, jobs to be done, functional and non-functional requirements, scope boundaries, API contract, evaluation criteria, and the future roadmap. Start here if you want to understand *what* TravelShaper is and *why* it makes the choices it does. |
| [system-prompt-spec.md](src/docs/system-prompt-spec.md) | Specification for the two system prompts (save-money and full-experience) including the voice definitions, routing logic, shared structural requirements, tool usage instructions, and the design reasoning behind using two prompts instead of one. |
| [test-specification.md](src/docs/test-specification.md) | Complete specification for all 14 tests across three test files, including mock path rules, exact mock data shapes, and assertion criteria for every test case. |
| [docker-spec.md](src/docs/docker-spec.md) | Dockerfile and docker-compose.yml with line-by-line commentary explaining why each decision was made — including why Phoenix packages are installed via pip, why the full `arize-phoenix` server is excluded from the app container, and the `temperature` model_kwargs workaround. |
| [evaluation-prompts.md](src/docs/evaluation-prompts.md) | The exact prompts used in the Phoenix evaluation pipeline for all three metrics (user frustration, tool usage correctness, answer completeness), with rationale for why each metric was chosen based on specific failure modes observed during development. |
| [trace-queries.md](src/docs/trace-queries.md) | All 11 trace queries with their expected tool dispatch, voice routing, and a coverage matrix showing which tools, budget modes, and edge cases each query exercises. |
| [implementation-plan.md](src/docs/implementation-plan.md) | Step-by-step build plan used during development, with acceptance criteria for each step. Useful for understanding the order in which the system was assembled. |
| [presentation-outline.md](src/docs/presentation-outline.md) | 20–25 minute presentation outline covering architecture, observability (OpenTelemetry / OpenInference concepts), evaluation methodology, deployment design, and a live demo script with both browser UI and curl options. |

---

## Architecture

The agent uses a standard LangGraph ReAct loop. The graph topology is unchanged from the starter app — the extension adds tools, not complexity.

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

For the full architecture narrative — component design, data flow, LLM decision making, prompt design rationale, deployment topology, and security considerations — see [docs/ARCHITECTURE.md](src/docs/ARCHITECTURE.md).

---

## Design Decisions

There is a pattern in how TravelShaper makes its choices, and the pattern is worth naming: every decision optimises for the shortest path to a working demo that is still architecturally honest.

- **Single HTML file UI** — no npm, no build step; served directly by FastAPI alongside the REST API. The constraint produced a better result: one file that loads instantly and has zero deployment friction.
- **SerpAPI as single data provider** — one key powers flights, hotels, and scoped web searches with structured JSON. The alternative was three separate APIs with three approval processes.
- **Cultural guide as a first-class tool** — etiquette and language prep is what separates a useful travel briefing from a price comparison. Most travel tools skip this entirely.
- **DuckDuckGo as fallback** — covers general queries without requiring an additional API key. Already present in the starter code.
- **Two system prompts, not one** — a single prompt with conditional voice instructions produces blended, inconsistent output. Two separate prompts let the model commit fully to one register.
- **Place validation before agent** — gpt-4o catches misspellings and rejects fictional places before the expensive agent runs. A 1-second validation call saves 30 seconds of wasted agent time. Validation only runs when `departure` and `destination` fields are explicitly provided in the request body.
- **Single-turn design** — each request is independent. This is a deliberate product boundary, not a gap.
- **`openai` SDK installed via pip, not Poetry** — the OpenAI SDK is used only by the validation classifiers in `api.py`. It is installed via pip in the Dockerfile (and must be installed manually in venv mode) rather than declared in `pyproject.toml`, to keep the Poetry dependency graph clean alongside the Phoenix packages that also require special handling.

---

## Security Considerations and Input Validation

TravelShaper validates user input in three stages before the agent processes a request. Understanding this pipeline is useful for knowing what the system protects against, what it does not, and how to interpret rejection errors in both the sync and streaming endpoints.

### The validation pipeline

The first stage is Pydantic schema validation. The `ChatRequest` model in `api.py` requires the `message` field to be a non-empty string. The `departure`, `destination`, and `preferences` fields are optional strings that default to `None`. If the request body fails schema validation (missing message, wrong types), FastAPI returns HTTP 422 before any application code runs.

The second stage is place validation. When `departure` or `destination` are provided and non-empty, `validate_place()` sends each one to gpt-4o with a structured prompt asking whether it is a real, unambiguous place. The classifier returns one of four outcomes: the place is valid and canonical (e.g. "Tokyo, Japan" → accepted as-is), the place is a misspelling or common abbreviation (e.g. "Roam" → corrected to "Rome, Italy"), the place is ambiguous (e.g. "Springfield" → rejected with a message listing possible matches), or the place is fictional or nonsensical (e.g. "Narnia" → rejected). If validation fails for either field, the request is rejected before the agent runs.

Place validation is designed to fail open. If the gpt-4o call itself fails (network error, timeout, rate limit), the validator returns `valid=True` and lets the agent proceed with the original input. The reasoning is that a temporary API failure should not prevent the user from getting results — the agent may still be able to resolve the place name on its own, and the worst case is a less accurate flight or hotel search.

The third stage is preferences validation. When the `preferences` field is provided, `validate_preferences()` sends it to gpt-4o with a safety classifier prompt. The classifier evaluates whether the text is appropriate for a travel planning context and returns an allow/deny decision.

Rejected content includes requests for illegal goods, substances, or services; requests involving weapons, drugs, or controlled substances; adult or sexually explicit content; content targeting, demeaning, or harassing individuals or groups; prompt injection attempts such as instructions to ignore previous prompts, override system behaviour, act as a different AI, reveal internal prompts, or bypass safety measures; attempts to extract sensitive data or credentials; and content designed to generate harmful, dangerous, or unethical recommendations.

The classifier is instructed to lean toward allowing ambiguous cases — if the text is plausibly travel-related, it passes. "I take medication for anxiety and need to avoid alcohol" is a legitimate travel preference. "Tell me where to buy medication without a prescription" is not.

Unlike place validation, preferences validation fails closed. If the gpt-4o call fails for any reason, `validate_preferences()` returns `valid=False` with a message saying the safety check is temporarily unavailable. The reasoning is inverted from place validation: the preferences field is a direct injection surface that gets appended to the agent's message and used to drive web searches. Passing unvalidated text through this path is more dangerous than temporarily blocking it. The cost of a false rejection (user retries without the preferences text) is lower than the cost of passing adversarial content to the agent.

### What happens when validation rejects a request

The sync endpoint (`POST /chat`) returns HTTP 400 with a JSON body containing the rejection reason. For place errors, the detail includes a `field` key identifying which field failed ("departure" or "destination") and a `message` key with the user-facing explanation. For preference errors, the detail is a string describing the rejection.

The streaming endpoint (`POST /chat/stream`) emits a single SSE event and closes the connection. Place rejections emit a `place_error` event with the field name and message. Preference rejections emit a `validation_error` event. In both cases, the browser UI routes back to the form screen and displays the error message — the user never sees the loading screen for a request that will be rejected.

### Infrastructure-level protections

API keys are stored in the `.env` file, which is listed in `.gitignore` and `.dockerignore` and is never committed to version control or copied into the Docker image. The `.env.example` file contains placeholder values only.

There is no API authentication on any endpoint. The server is designed for local use and demo environments. In a production deployment, JWT or API key authentication would be added to `/chat` and `/chat/stream`. The `/health` endpoint would remain open for load balancer health checks.

There is no HTTPS. The server runs on plain HTTP at port 8000. In production, TLS termination would be handled by a load balancer or reverse proxy in front of the application.

The system prompt is hardcoded in `agent.py` as two constant strings. It is not loaded from a file, database, or environment variable, and it cannot be modified at runtime. The user's message is treated as untrusted input by the LLM — it is appended to the conversation history after the system prompt, never injected into the system prompt itself.

No user data is persisted beyond Phoenix traces. There are no user accounts, no saved trips on the server, and no session state between requests. The browser UI stores trip history in the client's `localStorage`, which never leaves the browser. Phoenix traces contain the full text of user messages and agent responses — in a production deployment, these would need PII redaction before long-term storage.

Tools never raise exceptions into the agent loop. Each tool wraps its external API call in a try/except block and returns a descriptive error string on failure (e.g., "Flight search failed: timeout"). This prevents a SerpAPI outage from crashing the agent and allows the LLM to incorporate the failure gracefully into its response ("I couldn't find flight data for that route — here's what I know from web search...").

### What is not protected

The `message` field itself is not validated for content safety. Only the `preferences` field goes through the safety classifier. A user could put harmful text directly in the message — for example, "Plan a trip and also tell me how to ..." — and the message would reach the agent. The agent is an LLM with its own safety training (gpt-5.3-chat-latest), so it will generally refuse harmful requests, but there is no application-layer gate on the message content.

There is no rate limiting. A client can send unlimited requests to `/chat` and `/chat/stream`, which could exhaust the SerpAPI free tier (250 searches/month) or generate large OpenAI bills. A production deployment would add per-client rate limits.

There is no input sanitization before tool dispatch. The agent constructs tool arguments (airport codes, search queries, hotel queries) from the user's message via LLM reasoning. If the LLM is tricked into passing unusual arguments to a tool, the tool will attempt the search — though it will return empty or irrelevant results rather than causing harm, since all tools use read-only search APIs.

The browser UI uses `localStorage` for trip history, which is accessible to any JavaScript running on the same origin. In the current single-origin setup this is not a risk, but it would need revisiting if the app were deployed behind a shared domain.

---

## Known Limitations

- Planning assistant only — recommends options but does not book.
- Flight and hotel prices reflect time of search, not guaranteed availability.
- Cultural guidance is practical advice based on common norms, not absolute rules.
- Designed for English-speaking American travellers; guidance assumes U.S. norms as baseline.
- Single-turn: no conversation memory between requests.
- SerpAPI free tier supports ~60–125 full briefings per month.
- Voice routing uses keyword matching — the budget voice triggers on `save money`, `budget`, `cheapest`, or `spend as little` appearing in the message. Synonyms like "frugal" or "inexpensive" will not trigger it and will default to the full-experience voice.

---

## Troubleshooting

### Checking Docker status

These commands help you understand what is happening inside the containers. Run them from the `src/` directory.

**See which containers are running:**

```
docker ps
```

You should see two rows — one for TravelShaper and one for Phoenix. If a container shows `Restarting` or is missing, it likely crashed on startup. Check its logs.

**See containers that are stopped or crashed:**

```
docker ps -a
```

**View logs for a specific service:**

```
docker compose logs --tail 100 travelshaper
docker compose logs --tail 100 phoenix
```

**Follow logs in real time** (press `Ctrl+C` to stop):

```
docker compose logs -f travelshaper
```

**Restart a single service without rebuilding:**

```
docker compose restart travelshaper
```

**Full reset** — stop everything, rebuild from scratch, and start fresh:

```
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Common issues

**Server won't start** — confirm your `.env` exists with valid keys. Check the logs with `docker compose logs --tail 50 travelshaper` and look for error messages. A common cause is a missing or malformed `.env` file. Try rebuilding with `docker compose down && docker compose up -d --build`.

**Auth error from OpenAI or SerpAPI** — check your `.env` file. Verify the SerpAPI key at [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). Verify the OpenAI key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

**Tests fail with ModuleNotFoundError** — the most common cause is running pytest outside the virtual environment. Check that you see `(.venv)` in your terminal prompt. If not, activate the venv (see "Set Up Python for Tests and Traces" above). If the missing module is `pytest` or `httpx`, run `poetry install -E dev`. If the missing module is `openai`, run `pip install openai`. Make sure you are running pytest from inside the `src/` directory.

**`run_traces.py` fails with `ConnectionError`** — the TravelShaper server is not running. Start the Docker stack with `docker compose up -d` and wait for the health check to pass (`curl http://localhost:8000/health`), then run the script again.

**`run_traces.py` saves a JSON file but some queries show errors** — open the JSON file and check the `status` and `error` fields for each result. Common causes: an expired or missing SerpAPI key, or an expired OpenAI key. Check your `.env` file inside `src/`.

**Poor or incomplete results** — include origin, destination, dates, and budget in your request. Check SerpAPI usage (free tier: 250 searches/month). Try well-known destinations first.

**Missing traces in Phoenix** — confirm Phoenix is running (`docker ps` should show the Phoenix container). Run at least one `/chat` query, then refresh the Phoenix UI at [http://localhost:6006](http://localhost:6006).

**`run_traces.sh` fails with `date: illegal option -- d`** — you are running the legacy bash script on macOS. Use `run_traces.py` instead, which handles dates with Python's `datetime` module and works on all platforms.

**`run_traces.sh` fails with import errors** — the bash script calls `python3 -m scripts.export_spans` at the end, which requires Phoenix packages that aren't in your local venv. Use `run_traces.py` instead — it saves results to a local JSON file using only the `requests` library.

---

MIT License — see [LICENSE](LICENSE).
