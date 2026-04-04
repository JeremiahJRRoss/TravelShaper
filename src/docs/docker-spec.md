# Docker Specification — TravelShaper Travel Assistant

**Version:** 2.1 (v0.3.2)

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.2

# Copy dependency files first (layer caching)
COPY pyproject.toml ./

# Install Python dependencies (no virtualenv inside container)
# Poetry auto-generates a lockfile if one is not present
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Install packages that cannot go through Poetry due to version constraints:
# - arize-phoenix-otel: narrow Python version bounds conflict with Poetry resolver
# - openinference-instrumentation-langchain: same constraint family
# - openinference-semantic-conventions: OpenInference attribute keys for Phoenix UI
# - opentelemetry-sdk: core OTel SDK used by otel_routing.py TracerProvider
# - opentelemetry-exporter-otlp-proto-http: OTLP/HTTP exporter for Phoenix and generic OTLP
# - opentelemetry-exporter-otlp-proto-grpc: OTLP/gRPC exporter for generic OTLP (OTLP_PROTOCOL=grpc)
# - openai: direct SDK needed for place + preference validation classifiers
# - arize-otel: provides arize.otel.register() for Arize Cloud integration
RUN pip install --no-cache-dir \
    arize-phoenix-otel \
    openinference-instrumentation-langchain \
    openinference-semantic-conventions \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-http \
    opentelemetry-exporter-otlp-proto-grpc \
    openai \
    arize-otel

# Copy application code
COPY . .

# Ensure static directory exists (serves the browser chat UI)
RUN mkdir -p /app/static

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build and run

```bash
# Force clean rebuild (recommended after code changes)
docker compose down
docker compose build --no-cache
docker compose up -d
```

> **Important:** Always use `--no-cache` after modifying Python files. Docker caches
> the `COPY . .` layer aggressively and will serve stale code if the cache key does
> not change. `--no-cache` guarantees the container matches what is on disk.

---

## docker-compose.yml

```yaml
services:
  travelshaper:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - OTEL_DESTINATION=${OTEL_DESTINATION:-phoenix}
      - PHOENIX_ENDPOINT=http://phoenix:6006/v1/traces
      - ARIZE_API_KEY=${ARIZE_API_KEY:-}
      - ARIZE_SPACE_ID=${ARIZE_SPACE_ID:-}
      - OTLP_ENDPOINT=${OTLP_ENDPOINT:-}
      - OTLP_HEADERS=${OTLP_HEADERS:-}
      - OTLP_PROTOCOL=${OTLP_PROTOCOL:-http}
    depends_on:
      phoenix:
        condition: service_started
    restart: unless-stopped

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    restart: unless-stopped
    profiles:
      - phoenix
```

### Run with Docker Compose

The Makefile reads `OTEL_DESTINATION` from `.env` and starts Phoenix only when
needed:

```bash
make up        # reads .env, starts Phoenix if OTEL_DESTINATION=phoenix, both, or all
make down      # stops the stack
```

Or manually:

```bash
# With Phoenix (default):
docker compose --profile phoenix up -d --build

# Without Phoenix (e.g. Arize-only or none):
docker compose up -d --build
```

| Service | URL | When |
|---------|-----|------|
| TravelShaper API + browser UI | http://localhost:8000 | Always |
| Phoenix tracing UI | http://localhost:6006 | When profile `phoenix` is active |

---

## .dockerignore

```
.env
.git
.gitignore
__pycache__
*.pyc
.pytest_cache
.venv
docs/
tests/
scripts/
*.md
!README.md
spans_export.csv
run_traces.sh
```

---

## Notes

**Why `poetry.lock` is not copied:**
The Dockerfile copies only `pyproject.toml`. Poetry auto-generates the lockfile during
`poetry install` inside the container. This avoids the `poetry.lock not found` build error
that occurs when the lockfile has not been committed to the repo.

**Why Phoenix packages are installed via pip, not Poetry:**
`arize-phoenix-otel` declares narrow Python version constraints that conflict with Poetry's
resolver on Python 3.11/3.12. Installing them directly via pip bypasses the resolver.

**Why `arize-phoenix` (the full server) is NOT installed in this container:**
The full Phoenix server package would conflict with TravelShaper's FastAPI version.
Phoenix runs in its own container (`arizephoenix/phoenix:latest`) and TravelShaper
only needs the lightweight sender packages (`arize-phoenix-otel`,
`openinference-instrumentation-langchain`).

**Why `opentelemetry-sdk` and `opentelemetry-exporter-otlp-proto-http` are installed:**
The `otel_routing.py` module builds a `TracerProvider` with `BatchSpanProcessor` and
`OTLPSpanExporter` directly from the OpenTelemetry SDK. These packages are required
for the Phoenix and generic OTLP destinations in the configurable OTel routing, which
supports sending traces to Phoenix, Arize Cloud, any OTLP-compatible backend,
combinations of all three, or none — controlled by the `OTEL_DESTINATION`
environment variable.

**Why `opentelemetry-exporter-otlp-proto-grpc` is installed:**
The generic OTLP destination supports both HTTP and gRPC transport, controlled by the
`OTLP_PROTOCOL` environment variable (`http` default, `grpc` optional). The gRPC
exporter package provides `OTLPGrpcSpanExporter` used when `OTLP_PROTOCOL=grpc`. If
the package is missing, `otel_routing.py` falls back to the HTTP exporter with a
warning — the application never crashes due to a missing gRPC package.

**Why `arize-otel` is installed:**
The `arize-otel` package provides `arize.otel.register()`, which is the official SDK
for connecting to Arize Cloud. It handles the Arize endpoint, authentication, and
project naming internally. Used by `otel_routing.py` when `OTEL_DESTINATION` is set
to `arize`, `both`, or `all`.

**Why `openai` is installed via pip:**
The `openai` SDK is used by the place validation and preference validation classifiers
in `api.py`. It is not declared in `pyproject.toml` to keep the Poetry dependency graph
clean — it is installed directly here alongside the other pip packages.

**Why Phoenix uses a Docker Compose profile:**
Phoenix is optional as of v0.3.0. When `OTEL_DESTINATION` is set to `arize`, `otlp`, or `none`,
there is no reason to run the Phoenix container. The `profiles: [phoenix]` key means
Phoenix only starts when explicitly requested via `--profile phoenix` or when the
Makefile detects that Phoenix is needed from the `.env` configuration.

**The `temperature` model_kwargs pattern:**
`gpt-5.3-chat-latest` does not accept any explicit `temperature` value. LangChain's
`ChatOpenAI` has its own Pydantic field for `temperature` that rejects `None` on older
versions. The workaround is `model_kwargs={"temperature": 1}` which routes the parameter
directly to the API payload, bypassing Pydantic validation.
