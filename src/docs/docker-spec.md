# Docker Specification — TravelShaper Travel Assistant

**Version:** 2.0 (v0.1.4)

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
# - openai: direct SDK needed for place + preference validation classifiers
RUN pip install --no-cache-dir \
    arize-phoenix-otel \
    openinference-instrumentation-langchain \
    openai

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
docker-compose down
docker-compose build --no-cache
docker-compose up -d
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
      - PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006/v1/traces
    depends_on:
      phoenix:
        condition: service_started
    restart: unless-stopped

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    restart: unless-stopped
```

### Run with Docker Compose

```bash
docker-compose up --build -d
```

This starts:
- TravelShaper API + browser UI at `http://localhost:8000`
- Phoenix tracing UI at `http://localhost:6006`

---

## .dockerignore

```
.env
.git
.gitignore
__pycache__
*.pyc
.pytest_cache
docs/
*.md
!README.md
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

**Why `openai` is installed via pip:**
The `openai` SDK is used by the place validation and preference validation classifiers
in `api.py`. It is not declared in `pyproject.toml` to keep the Poetry dependency graph
clean — it is installed directly here alongside the other pip packages.

**The `temperature` model_kwargs pattern:**
`gpt-5.3-chat-latest` does not accept any explicit `temperature` value. LangChain's
`ChatOpenAI` has its own Pydantic field for `temperature` that rejects `None` on older
versions. The workaround is `model_kwargs={"temperature": 1}` which routes the parameter
directly to the API payload, bypassing Pydantic validation.
