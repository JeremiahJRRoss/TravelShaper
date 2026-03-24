"""TravelShaper — Phoenix trace generator.

Fires 11 queries against the running server and generates traces
viewable in Phoenix at http://localhost:6006. After all queries
complete, exports the traces to a timestamped JSON file via
Phoenix's GraphQL API.

Uses only the requests library (already a project dependency) and
the Python standard library. No platform-specific commands, no
bash, no jq — works identically on Windows, macOS, and Linux.

Usage:
    python run_traces.py                     # default: http://localhost:8000
    python run_traces.py http://localhost:8000  # explicit base URL
"""

import json
import sys
import time
from datetime import date, timedelta

import requests

# ── Configuration ────────────────────────────────────────────

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
PHOENIX_URL = "http://localhost:6006"
PAUSE_SECONDS = 3

# ── Date arithmetic ─────────────────────────────────────────
# All dates are computed relative to today so queries never go stale.

today = date.today()


def future(days: int) -> str:
    return (today + timedelta(days=days)).isoformat()


def past(days: int) -> str:
    return (today - timedelta(days=days)).isoformat()


# ── Query definitions ────────────────────────────────────────
# Each query is a dict with a label (for terminal output), the
# JSON body to POST to /chat, and a comment describing what
# tools the agent is expected to call.

