"""Flight search tool — queries Google Flights via SerpAPI."""

from langchain_core.tools import tool

from tools import serpapi_request


def _format_flight_option(flight: dict) -> str:
    """Format a single flight option into a readable string."""
    legs = flight.get("flights", [])
    if not legs:
        return "- Unknown flight"

    first_leg = legs[0]
    airline = first_leg.get("airline", "Unknown airline")
    price = flight.get("price", "N/A")
    total_duration = flight.get("total_duration", 0)
    hours, minutes = divmod(total_duration, 60)
    stops = len(legs) - 1
    stop_label = "nonstop" if stops == 0 else f"{stops} stop(s)"

    departure = first_leg.get("departure_airport", {})
    arrival = legs[-1].get("arrival_airport", {})
    dep_time = departure.get("time", "")
    arr_time = arrival.get("time", "")

    carbon = flight.get("carbon_emissions", {})
    carbon_kg = carbon.get("this_flight", 0) // 1000 if carbon else 0

    parts = [
        f"- {airline}: ${price}",
        f"{hours}h{minutes:02d}m",
        stop_label,
    ]
    if dep_time and arr_time:
        parts.append(f"departs {dep_time} → arrives {arr_time}")
    if carbon_kg:
        parts.append(f"{carbon_kg}kg CO₂")

    return ", ".join(parts)


@tool
def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str,
) -> str:
    """Search for flights between two airports on specific dates.

    Use this tool when the user wants to find flights for their trip.
    departure_id and arrival_id must be IATA airport codes (e.g. SFO, NRT, CDG, LHR, JFK).
    Dates must be in YYYY-MM-DD format.
    Returns a summary of the best available flights with prices, duration, and stops.
    """
    try:
        data = serpapi_request(
            {
                "engine": "google_flights",
                "departure_id": departure_id.upper(),
                "arrival_id": arrival_id.upper(),
                "outbound_date": outbound_date,
                "return_date": return_date,
                "currency": "USD",
                "hl": "en",
                "gl": "us",
                "type": "1",  # round trip
            }
        )
    except Exception as e:
        return f"Flight search failed: {e}"

    best = data.get("best_flights", [])
    other = data.get("other_flights", [])
    all_flights = best + other

    if not all_flights:
        return (
            f"No flights found from {departure_id} to {arrival_id} "
            f"on {outbound_date} returning {return_date}."
        )

    # Price insights if available
    insights = data.get("price_insights", {})
    price_level = insights.get("price_level", "")
    typical_range = insights.get("typical_price_range", [])

    lines = [
        f"Flight results: {departure_id} → {arrival_id}",
        f"Dates: {outbound_date} to {return_date}",
        "",
    ]

    if best:
        lines.append("Best flights:")
        for f in best[:3]:
            lines.append(_format_flight_option(f))

    if other:
        lines.append("\nOther options:")
        for f in other[:3]:
            lines.append(_format_flight_option(f))

    if price_level and typical_range:
        lines.append(
            f"\nPrice insight: current prices are {price_level} "
            f"(typical range: ${typical_range[0]}–${typical_range[1]})"
        )

    return "\n".join(lines)
