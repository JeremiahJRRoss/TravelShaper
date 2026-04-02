"""OTel routing — reads OTEL_DESTINATION from env and builds a
TracerProvider with the appropriate exporters attached.

Valid OTEL_DESTINATION values:
    phoenix   — local Phoenix or Phoenix Cloud
    arize     — Arize Cloud (requires ARIZE_API_KEY + ARIZE_SPACE_ID)
    both      — Phoenix and Arize simultaneously
    none      — disables all telemetry

Called once at startup from agent.py.
"""

import os
import sys

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


def _destination() -> str:
    return os.getenv("OTEL_DESTINATION", "phoenix").strip().lower()


def _phoenix_exporter() -> OTLPSpanExporter | None:
    endpoint = os.getenv("PHOENIX_ENDPOINT", "").strip()
    if not endpoint:
        print("[otel] PHOENIX_ENDPOINT not set — Phoenix disabled", file=sys.stderr)
        return None
    headers = {}
    if api_key := os.getenv("PHOENIX_API_KEY", "").strip():
        headers["authorization"] = f"Bearer {api_key}"
    return OTLPSpanExporter(endpoint=endpoint, headers=headers)


def _arize_exporter() -> OTLPSpanExporter | None:
    endpoint = os.getenv("ARIZE_ENDPOINT", "").strip()
    api_key  = os.getenv("ARIZE_API_KEY",  "").strip()
    space_id = os.getenv("ARIZE_SPACE_ID", "").strip()
    if not all([endpoint, api_key, space_id]):
        print("[otel] Arize credentials incomplete — Arize disabled", file=sys.stderr)
        return None
    return OTLPSpanExporter(
        endpoint=endpoint,
        headers={
            "authorization": api_key,
            "space-id":      space_id,
        },
    )


_FACTORIES = {
    "phoenix": _phoenix_exporter,
    "arize":   _arize_exporter,
}


def build_tracer_provider() -> TracerProvider:
    """Build and return a configured TracerProvider.

    Reads OTEL_DESTINATION to determine which exporters to attach.
    Logs which destinations are active to stderr on startup.
    Returns a no-op TracerProvider if destination is 'none' or
    all credentials are missing.
    """
    dest     = _destination()
    provider = TracerProvider()

    if dest == "none":
        print("[otel] Telemetry disabled (OTEL_DESTINATION=none)")
        return provider

    names = ["phoenix", "arize"] if dest == "both" else [dest]
    active = []

    for name in names:
        factory = _FACTORIES.get(name)
        if factory is None:
            print(f"[otel] Unknown destination '{name}' — skipping", file=sys.stderr)
            continue
        exporter = factory()
        if exporter is None:
            continue
        provider.add_span_processor(BatchSpanProcessor(exporter))
        active.append(name)

    if active:
        print(f"[otel] Traces → {', '.join(active)}")
    else:
        print("[otel] No active trace destinations — running without telemetry",
              file=sys.stderr)

    return provider
