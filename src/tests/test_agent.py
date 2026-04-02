"""Unit tests for the TravelShaper LangGraph agent structure.

Verifies that build_agent() produces a compiled graph with the expected
nodes and that all four tools are registered — without making any live
LLM or API calls.
"""

import pytest

from agent import build_agent, get_system_prompt, tools, tools_by_name


# ---------------------------------------------------------------------------
# Test 4 (overall): agent graph has the expected nodes
# ---------------------------------------------------------------------------

def test_agent_graph_has_expected_nodes() -> None:
    """build_agent() must return a compiled graph with 'llm_call' and 'tool_node'."""
    agent = build_agent()
    nodes = list(agent.get_graph().nodes.keys())

    assert "llm_call" in nodes, f"Expected 'llm_call' in graph nodes, got: {nodes}"
    assert "tool_node" in nodes, f"Expected 'tool_node' in graph nodes, got: {nodes}"


# ---------------------------------------------------------------------------
# Test 5 (overall): all four tools are registered
# ---------------------------------------------------------------------------

def test_agent_tools_registered() -> None:
    """The tools list must contain exactly 4 tools with the correct names."""
    tool_names = [t.name for t in tools]

    assert len(tools) == 4, f"Expected 4 tools, got {len(tools)}: {tool_names}"
    assert "search_flights" in tool_names, f"Missing 'search_flights' in {tool_names}"
    assert "search_hotels" in tool_names, f"Missing 'search_hotels' in {tool_names}"
    assert "get_cultural_guide" in tool_names, f"Missing 'get_cultural_guide' in {tool_names}"
    assert "duckduckgo_search" in tool_names, f"Missing 'duckduckgo_search' in {tool_names}"


# ---------------------------------------------------------------------------
# Test 6 (overall): get_cultural_guide has routing-relevant docstring
# ---------------------------------------------------------------------------

def test_cultural_guide_tool_has_routing_docstring() -> None:
    """get_cultural_guide must have a docstring that guides LLM tool selection."""
    assert "get_cultural_guide" in tools_by_name, "get_cultural_guide not in tools_by_name"

    tool = tools_by_name["get_cultural_guide"]
    doc = tool.description or ""

    assert "international" in doc.lower() or "cultural" in doc.lower(), (
        f"get_cultural_guide docstring should mention 'international' or 'cultural' "
        f"to guide LLM tool selection. Got: {doc[:100]}"
    )
    assert "etiquette" in doc.lower() or "customs" in doc.lower(), (
        f"get_cultural_guide docstring should mention 'etiquette' or 'customs'. "
        f"Got: {doc[:100]}"
    )


# ---------------------------------------------------------------------------
# Test 7 (overall): voice routing selects correct prompt
# ---------------------------------------------------------------------------

def test_voice_routing_selects_correct_prompt() -> None:
    """get_system_prompt must route 'save money' to budget voice and default to full experience."""
    budget_prompt = get_system_prompt("I want to save money on this trip")
    full_prompt = get_system_prompt("Give me the full experience")
    default_prompt = get_system_prompt("Plan a trip to Tokyo")

    assert "Bourdain" in budget_prompt or "Billy Dee" in budget_prompt, (
        "Budget keywords should activate the save-money voice"
    )
    assert "Robin Leach" in full_prompt or "Pharrell" in full_prompt or "Rushdie" in full_prompt, (
        "Full experience should activate the luxury voice"
    )
    # Default (no budget keyword) should be full experience
    assert full_prompt == default_prompt, (
        "Default (no budget keyword) should select the full-experience prompt"
    )
