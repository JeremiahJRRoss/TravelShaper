#!/bin/bash
# Run 10 trace queries against TravelShaper for Phoenix tracing
# Usage: ./run_traces.sh [BASE_URL]
# Defaults to http://localhost:8000 if no argument provided.
set -e

BASE_URL="${1:-http://localhost:8000}"

echo "Running 10 trace queries against ${BASE_URL}"
echo "Traces will appear in Phoenix UI at http://localhost:6006"
echo ""

# ---------------------------------------------------------------------------
# Query 1: Full trip request (all 5 inputs)
# Expected tools: search_flights, search_hotels, get_cultural_guide, duckduckgo_search
# ---------------------------------------------------------------------------
echo "=== Query 1 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "I am flying from San Francisco to Tokyo in mid-October for about 10 days. I want to save money. I love food and photography."}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 2: Full trip, different destination, full experience
# Expected tools: search_flights, search_hotels, get_cultural_guide, duckduckgo_search
# ---------------------------------------------------------------------------
echo "=== Query 2 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from JFK to Barcelona, Spain. October 1-10, 2026. Full experience. I care about arts, food, and nightlife."}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 3: Budget trip, minimal interests
# Expected tools: search_flights, search_hotels, get_cultural_guide
# ---------------------------------------------------------------------------
echo "=== Query 3 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Cheapest way to get from Chicago to Rome for a week in November? I am trying to spend as little as possible."}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 4: Destination only, no origin or dates
# Expected tools: get_cultural_guide, duckduckgo_search
# ---------------------------------------------------------------------------
echo "=== Query 4 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What should I know before visiting Japan?"}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 5: Interest-heavy request
# Expected tools: duckduckgo_search, possibly get_cultural_guide
# ---------------------------------------------------------------------------
echo "=== Query 5 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What are the best photography spots in Lisbon? I also want to find great local food."}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 6: Flights only
# Expected tools: search_flights
# ---------------------------------------------------------------------------
echo "=== Query 6 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find me round trip flights from LAX to London Heathrow, departing December 15 2026 and returning December 28 2026."}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 7: Hotels only
# Expected tools: search_hotels
# ---------------------------------------------------------------------------
echo "=== Query 7 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Find me budget hotels in Bangkok for January 5-12 2027. I want the cheapest options."}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 8: Cultural guide only
# Expected tools: get_cultural_guide
# ---------------------------------------------------------------------------
echo "=== Query 8 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "I am visiting Morocco next month. What should I know about etiquette, tipping, and what to wear?"}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 9: Vague / edge case
# Expected tools: duckduckgo_search (agent should do its best)
# ---------------------------------------------------------------------------
echo "=== Query 9 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to go somewhere warm in December. Where should I go?"}'
echo ""
sleep 2

# ---------------------------------------------------------------------------
# Query 10: Domestic trip (US-to-US)
# Expected tools: search_flights, search_hotels, duckduckgo_search (no cultural guide needed)
# ---------------------------------------------------------------------------
echo "=== Query 10 ==="
curl -s -X POST "${BASE_URL}/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from Seattle to Austin, Texas for SXSW in March 2027. I want the full experience — music, food, and nightlife."}'
echo ""

echo ""
echo "All 10 queries complete. View traces in Phoenix UI at http://localhost:6006"