QUERIES = [
    {
        "label": "SFO → Tokyo · Save money · Food + Photo",
        "expected": "search_flights, search_hotels, get_cultural_guide, duckduckgo_search",
        "body": {
            "message": (
                "I am planning a trip departing from San Francisco, CA "
                "(please identify the nearest major international airport). "
                f"Destination: Tokyo, Japan. Departure: {future(30)}. "
                f"Return: {future(40)} (10 days). Budget preference: save money. "
                "Interests: food and dining, photography. Please provide a complete "
                "travel briefing with hyperlinks for every named place, restaurant, "
                "hotel, and attraction."
            ),
            "departure": "San Francisco, CA",
            "destination": "Tokyo, Japan",
            "preferences": (
                "I want to eat where the locals eat — not a restaurant with an "
                "English menu out front. I am happy to point at things and hope "
                "for the best."
            ),
        },
    },
    {
        "label": "NYC → Barcelona · Full experience · Arts + Nightlife",
        "expected": "search_flights, search_hotels, get_cultural_guide, duckduckgo_search",
        "body": {
            "message": (
                "I am planning a trip departing from New York City, NY "
                "(please identify the nearest major international airport). "
                f"Destination: Barcelona, Spain. Departure: {future(45)}. "
                f"Return: {future(54)} (9 days). Budget preference: full experience. "
                "Interests: arts and culture, food and dining, nightlife and events. "
                "Please provide a complete travel briefing with hyperlinks for every "
                "named place, restaurant, hotel, and attraction."
            ),
            "departure": "New York City, NY",
            "destination": "Barcelona, Spain",
            "preferences": (
                "This is a 30th birthday trip. I want at least one dinner that I "
                "will still be talking about in ten years. Surprise me."
            ),
        },
    },
    {
        "label": "Chicago → Roam [sic] · Save money · Auto-correction test",
        "expected": "search_flights, search_hotels, get_cultural_guide",
        "body": {
            "message": (
                "I am planning a trip departing from Chicago, IL "
                "(please identify the nearest major international airport). "
                f"Destination: Roam, Italy. Departure: {future(60)}. "
                f"Return: {future(67)} (1 week). Budget preference: save money. "
                "Please provide a complete travel briefing with hyperlinks for every "
                "named place, restaurant, hotel, and attraction."
            ),
            "departure": "Chicago, IL",
            "destination": "Roam, Italy",
            "preferences": (
                "I am a broke grad student. Every dollar counts. I will eat "
                "standing up if I have to."
            ),
        },
    },
    {
        "label": "Japan etiquette · No origin/dates · Tattoo edge case",
        "expected": "get_cultural_guide, duckduckgo_search",
        "body": {
            "message": (
                "I am visiting Japan for the first time next month. What should "
                "I know about etiquette, language, what to wear, and what not to do?"
            ),
            "destination": "Japan",
            "preferences": (
                "I have read that bowing is important but I have no idea when or "
                "how much. Also I have a sleeve tattoo — will that be a problem?"
            ),
        },
    },
    {
        "label": "Lisbon · Already there · Photo + Food · No transport",
        "expected": "duckduckgo_search, get_cultural_guide",
        "body": {
            "message": (
                "I am already in Lisbon, Portugal. I do not need flights or hotels. "
                "I want to know the best photography spots — golden hour, street "
                "life, the stuff that does not show up on Instagram. Also where "
                "should I eat that is not a tourist trap?"
            ),
            "destination": "Lisbon, Portugal",
            "preferences": (
                "I shoot film, not digital. I am looking for texture — peeling "
                "tiles, old men playing cards, laundry across alleys. That kind "
                "of thing."
            ),
        },
    },
    {
        "label": "LAX → London · Flights only · Single tool",
        "expected": "search_flights only",
        "body": {
            "message": (
                "I am planning a trip departing from Los Angeles, CA "
                "(please identify the nearest major international airport). "
                f"Destination: London, United Kingdom. Departure: {future(90)}. "
                f"Return: {future(103)}. Budget preference: save money. "
                "Please focus only on flight options — I have accommodation sorted."
            ),
            "departure": "Los Angeles, CA",
            "destination": "London, United Kingdom",
        },
    },
    {
        "label": "Bangkok · Hotels only · Single tool",
        "expected": "search_hotels only",
        "body": {
            "message": (
                "I am already booked on a flight to Bangkok, Thailand. I need "
                f"budget hotel options only — check-in {future(120)}, "
                f"check-out {future(127)}. Save money mode. No flights, no "
                "cultural guide, just hotels."
            ),
            "destination": "Bangkok, Thailand",
            "preferences": (
                "I would like a safe, clean, trip that focuses on learning about "
                "the religious history in the region"
            ),
        },
    },
    {
        "label": "Miami → Queenstown · Full experience · Nature + Fitness",
        "expected": "search_flights, search_hotels, get_cultural_guide, duckduckgo_search",
        "body": {
            "message": (
                "I am planning a trip departing from Miami, FL "
                "(please identify the nearest major international airport). "
                f"Destination: Queenstown, New Zealand. Departure: {future(150)}. "
                f"Return: {future(164)} (2 weeks). Budget preference: full experience. "
                "Interests: nature and outdoors, fitness and sports. Please provide "
                "a complete travel briefing with hyperlinks for every named place."
            ),
            "departure": "Miami, FL",
            "destination": "Queenstown, New Zealand",
            "preferences": (
                "I want to jump off something tall, run up something steep, and "
                "kayak something cold. Southern hemisphere summer is the whole "
                "reason for the timing."
            ),
        },
    },
    {
        "label": "Somewhere warm · Vague input · Agent chooses",
        "expected": "duckduckgo_search",
        "body": {
            "message": (
                "I need a break. I want somewhere warm in February, not too far "
                "from the East Coast, cheap to get to, good food, and where I can "
                "actually switch off. I do not want to go to Cancun. Surprise me."
            ),
            "preferences": (
                "I have been staring at a laptop for six months. I want to feel "
                "like a human being again."
            ),
        },
    },
    {
        "label": "Seattle → Austin · SXSW · Full experience · Domestic",
        "expected": "search_flights, search_hotels, duckduckgo_search (no cultural guide)",
        "body": {
            "message": (
                "I am planning a trip departing from Seattle, WA "
                "(please identify the nearest major international airport). "
                f"Destination: Austin, Texas. Departure: {future(180)}. "
                f"Return: {future(185)} (SXSW week). Budget preference: full "
                "experience. Interests: nightlife and events, food and dining. "
                "Please provide a complete travel briefing with hyperlinks for "
                "every named place, venue, hotel, and restaurant."
            ),
            "departure": "Seattle, WA",
            "destination": "Austin, Texas",
            "preferences": (
                "I go to SXSW every year but I always end up at the same venues. "
                "I want someone to tell me what I have been missing. Specifically: "
                "where are the locals actually going that week?"
            ),
        },
    },
    {
        "label": "Boston → Paris · PAST DATES · Error handling test",
        "expected": "agent should reject or warn about past departure dates",
        "body": {
            "message": (
                "I am planning a trip departing from Boston, MA "
                "(please identify the nearest major international airport). "
                f"Destination: Paris, France. Departure: {past(30)}. "
                f"Return: {past(23)} (7 days). Budget preference: save money. "
                "Please provide flight and hotel options."
            ),
            "departure": "Boston, MA",
            "destination": "Paris, France",
            "preferences": (
                "This is a test with past dates — the system should handle "
                "this gracefully."
            ),
        },
    },
]


