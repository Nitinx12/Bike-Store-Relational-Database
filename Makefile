# Bike Store — one entry for every common workflow.
# Unix/macOS/CI:  make <target>     Windows:  tasks.bat <target>
.PHONY: help setup pipeline pipeline-full dq gx contracts dashboard test test-unit test-smoke lint sql-lint lock clean

help: ## list targets
	@echo "  setup           install dependencies"
	@echo "  pipeline        full pass: preflight, load, SQL checks, GX"
	@echo "  pipeline-full   truncate and reload every collection, then validate"
	@echo "  dq              SQL data-quality suite in FK order"
	@echo "  gx              Great Expectations suite (9 tables)"
	@echo "  contracts       refresh contracts/*.yml from Mongo schemas"
	@echo "  dashboard       local Streamlit dashboard"
	@echo "  test            unit + smoke suites"
	@echo "  test-unit       fast unit suite, no database needed"
	@echo "  test-smoke      live smoke suite (needs Postgres + MongoDB)"
	@echo "  lint            ruff, format check and mypy"
	@echo "  sql-lint        sqlfluff on every sql/ file"
	@echo "  lock            re-resolve dependencies"
	@echo "  clean           drop caches and bytecode"

setup: ## install dependencies
	uv sync

pipeline: ## full pass: preflight, load, SQL checks, GX
	uv run python main.py

pipeline-full: ## truncate and reload every collection, then validate
	uv run python main.py --full

dq: ## SQL data-quality suite in FK order
	uv run python src/jobs/run_dq.py

gx: ## Great Expectations suite (9 tables)
	uv run python scripts/run_gx.py

contracts: ## refresh contracts/*.yml from Mongo schemas
	uv run python scripts/update_contract.py

dashboard: ## local Streamlit dashboard
	uv run streamlit run dashboard/home.py

test: ## unit + smoke suites
	uv run pytest -q

test-unit: ## fast unit suite, no database needed
	uv run pytest tests/unit -q

test-smoke: ## live smoke suite (needs Postgres + MongoDB)
	uv run pytest tests/smoke -q

lint: ## ruff, format check and mypy
	uv run ruff check . && uv run ruff format --check . && uv run mypy .

sql-lint: ## sqlfluff on every sql/ file
	uv run sqlfluff lint sql/ --dialect postgres

lock: ## re-resolve dependencies
	uv lock && uv sync

clean: ## drop caches and bytecode
	rm -rf .pytest_cache __pycache__ dashboard/__pycache__ src/__pycache__ scripts/__pycache__ tests/__pycache__
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
