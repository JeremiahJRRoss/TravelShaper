"""TravelShaper — Evaluation runner.

Connects to Phoenix at localhost:6006, pulls collected traces, and
scores each one against three LLM-as-judge metrics:

  1. User Frustration    — was the user experience poor?
  2. Tool Usage Correctness — did the agent call the right tools?
  3. Answer Completeness — did the response cover what was asked?

Unlike a naive span-level approach, this script works at the TRACE
level. It groups all spans by trace ID, identifies the root span
(user input + agent output) and the child spans (actual tool calls),
and assembles a composite record per trace. The tool correctness
metric receives the real list of tools that were called — not an
inference from the response text.

Results are written back to Phoenix as annotations on the root spans
and saved to a local JSON summary file.

Dependencies (install once):
    pip install arize-phoenix arize-phoenix-evals pandas openai

Usage:
    cd src
    python -m evaluations.run_evals          # evaluate 11 most recent traces (default)
    python -m evaluations.run_evals 5        # evaluate 5 most recent traces
    python -m evaluations.run_evals all      # evaluate all traces in Phoenix
"""

import json
import os
import sys
import threading
import time

# ── Dependency check ─────────────────────────────────────────

_missing = []
for _pkg, _label in [
    ("phoenix", "arize-phoenix"),
    ("phoenix.evals", "arize-phoenix-evals"),
    ("pandas", "pandas"),
    ("openai", "openai"),
]:
    try:
        __import__(_pkg)
    except ImportError:
        _missing.append(_label)
if _missing:
    print()
    print(f"  Missing packages: {', '.join(_missing)}")
    print()
    print("  Install eval dependencies into your venv:")
    print("    pip install arize-phoenix arize-phoenix-evals pandas openai")
    print()
    sys.exit(1)

import pandas as pd
from phoenix.client import Client
from phoenix.evals import (
    OpenAIModel,
    llm_classify,
)

# ── Configuration ────────────────────────────────────────────

PHOENIX_URL = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
PHOENIX_BASE = PHOENIX_URL.replace("/v1/traces", "")

EVAL_MODEL = "gpt-4o"
PROJECT_NAME = "travelshaper"

# Number of traces to evaluate. Defaults to 11 (one run of
# run_traces.py). Pass a number as a command-line argument to
# override, or use 0 / "all" to evaluate everything.
#
# Usage:
#   python -m evaluations.run_evals          # evaluate 11 most recent traces
#   python -m evaluations.run_evals 5        # evaluate 5 most recent traces
#   python -m evaluations.run_evals all      # evaluate all traces
DEFAULT_MAX_TRACES = 11

if len(sys.argv) > 1:
    arg = sys.argv[1].strip().lower()
    if arg in ("all", "0"):
        MAX_TRACES = None  # no limit
    else:
        try:
            MAX_TRACES = int(arg)
        except ValueError:
            print(f"  Usage: python -m evaluations.run_evals [number | all]")
            print(f"  Got: '{sys.argv[1]}'")
            sys.exit(1)
else:
    MAX_TRACES = DEFAULT_MAX_TRACES

# The four tools the agent has access to.
KNOWN_TOOLS = {
    "search_flights",
    "search_hotels",
    "get_cultural_guide",
    "duckduckgo_search",
}


# ── Evaluation prompt templates ──────────────────────────────
# Variables in curly braces must match column names in the
# DataFrame passed to llm_classify.

FRUSTRATION_TEMPLATE = (
    "You are evaluating whether a user would feel frustrated "
    "by an AI travel assistant's response.\n\n"
    "CONVERSATION:\n"
    "User: {input}\n\n"
    "Assistant: {output}\n\n"
    "Consider: Was the response helpful? Did it address the user's "
    "needs? Was the tone appropriate? Was important information "
    "missing or wrong? Did the assistant understand the request?\n\n"
    "Respond with one word: \"frustrated\" or \"not frustrated\""
)

