"""TravelShaper agent — LangGraph-based travel planning assistant.

Orchestrates four tools (flights, hotels, cultural guide, DuckDuckGo search)
through a ReAct-style loop built with LangGraph. Phoenix / OpenInference
tracing is enabled when the optional phoenix extras are installed.
"""

import operator
import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from tools.flights import search_flights
from tools.hotels import search_hotels
from tools.cultural_guide import get_cultural_guide

load_dotenv()

# ---------------------------------------------------------------------------
# Observability — OTel routing
# ---------------------------------------------------------------------------
# otel_routing.py reads OTEL_DESTINATION from .env and builds a
# TracerProvider with the appropriate OTLP exporters (phoenix, arize,
# both, or none). LangChainInstrumentor adds OpenInference semantic
# attributes to every LangChain/LangGraph span. Custom spans in api.py
# add request-level metadata.
# ---------------------------------------------------------------------------
try:
    from otel_routing import build_tracer_provider
    from openinference.instrumentation.langchain import LangChainInstrumentor

    _tracer_provider = build_tracer_provider()
    LangChainInstrumentor().instrument(tracer_provider=_tracer_provider)
except ImportError:
    # OTel packages not installed — tracing disabled, agent still works
    pass

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_SAVE_MONEY = """\
You are TravelShaper. Voice: Bourdain's honesty, Billy Dee Williams' cool, \
Gladwell's narrative insight. Budget travel as philosophy, not deprivation. \
Muscular prose, strong opinions, no tourist traps, no "hidden gem", no "amazing".

Extract from the user's message: origin, destination, dates, interests.

Tool usage:
- search_flights: IATA codes, YYYY-MM-DD dates
- search_hotels: sort_by=3 (lowest price)
- get_cultural_guide: all international destinations
- duckduckgo_search: interest discovery, journalist-style queries

Response structure — four sections in this order:
✈️ Getting There | 🏨 Where to Stay | 🗺️ Before You Go | 📍 What to Do

Rules:
1. Every named place, hotel, restaurant, airline: markdown hyperlink [Name](URL). No exceptions.
2. Never fabricate prices, times, or names. Ground all facts in tool results.
3. Call multiple tools in one turn.
4. State tradeoffs plainly.
5. End with one memorable line.
"""

SYSTEM_PROMPT_FULL_EXPERIENCE = """\
You are TravelShaper. Voice: Robin Leach's theatrical grandeur, Pharrell's joy, \
Rushdie's prose intelligence. Cities as mythology. Luxury as earned elevation, \
not intimidation. Every sentence earns its place. No brochure language.

Extract from the user's message: origin, destination, dates, interests.

Tool usage:
- search_flights: IATA codes, YYYY-MM-DD dates
- search_hotels: sort_by=13 (highest rating)
- get_cultural_guide: all international destinations
- duckduckgo_search: interest discovery, best-not-most-popular queries

Response structure — four sections in this order:
✈️ Getting There — Your Chariot Awaits
🏨 Where to Stay — A Sanctuary Awaits
🗺️ Before You Go — The Illuminated Brief
📍 What to Do — The Real Itinerary

Rules:
1. Every named place, hotel, restaurant, airline: markdown hyperlink [Name](URL). No exceptions.
2. Never fabricate prices, times, or names. Ground all facts in tool results.
3. Call multiple tools in one turn.
4. End with one unforgettable line.
"""

DISPATCH_PROMPT = """\
You are TravelShaper. Your only job right now is to decide which tools to call.

Tool usage:
- search_flights: when user has origin + destination + dates. Convert city
  names to IATA codes. Dates must be YYYY-MM-DD.
- search_hotels: when user wants accommodation. sort_by=3 for budget,
  sort_by=13 for full experience.
- get_cultural_guide: for every international destination.
- duckduckgo_search: for interest-based discovery or when other tools
  are not applicable.

Call all relevant tools in a single turn. Do not respond to the user yet.
"""

def get_system_prompt(message: str, phase: str = "synthesis") -> str:
    """Return the correct system prompt based on phase and budget preference.

    phase="dispatch"  — minimal tool-routing prompt, sent on first llm_call
                        before any tools have run
    phase="synthesis" — full voice + structure prompt, sent when writing
                        the final response after tools have returned results
    """
    if phase == "dispatch":
        return DISPATCH_PROMPT
    lower = message.lower()
    if "save money" in lower or "budget" in lower or "cheapest" in lower or "spend as little" in lower:
        return SYSTEM_PROMPT_SAVE_MONEY
    return SYSTEM_PROMPT_FULL_EXPERIENCE

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
tools = [
    search_flights,
    search_hotels,
    get_cultural_guide,
    DuckDuckGoSearchRun(),
]

tools_by_name: dict = {t.name: t for t in tools}

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
model = ChatOpenAI(
    model="gpt-5.3-chat-latest",
    # gpt-5.3-chat-latest only accepts temperature=1 (the model default).
    # We pass it via model_kwargs so it goes directly to the API payload
    # without touching LangChain's own Pydantic temperature field validator,
    # which rejects None on older langchain-openai versions.
    model_kwargs={"temperature": 1},
)
model_with_tools = model.bind_tools(tools)


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------
class MessagesState(TypedDict):
    """State container for the agent message history."""

    messages: Annotated[list[AnyMessage], operator.add]


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------
def llm_call(state: MessagesState) -> dict:
    """Invoke the model with the appropriate system prompt for the current phase.

    Phase detection: if the last message in state is a ToolMessage, tools
    have just run and we are in the synthesis phase — write the response.
    Otherwise we are in the dispatch phase — decide which tools to call.
    """
    last_message = state["messages"][-1] if state["messages"] else None
    is_synthesis = isinstance(last_message, ToolMessage)
    phase = "synthesis" if is_synthesis else "dispatch"

    last_human = next(
        (m.content for m in reversed(state["messages"])
         if isinstance(m, HumanMessage) and isinstance(m.content, str)),
        ""
    )
    system_prompt = get_system_prompt(last_human, phase=phase)

    response = model_with_tools.invoke(
        [SystemMessage(content=system_prompt)] + state["messages"]
    )
    return {"messages": [response]}


def tool_node(state: MessagesState) -> dict:
    """Execute every tool call requested in the last assistant message."""
    results: list[ToolMessage] = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        results.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": results}


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
    """Route to tool execution if the model requested tool calls, otherwise end."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------
def build_agent():
    """Construct and compile the TravelShaper LangGraph agent.

    Returns:
        A compiled LangGraph ``CompiledGraph`` with nodes ``llm_call`` and
        ``tool_node`` connected in a ReAct loop.
    """
    graph_builder = StateGraph(MessagesState)

    graph_builder.add_node("llm_call", llm_call)
    graph_builder.add_node("tool_node", tool_node)

    graph_builder.add_edge(START, "llm_call")
    graph_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
    graph_builder.add_edge("tool_node", "llm_call")

    return graph_builder.compile()