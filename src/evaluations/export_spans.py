"""Export Phoenix spans to CSV.

Usage:
    cd src
    python -m evaluations.export_spans

Writes a timestamped CSV file to the current working directory.
Run this AFTER generating traces with `python -m traces.run_traces`.
"""

import os
import sys
import time
from pathlib import Path

from phoenix.client import Client


def export_spans(project_name: str = "travelshaper") -> None:
    """Fetch spans from Phoenix and write to CSV."""
    phoenix_url = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
    phoenix_base = phoenix_url.replace("/v1/traces", "")

    client = Client(base_url=phoenix_base)

    try:
        spans_df = client.spans.get_spans_dataframe(project_name=project_name)
    except Exception as exc:
        print(f"Could not connect to Phoenix: {exc}")
        print(f"Make sure Phoenix is running at {phoenix_base}")
        sys.exit(1)

    if spans_df is None or spans_df.empty:
        print("No spans found. Run `python -m traces.run_traces` first to generate traces.")
        sys.exit(0)  # Not an error state — just no data yet

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    output_path = Path.cwd() / f"spans_export_{timestamp}.csv"

    spans_df.to_csv(output_path, index=False)

    root_spans = spans_df[spans_df["parent_id"].isna()] if "parent_id" in spans_df.columns else spans_df.head(0)

    llm_count = 0
    tool_count = 0
    if "span_kind" in spans_df.columns:
        kind_upper = spans_df["span_kind"].astype(str).str.upper()
        llm_count = int((kind_upper == "LLM").sum())
        tool_count = int((kind_upper == "TOOL").sum())

    print(f"Exported {len(spans_df)} total spans to {output_path}")
    print(f"  Root (request) spans : {len(root_spans)}")
    print(f"  LLM spans            : {llm_count}")
    print(f"  Tool spans           : {tool_count}")


if __name__ == "__main__":
    export_spans()
