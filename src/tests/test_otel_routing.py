"""Unit tests for OTel routing module.

Tests mock env vars, OTLPSpanExporter (for Phoenix), and
arize.otel.register (for Arize) so no live endpoints are required.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from otel_routing import build_tracer_provider


# ── Phoenix tests (unchanged logic) ──────────────────────────

@patch("otel_routing.OTLPSpanExporter")
def test_phoenix_destination_creates_one_exporter(mock_exporter):
    mock_exporter.return_value = MagicMock()
    env = {
        "OTEL_DESTINATION": "phoenix",
        "PHOENIX_ENDPOINT": "http://localhost:6006/v1/traces",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    assert mock_exporter.call_count == 1
    call_kwargs = mock_exporter.call_args.kwargs
    assert "localhost:6006" in call_kwargs.get("endpoint", "")


@patch("otel_routing.OTLPSpanExporter")
def test_phoenix_api_key_added_to_headers_when_present(mock_exporter):
    mock_exporter.return_value = MagicMock()
    env = {
        "OTEL_DESTINATION": "phoenix",
        "PHOENIX_ENDPOINT": "https://phoenix-cloud.example.com/v1/traces",
        "PHOENIX_API_KEY":  "my-cloud-key",
    }
    with patch.dict(os.environ, env, clear=False):
        build_tracer_provider()
    headers = mock_exporter.call_args.kwargs.get("headers", {})
    assert headers.get("authorization") == "Bearer my-cloud-key"


@patch("otel_routing.OTLPSpanExporter")
def test_phoenix_no_api_key_sends_no_auth_header(mock_exporter):
    mock_exporter.return_value = MagicMock()
    env = {
        "OTEL_DESTINATION": "phoenix",
        "PHOENIX_ENDPOINT": "http://localhost:6006/v1/traces",
    }
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("PHOENIX_API_KEY", None)
        build_tracer_provider()
    headers = mock_exporter.call_args.kwargs.get("headers", {})
    assert "authorization" not in headers


# ── Arize tests (now using arize.otel.register) ──────────────

@patch("otel_routing._build_arize_provider")
def test_arize_destination_calls_arize_register(mock_build):
    mock_provider = MagicMock()
    mock_build.return_value = mock_provider
    env = {"OTEL_DESTINATION": "arize"}
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    mock_build.assert_called_once()
    assert provider == mock_provider


def test_arize_missing_credentials_skips_silently():
    env = {
        "OTEL_DESTINATION": "arize",
        "ARIZE_API_KEY":    "",
        "ARIZE_SPACE_ID":   "",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    # Should return a provider (no-op) without crashing
    assert provider is not None


# ── Both tests ────────────────────────────────────────────────

@patch("otel_routing.OTLPSpanExporter")
@patch("otel_routing._build_arize_provider")
def test_both_destination_uses_arize_and_phoenix(mock_arize, mock_exporter):
    mock_arize.return_value = MagicMock()
    mock_exporter.return_value = MagicMock()
    env = {
        "OTEL_DESTINATION": "both",
        "PHOENIX_ENDPOINT": "http://localhost:6006/v1/traces",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    mock_arize.assert_called_once()
    mock_exporter.assert_called_once()


# ── None test ─────────────────────────────────────────────────

@patch("otel_routing.OTLPSpanExporter")
def test_none_destination_creates_no_exporters(mock_exporter):
    env = {"OTEL_DESTINATION": "none"}
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    mock_exporter.assert_not_called()


# ── Project name tests ────────────────────────────────────────

def test_project_name_sets_service_name():
    env = {
        "OTEL_DESTINATION": "none",
        "OTEL_PROJECT_NAME": "my-custom-project",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    assert provider.resource.attributes.get("service.name") == "my-custom-project"


def test_default_project_name_is_travelshaper():
    env = {"OTEL_DESTINATION": "none"}
    with patch.dict(os.environ, env, clear=False):
        os.environ.pop("OTEL_PROJECT_NAME", None)
        provider = build_tracer_provider()
    assert provider.resource.attributes.get("service.name") == "travelshaper"
