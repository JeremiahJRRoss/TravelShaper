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
import time

# ── Dependency check ─────────────────────────────────────────
# Give a clear error if packages are missing, rather than a
# confusing ImportError from deep inside a library.

_missing = []
for _pkg in ["phoenix", "phoenix.evals", "pandas", "openai"]:
    try:
        __import__(_pkg)
    except ImportError:
        _missing.append(_pkg)
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
PROJECT_NAME = "default"  # Phoenix project name where traces live


# ── Helpers ──────────────────────────────────────────────────


def get_spans() -> pd.DataFrame:
    """Pull spans from Phoenix as a DataFrame."""
    print("  Connecting to Phoenix and pulling spans...")
    client = Client(endpoint=PHOENIX_BASE)
    df = client.spans.get_spans_dataframe(project_name=PROJECT_NAME)
    if df is None or df.empty:
        print("  ✗ No spans found in Phoenix. Run traces first.")
        sys.exit(1)
    print(f"  ✓ Pulled {len(df)} spans")
    return df


def run_metric(name: str, df: pd.DataFrame, template: str, model) -> pd.DataFrame:
    """Run a single LLM-as-judge metric against the spans."""
    print(f"  Scoring: {name}...")
    start = time.time()
    results = llm_classify(
        dataframe=df,
        template=template,
        model=model,
        rails=["frustrated", "not frustrated"] if "frustration" in name.lower()
        else ["correct", "incorrect"] if "tool" in name.lower()
        else ["complete", "incomplete"],
    )
    elapsed = time.time() - start
    print(f"  ✓ {name} complete ({elapsed:.1f}s)")
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

    print()
    print("  TravelShaper — Evaluation Runner")
    print(f"  Phoenix: {PHOENIX_BASE}")
    print(f"  Model:   {EVAL_MODEL}")
    print()

    # ── Pull spans ────────────────────────────────────────────
    spans_df = get_spans()

    # ── Set up the eval model ─────────────────────────────────
    model = OpenAIModel(model=EVAL_MODEL)

    # ── Run all three metrics ─────────────────────────────────
    print()
    results = {}

    frustration_results = run_metric(
        "User Frustration",
        spans_df,
        USER_FRUSTRATION_PROMPT_TEMPLATE,
        model,
    )
    results["user_frustration"] = frustration_results

    tool_results = run_metric(
        "Tool Usage Correctness",
        spans_df,
        TOOL_CORRECTNESS_PROMPT,
        model,
    )
    results["tool_correctness"] = tool_results

    completeness_results = run_metric(
        "Answer Completeness",
        spans_df,
        ANSWER_COMPLETENESS_PROMPT,
        model,
    )
    results["answer_completeness"] = completeness_results

    # ── Write results back to Phoenix ─────────────────────────
    print()
    print("  Writing results to Phoenix...")
    client = Client(endpoint=PHOENIX_BASE)

    for metric_name, result_df in results.items():
        client.spans.log_span_annotations_dataframe(
            dataframe=result_df,
            annotation_name=metric_name,
            annotator_kind="LLM",
        )
        print(f"  ✓ Logged {metric_name}")

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
            "label_distribution": counts,
        }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # ── Print summary ─────────────────────────────────────────
    print()
    print(f"  Results saved → {filename}")
    print(f"  View in Phoenix → {PHOENIX_BASE}")
    print()
    print("  Summary:")
    for metric_name, metric_data in summary["metrics"].items():
        dist = metric_data["label_distribution"]
        dist_str = ", ".join(f"{k}: {v}" for k, v in dist.items())
        print(f"    {metric_name}: {dist_str}")
    print()


if __name__ == "__main__":
    main()
