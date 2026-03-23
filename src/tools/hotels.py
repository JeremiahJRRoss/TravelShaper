"""Hotel search tool — queries Google Hotels via SerpAPI."""

from langchain_core.tools import tool

from tools import serpapi_request


def _format_property(prop: dict) -> str:
    """Format a single hotel property into a readable string."""
    name = prop.get("name", "Unknown hotel")
    hotel_class = prop.get("hotel_class", "")
    rating = prop.get("overall_rating", 0)
    reviews = prop.get("reviews", 0)
    rate_info = prop.get("rate_per_night", {})
    price = rate_info.get("lowest", "N/A")

    amenities = prop.get("amenities", [])
    top_amenities = ", ".join(amenities[:5]) if amenities else "not listed"

    check_in = prop.get("check_in_time", "")
    check_out = prop.get("check_out_time", "")

    parts = [f"- {name}"]
    if hotel_class:
        parts[0] += f" ({hotel_class})"
    parts.append(f"  {price}/night")
    if rating:
        parts.append(f"  Rating: {rating}/5 ({reviews} reviews)")
    parts.append(f"  Amenities: {top_amenities}")
    if check_in and check_out:
        parts.append(f"  Check-in: {check_in}, Check-out: {check_out}")

    return "\n".join(parts)


@tool
def search_hotels(
    query: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
    sort_by: int = 13,
) -> str:
    """Search for hotels at a destination for specific dates.

    Use this tool when the user wants to find hotels or accommodation.
    query should be a destination like 'Tokyo hotels' or 'Barcelona hotels'.
    Dates must be in YYYY-MM-DD format.
    sort_by: 3 for lowest price, 13 for highest rating (default).
    For budget travelers, use sort_by=3. For full experience, use sort_by=13.
    Returns a summary of available hotels with prices, ratings, and amenities.
    """
    try:
        data = serpapi_request(
            {
                "engine": "google_hotels",
                "q": query,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "adults": str(adults),
                "currency": "USD",
                "gl": "us",
                "hl": "en",
                "sort_by": str(sort_by),
            }
        )
    except Exception as e:
        return f"Hotel search failed: {e}"

    properties = data.get("properties", [])

    if not properties:
        return f"No hotels found for '{query}' on {check_in_date} to {check_out_date}."

    lines = [
        f"Hotel results: {query}",
        f"Dates: {check_in_date} to {check_out_date}",
        f"Sorted by: {'lowest price' if sort_by == 3 else 'highest rating'}",
        "",
    ]

    for prop in properties[:5]:
        lines.append(_format_property(prop))
        lines.append("")

    return "\n".join(lines)
