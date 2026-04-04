# Changelog

## [0.4.0] — 2026-04-04

### Generic OTLP destination

- Added `otlp` destination to `OTEL_DESTINATION` — sends traces to any
  OTLP-compatible backend (Jaeger, Grafana Tempo, Honeycomb, Datadog, etc.)
  using the existing `OTLPSpanExporter`
- Added `all` destination — sends traces to Phoenix, Arize, and generic OTLP
  simultaneously
- New env vars: `OTLP_ENDPOINT` (required for `otlp`/`all`), `OTLP_HEADERS`
  (optional comma-separated `key=value` auth headers)
- Added `_parse_otlp_headers()` and `_otlp_exporter()` helpers to
  `otel_routing.py`
- `both` destination unchanged (Arize + Phoenix only) for backward
  compatibility
- Updated `docker-compose.yml` to pass through `OTLP_ENDPOINT` and
  `OTLP_HEADERS`
- Added 4 unit tests for generic OTLP routing (31 total)
- No new packages required

## [0.3.2] — 2026-04-02

### Token reduction (PR 2 of 2)

- Added DISPATCH_PROMPT (~150 tokens) for tool-dispatch phase
- llm_call now detects phase from message state: sends DISPATCH_PROMPT
  before tools run, voice prompt after tools return results
- Updated get_system_prompt to accept phase parameter (default: synthesis)
- Added 2 unit tests for phase detection in llm_call (25 total)
- Estimated additional savings: ~300–600 tokens per full-trip request
- Bumped version 0.3.1 → 0.3.2

## [0.3.1] — 2026-04-03

### Token reduction (part 1 of 2)

- Condensed both system prompts (~90 lines each → ~20 lines)
- Switched `_llm_json` validation model from `gpt-4o` to `gpt-4o-mini`
- Reduced hotel results from 5 to 3 per search
- Bumped API version `0.1.4` → `0.1.5`
- Updated CLAUDE.md tools/ policy

## [0.3.0] — 2026-04-02

### Configurable OTel routing

- Added `otel_routing.py` — single module owning all telemetry config
- `OTEL_DESTINATION` in `.env` controls where traces go:
  `phoenix` | `arize` | `both` | `none`
- Phoenix is now optional — runs via Docker Compose `--profile phoenix`
- Arize Cloud support via standard OTLP/HTTP — no proprietary SDK
- Phoenix Cloud support via `PHOENIX_API_KEY`
- Added 7 unit tests for routing logic (23 total)
- Renamed `PHOENIX_COLLECTOR_ENDPOINT` → `PHOENIX_ENDPOINT`
- Added `opentelemetry-sdk` and `opentelemetry-exporter-otlp-proto-http` to Dockerfile
- Bumped version `0.2.0` → `0.3.0`

## [0.2.0] — 2026-04-02

### Post-review restructuring and Arize alignment

#### Project restructuring
- Moved `run_traces.py` into `traces/run_traces.py` with `traces/README.md`
- Consolidated evaluation runner from project root into `evaluations/run_evals.py`
  (kept the trace-level assembly version; added frustrated dataset creation)
- Moved `scripts/export_spans.py` into `evaluations/export_spans.py`
- Removed `scripts/` directory
- Added `Makefile` with `make demo` pipeline (up, test, traces, evals, export)

#### Evaluation improvements
- Added frustrated interactions dataset creation to the primary evaluation runner
- After scoring frustration, uploads a `frustrated_interactions` Phoenix dataset
- Dataset info included in local JSON summary under `"datasets"` key

#### Phoenix / OpenInference improvements
- Custom spans in `api.py` now set OpenInference semantic attributes
  (`SpanAttributes.INPUT_VALUE`, `SpanAttributes.OUTPUT_VALUE`) for proper
  Phoenix UI rendering
- Added `openinference-semantic-conventions` to Dockerfile dependencies
- Added documentation distinguishing OpenTelemetry (transport) from
  OpenInference (semantic conventions) in ARCHITECTURE.md Section 7.5