# ── Runner ───────────────────────────────────────────────────


def fire(number: int, label: str, body: dict) -> None:
    """Send a single query and print a preview of the response."""
    print(f"┌─ Query {number} ─ {label}")

    try:
        r = requests.post(
            f"{BASE_URL}/chat",
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        text = data.get("response", "") or str(data)
        preview = text[:120].replace("\n", " ")
        suffix = "..." if len(text) > 120 else ""
        print(f"│  ✓ {preview}{suffix}")
    except requests.exceptions.ConnectionError:
        print("│  ✗ Connection refused — is the server running?")
    except requests.exceptions.Timeout:
        print("│  ✗ Request timed out (120s)")
    except Exception as e:
        print(f"│  ✗ {e}")

    print("└─────────────────────────────────────────────────────")
    print()


def export_traces() -> str | None:
    """Export traces from Phoenix via GraphQL. Returns filename or None."""
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"trace-results_{timestamp}.json"

    graphql_query = {
        "query": (
            "{ spans(last: 100, sort: { col: startTime, dir: desc }) "
            "{ edges { node { name spanKind statusCode startTime latencyMs "
            "parentId context { traceId spanId } input { value } "
            "output { value } attributes } } } }"
        )
    }

    try:
        r = requests.post(
            f"{PHOENIX_URL}/graphql",
            json=graphql_query,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()

        with open(filename, "w", encoding="utf-8") as f:
            f.write(r.text)

        return filename

    except requests.exceptions.ConnectionError:
        return None
    except Exception:
        return None


def main() -> None:
    print()
    print("  TravelShaper — Phoenix Trace Generator")
    print(f"  Target:  {BASE_URL}")
    print(f"  Phoenix: {PHOENIX_URL}")
    print(f"  Queries: {len(QUERIES)}")
    print(f"  Dates generated relative to: {today.isoformat()}")
    print()
    print("  Starting in 2 seconds...")
    time.sleep(2)
    print()

    # ── Fire all queries ──────────────────────────────────────
    for i, query in enumerate(QUERIES, start=1):
        fire(i, query["label"], query["body"])
        if i < len(QUERIES):
            time.sleep(PAUSE_SECONDS)

    # ── Export traces ─────────────────────────────────────────
    print()
    print("  Exporting traces from Phoenix...")

    filename = export_traces()
    if filename:
        import os

        size = os.path.getsize(filename)
        if size > 0:
            # Format size in human-readable form
            if size > 1_000_000:
                size_str = f"{size / 1_000_000:.1f}MB"
            elif size > 1_000:
                size_str = f"{size / 1_000:.1f}KB"
            else:
                size_str = f"{size}B"
            print(f"  ✓ Exported to {filename} ({size_str})")
        else:
            print("  ✗ Export file is empty — Phoenix may have no trace data yet")
            os.remove(filename)
    else:
        print(
            "  ✗ Export failed — Phoenix may not be reachable at "
            f"{PHOENIX_URL}"
        )

    print()
    print("  All 11 queries complete.")
    print(f"  View traces → {PHOENIX_URL}")
    print("  Run evals  → python -m evaluations.run_evals")
    print()


if __name__ == "__main__":
    main()
