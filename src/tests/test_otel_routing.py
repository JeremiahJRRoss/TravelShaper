"""Unit tests for OTel routing module.

All tests mock env vars and OTLPSpanExporter so no live endpoints
are required.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from otel_routing import build_tracer_provider


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
def test_arize_destination_creates_one_exporter(mock_exporter):
    mock_exporter.return_value = MagicMock()
    env = {
        "OTEL_DESTINATION": "arize",
        "ARIZE_ENDPOINT":   "https://otlp.arize.com/v1",
        "ARIZE_API_KEY":    "test-key",
        "ARIZE_SPACE_ID":   "test-space",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    assert mock_exporter.call_count == 1
    call_kwargs = mock_exporter.call_args.kwargs
    assert "arize.com" in call_kwargs.get("endpoint", "")


@patch("otel_routing.OTLPSpanExporter")
def test_both_destination_creates_two_exporters(mock_exporter):
    mock_exporter.return_value = MagicMock()
    env = {
        "OTEL_DESTINATION": "both",
        "PHOENIX_ENDPOINT": "http://localhost:6006/v1/traces",
        "ARIZE_ENDPOINT":   "https://otlp.arize.com/v1",
        "ARIZE_API_KEY":    "test-key",
        "ARIZE_SPACE_ID":   "test-space",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    assert mock_exporter.call_count == 2


@patch("otel_routing.OTLPSpanExporter")
def test_none_destination_creates_no_exporters(mock_exporter):
    env = {"OTEL_DESTINATION": "none"}
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    mock_exporter.assert_not_called()


@patch("otel_routing.OTLPSpanExporter")
def test_arize_missing_credentials_skips_silently(mock_exporter):
    env = {
        "OTEL_DESTINATION": "arize",
        "ARIZE_ENDPOINT":   "",
        "ARIZE_API_KEY":    "",
        "ARIZE_SPACE_ID":   "",
    }
    with patch.dict(os.environ, env, clear=False):
        provider = build_tracer_provider()
    mock_exporter.assert_not_called()


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