#### Testing
- Added `test_cultural_guide_tool_has_routing_docstring` — verifies tool
  docstring contains LLM routing keywords
- Added `test_voice_routing_selects_correct_prompt` — verifies budget
  keyword routing to correct system prompt
- Total tests: **16 passing** (was 14)

#### Documentation
- Updated project structure in README to reflect new layout
- Added production observability transition path (Phoenix to Arize Cloud)
  to ARCHITECTURE.md Section 12.4
- Added OpenTelemetry vs OpenInference explanation (Section 7.5)
- Updated glossary with expanded OpenInference and Arize Cloud entries
- Documented Docker vs local Phoenix endpoint difference in `.env.example`
- Updated all file path references across README, RUNNING.md, and docs/
- Added Quick Start with Make section to README

#### Code quality
- Moved `import os` to top-level imports in `agent.py`
- Added comment block in `agent.py` explaining two-layer observability
- Bumped version `0.1.4` to `0.2.0`

## [0.1.2] — 2026-03-23

### Two changes: place validation + Tribeca art-house UI

#### 1. Place name validation

**`api.py`** — new `validate_place(name, field) → PlaceValidationResult`
using `gpt-4o` with a geographic classifier prompt. Handles four cases:

- **Valid** — recognisable real place; returns `canonical` (standardised
  English name, e.g. "SF" → "San Francisco, California, USA")
- **Corrected** — misspelling of an identifiable place; returns both
  `corrected` and `canonical`; agent proceeds with the corrected name
- **Ambiguous** — multiple real places match (e.g. "Springfield",
  "Georgia"); returns `valid=False` with a disambiguation prompt
- **Invalid/fake** — unrecognisable or fictional; returns `valid=False`
  with a user-friendly message
- **Prompt injection** — malicious content in place field; rejected safely

Both `departure` and `destination` fields on `ChatRequest` are validated
before the agent is invoked, in both the sync `/chat` and SSE
`/chat/stream` endpoints.

**`/chat/stream` SSE events added:**
- `place_error` — `{field, message}` — invalid place; UI highlights the
  field and shows the message on the form screen
- `place_corrected` — `{field, original, canonical}` — auto-correction
  happened; UI shows a teal banner after the result loads

**`static/index.html`** — correction banner + field highlighting:
- Teal `correction-banner` div appears on the result screen when a name
  was auto-corrected: "Departure interpreted as: San Francisco, California"
- The offending input field gets a red border on `place_error` with focus

**`tests/test_api.py`** expanded to 8 API tests (was 5):
- `test_chat_accepts_valid_places` — valid place passes through
- `test_chat_rejects_invalid_place` — fake place → 400, agent not called;
  uses `side_effect` mock so departure passes and destination fails
- `test_chat_auto_corrects_misspelled_place` — "Tokio" → "Tokyo, Japan",
  agent is still called with corrected name

#### 2. Tribeca art-house UI redesign

Complete visual rebuild of `static/index.html`.

**Aesthetic:** Black-and-white editorial with a single hot accent (sunset
orange). Raw, architectural, poster-like. Think: a gallery on Franklin
Street, a cast-iron loft, an art magazine at the MoMA bookshop.

**Fonts:**
- **Bebas Neue** — ultra-condensed display, all-caps, pure poster energy.
  Used for form headline, loading title, section numbers, result hero,
  nav logo. Sizes from 26px up to `clamp(56px, 10vw, 120px)`.
- **Cormorant Garamond** — italic serif for elegance and contrast.
  Used for the "The world is waiting." sub-headline and section subtitles.
- **DM Sans** — clean, minimal body. All form labels, body copy, metadata.

**Layout principles:**
- No card boxes or rounded corners — everything is ruled lines and raw white
- Three-weight border system: 3px black (section openers), 1px rule, 1.5px
  form borders
