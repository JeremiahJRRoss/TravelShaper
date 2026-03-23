# Trace Queries — 10 Queries for Phoenix Tracing

**Run these via curl after starting both TravelShaper and Phoenix. The `departure` and `destination` fields enable place validation and auto-correction. They are optional — omit them if testing the raw message path.**
Each query is designed to exercise different tool combinations and edge cases.

---

## Query 1: Full trip request (all 5 inputs)
**Expected tools:** search_flights, search_hotels, get_cultural_guide, duckduckgo_search
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I am flying from San Francisco to Tokyo in mid-October for about 10 days. I want to save money. I love food and photography."}'
```

## Query 2: Full trip, different destination, full experience
**Expected tools:** search_flights, search_hotels, get_cultural_guide, duckduckgo_search
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from JFK to Barcelona, Spain. October 1-10, 2026. Full experience. I care about arts, food, and nightlife."}'
```

## Query 3: Budget trip, minimal interests
**Expected tools:** search_flights, search_hotels, get_cultural_guide
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Cheapest way to get from Chicago to Rome for a week in November? I am trying to spend as little as possible."}'
```

## Query 4: Destination only, no origin or dates
**Expected tools:** get_cultural_guide, duckduckgo_search
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What should I know before visiting Japan?"}'
```

## Query 5: Interest-heavy request
**Expected tools:** duckduckgo_search, possibly get_cultural_guide
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the best photography spots in Lisbon? I also want to find great local food."}'
```

## Query 6: Flights only
**Expected tools:** search_flights
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find me round trip flights from LAX to London Heathrow, departing December 15 2026 and returning December 28 2026."}'
```

## Query 7: Hotels only
**Expected tools:** search_hotels
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find me budget hotels in Bangkok for January 5-12 2027. I want the cheapest options."}'
```

## Query 8: Cultural guide only
**Expected tools:** get_cultural_guide
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I am visiting Morocco next month. What should I know about etiquette, tipping, and what to wear?"}'
```

## Query 9: Vague / edge case
**Expected tools:** duckduckgo_search (agent should do its best)
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to go somewhere warm in December. Where should I go?"}'
```

## Query 10: Domestic trip (US-to-US)
**Expected tools:** search_flights, search_hotels, duckduckgo_search (no cultural guide needed)
```bash
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from Seattle to Austin, Texas for SXSW in March 2027. I want the full experience — music, food, and nightlife."}'
```

---

## Coverage matrix

| Query | Flights | Hotels | Cultural | Web search | Budget mode | Interests | Edge case |
|-------|---------|--------|----------|------------|-------------|-----------|-----------|
| 1     | ✓       | ✓      | ✓        | ✓          | Save        | Food, Photo |         |
| 2     | ✓       | ✓      | ✓        | ✓          | Full        | Arts, Food, Events | |
| 3     | ✓       | ✓      | ✓        |            | Save        |           |           |
| 4     |         |        | ✓        | ✓          |             |           | No origin/dates |
| 5     |         |        |          | ✓          |             | Photo, Food | No transport |
| 6     | ✓       |        |          |            |             |           | Single tool |
| 7     |         | ✓      |          |            | Save        |           | Single tool |
| 8     |         |        | ✓        |            |             |           | Single tool |
| 9     |         |        |          | ✓          |             |           | Vague input |
| 10    | ✓       | ✓      |          | ✓          | Full        | Music, Food, Events | Domestic |

**This set covers:** all 4 tools, both budget modes, 5 of 6 interest categories, partial inputs, single-tool requests, vague requests, and domestic vs. international trips.

---

## Running all 10

Save the curl commands to a shell script:
```bash
#!/bin/bash
for i in $(seq 1 10); do
  echo "=== Query $i ==="
  # paste curl command here
  echo ""
  sleep 2  # avoid rate limiting
done
```

Or use the provided `run_traces.sh` script if included in the repo.
