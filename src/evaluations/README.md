# Evaluations

LLM-as-judge evaluation pipeline for TravelShaper traces captured in Phoenix.

## What it does

Connects to Phoenix, pulls collected traces, groups spans by trace ID to assemble trace-level records, and scores each trace against three metrics using gpt-4o:

1. **User Frustration** — detects responses that are technically correct but experientially poor (curt, dismissive, missing key info).
2. **Tool Usage Correctness** — evaluates whether the agent called the right tools, using the actual tool calls extracted from child spans (not inferred from response text).
3. **Answer Completeness** — checks whether the response covers everything the user asked for, with scope awareness (a flights-only request only needs flights).

Results are written back to Phoenix as span annotations and saved to a local timestamped JSON summary file.

## Usage

```bash
cd src
python -m evaluations.run_evals          # evaluate 11 most recent traces (default)
python -m evaluations.run_evals 5        # evaluate 5 most recent traces
python -m evaluations.run_evals all      # evaluate all traces in Phoenix
```

## Prerequisites

- Phoenix running at `localhost:6006` with traces already captured
- `OPENAI_API_KEY` set in `.env` or environment (used for gpt-4o evaluation calls)
- Packages: `arize-phoenix arize-phoenix-evals pandas openai`

## Output

- **Phoenix annotations** — scores appear on root spans in the Phoenix UI Evaluations tab
- **Local JSON file** — e.g. `eval-results_2026-04-02_14-08-12.json` with per-trace labels, explanations, and label distributions

## Metrics directory

The `metrics/` subdirectory contains reference prompt templates:

- `frustration.py` — USER_FRUSTRATION_PROMPT (reference)
- `answer_completeness.py` — ANSWER_COMPLETENESS_PROMPT
- `tool_correctness.py` — TOOL_CORRECTNESS_PROMPT

The consolidated evaluation runner defines its own prompt templates inline for self-containment. These files serve as documentation of the prompt design.

## Export spans

Export all Phoenix spans to a timestamped CSV file for offline analysis:

```bash
cd src
python -m evaluations.export_spans
```

Produces a file like `spans_export_2026-04-02_14-10-00.csv` in the current directory.