- Form inputs have a brutalist `box-shadow: 3px 3px 0 var(--black)` on focus
- CTA button is flat orange with a `4px 4px 0 black` drop shadow that
  animates on hover (lift + larger shadow)
- Report sections numbered 01–04 with giant muted numerals as section markers
- Bullet dots replaced with an em dash `—`
- Hyperlinks: black text, orange underline, 2px thick
- Loading screen: animated sliding orange bar instead of a spinner
- Responsive: single-column below 780px, sidebar moves below with a 3px
  black top border; all type scales with `clamp()`

**`pyproject.toml`** — version bumped `0.1.1` → `0.1.2`

Total tests: **14 passing**

---

## [0.1.1] — 2026-03-23

### Four changes: real-time status, model updates, typography, writing style

#### 1. Real-time SSE status during agent execution

**`api.py`** — new `POST /chat/stream` endpoint using `StreamingResponse`
with `media_type="text/event-stream"`. Uses LangGraph's `.stream()` with
`stream_mode="updates"` to emit one event per node execution:

- When `llm_call` produces tool_calls → emits `status` event with the
  specific tool label (✈️ Searching flights, 🏨 Finding hotels, etc.)
- When `llm_call` produces a final message (no tool_calls) → emits
  "✍️ Writing your personalised briefing"
- When `tool_node` executes → emits "📊 Processing search results"
- On completion → emits `done` event with the full response text
- On error → emits `error` event

Event format: standard SSE `event: <type>\ndata: <json>\n\n`

The original `POST /chat` endpoint (synchronous, returns full JSON) is
unchanged — curl, pytest, and all non-browser clients continue to work.

**`static/index.html`** — loading screen redesigned:
- Replaces hardcoded animated steps with a live `status-feed` div
- `addStatus(message, state)` appends a new `.status-item` element per
  SSE event, marks the previous item as `.done`
- Active item has a pulsing dot; done items turn teal
- 600ms pause after the "ready" status so users can see it before the
  result transitions in
- Validation errors from SSE (`validation_error` event) route back to
  the form screen with the rejection message

#### 2. Model updates

- **Agent:** `gpt-4.1` → `gpt-5.3-chat-latest`
- **Validator:** `gpt-4.1-mini` → `gpt-4o` (more reliable classification)

#### 3. Typography and spacing

- **Fonts:** Cormorant Garamond replaced with **Cormorant Garamond** for
  display; body switched to **Poppins** (geometric, designer-grade, highly
  legible at large sizes)
- **Body size:** 15px → **18px** with line-height 1.85
- **Paragraph gap:** 16px between paragraphs in report sections
- **Card title:** 32px → **52px** italic Cormorant Garamond
- **Result hero title:** 42px → **58px** italic bold
- **Section titles:** 20px → **26px** italic bold
- **Loading title:** 26px → **36px** italic
- Card padding: 40px → **48px**; rep-body padding: 22px → **28px 32px**;
  hero padding: 36px → **48px 52px**

#### 4. Writing style — Robin Leach + Pharrell Williams

`SYSTEM_PROMPT` completely rewritten with a new voice section:
- **Robin Leach:** theatrical, aspirational, vivid sensory prose —
  "sanctuaries of refined indulgence", cinematic openers per section
- **Pharrell:** infectious joy, warmth, celebratory energy, inclusive
  enthusiasm — "trust us, you are going to LOVE this"
- Combined opening hook required before every briefing
- Section headers reframed as editorial titles:
  "✈️ Getting There — Your Chariot Awaits"
  "🏨 Where to Stay — Your Home Away From Home"
  "🗺️ Before You Go — The Insider Brief"
  "📍 What to Do — The Real Itinerary"
- Required memorable closing line at end of every briefing
- SECTIONS matcher updated to catch new header vocabulary
  (chariot, sanctuary, insider brief, real itinerary)

**`pyproject.toml`** — version bumped `0.1.0` → `0.1.1`

---

## [0.1.0] — 2026-03-23

### Three changes: UI redesign, model upgrade, hyperlinks in reports

