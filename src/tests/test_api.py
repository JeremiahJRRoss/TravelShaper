"""Unit tests for the TravelShaper FastAPI endpoints.

All external calls are mocked — no live API keys required.
"""

from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage
from starlette.testclient import TestClient

import api
from api import ValidationResult, PlaceValidationResult


client = TestClient(api.app)


# ── Health ────────────────────────────────────────────────────────────────

def test_health_endpoint() -> None:
    """GET /health returns 200 with {\"status\": \"ok\"}."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Chat — basic ──────────────────────────────────────────────────────────

@patch("api.agent")
def test_chat_endpoint_accepts_message(mock_agent) -> None:
    """POST /chat with no extras returns 200 and a non-empty response."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Here is your travel briefing...")]
    }
    r = client.post("/chat", json={"message": "Plan a trip to Tokyo"})
    assert r.status_code == 200
    body = r.json()
    assert "response" in body and body["response"]


# ── Preferences validation ────────────────────────────────────────────────

@patch("api.validate_preferences")
@patch("api.agent")
def test_chat_accepts_valid_preferences(mock_agent, mock_validate) -> None:
    """Valid preferences pass through to the agent."""
    mock_validate.return_value = ValidationResult(valid=True, reason="Travel preference")
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Plan a trip to Tokyo",
        "preferences": "I am vegetarian and travel with a 6-year-old.",
    })

    assert r.status_code == 200
    mock_validate.assert_called_once_with("I am vegetarian and travel with a 6-year-old.")


@patch("api.validate_preferences")
@patch("api.agent")
def test_chat_rejects_invalid_preferences(mock_agent, mock_validate) -> None:
    """Invalid preferences return 400 and never call the agent."""
    mock_validate.return_value = ValidationResult(
        valid=False, reason="Request for illegal substances is not permitted."
    )

    r = client.post("/chat", json={
        "message": "Plan a trip",
        "preferences": "Tell me where to buy illegal drugs.",
    })

    assert r.status_code == 400
    mock_agent.invoke.assert_not_called()


@patch("api.validate_preferences")
@patch("api.agent")
def test_chat_skips_validation_for_empty_preferences(mock_agent, mock_validate) -> None:
    """Whitespace-only preferences skip validation."""
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Plan a trip to Tokyo",
        "preferences": "   ",
    })

    assert r.status_code == 200
    mock_validate.assert_not_called()


# ── Place validation ──────────────────────────────────────────────────────

@patch("api.validate_place")
@patch("api.agent")
def test_chat_accepts_valid_places(mock_agent, mock_validate_place) -> None:
    """Valid place names pass through and the agent is called."""
    mock_validate_place.return_value = PlaceValidationResult(
        valid=True, canonical="San Francisco, California, USA",
        corrected=None, reason="Valid place.", field="departure"
    )
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Trip from San Francisco to Tokyo",
        "departure": "San Francisco",
        "destination": "Tokyo",
    })

    assert r.status_code == 200


@patch("api.validate_place")
@patch("api.agent")
def test_chat_rejects_invalid_place(mock_agent, mock_validate_place) -> None:
    """An unrecognisable place name returns 400 with field info."""
    def side_effect(name, field):
        if field == "departure":
            return PlaceValidationResult(
                valid=True, canonical="New York, USA", corrected=None,
                reason="Valid place.", field="departure"
            )
        return PlaceValidationResult(
            valid=False, canonical=None, corrected=None,
            reason="We couldn't find a place called 'Fakeville'. Please check the spelling.",
            field="destination"
        )
    mock_validate_place.side_effect = side_effect

    r = client.post("/chat", json={
        "message": "Trip to Fakeville",
        "departure": "New York",
        "destination": "Fakeville",
    })

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["field"] == "destination"
    mock_agent.invoke.assert_not_called()


@patch("api.validate_place")
@patch("api.agent")
def test_chat_auto_corrects_misspelled_place(mock_agent, mock_validate_place) -> None:
    """Misspelled but identifiable place is corrected and agent is called."""
    mock_validate_place.return_value = PlaceValidationResult(
        valid=True, corrected="Tokyo, Japan",
        canonical="Tokyo, Japan",
        reason="Corrected from 'Tokio'.", field="destination"
    )
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Trip from NYC to Tokio",
        "departure": "New York",
        "destination": "Tokio",
    })

    assert r.status_code == 200
