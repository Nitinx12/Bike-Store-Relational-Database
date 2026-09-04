# ============================================================================
# Bike Store Pipeline — Production Makefile
# ----------------------------------------------------------------------------
# Usage:
#   make help          - Show available commands and descriptions
#   make build         - Build the main batch job Docker image
#   make up            - Spin up the full stack (Postgres, MongoDB, monitoring)
#   make pipeline      - Run the full end-to-end pipeline (ETL + PL/pgSQL + GX)
# ============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Colors for terminal output
CYAN  := \033[36m
RESET := \033[0m
BOLD  := \033[1m

.PHONY: help build up down pipeline etl dq-loops dq-gx seed inspect-schema monitor-logs log-cleanup shell clean prune check-env health-check init-db backup-postgres restore-postgres backup-mongo restore-mongo

help: ## Show this help message
	@echo -e "$(BOLD)Bike Store Pipeline Management$(RESET)"
	@echo -e "Usage: $(CYAN)make <target> [ARGS=\"...\"]$(RESET)"
	@echo ""
	@echo -e "$(BOLD)Targets:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-22s$(RESET) %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------
# Environment bootstrap
# ----------------------------------------------------------------------------

check-env: ## Verify .env exists; copy from .env.example if missing
	@if [[ ! -f .env ]]; then \
		echo -e "$(CYAN)No .env file found — copying from .env.example$(RESET)"; \
		cp .env.example .env; \
		echo -e "$(CYAN)Edit .env with your DB credentials before running jobs$(RESET)"; \
	fi

# ----------------------------------------------------------------------------
# Infrastructure & Docker Lifecycle
# ----------------------------------------------------------------------------

build: check-env ## Build the main batch application Docker image
	@echo -e "$(CYAN)Building Docker image via Compose...$(RESET)"
	docker compose build app

up: check-env ## Start the full stack (Postgres, MongoDB, Pushgateway, Prometheus, Grafana)
	@echo -e "$(CYAN)Starting full stack...$(RESET)"
	docker compose up -d postgres mongodb pushgateway prometheus grafana
	@echo -e ""
	@echo -e "$(BOLD)Endpoints:$(RESET)"
	@echo -e "  Grafana:     http://localhost:3000  (admin / \$$GRAFANA_ADMIN_PASSWORD)"
	@echo -e "  Prometheus:  http://localhost:9090"
	@echo -e "  Pushgateway: http://localhost:9091"

down: ## Stop the stack (keeps volumes)
	@echo -e "$(CYAN)Stopping stack...$(RESET)"
	docker compose down

# ----------------------------------------------------------------------------
# Job Orchestration Targets
# ----------------------------------------------------------------------------

pipeline: ## Run the full unified pipeline (ETL -> PL/pgSQL -> GX)
	@echo -e "$(CYAN)Running full pipeline orchestration...$(RESET)"
	docker compose --profile jobs run --rm app pipeline $(ARGS)

etl: ## Run MongoDB -> PostgreSQL ETL (ARGS="--full-refresh" or "--collection orders")
	@echo -e "$(CYAN)Running ETL stage...$(RESET)"
	docker compose --profile jobs run --rm app etl $(ARGS)

dq-loops: ## Run the PL/pgSQL data quality loop tests
	@echo -e "$(CYAN)Running PL/pgSQL data quality tests...$(RESET)"
	docker compose --profile jobs run --rm app dq-loops $(ARGS)

dq-gx: ## Run Great Expectations suite (ARGS="orders products" to target tables)
	@echo -e "$(CYAN)Running Great Expectations suite...$(RESET)"
	docker compose --profile jobs run --rm app dq-gx $(ARGS)

seed: ## Seed MongoDB with sample bike-store data (drops & reinserts each collection)
	@echo -e "$(CYAN)Seeding MongoDB with sample data...$(RESET)"
	docker compose --profile jobs run --rm app seed

inspect-schema: ## Inspect PostgreSQL public schema layout
	@echo -e "$(CYAN)Inspecting database schema...$(RESET)"
	docker compose --profile jobs run --rm app inspect-schema $(ARGS)

monitor-logs: ## Manage pipeline logs (ARGS="summary" or "clean --dry-run")
	@echo -e "$(CYAN)Running log manager...$(RESET)"
	docker compose --profile jobs run --rm app monitor-logs $(ARGS)

log-cleanup: ## Run local log cleanup (ARGS="clean --dry-run")
	@echo -e "$(CYAN)Running local log cleanup...$(RESET)"
	./scripts/log_cleanup.sh $(ARGS)

shell: ## Open an interactive bash shell inside the app container for debugging
	@echo -e "$(CYAN)Dropping into container shell...$(RESET)"
	docker compose --profile jobs run --rm app shell

# ----------------------------------------------------------------------------
# Database Lifecycle (first run, backup, restore)
# ----------------------------------------------------------------------------

init-db: up ## First-run DB initializer: create bike_store database and verify connectivity
	@echo -e "$(CYAN)Initializing databases for first run...$(RESET)"
	./scripts/init_db.sh

health-check: up ## One-shot liveness probe for Postgres, Mongo, Prometheus, Pushgateway
	@echo -e "$(CYAN)Running health check...$(RESET)"
	./scripts/health_check.sh

backup-postgres: ## Dump the bike_store database to backups/postgres/ (ARGS="<dir> --schema-only")
	@echo -e "$(CYAN)Backing up Postgres...$(RESET)"
	./scripts/backup_postgres.sh $(ARGS)

restore-postgres: ## DESTRUCTIVE: drop + restore from a backup file (ARGS="<file.sql.gz>")
	@echo -e "$(CYAN)Restoring Postgres from backup...$(RESET)"
	./scripts/restore_postgres.sh $(ARGS)

backup-mongo: ## Dump the Mongo database to backups/mongo/ (ARGS="<dir>")
	@echo -e "$(CYAN)Backing up MongoDB...$(RESET)"
	./scripts/backup_mongo.sh $(ARGS)

restore-mongo: ## DESTRUCTIVE: drop + restore from a mongodump directory (ARGS="<dir>")
	@echo -e "$(CYAN)Restoring MongoDB from backup...$(RESET)"
	./scripts/restore_mongo.sh $(ARGS)

# ----------------------------------------------------------------------------
# Maintenance & Cleanup
# ----------------------------------------------------------------------------

clean: ## Stop and remove all containers, networks, and ephemeral volumes
	@echo -e "$(CYAN)Cleaning up containers and volumes...$(RESET)"
	docker compose down -v

prune: clean ## Deep clean: remove unused docker images, build cache, and volumes
	@echo -e "$(CYAN)Pruning unused Docker assets...$(RESET)"
	docker system prune -af --volumes