#### 1. UI redesign — new brand palette and typography

Complete visual overhaul of `static/index.html`.

**Palette (exact values from spec):**
- Primary Ocean Blue `#0F4C81` — header, form labels, section titles, sidebar hover
- Secondary Deep Teal `#006D77` — hyperlinks, checked interest chips
- Accent / CTA Sunset Orange `#FF7A00` — submit button, bullet dots, form logo mark, eyebrow text
- Text / UI Dark Slate `#1F2937` — body copy
- Background Cloud `#F8FAFC` — page background, input backgrounds
- Base White `#FFFFFF` — cards, sections

**Typography:**
- **Fraunces** (display / optical size variable font) — card titles, result title, section titles, loading title. Larger sizes: card title 32px, result hero 42px, section titles 20px.
- **Sora** (geometric sans) — all body text, labels, form fields, buttons

**Visual changes:**
- Header: sticky, primary blue with orange logo mark and version badge
- Form card: rounded-xl corners, larger title hierarchy, orange CTA button with shadow and hover lift
- Budget toggle: primary blue when selected (was green)
- Interest chips: teal when selected
- Result hero: gradient banner (primary → teal) with decorative circles
- Report sections: icon box with orange-light background, teal hyperlinks, hover shadow
- Sidebar: primary blue route text, slide-right hover animation
- Bullet dots changed from gold to sunset orange

#### 2. Model upgrade

- **Agent:** `gpt-4o` → `gpt-4.1` (better instruction following, stronger at agentic tasks)
- **Validator:** `gpt-4o-mini` → `gpt-4.1-mini` (faster, cheaper, stronger than 4o-mini)

#### 3. Hyperlinks in every report recommendation

**`agent.py` — SYSTEM_PROMPT updated:**
Added a "Hyperlinks — REQUIRED" section instructing the model to include a
markdown `[Name](URL)` link for every named place, restaurant, hotel,
attraction, neighborhood, airline, and activity. Provides examples and
fallback URL patterns (Google Maps, Google Search) for cases where an
official website is not known.

**`static/index.html` — `renderInline()` updated:**
Added regex to convert `[text](url)` → `<a href="url" target="_blank"
rel="noopener noreferrer">text</a>`. Links are styled in Deep Teal with
underline, hover transition to Primary Blue. Works in both sectioned report
cards and the raw fallback renderer. The order of replacement matters:
links are rendered before bold/italic to avoid conflicts.

#### Other changes
- `pyproject.toml` version bumped `0.0.9` → `0.1.0`
- `api.py` version string updated to `0.1.0`
- Loading screen last step updated: "Compiling your briefing with links"

---

## [0.0.9] — 2026-03-22

### Feature: Free-form preferences field with LLM safety validation

#### Free-form preferences (Change 1)

A new optional `preferences` field (max 500 characters) is added to both
the API and the UI. It accepts free-form text describing additional
considerations the user wants applied to web search queries — things like
dietary restrictions, mobility needs, travel companions, or style
preferences that don't fit the structured form fields.

The field is passed to the agent framed explicitly as DuckDuckGo search
context: *"Additional context for web search queries (use when calling
duckduckgo_search to refine results): …"*. This ensures the agent knows
to apply the text to general web queries rather than the structured SerpAPI
tools.

#### LLM safety validation (Change 2)

All non-empty `preferences` values are validated by `gpt-4o-mini` before
the main agent is invoked. The classifier uses a strict system prompt that:

- **Allows** legitimate travel preferences: dietary restrictions, health
  and mobility needs, travel style, interest refinements, budget details,
  companion context
- **Rejects** illegal requests, adult content, hate speech, prompt
  injection attempts, credential extraction, and off-topic attack vectors

If validation fails, the API returns **HTTP 400** with a user-facing
explanation. The main agent is **never invoked** with unvalidated content.
Empty or whitespace-only preferences bypass validation entirely.

