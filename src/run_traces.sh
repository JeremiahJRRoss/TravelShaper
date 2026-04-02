#!/bin/bash
# Run 10 trace queries against TravelShaper for Phoenix tracing
# Usage: ./run_traces.sh [BASE_URL]
#   Default BASE_URL is http://localhost:8000
set -e

BASE_URL="${1:-http://localhost:8000}"

echo ""
echo "  TravelShaper — Phoenix Trace Generator (bash)"
echo "  Target: $BASE_URL"
echo "  Queries: 10"
echo ""

echo "=== Query 1: SFO → Tokyo · Save money · Food + Photo ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from San Francisco, CA (please identify the nearest major international airport). Destination: Tokyo, Japan. Departure: 2026-10-15. Return: 2026-10-25 (10 days). Budget preference: save money. Interests: food and dining, photography. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "San Francisco, CA",
    "destination": "Tokyo, Japan",
    "preferences": "I want to eat where the locals eat — not a restaurant with an English menu out front. I am happy to point at things and hope for the best."
  }'
echo ""
sleep 2

echo "=== Query 2: NYC → Barcelona · Full experience · Arts + Nightlife ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from New York City, NY (please identify the nearest major international airport). Destination: Barcelona, Spain. Departure: 2026-10-01. Return: 2026-10-10 (9 days). Budget preference: full experience. Interests: arts and culture, food and dining, nightlife and events. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "New York City, NY",
    "destination": "Barcelona, Spain",
    "preferences": "This is a 30th birthday trip. I want at least one dinner that I will still be talking about in ten years. Surprise me."
  }'
echo ""
sleep 2

echo "=== Query 3: Chicago → Roam · Save money · Auto-correction test ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Chicago, IL (please identify the nearest major international airport). Destination: Roam, Italy. Departure: 2026-11-05. Return: 2026-11-12 (1 week). Budget preference: save money. Please provide a complete travel briefing with hyperlinks for every named place, restaurant, hotel, and attraction.",
    "departure": "Chicago, IL",
    "destination": "Roam, Italy",
    "preferences": "I am a broke grad student. Every dollar counts. I will eat standing up if I have to."
  }'
echo ""
sleep 2

echo "=== Query 4: Japan etiquette · No origin/dates · Tattoo edge case ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am visiting Japan for the first time next month. What should I know about etiquette, language, what to wear, and what not to do?",
    "destination": "Japan",
    "preferences": "I have read that bowing is important but I have no idea when or how much. Also I have a sleeve tattoo — will that be a problem?"
  }'
echo ""
sleep 2

echo "=== Query 5: Lisbon · Already there · Photo + Food · No transport ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am already in Lisbon, Portugal. I do not need flights or hotels. I want to know the best photography spots — golden hour, street life, the stuff that does not show up on Instagram. Also where should I eat that is not a tourist trap?",
    "destination": "Lisbon, Portugal",
    "preferences": "I shoot film, not digital. I am looking for texture — peeling tiles, old men playing cards, laundry across alleys. That kind of thing."
  }'
echo ""
sleep 2

echo "=== Query 6: LAX → London · Flights only · Single tool ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Los Angeles, CA (please identify the nearest major international airport). Destination: London, United Kingdom. Departure: 2026-12-15. Return: 2026-12-28. Budget preference: save money. Please focus only on flight options — I have accommodation sorted.",
    "departure": "Los Angeles, CA",
    "destination": "London, United Kingdom"
  }'
echo ""
sleep 2

echo "=== Query 7: Bangkok · Hotels only · Single tool ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am already booked on a flight to Bangkok, Thailand. I need budget hotel options only — check-in January 5 2027, check-out January 12 2027. Save money mode. No flights, no cultural guide, just hotels.",
    "destination": "Bangkok, Thailand",
    "preferences": "I need AC that actually works and a bathroom I am not scared of. That is the full list of requirements."
  }'
echo ""
sleep 2

echo "=== Query 8: Miami → Queenstown · Full experience · Nature + Fitness ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Miami, FL (please identify the nearest major international airport). Destination: Queenstown, New Zealand. Departure: 2026-12-26. Return: 2027-01-09 (2 weeks). Budget preference: full experience. Interests: nature and outdoors, fitness and sports. Please provide a complete travel briefing with hyperlinks for every named place.",
    "departure": "Miami, FL",
    "destination": "Queenstown, New Zealand",
    "preferences": "I want to jump off something tall, run up something steep, and kayak something cold. Southern hemisphere summer is the whole reason for the timing."
  }'
echo ""
sleep 2

echo "=== Query 9: Somewhere warm · Vague input · Agent chooses ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need a break. I want somewhere warm in February, not too far from the East Coast, cheap to get to, good food, and where I can actually switch off. I do not want to go to Cancun. Surprise me.",
    "preferences": "I have been staring at a laptop for six months. I want to feel like a human being again."
  }'
echo ""
sleep 2

echo "=== Query 10: Seattle → Austin · SXSW · Full experience · Domestic ==="
curl -s -X POST "$BASE_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I am planning a trip departing from Seattle, WA (please identify the nearest major international airport). Destination: Austin, Texas. Departure: 2027-03-12. Return: 2027-03-17 (SXSW week). Budget preference: full experience. Interests: nightlife and events, food and dining. Please provide a complete travel briefing with hyperlinks for every named place, venue, hotel, and restaurant.",
    "departure": "Seattle, WA",
    "destination": "Austin, Texas",
    "preferences": "I go to SXSW every year but I always end up at the same venues. I want someone to tell me what I have been missing. Specifically: where are the locals actually going that week?"
  }'
echo ""
sleep 2

echo "  Exporting spans..."
python3 -m scripts.export_spans

echo ""
echo "  10 queries complete."
echo "  View traces at http://localhost:6006"
echo ""
