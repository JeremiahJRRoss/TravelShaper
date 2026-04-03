# Test Specification — TravelShaper Travel Assistant

**Version:** 2.1 (v0.3.2)  
**Total tests:** 26 passing  
**Every test uses mocked external calls.** No test requires a live API key.

---

## Mock path rules

Each tool imports `serpapi_request` via `from tools import serpapi_request`.
Mock where the name is *used*, not where it is *defined*:

- `tools.flights.serpapi_request`
- `tools.hotels.serpapi_request`
- `tools.cultural_guide.serpapi_request`

Validation functions are mocked at the `api` module level:
- `api.validate_preferences`
- `api.validate_place`
- `api.agent`

OTel routing tests mock environment variables and the OTLP exporter:
- `otel_routing.OTLPSpanExporter`
- `os.environ` (via `patch.dict`)

---

## tests/test_tools.py (4 tests)

### Test 1 — test_search_flights_formats_results
Verifies the flights tool formats a SerpAPI response into a readable string.
Mock returns full flight data with ANA + United flights.
Assertions: result is a string; contains "ANA", "687", "United", "845", "SFO", "NRT", "Best flights".

### Test 2 — test_search_flights_handles_empty_results
Verifies graceful degradation when no flights found.
Mock returns `{"best_flights": [], "other_flights": []}`.
Assertion: result contains "No flights found".

### Test 3 — test_search_hotels_formats_results
Verifies the hotels tool formats a SerpAPI response.
Mock returns two properties: Hotel Gracery Shinjuku ($89) and Khaosan Tokyo Kabuki ($35).
Assertions: contains hotel names, "$89", "$35", "4.3" (rating).

### Test 4 — test_cultural_guide_returns_guidance
Verifies the cultural guide compiles organic search results.
Mock returns two organic results about Japan etiquette and phrases.
Assertions: contains "Bowing"/"bowing", "Sumimasen"/"sumimasen", "Japan Etiquette Guide".

---

## tests/test_agent.py (6 tests)

### Test 5 — test_agent_graph_has_expected_nodes
Calls `build_agent()`, inspects the compiled graph.
Assertions: graph has nodes named "llm_call" and "tool_node".

### Test 6 — test_agent_tools_registered
Imports `tools` from agent module.
Assertions: `len(tools) == 4`; names include "search_flights", "search_hotels",
"get_cultural_guide", "duckduckgo_search".

### Test 7 — test_cultural_guide_tool_has_routing_docstring
Verifies that `get_cultural_guide` is in `tools_by_name` and that its description
contains LLM routing keywords ("international" or "cultural", "etiquette" or "customs").

### Test 8 — test_voice_routing_selects_correct_prompt
Calls `get_system_prompt()` with different messages and phases to verify:
- "save money" with synthesis phase → budget voice (contains "Bourdain" or "Billy Dee")
- default → full experience voice (contains "Robin Leach" or "Pharrell" or "Rushdie")
- No budget keyword matches full experience (default)
- `phase="dispatch"` → always returns DISPATCH_PROMPT regardless of budget keyword
- Dispatch prompt contains "IATA" (tool routing instructions) but not "Bourdain" (no voice)

### Test 9 — test_llm_call_uses_dispatch_prompt_before_tools
Verifies that `llm_call` sends `DISPATCH_PROMPT` when the last message in state
is a `HumanMessage` (no tools have run yet).
Mocks: `agent.model_with_tools.invoke` — captures the system prompt from the
first message in the invoke call.
Assertion: captured prompt content equals `DISPATCH_PROMPT`.

### Test 10 — test_llm_call_uses_synthesis_prompt_after_tools
Verifies that `llm_call` sends a voice prompt (not `DISPATCH_PROMPT`) when the
last message in state is a `ToolMessage` (tools have just returned results).
Mocks: `agent.model_with_tools.invoke` — captures the system prompt.
Assertions: captured prompt is NOT `DISPATCH_PROMPT`; for a message containing
"save money", the prompt is `SYSTEM_PROMPT_SAVE_MONEY`.

---

## tests/test_api.py (8 tests)

### Test 11 — test_health_endpoint
GET `/health` returns 200 with `{"status": "ok"}`.