The UI handles a 400 response by returning to the form screen and
displaying the rejection reason — the user never sees the loading screen
for a rejected request.

#### Changes

**`api.py`**
- Added `VALIDATION_SYSTEM_PROMPT` constant — the classifier prompt
- Added `ValidationResult` Pydantic model
- Added `validate_preferences(text) → ValidationResult` — calls
  `gpt-4o-mini` at temperature 0; returns `valid=False` on any error
- Added `build_agent_message(base, preferences)` — appends validated
  preferences framed as DuckDuckGo context
- Updated `ChatRequest` — added `preferences: str | None` field
  (max_length=500)
- Updated `chat()` endpoint — validates preferences before agent invocation;
  raises HTTP 400 if invalid
- Added `openai` import and `_openai` client instance
- Version string updated to `0.0.9`

**`static/index.html`**
- Added `<textarea id="preferences">` with `maxlength="500"` below the
  interest chips
- Live character counter (`updateCharCount()`) turns amber at 450, red at
  500
- Field note: *"Used to refine web search queries. Content is
  safety-checked before use."*
- `onSubmit` reads the preferences value and includes it in the fetch
  body only when non-empty
- 400 responses are handled gracefully: returns to the form screen and
  shows the rejection message rather than displaying an error on the
  loading screen

**`tests/test_api.py`**
- Expanded from 2 tests to 5:
  - `test_health_endpoint` (unchanged)
  - `test_chat_endpoint_accepts_message` (unchanged)
  - `test_chat_accepts_valid_preferences` — mocks validate to pass, asserts
    agent is called and validate was called with the correct text
  - `test_chat_rejects_invalid_preferences` — mocks validate to fail,
    asserts 400 returned and agent.invoke never called
  - `test_chat_skips_validation_for_empty_preferences` — whitespace
    preferences, asserts validate not called

**`pyproject.toml`**
- Version bumped `0.0.8` → `0.0.9`
- Added `openai` as a direct dependency note (installed via pip in Docker)

Total tests: **11 passing**

---

## [0.0.8] — 2026-03-22

### Feature: Structured form UI, history, and directory versioning

#### Web interface redesign
Complete redesign of `static/index.html`. The free-text chat box is
replaced with a structured one-shot trip planning form.

**Form fields:**
- Departure city / region (free text — agent resolves nearest airport)
- Destination (free text)
- Departure date (date picker, min = today)
- Trip duration (1–4 weeks, select)
- Budget preference (Save money / Full experience toggle)
- Interests (6 checkboxes: Food, Arts, Photography, Nature, Fitness, Nightlife)

**One-shot flow:**
The user fills the form, submits once, and receives a single complete
travel briefing. There is no back-and-forth. A "Plan another trip" button
resets the form. This matches the single-turn architecture of the agent.

**Structured message construction:**
The form fields are assembled into a precise natural-language prompt
including departure city, IATA lookup instruction, destination, exact
dates (departure + calculated return), budget, and interests. This
produces more reliable agent responses than open-ended chat.

**Formatted report rendering:**
The agent's markdown response is parsed into named sections
(Getting There, Where to Stay, Before You Go, What to Do) and rendered
as styled cards with section icons, bullet lists, and inline bold
formatting. Falls back to a styled raw view if sections cannot be parsed.

**Trip history:**
The last 10 completed trips are saved to `localStorage` and displayed in
a sidebar on the main page. Each entry shows the route and dates. Clicking
any entry re-renders that trip's briefing. History can be cleared.

**Print / Save as PDF:**
A "Save as PDF" button triggers `window.print()`. Print CSS hides the
header, sidebar, and action buttons so only the report renders cleanly.

#### App structure
- **Versioned directory:** project now lives in `travelshaper-v0.0.8/src/`
  instead of the opaque `se-interview-main/` name. The top-level folder
  carries the version; the source subdirectory uses the standard `src/`
  convention.

#### Other changes
- `pyproject.toml` version bumped `0.0.7` → `0.0.8`
- `api.py` version string updated to `0.0.8`

