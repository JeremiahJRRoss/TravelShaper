"""Unit tests for the TravelShaper LangGraph agent structure.

Verifies that build_agent() produces a compiled graph with the expected
nodes and that all four tools are registered — without making any live
LLM or API calls.
"""

import pytest

from agent import build_agent, tools


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
