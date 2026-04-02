# TravelShaper — Claude Code Context

## Project root
All commands run from `src/`.

## Stack
- Python 3.11, FastAPI, LangGraph, LangChain
- Poetry for deps, pytest for tests
- Docker Compose: travelshaper (:8000) + phoenix (:6006)

## Key files
- agent.py          — LangGraph agent + Phoenix/OTel instrumentation
- api.py            — FastAPI endpoints + custom spans
- otel_routing.py   — OTel config routing (OTEL_DESTINATION in .env)
- .env              — secrets, never committed
- .env.example      — committed template

## OTel goal
Replace the hardcoded Phoenix setup in agent.py with a routing
module driven by OTEL_DESTINATION in .env.
Valid values: phoenix | arize | both | none

## Do not touch
- tools/           — no changes needed
- tests/           — add tests only, never delete
- static/          — no changes needed

## After every step
Run: pytest tests/ -v
All tests must pass before moving on.
