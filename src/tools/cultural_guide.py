"""Cultural guide tool — searches for etiquette, language, and dress guidance."""

from langchain_core.tools import tool

from tools import serpapi_request


def _extract_snippets(data: dict, max_results: int = 5) -> list[str]:
    """Extract readable snippets from Google search results."""
    results = data.get("organic_results", [])
    snippets = []
    for r in results[:max_results]:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        source = r.get("displayed_link", "")
        if snippet:
            snippets.append(f"- {title} ({source}): {snippet}")
    return snippets


@tool
def get_cultural_guide(destination: str) -> str:
    """Get cultural and travel preparation guidance for a destination.

    Use this tool when the user is traveling to an international destination
    and needs help with local customs, language, etiquette, dress code, or
    tipping norms. Also use this for domestic destinations where cultural
    context would be helpful.

    destination should be a city or country name like 'Tokyo, Japan' or 'Barcelona, Spain'.

    Returns a compilation of web-sourced guidance on:
    - Essential local phrases and pronunciation
    - Greeting and etiquette customs
    - Tipping expectations
    - Dress code and packing advice
    - Common mistakes American travelers make
    """
    queries = [
        f"{destination} etiquette tips for American tourists",
        f"{destination} essential local phrases for travelers",
        f"{destination} what to wear dress code tourists",
    ]

    all_snippets = []

    for query in queries:
        try:
            data = serpapi_request(
                {
                    "engine": "google",
                    "q": query,
                    "gl": "us",
                    "hl": "en",
                    "num": "5",
                }
            )
            snippets = _extract_snippets(data, max_results=3)
            all_snippets.extend(snippets)
        except Exception as e:
            all_snippets.append(f"- Search for '{query}' failed: {e}")

    if not all_snippets:
        return (
            f"Could not find cultural guidance for {destination}. "
            f"I'll provide general advice based on my knowledge."
        )

    lines = [
        f"Cultural and travel prep research for {destination}:",
        "",
    ] + all_snippets

    return "\n".join(lines)
