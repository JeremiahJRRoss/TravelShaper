"""Run Phoenix evaluations on captured TravelShaper traces.

Usage (after running trace queries against a live TravelShaper + Phoenix stack):

    python -m evaluations.run_evals

Requires the phoenix extras:
    poetry install -E phoenix

NOTE: Template variables {input}, {output}, {tool_calls} must map to span
DataFrame columns.  Phoenix span columns are typically named
"attributes.input.value" and "attributes.output.value".  You may need to
rename columns or supply a ``template_variables`` mapping depending on the
Phoenix version in use.  Check Phoenix docs for the exact column name mapping:
https://arize.com/docs/phoenix/evaluation/python-quickstart
"""

import sys

import phoenix as px
from phoenix.evals import llm_classify, OpenAIModel
from phoenix.trace import SpanEvaluations

from evaluations.metrics.frustration import USER_FRUSTRATION_PROMPT
from evaluations.metrics.tool_correctness import TOOL_CORRECTNESS_PROMPT

# ---------------------------------------------------------------------------
# Connect to Phoenix and fetch spans
# ---------------------------------------------------------------------------

client = px.Client()

spans_df = client.get_spans_dataframe()

# Filter to root spans — one row per user request
root_spans = spans_df[spans_df["parent_id"].isna()].copy()

if root_spans.empty:
    print("No traces found. Run some queries first (see run_traces.sh).")
    sys.exit(1)

print(f"Found {len(root_spans)} traces. Running evaluations...")

# ---------------------------------------------------------------------------
# Evaluation model
# ---------------------------------------------------------------------------

eval_model = OpenAIModel(model="gpt-4o", temperature=0)

# ---------------------------------------------------------------------------
# Evaluation 1: User Frustration
# ---------------------------------------------------------------------------

frustration_results = llm_classify(
    dataframe=root_spans,
    template=USER_FRUSTRATION_PROMPT,
    model=eval_model,
    rails=["frustrated", "not_frustrated"],
    provide_explanation=True,
)

client.log_evaluations(
    SpanEvaluations(
        eval_name="User Frustration",
        dataframe=frustration_results,
    )
)

frustrated_count = (frustration_results["label"] == "frustrated").sum()
total = len(frustration_results)
print(
    f"User Frustration: {frustrated_count}/{total} frustrated "
    f"({frustrated_count / total * 100:.0f}%)"
)

# ---------------------------------------------------------------------------
# Evaluation 2: Tool Usage Correctness
# ---------------------------------------------------------------------------

tool_correctness_results = llm_classify(
    dataframe=root_spans,
    template=TOOL_CORRECTNESS_PROMPT,
    model=eval_model,
    rails=["correct", "incorrect"],
    provide_explanation=True,
)

client.log_evaluations(
    SpanEvaluations(
        eval_name="Tool Usage Correctness",
        dataframe=tool_correctness_results,
    )
)

correct_count = (tool_correctness_results["label"] == "correct").sum()
total = len(tool_correctness_results)
print(
    f"Tool Correctness: {correct_count}/{total} correct "
    f"({correct_count / total * 100:.0f}%)"
)

# ---------------------------------------------------------------------------
# Create 'frustrated_interactions' dataset from frustrated results
# ---------------------------------------------------------------------------

frustrated_df = root_spans[frustration_results["label"] == "frustrated"]

if not frustrated_df.empty:
    dataset = client.upload_dataset(
        dataframe=frustrated_df,
        dataset_name="frustrated_interactions",
        input_keys=["attributes.input.value"],
        output_keys=["attributes.output.value"],
    )
    print(
        f"Created 'frustrated_interactions' dataset with {len(frustrated_df)} examples."
    )
else:
    print("No frustrated interactions found — no dataset created.")

print("Evaluations complete. View results in Phoenix UI at http://localhost:6006")