---

## [0.0.7] — 2026-03-22

### Feature: Browser chat interface

Added a self-contained browser UI served directly by FastAPI. Users can
now interact with TravelShaper at `http://localhost:8000` without using
curl. The REST API (`/chat`, `/health`) is completely unchanged and
coexists with the UI — curl, pytest, and all scripts continue to work
identically.

### Changes

**`static/index.html`** *(new file)*
- Single self-contained HTML/CSS/JS chat interface
- Dark, travel-themed design using DM Serif Display + DM Sans fonts
- Auto-growing textarea; Enter to send, Shift+Enter for newline
- Animated thinking indicator while the agent is working
- Lightweight markdown rendering: `**bold**`, headers, bullet points
- Error state shown inline if the server returns a non-200 response
- No npm, no build step, no external dependencies beyond Google Fonts

**`api.py`**
- Added `from fastapi.staticfiles import StaticFiles`
- Added `app.mount("/", StaticFiles(directory="static", html=True), name="static")` after all API routes — API routes take priority, static mount handles everything else
- Updated app title and version string

**`Dockerfile`**
- Added `RUN mkdir -p /app/static` after `COPY . .` to guarantee the directory exists in the container even on a clean build

**`README.md`** *(updated in documentation pass)*
- Added "Using the Web Interface" section
- Added `GET /` to API endpoint docs
- Added `static/index.html` to project structure

**`docs/PRD.md`** *(updated in documentation pass)*
- Version bumped to 1.1
- Browser UI added to in-scope capabilities table
- `GET /` added to API contract
- Success criteria updated

**`pyproject.toml`**
- Version bumped `0.0.6` → `0.0.7`

---

## [0.0.6] — 2026-03-22

### Problem
Docker build failed at step 6/8 with:
```
The option "--no-lock" does not exist
```
The `--no-lock` flag was introduced in a later version of Poetry.
Poetry 1.8.2 (pinned in our Dockerfile) does not support it.

### Fix
Remove the `--no-lock` flag. Poetry 1.8.2 automatically generates a
lockfile during `install` if one is not present — no flag needed.

### Changes

**`Dockerfile`**
- Removed `--no-lock` from `poetry install` command
- Updated comment to note that Poetry auto-generates the lockfile

**`pyproject.toml`**
- Bumped version `0.0.5` → `0.0.6`

---

## [0.0.5] — 2026-03-22

### Problem
Docker build failed at step 5/8 with:
```
"/poetry.lock": not found
```
The Dockerfile tried to `COPY pyproject.toml poetry.lock ./` but no
`poetry.lock` file exists in the project — it was never generated.

### Root cause
`poetry.lock` is generated by running `poetry lock` locally and should be
committed to the repo. Since it was never generated, the Docker build had
nothing to copy. Rather than requiring users to run `poetry lock` before
building, we drop the lock file requirement from the Docker build entirely.

### Changes

**`Dockerfile`**
- Removed `poetry.lock` from the `COPY` line (now only copies `pyproject.toml`)
- Added `--no-lock` flag to `poetry install` so Poetry resolves dependencies
  fresh from `pyproject.toml` without requiring a lockfile

**`pyproject.toml`**
- Bumped version `0.0.4` → `0.0.5`

---

## [0.0.4] — 2026-03-22

### Problem
TravelShaper container kept restarting with:
```
AssertionError: Status code 204 must not have a response body
```
Installing the full `arize-phoenix` package inside the TravelShaper
container caused a conflict: `arize-phoenix` internally registers FastAPI
routes using `status_code=204` with a response body, which newer versions
of FastAPI correctly reject. The container crashed on startup before
uvicorn could serve a single request.

### Root cause
`arize-phoenix` is the full Phoenix **server** — the UI and ingestion
backend that runs at `http://localhost:6006`. It should never be installed
in the TravelShaper container because we already run it as a separate
service (`arizephoenix/phoenix:latest`) via docker-compose. Installing it
in both containers introduced the FastAPI version conflict.

