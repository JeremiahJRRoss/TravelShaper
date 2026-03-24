"""TravelShaper — Evaluation runner.

Connects to Phoenix at localhost:6006, pulls collected traces, and
scores each one against three LLM-as-judge metrics: User Frustration,
Tool Usage Correctness, and Answer Completeness. Results are written
back to Phoenix as annotations and saved to a local JSON summary.

Run this from the src/ directory after generating traces (either via
run_traces.py, the browser UI, or curl requests).

Dependencies (install once):
    pip install arize-phoenix arize-phoenix-evals pandas openai

Usage:
    cd src
    python run_evals.py
"""

import json
import os
import sys
import threading
import time

# ── Dependency check ─────────────────────────────────────────
# Give a clear error if packages are missing, rather than a
# confusing ImportError from deep inside a library.

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
    print(f"  ✗ Missing packages: {', '.join(_missing)}")
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

# Import the custom evaluation prompts from the project's
# evaluations/metrics/ directory. This works because the
# script runs from src/ where that package lives.
from evaluations.metrics.tool_correctness import TOOL_CORRECTNESS_PROMPT
from evaluations.metrics.answer_completeness import ANSWER_COMPLETENESS_PROMPT

# User frustration uses Phoenix's built-in template.
from phoenix.evals import USER_FRUSTRATION_PROMPT_TEMPLATE

# ── Configuration ────────────────────────────────────────────

PHOENIX_URL = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
# Strip the /v1/traces suffix if present (the Client wants the base URL)
PHOENIX_BASE = PHOENIX_URL.replace("/v1/traces", "")

EVAL_MODEL = "gpt-4o"
PROJECT_NAME = "travelshaper"  # Phoenix project name where traces live


# ── Heartbeat timer ──────────────────────────────────────────
# Prints elapsed time every few seconds so you know the script
# hasn't hung during long llm_classify calls.


class Heartbeat:
    """Background thread that prints elapsed time while a metric is scoring."""

    def __init__(self, label: str, span_count: int, interval: float = 10.0):
        self.label = label
        self.span_count = span_count
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


def get_spans() -> pd.DataFrame:
    """Pull spans from Phoenix as a DataFrame."""
    print("  Connecting to Phoenix at", PHOENIX_BASE)
    try:
        client = Client(base_url=PHOENIX_BASE)
        df = client.spans.get_spans_dataframe(project_name=PROJECT_NAME)
    except Exception as e:
        print(f"  ✗ Could not connect to Phoenix: {e}")
        print("    Is the Docker stack running? Check with: docker ps")
        sys.exit(1)

    if df is None or df.empty:
        print("  ✗ No spans found in Phoenix.")
        print("    Generate traces first: python run_traces.py")
        sys.exit(1)

    print(f"  ✓ Pulled {len(df)} spans from project '{PROJECT_NAME}'")
    return df


def run_metric(
    name: str,
    df: pd.DataFrame,
    template: str,
    model,
    rails: list[str],
) -> pd.DataFrame:
    """Run a single LLM-as-judge metric with a heartbeat timer."""
    print(f"  Scoring: {name} ({len(df)} spans × 1 gpt-4o call each)...")

    with Heartbeat(name, len(df)):
        start = time.time()
        results = llm_classify(
            dataframe=df,
            template=template,
            model=model,
            rails=rails,
        )
        elapsed = time.time() - start

    # Summarize results
    if "label" in results.columns:
        counts = results["label"].value_counts().to_dict()
        summary_parts = [f"{v} {k}" for k, v in counts.items()]
        summary_str = ", ".join(summary_parts)
    else:
        summary_str = "no labels returned"

    print(f"  ✓ {name} complete in {elapsed:.1f}s — {summary_str}")
    return results


def main() -> None:
    # ── Check for OpenAI key ──────────────────────────────────
    if not os.environ.get("OPENAI_API_KEY"):
        # Try loading from .env file in current directory
        env_path = os.path.join(os.getcwd(), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY=") and not line.startswith("#"):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key:
                            os.environ["OPENAI_API_KEY"] = key
                            break

    if not os.environ.get("OPENAI_API_KEY"):
        print()
        print("  ✗ OPENAI_API_KEY not found.")
        print("    Set it in your .env file or export it in your shell.")
        print()
        sys.exit(1)

    total_start = time.time()

    print()
    print("  TravelShaper — Evaluation Runner")
    print(f"  Phoenix: {PHOENIX_BASE}")
    print(f"  Model:   {EVAL_MODEL}")
    print()

    # ── Pull spans ────────────────────────────────────────────
    spans_df = get_spans()
    print()

    # ── Set up the eval model ─────────────────────────────────
    model = OpenAIModel(model=EVAL_MODEL)

    # ── Run all three metrics ─────────────────────────────────
    # Each metric defines its own "rails" — the set of labels
    # the classifier can assign to each span.

    results = {}

    results["user_frustration"] = run_metric(
        "User Frustration",
        spans_df,
        USER_FRUSTRATION_PROMPT_TEMPLATE,
        model,
        rails=["frustrated", "not frustrated"],
    )

    results["tool_correctness"] = run_metric(
        "Tool Usage Correctness",
        spans_df,
        TOOL_CORRECTNESS_PROMPT,
        model,
        rails=["correct", "incorrect"],
    )

    results["answer_completeness"] = run_metric(
        "Answer Completeness",
        spans_df,
        ANSWER_COMPLETENESS_PROMPT,
        model,
        rails=["complete", "incomplete"],
    )

    # ── Write results back to Phoenix ─────────────────────────
    print()
    print("  Writing results to Phoenix...")
    client = Client(base_url=PHOENIX_BASE)

    for metric_name, result_df in results.items():
        try:
            client.spans.log_span_annotations_dataframe(
                dataframe=result_df,
                annotation_name=metric_name,
                annotator_kind="LLM",
            )
            print(f"  ✓ Logged {metric_name}")
        except Exception as e:
            print(f"  ✗ Failed to log {metric_name}: {e}")

    # ── Save local summary ────────────────────────────────────
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"eval-results_{timestamp}.json"

    summary = {
        "generated": timestamp,
        "phoenix": PHOENIX_BASE,
        "model": EVAL_MODEL,
        "spans_evaluated": len(spans_df),
        "metrics": {},
    }

    for metric_name, result_df in results.items():
        if "label" in result_df.columns:
            counts = result_df["label"].value_counts().to_dict()
        else:
            counts = {}
        summary["metrics"][metric_name] = {
            "total": len(result_df),
            "label_distribution": {str(k): int(v) for k, v in counts.items()},
        }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # ── Final summary ─────────────────────────────────────────
    total_elapsed = time.time() - total_start

    print()
    print(f"  All evaluations complete in {total_elapsed:.0f}s")
    print(f"  Results saved → {filename}")
    print(f"  View in Phoenix → {PHOENIX_BASE}")
    print()
    print("  Summary:")
    for metric_name, metric_data in summary["metrics"].items():
        dist = metric_data["label_distribution"]
        dist_str = ", ".join(f"{v} {k}" for k, v in dist.items())
        print(f"    {metric_name}: {dist_str}")
    print()


if __name__ == "__main__":
    main()
