# Test Specification — TravelShaper Travel Assistant

**Version:** 2.0 (v0.1.4)  
**Total tests:** 16 passing  
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

## tests/test_agent.py (4 tests)

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
Calls `get_system_prompt()` with different messages to verify:
- "save money" → budget voice (contains "Bourdain" or "Billy Dee")
- default → full experience voice (contains "Robin Leach" or "Pharrell" or "Rushdie")
- No budget keyword matches full experience (default)

---

## tests/test_api.py (8 tests)

### Test 9 — test_health_endpoint
GET `/health` returns 200 with `{"status": "ok"}`.

### Test 10 — test_chat_endpoint_accepts_message
POST `/chat` with no extras returns 200 and a non-empty `response` string.
Mocks: `api.agent`.

### Test 11 — test_chat_accepts_valid_preferences
Valid preferences pass through validation and reach the agent.
Mock: `api.validate_preferences` returns `ValidationResult(valid=True)`.
Assertions: 200 response; `validate_preferences` called once with preference text.

### Test 12 — test_chat_rejects_invalid_preferences
Invalid preferences return 400; agent is never called.
Mock: `api.validate_preferences` returns `ValidationResult(valid=False, reason="...")`.
Assertions: status 400; `api.agent.invoke` not called.

### Test 13 — test_chat_skips_validation_for_empty_preferences
Whitespace-only `preferences` field skips validation entirely.
Assertions: 200 response; `api.validate_preferences` not called.

### Test 14 — test_chat_accepts_valid_places
Valid `departure` and `destination` fields pass place validation; agent runs.
Mock: `api.validate_place` returns `PlaceValidationResult(valid=True, ...)`.
Assertion: 200 response.

### Test 15 — test_chat_rejects_invalid_place
An unrecognisable destination returns 400; agent is never called.
Mock: `api.validate_place` uses `side_effect` — departure passes, destination fails.
Assertions: status 400; `detail["field"] == "destination"`; `api.agent.invoke` not called.

### Test 16 — test_chat_auto_corrects_misspelled_place
Misspelled but identifiable place is corrected; agent is called with canonical name.
Mock: `api.validate_place` returns `PlaceValidationResult(valid=True, corrected="Tokyo, Japan", ...)`.
Assertion: 200 response; agent called.

---

## Running the full suite

```bash
cd src
poetry run pytest tests/ -v
```

Expected output: `16 passed` (1 warning about `temperature` in `model_kwargs` is expected and harmless).
