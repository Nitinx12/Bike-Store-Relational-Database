# ============================================================================
# Bike Store Pipeline — Production Makefile
# ----------------------------------------------------------------------------
# Usage:
#   make help          - Show available commands and descriptions
#   make build         - Build the main batch job Docker image
#   make up            - Spin up the monitoring stack (Prometheus, Grafana, Pushgateway)
#   make pipeline      - Run the full end-to-end pipeline (ETL + PL/pgSQL + GX)
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Colors for terminal output
CYAN := \033[36m
RESET := \033[0m
BOLD := \033[1m

.PHONY: help build up down pipeline etl dq-loops dq-gx inspect-schema monitor-logs shell clean prune

help: ## Show this help message
	@echo -e "$(BOLD)Bike Store Pipeline Management$(RESET)"
	@echo -e "Usage: $(CYAN)make <target>$(RESET)"
	@echo ""
	@echo -e "$(BOLD)Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-18s$(RESET) %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------
# Infrastructure & Docker Lifecycle
# ----------------------------------------------------------------------------

build: ## Build the main batch application Docker image
	@echo -e "$(CYAN)Building Docker image via Compose...$(RESET)"
	docker compose build app

up: ## Start the observability stack (Pushgateway, Prometheus, Grafana)
	@echo -e "$(CYAN)Starting monitoring stack...$(RESET)"
	docker compose up -d pushgateway prometheus grafana
	@echo -e "Grafana:     http://localhost:3000"
	@echo -e "Prometheus:  http://localhost:9090"
	@echo -e "Pushgateway: http://localhost:9091"

down: ## Stop the observability stack
	@echo -e "$(CYAN)Stopping monitoring stack...$(RESET)"
	docker compose down

# ----------------------------------------------------------------------------
# Job Orchestration Targets
# ----------------------------------------------------------------------------

pipeline: ## Run the full unified pipeline (ETL -> PL/pgSQL -> GX)
	@echo -e "$(CYAN)Running full pipeline orchestration...$(RESET)"
	docker compose --profile jobs run --rm app pipeline $(ARGS)

etl: ## Run MongoDB -> PostgreSQL ETL load (pass ARGS="--full-refresh" or ARGS="--collection orders")
	@echo -e "$(CYAN)Running ETL stage...$(RESET)"
	docker compose --profile jobs run --rm app etl $(ARGS)

dq-loops: ## Run the PL/pgSQL data quality loop tests
	@echo -e "$(CYAN)Running PL/pgSQL data quality tests...$(RESET)"
	docker compose --profile jobs run --rm app dq-loops $(ARGS)

dq-gx: ## Run Great Expectations suite (pass ARGS="orders products" to target tables)
	@echo -e "$(CYAN)Running Great Expectations suite...$(RESET)"
	docker compose --profile jobs run --rm app dq-gx $(ARGS)

inspect-schema: ## Inspect PostgreSQL public schema layout
	@echo -e "$(CYAN)Inspecting database schema...$(RESET)"
	docker compose --profile jobs run --rm app inspect-schema $(ARGS)

monitor-logs: ## Manage or view pipeline logs (pass ARGS="summary" or ARGS="clean --dry-run")
	@echo -e "$(CYAN)Running log manager...$(RESET)"
	docker compose --profile jobs run --rm app monitor-logs $(ARGS)

shell: ## Open an interactive bash shell inside the container for debugging
	@echo -e "$(CYAN)Dropping into container shell...$(RESET)"
	docker compose --profile jobs run --rm app shell

# ----------------------------------------------------------------------------
# Maintenance & Cleanup
# ----------------------------------------------------------------------------

clean: ## Stop and remove all containers, networks, and ephemeral volumes
	@echo -e "$(CYAN)Cleaning up containers and volumes...$(RESET)"
	docker compose down -v

prune: clean ## Deep clean: remove unused docker images, build cache, and volumes
	@echo -e "$(CYAN)Pruning unused Docker assets...$(RESET)"
	docker system prune -af --volumes