# This template receives {tools_called} — the ACTUAL list of tools
# extracted from child spans, not inferred from the response.
TOOL_CORRECTNESS_TEMPLATE = (
    "You are evaluating whether an AI travel planning assistant "
    "called the correct tools for a user's request.\n\n"
    "The assistant has four tools available:\n"
    "- search_flights: Search for flights (needs departure city, destination, dates)\n"
    "- search_hotels: Search for hotels (needs destination, check-in/check-out dates)\n"
    "- get_cultural_guide: Get cultural etiquette and travel tips (for international destinations)\n"
    "- duckduckgo_search: General web search (for interests, activities, recommendations)\n\n"
    "USER REQUEST:\n{input}\n\n"
    "TOOLS ACTUALLY CALLED:\n{tools_called}\n\n"
    "ASSISTANT RESPONSE:\n{output}\n\n"
    "Rules for evaluation:\n"
    "- If the user asked for flights, search_flights should appear in the tools list.\n"
    "- If the user asked for hotels, search_hotels should appear.\n"
    "- If the user said they already have flights or hotels, those tools should NOT appear.\n"
    "- If the destination is international, get_cultural_guide is appropriate.\n"
    "- If the user mentioned specific interests, duckduckgo_search is appropriate.\n"
    "- If the user asked for ONLY one thing (e.g. 'only flights'), other search tools should not appear.\n"
    "- A tool that was called but returned an error is still CORRECT tool selection (the choice was right, the execution failed).\n\n"
    "Based on the user's request and the tools that were actually called, "
    "was the tool selection correct?\n\n"
    "Respond with one word: \"correct\" or \"incorrect\""
)

COMPLETENESS_TEMPLATE = (
    "You are evaluating whether an AI travel assistant's response "
    "completely addresses the user's request.\n\n"
    "USER REQUEST:\n{input}\n\n"
    "ASSISTANT RESPONSE:\n{output}\n\n"
    "First, determine the SCOPE of what the user asked for. "
    "Then check whether the response covers each element.\n\n"
    "Important:\n"
    "- A response is COMPLETE if it covers everything the user asked for, "
    "even if that is only one thing.\n"
    "- If the user asked only for flights, a flights-only response is complete.\n"
    "- If the user asked only for cultural tips, a cultural-tips-only response is complete.\n"
    "- If the user asked for a full trip briefing, the response should cover "
    "flights, hotels, cultural info, and activities.\n"
    "- A response can include MORE than what was asked and still be complete.\n\n"
    "Respond with one word: \"complete\" or \"incomplete\""
)


# ── Heartbeat timer ──────────────────────────────────────────

class Heartbeat:
    """Background thread that prints elapsed time while a metric is scoring."""

    def __init__(self, label, interval=10.0):
        self.label = label
        self.interval = interval
        self.start = time.time()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.wait(self.interval):
            elapsed = time.time() - self.start
            print(f"    ... {self.label} still running ({elapsed:.0f}s elapsed)")

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join(timeout=1)


# ── Helpers ──────────────────────────────────────────────────

