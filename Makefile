# ============================================================================
# Bike Store Pipeline — Production Makefile
# ----------------------------------------------------------------------------
# Conventions:
#   - Indentation uses real TAB characters (not spaces).
#   - All non-file targets are declared with .PHONY.
#   - Environment is loaded from .env at the top of the file.
#   - Verbose targets (make run-verbose, make local-pipeline) echo commands.
#
# Entry points:
#   uv run main.py      — all three stages in one Python process (recommended).
#   pwsh local_runner   — three separate uv-run processes, richer terminal UI.
#
# See 'make help' for the full target list.
# ============================================================================

# NOTE: Make's `include` only handles plain unquoted `KEY=value` lines —
# quoted values keep their literal quotes and inline `#` comments truncate
# the value. Keep .env to plain `KEY=value` lines (see .env.example).
# Requires WSL/Git-Bash on Windows; native cmd.exe is not supported.
ifneq (,$(wildcard .env))
    -include .env
    export
endif

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Colors
CYAN  := \033[36m
RESET := \033[0m
BOLD  := \033[1m

.PHONY: help build up down pipeline local-pipeline etl local-etl dq-loops local-dq-loops dq-gx local-dq-gx seed local-seed inspect-schema local-inspect-schema monitor-logs log-cleanup shell clean prune check-env health-check init-db backup-postgres restore-postgres backup-mongo restore-mongo lint test format run run-verbose run-full run-etl run-dq run-gx run-collection run-collection-full run-etl-only run-etl-dq run-gx-table install verify run-clean check-deps doctor

help: ## Show this help message
	@echo -e "$(BOLD)Bike Store Pipeline Management$(RESET)"
	@echo Usage: make "<target>" [ARGS=...]
	@echo ""
	@echo -e "$(BOLD)Quick Start (production-grade):$(RESET)"
	@echo "  run                      Run the full pipeline in-process (recommended)"
	@echo "  install                  Sync dependencies from pyproject.toml"
	@echo "  doctor                   Full system + dependency + import health check"
	-@bash -c 'grep -h -E "^[a-zA-Z0-9_.-]+:.*?## " $(MAKEFILE_LIST) 2>/dev/null | grep -E "^(run|install|verify|doctor|check-env|check-deps):" | awk -F ":.*?## " "{printf \"  $(CYAN)%-22s$(RESET) %s\n\", $$1, $$2}" | sort' 2>nul || true
	@echo ""
	@echo -e "$(BOLD)Stage-level targets:$(RESET)"
	@echo "  run-etl                  Run only the ETL stage (MongoDB -> Postgres)"
	-@bash -c 'grep -h -E "^[a-zA-Z0-9_.-]+:.*?## " $(MAKEFILE_LIST) 2>/dev/null | grep -E "^(run-etl|run-dq|run-gx|run-etl-only|run-etl-dq|etl|local-etl|dq-loops|local-dq-loops|dq-gx|local-dq-gx):" | awk -F ":.*?## " "{printf \"  $(CYAN)%-22s$(RESET) %s\n\", $$1, $$2}" | sort' 2>nul || true
	@echo ""
	@echo -e "$(BOLD)Collection targets:$(RESET)"
	@echo "  run-collection           make ARGS=\"--collection orders\""
	-@bash -c 'grep -h -E "^[a-zA-Z0-9_.-]+:.*?## " $(MAKEFILE_LIST) 2>/dev/null | grep -E "^(run-collection|run-collection-full|run-gx-table):" | awk -F ":.*?## " "{printf \"  $(CYAN)%-22s$(RESET) %s\n\", $$1, $$2}" | sort' 2>nul || true
	@echo "    example: make run-collection ARGS=\"--collection orders\""
	@echo "    example: make run-gx-table GX_TABLES=\"orders products\""
	@echo ""
	@echo -e "$(BOLD)Docker targets:$(RESET)"
	@echo "  up                       Start Postgres, MongoDB, and monitoring stack"
	-@bash -c 'grep -h -E "^[a-zA-Z0-9_.-]+:.*?## " $(MAKEFILE_LIST) 2>/dev/null | grep -E "^(up|down|build|pipeline|local-pipeline|clean|prune|shell):" | awk -F ":.*?## " "{printf \"  $(CYAN)%-22s$(RESET) %s\n\", $$1, $$2}" | sort' 2>nul || true
	@echo ""
	@echo -e "$(BOLD)DevOps / utilities:$(RESET)"
	@echo "  lint                     Run Ruff, Mypy, and SQLFluff"
	-@bash -c 'grep -h -E "^[a-zA-Z0-9_.-]+:.*?## " $(MAKEFILE_LIST) 2>/dev/null | grep -E "^(lint|test|format|health-check|init-db|seed|local-seed|inspect-schema|local-inspect-schema|monitor-logs|log-cleanup|backup-postgres|restore-postgres|backup-mongo|restore-mongo|run-clean):" | awk -F ":.*?## " "{printf \"  $(CYAN)%-22s$(RESET) %s\n\", $$1, $$2}" | sort' 2>nul || true
	@echo ""
	@echo -e "$(CYAN)Tip: help auto-parses ## comments via grep + awk on WSL/Git-Bash$(RESET)"

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

local-pipeline: check-env ## Full pipeline (Local)
	$(SHELL) -c 'if command -v pwsh >/dev/null 2>&1; then pwsh scripts/ps1/local_runner.ps1 $(ARGS); else echo "pwsh not found - use: make run"; exit 1; fi'

etl: ## MongoDB -> PostgreSQL ETL (Docker)
	docker compose --profile jobs run --rm app etl $(ARGS)

local-etl: check-env ## MongoDB -> PostgreSQL ETL (Local)
	uv run python scripts/python/mongo_to_postgres.py $(ARGS)

dq-loops: ## PL/pgSQL DQ tests (Docker)
	docker compose --profile jobs run --rm app dq-loops $(ARGS)

local-dq-loops: check-env ## PL/pgSQL DQ tests (Local)
	uv run python scripts/python/plpgsql_loops_tests.py $(ARGS)

dq-gx: ## GX suite (Docker)
	docker compose --profile jobs run --rm app dq-gx $(GX_TABLES)

local-dq-gx: check-env ## GX suite (Local)
	uv run python scripts/python/run_gx.py $(GX_TABLES)

seed: ## Seed MongoDB (Docker)
	docker compose --profile jobs run --rm app seed

local-seed: check-env ## Seed MongoDB (Local)
	uv run python scripts/python/seed_mongo.py $(ARGS)

inspect-schema: ## Inspect schema (Docker)
	docker compose --profile jobs run --rm app inspect-schema $(ARGS)

local-inspect-schema: check-env ## Inspect schema (Local)
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

prune: clean ## Deep prune Docker (requires CONFIRM=1)
	@if [ "$(CONFIRM)" != "1" ]; then echo "Refusing to prune without CONFIRM=1. Run: make prune CONFIRM=1"; exit 1; fi
	docker system prune -af --volumes

# ============================================================================
# Production-grade local run targets
# All targets invoke 'uv run' so dependencies are always resolved from
# pyproject.toml.  Never invoke the interpreter directly.
# ============================================================================

check-deps: ## Verify required tools (uv, python, docker, etc.) are available
	@echo Checking prerequisites...
	@uv_version=$$(uv --version 2>/dev/null) && echo "  uv OK ($$uv_version)" || (echo "  FATAL: uv not found." && exit 1)
	@python --version >/dev/null 2>&1 && echo "  python OK ($$(python --version 2>&1))" || (echo "  FATAL: python not found." && exit 1)
	@docker --version >/dev/null 2>&1 && echo "  docker OK ($$(docker --version 2>&1 | head -n1))" || echo "  WARN: docker not found (only needed for Docker targets)."
	@uv lock --check >/dev/null 2>&1 && echo "  uv lockfile OK" || (echo "  FATAL: uv lockfile out of sync. Run 'uv lock'." && exit 1)
	@echo All prerequisites met.

install: check-deps ## Install / sync dependencies and verify
	uv sync
	@echo Dependencies installed.

verify: check-deps ## Alias for 'check-deps' (runs dependency checks only)
	@echo Dependency verification complete.

doctor: check-deps ## Run dependency + import health check; exit non-zero if anything is misconfigured
	@echo === Doctor: uv lockfile ===
	@uv lock --check >/dev/null 2>&1 && echo "  Lockfile OK" || (echo "  ERROR: Lockfile out of sync. Run 'make install'." && exit 1)
	@echo === Doctor: Pipeline imports ===
	@uv run python -c "from src.pipeline.runner import run_pipeline; print('  Pipeline import OK')" || (echo "  ERROR: Cannot import pipeline modules." && exit 1)
	@uv run python -c "from src.validation.plpgsql_loops import run_all; print('  PL/pgSQL import OK')" || (echo "  ERROR: Cannot import plpgsql modules." && exit 1)
	@uv run python -c "from tests.data_quality import run; print('  GX import OK')" || (echo "  ERROR: Cannot import GX modules." && exit 1)
	@echo All doctor checks passed.

run-clean: ## Remove pipeline log files older than 7 days
	@bash scripts/shell/log_cleanup.sh $(ARGS)

# ----------------------------------------------------------------------------
# Primary run targets
# ----------------------------------------------------------------------------

run: check-env check-deps ## Run the full pipeline in-process (recommended for local dev)
	uv run python main.py

run-verbose: check-env check-deps ## Run the full pipeline with verbose Python output (PYTHONVERBOSE=1)
	PYTHONVERBOSE=1 uv run python main.py

run-full: check-env check-deps ## Run a full-refresh pipeline (truncates and reloads every collection)
	uv run python main.py --full-refresh

run-etl: check-env check-deps ## Run only the ETL stage (MongoDB -> Postgres)
	uv run python scripts/python/mongo_to_postgres.py $(ARGS)

run-dq: check-env check-deps ## Run only the PL/pgSQL data-quality suite
	uv run python scripts/python/plpgsql_loops_tests.py $(ARGS)

run-gx: check-env check-deps ## Run only the Great Expectations suite
	uv run python scripts/python/run_gx.py $(GX_TABLES)

# Per-collection incremental ETL runs (ARGS=--collection orders --collection products)
run-collection: check-env check-deps ## Run ETL for specific collection(s): make run-collection ARGS="--collection orders"
	uv run python scripts/python/mongo_to_postgres.py $(ARGS)

# Full-refresh for specific collection(s)
run-collection-full: check-env check-deps ## Run full-refresh ETL for specific collection(s): make run-collection-full ARGS="--collection orders --collection products"
	uv run python scripts/python/mongo_to_postgres.py --full-refresh $(ARGS)

# Run ETL then skip PL/pgSQL and Great Expectations (useful during development)
run-etl-only: check-env check-deps ## Run ETL and skip all validation suites
	uv run python main.py --skip-plpgsql --skip-gx

# Run ETL + PL/pgSQL only (skip Great Expectations)
run-etl-dq: check-env check-deps ## Run ETL and PL/pgSQL suite; skip Great Expectations
	uv run python main.py --skip-gx

# Run Great Expectations only against specific tables (alias for 'run-gx';
# both read GX_TABLES, e.g. make run-gx-table GX_TABLES="orders products")
run-gx-table: run-gx ## Alias for 'run-gx' (same recipe, GX_TABLES-filtered)
