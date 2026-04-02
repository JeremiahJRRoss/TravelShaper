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
# Poetry will auto-generate a lockfile if one is not present
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Install Phoenix tracing packages and OpenAI SDK directly with pip.
# Phoenix packages excluded from pyproject.toml due to arize-phoenix-otel
# version constraint conflicts with Poetry's resolver on Python 3.11/3.12.
# OpenAI SDK installed here to ensure the validation classifier is available.
RUN pip install --no-cache-dir \
    arize-phoenix-otel \
    openinference-instrumentation-langchain \
    openinference-semantic-conventions \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-http \
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
