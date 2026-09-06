# ============================================================================
# Bike Store Pipeline — Production Makefile
# ----------------------------------------------------------------------------
# Usage:
#   make help          - Show available commands and descriptions
#   make build         - Build the main batch job Docker image
#   make up            - Spin up the full stack (Postgres, MongoDB, monitoring)
#   make pipeline      - Run the full end-to-end pipeline (Docker)
#   make local-pipeline - Run the full end-to-end pipeline (Local)
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Colors
CYAN  := \033[36m
RESET := \033[0m
BOLD  := \033[1m

.PHONY: help build up down pipeline local-pipeline etl local-etl dq-loops local-dq-loops dq-gx local-dq-gx seed local-seed inspect-schema local-inspect-schema monitor-logs log-cleanup shell clean prune check-env health-check init-db backup-postgres restore-postgres backup-mongo restore-mongo lint test format

help: ## Show this help message
	@echo -e "$(BOLD)Bike Store Pipeline Management$(RESET)"
	@echo -e "Usage: $(CYAN)make <target> [ARGS=\"...\"]$(RESET)"
	@echo ""
	@echo -e "$(BOLD)General Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -v 'local-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo -e "$(BOLD)Local-Only Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep 'local-' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-22s$(RESET) %s\n", $$1, $$2}'

check-env: ## Verify .env exists
	@if [[ ! -f .env ]]; then \
		echo -e "$(CYAN)No .env file found — copying from .env.example$(RESET)"; \
		cp .env.example .env; \
	fi

# ----------------------------------------------------------------------------
# Infrastructure
# ----------------------------------------------------------------------------

build: check-env ## Build Docker image
	docker compose build app

up: check-env ## Start full stack
	docker compose up -d postgres mongodb pushgateway prometheus grafana

down: ## Stop stack
	docker compose down

# ----------------------------------------------------------------------------
# Job Orchestration (Docker vs Local)
# ----------------------------------------------------------------------------

pipeline: ## Full pipeline (Docker)
	docker compose --profile jobs run --rm app pipeline $(ARGS)

local-pipeline: ## Full pipeline (Local)
	pwsh scripts/ps1/local_runner.ps1 $(ARGS)

etl: ## MongoDB -> PostgreSQL ETL (Docker)
	docker compose --profile jobs run --rm app etl $(ARGS)

local-etl: ## MongoDB -> PostgreSQL ETL (Local)
	uv run python scripts/python/mongo_to_postgres.py $(ARGS)

dq-loops: ## PL/pgSQL DQ tests (Docker)
	docker compose --profile jobs run --rm app dq-loops $(ARGS)

local-dq-loops: ## PL/pgSQL DQ tests (Local)
	uv run python scripts/python/plpgsql_loops_tests.py $(ARGS)

dq-gx: ## GX suite (Docker)
	docker compose --profile jobs run --rm app dq-gx $(ARGS)

local-dq-gx: ## GX suite (Local)
	uv run python scripts/python/run_gx.py $(ARGS)

seed: ## Seed MongoDB (Docker)
	docker compose --profile jobs run --rm app seed

local-seed: ## Seed MongoDB (Local)
	uv run python scripts/python/seed_mongo.py $(ARGS)

inspect-schema: ## Inspect schema (Docker)
	docker compose --profile jobs run --rm app inspect-schema $(ARGS)

local-inspect-schema: ## Inspect schema (Local)
	uv run python scripts/python/inspect_schema.py $(ARGS)

# ----------------------------------------------------------------------------
# Quality Assurance (Production Grade)
# ----------------------------------------------------------------------------

lint: ## Run all linters (Ruff, Mypy, SQLFluff)
	@echo -e "$(CYAN)Running Ruff...$(RESET)"
	uv run ruff check .
	@echo -e "$(CYAN)Running Mypy...$(RESET)"
	uv run mypy .
	@echo -e "$(CYAN)Running SQLFluff...$(RESET)"
	uv run sqlfluff lint sql/

test: ## Run Python tests
	uv run pytest

format: ## Format code with Ruff
	uv run ruff format .

# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------

monitor-logs: ## Manage logs (Docker)
	docker compose --profile jobs run --rm app monitor-logs $(ARGS)

log-cleanup: ## Local log cleanup
	bash scripts/shell/log_cleanup.sh $(ARGS)

shell: ## Container shell
	docker compose --profile jobs run --rm app shell

init-db: up ## Initialize DB
	bash scripts/shell/init_db.sh

health-check: up ## Infrastructure liveness probe
	bash scripts/shell/health_check.sh

backup-postgres: ## Backup Postgres
	bash scripts/shell/backup_postgres.sh $(ARGS)

restore-postgres: ## Restore Postgres
	bash scripts/shell/restore_postgres.sh $(ARGS)

backup-mongo: ## Backup MongoDB
	bash scripts/shell/backup_mongo.sh $(ARGS)

restore-mongo: ## Restore MongoDB
	bash scripts/shell/restore_mongo.sh $(ARGS)

clean: ## Clean containers/volumes
	docker compose down -v

prune: clean ## Deep prune Docker
	docker system prune -af --volumes
