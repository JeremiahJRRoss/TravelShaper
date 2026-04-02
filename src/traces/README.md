# Trace Generator

Fires 11 curated travel planning queries against the running TravelShaper server and records the results in Phoenix for observability analysis.

## What it does

Each query exercises a different combination of tools, budget voices, edge cases, and input patterns. All dates are computed relative to today so the script never goes stale. Responses are saved to a timestamped JSON file and also appear as traces in Phoenix.

## Usage

```bash
cd src
python -m traces.run_traces              # run all 11 queries (default)
python -m traces.run_traces 3            # run first 3 queries (quick test)
python -m traces.run_traces all          # run all 11 queries (explicit)
python -m traces.run_traces 3 http://localhost:8000   # custom URL
```

## Prerequisites

- TravelShaper server running at `localhost:8000`
- Phoenix running at `localhost:6006` (for trace collection)
- `requests` package installed (`pip install requests`)

## Output

- **Timestamped JSON file** in the current working directory (e.g. `trace-results_2026-04-02_14-05-32.json`) containing each query's request body, response, and status.
- **Phoenix traces** visible at [http://localhost:6006](http://localhost:6006) — one trace per query showing the full tool call chain.

Run from `src/` so the output JSON lands alongside other project files.