def load_openai_key():
    """Load OPENAI_API_KEY from .env if not already set."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("OPENAI_API_KEY=") and not line.startswith("#"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        os.environ["OPENAI_API_KEY"] = key
                        return
    print()
    print("  OPENAI_API_KEY not found.")
    print("  Set it in your .env file or export it in your shell.")
    print()
    sys.exit(1)


def find_column(df, candidates):
    """Find the first matching column name from a list of candidates."""
    for col in candidates:
        if col in df.columns:
            return col
    return None


def get_trace_records(client):
    """
    Pull all spans from Phoenix, group by trace, and build one
    composite record per trace containing:
      - span_id:      the root span's ID (used to attach annotations)
      - input:         the user's message (from root span)
      - output:        the agent's response (from root span)
      - tools_called:  comma-separated list of actual tool names
      - tool_count:    number of tools called
      - all_spans:     list of all span names in the trace (for debugging)
    """
    print(f"  Connecting to Phoenix at {PHOENIX_BASE}")
    try:
        df = client.spans.get_spans_dataframe(project_name=PROJECT_NAME)
    except Exception as e:
        print(f"  Could not connect to Phoenix: {e}")
        print("  Is the Docker stack running? Check with: docker ps")
        sys.exit(1)

    if df is None or df.empty:
        print("  No spans found in Phoenix.")
        print("  Generate traces first: python -m traces.run_traces")
        sys.exit(1)

    print(f"  Pulled {len(df)} total spans from project '{PROJECT_NAME}'")

    # ── Discover column names ─────────────────────────────────
    input_col = find_column(df, [
        "attributes.input.value", "input.value", "input",
    ])
    output_col = find_column(df, [
        "attributes.output.value", "output.value", "output",
    ])
    trace_col = find_column(df, [
        "context.trace_id", "trace_id",
    ])
    parent_col = find_column(df, [
        "parent_id", "parentId", "context.parent_id",
    ])
    name_col = find_column(df, [
        "name", "span_name",
    ])
    kind_col = find_column(df, [
        "span_kind", "attributes.openinference.span.kind",
    ])

    # The span_id is typically the DataFrame index for Phoenix spans
    # but may also be a column
    span_id_col = find_column(df, [
        "context.span_id", "span_id",
    ])

    if not input_col or not output_col or not trace_col:
        print()
        print("  Could not find required columns in spans DataFrame.")
        print(f"  Available columns: {list(df.columns[:20])}")
        print(f"  Found: input='{input_col}', output='{output_col}', trace_id='{trace_col}'")
        sys.exit(1)

    print(f"  Columns: input='{input_col}', output='{output_col}', "
          f"trace='{trace_col}', parent='{parent_col}', name='{name_col}'")

    # ── Group spans by trace ──────────────────────────────────
    # For each trace, find:
    #   - The root span (no parent, or parent is null/empty)
    #   - The tool spans (name matches a known tool)

    # Make sure we have a span_id to work with
    if span_id_col and span_id_col in df.columns:
        df["_span_id"] = df[span_id_col]
    elif df.index.name and "span" in df.index.name.lower():
        df["_span_id"] = df.index
    else:
        # Use the index as-is
        df["_span_id"] = df.index

    traces = df.groupby(trace_col)
    total_traces = len(traces)

    # ── Limit to most recent traces if MAX_TRACES is set ──────
    # Sort trace groups by their earliest span's start time
    # (most recent first) and take only the requested number.
    if MAX_TRACES and total_traces > MAX_TRACES:
        # Find the start time column
        time_col = find_column(df, [
            "start_time", "startTime", "attributes.start_time",
        ])
        if time_col:
            # Get the max start time per trace for sorting
            trace_times = df.groupby(trace_col)[time_col].max().sort_values(ascending=False)
            recent_trace_ids = trace_times.head(MAX_TRACES).index.tolist()
            df = df[df[trace_col].isin(recent_trace_ids)]
            traces = df.groupby(trace_col)
            print(f"  Evaluating {len(traces)} most recent traces (of {total_traces} total)")
        else:
            # No time column found — just take the last N groups
            trace_ids = list(traces.groups.keys())[-MAX_TRACES:]
            df = df[df[trace_col].isin(trace_ids)]
            traces = df.groupby(trace_col)
            print(f"  Evaluating {len(traces)} traces (of {total_traces} total)")
    else:
        limit_label = "all" if not MAX_TRACES else f"all {total_traces}"
        print(f"  Evaluating {limit_label} traces")

    records = []
    skipped = 0
    tool_detail_log = []  # For the JSON summary

    for trace_id, group in traces:
        # ── Find the best span to evaluate ─────────────────────
        # The trace may contain multiple spans:
        #   travelshaper.request  (HTTP layer — often has NO input/output)
        #   LangGraph             (agent layer — has the conversation)
        #   search_flights        (tool — has tool-specific I/O)
        #   search_hotels         (tool)
        #   ...
        #
        # We need the span with the actual user message and agent
        # response. That's usually the LangGraph/agent span, NOT
        # the HTTP request span. Strategy: find all spans that have
        # both non-empty input AND output, then pick the one with
        # the longest output (the full travel briefing).

        candidates = []
        for idx, span in group.iterrows():
            span_input = str(span.get(input_col, "")) if pd.notna(span.get(input_col)) else ""
            span_output = str(span.get(output_col, "")) if pd.notna(span.get(output_col)) else ""
            if span_input.strip() and span_output.strip():
                candidates.append({
                    "idx": idx,
                    "span": span,
                    "input": span_input,
                    "output": span_output,
                    "output_len": len(span_output),
                    "name": str(span.get(name_col, "")) if name_col else "",
                })

        if not candidates:
            skipped += 1
            continue

        # Pick the candidate with the longest output — that's the
        # agent's full briefing, not a tool's raw API response.
        best = max(candidates, key=lambda c: c["output_len"])
        root_input = best["input"]
        root_output = best["output"]
        root_span_id = best["span"].get("_span_id", best["idx"])

        # ── Find tool spans ───────────────────────────────────
        # Match child span names against known tool names
        tools_called = []
        all_span_names = []

        for _, span in group.iterrows():
            span_name = str(span.get(name_col, "")) if name_col else ""
            all_span_names.append(span_name)

            # Check if this span's name matches a known tool
            for tool in KNOWN_TOOLS:
                if tool.lower() in span_name.lower():
                    tools_called.append(tool)
                    break

            # Also check span_kind if available
            if kind_col and kind_col in group.columns:
                span_kind = str(span.get(kind_col, "")).upper()
                if span_kind == "TOOL" and span_name not in tools_called:
                    tools_called.append(span_name)

        # Deduplicate while preserving order
        seen = set()
        unique_tools = []
        for t in tools_called:
            if t not in seen:
                seen.add(t)
                unique_tools.append(t)

        tools_str = ", ".join(unique_tools) if unique_tools else "(no tools called)"

        records.append({
            "span_id": root_span_id,
            "trace_id": trace_id,
            "input": root_input,
            "output": root_output,
            "tools_called": tools_str,
            "tool_count": len(unique_tools),
            "all_span_names": ", ".join(all_span_names),
            "total_spans_in_trace": len(group),
        })

        tool_detail_log.append({
            "trace_id": str(trace_id),
            "input_preview": root_input[:100],
            "tools_called": unique_tools,
            "total_spans": len(group),
        })

    if not records:
        print("  No complete traces found (traces need both input and output).")
        print("  Generate traces first: python -m traces.run_traces")
        sys.exit(1)

    eval_df = pd.DataFrame(records)
    eval_df = eval_df.set_index("span_id")

    print(f"  Assembled {len(eval_df)} trace-level records "
          f"(from {len(df)} total spans)")
    if skipped:
        print(f"  Skipped {skipped} traces with no input/output data")
    print()

    # Print a preview of what tools were found per trace
    print("  Tool calls per trace:")
    for rec in tool_detail_log:
        tools = rec["tools_called"]
        tools_display = ", ".join(tools) if tools else "(none)"
        input_preview = rec["input_preview"][:60]
        print(f"    [{rec['total_spans']} spans] {tools_display}")
        print(f"             {input_preview}...")
    print()

    return eval_df, tool_detail_log


def run_metric(name, df, template, model, rails):
    """Run a single LLM-as-judge metric with a heartbeat timer."""
    print(f"  Scoring: {name} ({len(df)} traces)...")

    with Heartbeat(name):
        start = time.time()
        results = llm_classify(
            data=df,
            template=template,
            model=model,
            rails=rails,
            provide_explanation=True,
        )
        elapsed = time.time() - start

    if "label" in results.columns:
        counts = results["label"].value_counts().to_dict()
        parts = [f"{v} {k}" for k, v in counts.items()]
        summary = ", ".join(parts) if parts else "no labels"
    else:
        summary = "no labels returned"

    print(f"  Done: {name} in {elapsed:.1f}s — {summary}")
    return results


def main():
    load_openai_key()

    total_start = time.time()

    print()
    print("  TravelShaper — Evaluation Runner")
    print(f"  Phoenix: {PHOENIX_BASE}")
    print(f"  Model:   {EVAL_MODEL}")
    limit_display = str(MAX_TRACES) if MAX_TRACES else "all"
    print(f"  Traces:  {limit_display} most recent")
    print()

    # ── Pull and assemble trace-level records ─────────────────
    client = Client(base_url=PHOENIX_BASE)
    eval_df, tool_detail_log = get_trace_records(client)

    # ── Set up the eval model ─────────────────────────────────
    model = OpenAIModel(model=EVAL_MODEL)

    # ── Run all three metrics ─────────────────────────────────
    results = {}

    results["user_frustration"] = run_metric(
        "User Frustration",
        eval_df,
        FRUSTRATION_TEMPLATE,
        model,
        rails=["frustrated", "not frustrated"],
    )

    results["tool_correctness"] = run_metric(
        "Tool Usage Correctness",
        eval_df,
        TOOL_CORRECTNESS_TEMPLATE,
        model,
        rails=["correct", "incorrect"],
    )

    results["answer_completeness"] = run_metric(
        "Answer Completeness",
        eval_df,
        COMPLETENESS_TEMPLATE,
        model,
        rails=["complete", "incomplete"],
    )

    # ── Write results back to Phoenix ─────────────────────────
    print()
    print("  Writing results to Phoenix...")

    for metric_name, result_df in results.items():
        if result_df is None or result_df.empty:
            print(f"  Skipping {metric_name} — no results")
            continue

        has_data = False
        for col in ["label", "score", "explanation"]:
            if col in result_df.columns and result_df[col].notna().any():
                has_data = True
                break

        if not has_data:
            print(f"  Skipping {metric_name} — no labels/scores produced")
            continue

        try:
            client.spans.log_span_annotations_dataframe(
                dataframe=result_df,
                annotation_name=metric_name,
                annotator_kind="LLM",
            )
            print(f"  Logged {metric_name}")
        except Exception as e:
            print(f"  Failed to log {metric_name}: {e}")

    # ── Create frustrated interactions dataset ─────────────────
    dataset_info = {"created": False, "count": 0, "error": None}
    frustration_df = results.get("user_frustration")

    if frustration_df is not None and "label" in frustration_df.columns:
        frustrated_mask = frustration_df["label"] == "frustrated"
        frustrated_rows = eval_df[frustrated_mask]

        if not frustrated_rows.empty:
            try:
                dataset_df = frustrated_rows[["input", "output"]].copy()
                client.upload_dataset(
                    dataframe=dataset_df,
                    dataset_name="frustrated_interactions",
                    input_keys=["input"],
                    output_keys=["output"],
                )
                dataset_info["created"] = True
                dataset_info["count"] = len(dataset_df)
                print(f"  Created 'frustrated_interactions' dataset: {len(dataset_df)} examples")
            except Exception as e:
                dataset_info["error"] = str(e)
                print(f"  Could not create frustrated dataset: {e}")
                print(f"  (Non-critical — evaluation results are still in Phoenix)")
        else:
            print(f"  No frustrated interactions — no dataset created.")
    else:
        print(f"  No frustration results — skipping dataset creation.")

    # ── Save local summary ────────────────────────────────────
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"eval-results_{timestamp}.json"

    summary = {
        "generated": timestamp,
        "phoenix": PHOENIX_BASE,
        "model": EVAL_MODEL,
        "traces_evaluated": len(eval_df),
        "trace_tool_details": tool_detail_log,
        "datasets": {
            "frustrated_interactions": dataset_info,
        },
        "metrics": {},
    }

    for metric_name, result_df in results.items():
        if "label" in result_df.columns:
            counts = result_df["label"].value_counts().to_dict()
        else:
            counts = {}

        # Include per-trace labels and explanations
        trace_results = []
        for idx, row in result_df.iterrows():
            entry = {"span_id": str(idx)}
            if "label" in result_df.columns:
                entry["label"] = str(row.get("label", ""))
            if "explanation" in result_df.columns:
                entry["explanation"] = str(row.get("explanation", ""))
            trace_results.append(entry)

        summary["metrics"][metric_name] = {
            "total": len(result_df),
            "label_distribution": {str(k): int(v) for k, v in counts.items()},
            "per_trace": trace_results,
        }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # ── Final summary ─────────────────────────────────────────
    total_elapsed = time.time() - total_start

    print()
    print(f"  All evaluations complete in {total_elapsed:.0f}s")
    print(f"  Results saved to {filename}")
    print(f"  View in Phoenix at {PHOENIX_BASE}")
    print()
    print("  Summary:")
    for metric_name, metric_data in summary["metrics"].items():
        dist = metric_data["label_distribution"]
        dist_str = ", ".join(f"{v} {k}" for k, v in dist.items())
        print(f"    {metric_name}: {dist_str if dist_str else '(no results)'}")
    print()


if __name__ == "__main__":
    main()