### Test 12 — test_chat_endpoint_accepts_message
POST `/chat` with no extras returns 200 and a non-empty `response` string.
Mocks: `api.agent`.

### Test 13 — test_chat_accepts_valid_preferences
Valid preferences pass through validation and reach the agent.
Mock: `api.validate_preferences` returns `ValidationResult(valid=True)`.
Assertions: 200 response; `validate_preferences` called once with preference text.

### Test 14 — test_chat_rejects_invalid_preferences
Invalid preferences return 400; agent is never called.
Mock: `api.validate_preferences` returns `ValidationResult(valid=False, reason="...")`.
Assertions: status 400; `api.agent.invoke` not called.

### Test 15 — test_chat_skips_validation_for_empty_preferences
Whitespace-only `preferences` field skips validation entirely.
Assertions: 200 response; `api.validate_preferences` not called.

### Test 16 — test_chat_accepts_valid_places
Valid `departure` and `destination` fields pass place validation; agent runs.
Mock: `api.validate_place` returns `PlaceValidationResult(valid=True, ...)`.
Assertion: 200 response.

### Test 17 — test_chat_rejects_invalid_place
An unrecognisable destination returns 400; agent is never called.
Mock: `api.validate_place` uses `side_effect` — departure passes, destination fails.
Assertions: status 400; `detail["field"] == "destination"`; `api.agent.invoke` not called.

### Test 18 — test_chat_auto_corrects_misspelled_place
Misspelled but identifiable place is corrected; agent is called with canonical name.
Mock: `api.validate_place` returns `PlaceValidationResult(valid=True, corrected="Tokyo, Japan", ...)`.
Assertion: 200 response; agent called.

---

## tests/test_otel_routing.py (8 tests)

All tests mock `OTLPSpanExporter` and use `patch.dict(os.environ)` to control
environment variables. No live OTel endpoints are required.

### Test 19 — test_phoenix_destination_creates_one_exporter
Sets `OTEL_DESTINATION=phoenix` and `PHOENIX_ENDPOINT=http://localhost:6006/v1/traces`.
Assertions: `OTLPSpanExporter` called exactly once; endpoint contains "localhost:6006".

### Test 20 — test_phoenix_api_key_added_to_headers_when_present
Sets `PHOENIX_API_KEY=my-cloud-key` alongside Phoenix endpoint.
Assertion: exporter headers contain `authorization: Bearer my-cloud-key`.

### Test 21 — test_phoenix_no_api_key_sends_no_auth_header
Sets Phoenix endpoint without a `PHOENIX_API_KEY`.
Assertion: exporter headers do not contain an `authorization` key.

### Test 22 — test_arize_destination_calls_arize_register
Sets `OTEL_DESTINATION=arize`. Mocks `_build_arize_provider` to return a mock provider.
Assertions: `_build_arize_provider` called once; returned provider matches mock.

### Test 23 — test_arize_missing_credentials_skips_silently
Sets `OTEL_DESTINATION=arize` with empty `ARIZE_API_KEY` and `ARIZE_SPACE_ID`.
Assertion: returns a non-None provider without crashing.

### Test 24 — test_both_destination_uses_arize_and_phoenix
Sets `OTEL_DESTINATION=both` with Phoenix endpoint. Mocks both `_build_arize_provider` and `OTLPSpanExporter`.
Assertion: `_build_arize_provider` called once; `OTLPSpanExporter` called once.

### Test 25 — test_none_destination_creates_no_exporters
Sets `OTEL_DESTINATION=none`.
Assertion: `OTLPSpanExporter` never called.

### Test 26 — test_project_name_sets_service_name
Sets `OTEL_DESTINATION=none` and `OTEL_PROJECT_NAME=my-custom-project`.
Assertion: `provider.resource.attributes.get("service.name") == "my-custom-project"`.

### Test 27 — test_default_project_name_is_travelshaper
Sets `OTEL_DESTINATION=none` without `OTEL_PROJECT_NAME`.
Assertion: `provider.resource.attributes.get("service.name") == "travelshaper"`.

---

## Running the full suite

```bash
cd src
pytest tests/ -v
```

Expected output: `27 passed` (1 warning about `temperature` in `model_kwargs` is expected and harmless).
