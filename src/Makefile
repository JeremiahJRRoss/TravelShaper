.PHONY: help up down test traces evals export demo clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start Docker stack — reads OTEL_DESTINATION from .env to control telemetry
	@DEST=$$(grep -E '^OTEL_DESTINATION=' .env 2>/dev/null | cut -d= -f2 | tr -d ' '); \
	if [ "$$DEST" = "phoenix" ] || [ "$$DEST" = "both" ] || [ -z "$$DEST" ]; then \
		echo "Starting with Phoenix profile..."; \
		docker compose --profile phoenix up -d --build; \
	else \
		echo "Starting without Phoenix (OTEL_DESTINATION=$$DEST)..."; \
		docker compose up -d --build; \
	fi
	@echo "Waiting for health check..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		curl -sf http://localhost:8000/health > /dev/null 2>&1 && break || sleep 2; \
	done
	@echo "TravelShaper: http://localhost:8000"

down: ## Stop Docker stack
	docker compose down

test: ## Run all unit tests (no API keys needed)
	pytest tests/ -v

traces: ## Generate 11 trace queries against running server
	python -m traces.run_traces

evals: ## Run 3 LLM-as-judge evaluations on Phoenix traces
	python -m evaluations.run_evals

export: ## Export Phoenix spans to CSV
	python -m evaluations.export_spans

demo: up test traces evals export ## Full demo: build, test, traces, evaluate, export
	@echo ""
	@echo "Demo complete."
	@echo "  App:     http://localhost:8000"
	@echo "  Phoenix: http://localhost:6006"
	@echo "  Spans exported to spans_export_*.csv"

clean: ## Remove generated JSON/CSV files
	rm -f trace-results_*.json eval-results_*.json spans_export*.csv