Our app only needs two lightweight packages to **send** traces:
- `arize-phoenix-otel` — configures the OpenTelemetry exporter
- `openinference-instrumentation-langchain` — auto-instruments LangChain/LangGraph calls

### Changes

**`Dockerfile`**
- Removed `arize-phoenix` and `arize-phoenix-evals` from the `pip install` step
- Kept only `arize-phoenix-otel` and `openinference-instrumentation-langchain`
- Updated comment to explain the separation of concerns

**`pyproject.toml`**
- Bumped version `0.0.3` → `0.0.4`

---

## [0.0.3] — 2026-03-22

### Problem
Phoenix traces were not appearing in the Phoenix UI despite the agent
responding correctly. The Phoenix packages (`arize-phoenix-otel`,
`openinference-instrumentation-langchain`) were missing from the Docker
container because they were removed from `pyproject.toml` in v0.0.1 to
fix Poetry's version resolver conflict. The local venv `pip install` step
was never replicated inside the container, so the instrumentation block
in `agent.py` silently fell through the `except ImportError: pass` and
no traces were sent.

### Changes

**`Dockerfile`**
- Added a `RUN pip install --no-cache-dir` step after `poetry install`
  to install the four Phoenix packages directly:
  `arize-phoenix`, `arize-phoenix-evals`, `arize-phoenix-otel`,
  `openinference-instrumentation-langchain`
- Added a comment explaining why these are installed via pip rather than
  Poetry

**`pyproject.toml`**
- Bumped version `0.0.2` → `0.0.3`

---

## [0.0.2] — 2026-03-22

### Problem
`docker-compose up --build` emitted a warning:
```
the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion
```
Docker Compose v2+ no longer uses the top-level `version` field. It is
silently ignored but produces noise in the build output and could confuse
readers of the file.

### Changes

**`docker-compose.yml`**
- Removed the obsolete top-level `version: "3.8"` line

**`pyproject.toml`**
- Bumped version `0.0.1` → `0.0.2`

---

## [0.0.1] — 2026-03-22

### Problem
`poetry install -E phoenix` failed with a dependency resolution error because
`arize-phoenix-otel` declares narrow Python version constraints (e.g.
`>=3.13,<3.14`) that conflict with the project's `python = "^3.11"` constraint.
Poetry's resolver cannot find a single version of `arize-phoenix-otel` that
satisfies both the project's allowed Python range (3.11–3.13) and the
package's own bounds simultaneously.

### Changes

**`pyproject.toml`**
- Bumped version `0.1.0` → `0.0.1`
- Removed `arize-phoenix`, `arize-phoenix-evals`, `arize-phoenix-otel`, and
  `openinference-instrumentation-langchain` as optional dependencies
- Removed the `[tool.poetry.extras] phoenix` extra
- Added a comment explaining why these packages are excluded and directing
  users to `RUNNING.md`

**`RUNNING.md`**
- Step 1d: replaced `poetry install` / `poetry install -E phoenix` with
  `poetry install -E dev` for core deps, followed by a separate
  `pip install` block for the Phoenix packages
- Added explanation of why `pip` is used instead of a Poetry extra
- Troubleshooting: replaced `poetry install -E phoenix` fix with the correct
  `pip install` command for Phoenix packages
- Removed the "Poetry creates a nested virtualenv" troubleshooting entry
  (no longer relevant now that Phoenix is pip-installed)

**`README.md`**
- Setup section: expanded from a single `poetry install` step to the full
  venv → Poetry → `poetry install -E dev` → optional `pip install` for
  Phoenix flow; added note explaining the Phoenix constraint issue
- `poetry run phoenix serve` → `phoenix serve` (two occurrences)
- Troubleshooting: updated "server does not start" entry to reference venv
  activation and `poetry install -E dev`

---

## [0.0] — 2026-03-22

Initial implementation. See `README.md` for full feature description.
