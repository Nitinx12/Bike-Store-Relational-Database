# AI Agent Instructions for Bike-Store-Relational-Database

This document provides strict instructions, coding standards, and architectural context for any AI/LLM assisting with this project. 

## 1. Project Overview & Structure
This is an ETL (Extract, Transform, Load) data pipeline project that extracts data (likely from MongoDB, based on `mongo_to_postgres.py`), transforms it using PySpark, validates it via Great Expectations (`gx/`), and loads it into a PostgreSQL relational database. It includes observability via Docker/Grafana and extensive SQL-based analytics.

### Directory Map Context
*   **`src/`**: Core Python ETL pipeline logic (`pipeline/`), database connections (`database/`), and validation triggers (`validation/`).
*   **`scripts/`**: Operational Bash and Python scripts (e.g., `monitor_logs.sh`, `run_gx.py`).
*   **`sql/`**: Analytical queries, schema explorations, and PL/pgSQL functions.
*   **`tests/`**: Data quality tests using Python (`data_quality/`) and SQL/PLpgSQL (`generic/loops/`).
*   **`gx/`**: Great Expectations configurations, suites, and uncommitted data docs.
*   **`docker/`**: Grafana and Prometheus observability stack.
*   **`ps1/`**: PowerShell automation (e.g., `local_runner.ps1`).
*   **`utils/`**: Shared Python utilities (logging, metrics, engines).
*   **`docs/` & `reports/`**: Documentation and generated Markdown reports.

## 2. General AI Behavior & Guidelines
*   **Think Step-by-Step**: Plan your logic before generating code.
*   **Short & Concise Comments**: Write meaningful, brief comments. Explain the *why*, not the *what*. Do not over-comment obvious code.
*   **No Placeholders**: Do not use `// ... existing code ...` unless explicitly asked to truncate. Provide fully working blocks.
*   **Modularity**: Keep functions small and single-purpose.

## 3. Language-Specific Coding Styles

### Python (`.py`)
*   **Standard**: Follow PEP 8 strict guidelines.
*   **Type Hinting**: Always use strict type hints (e.g., `def transform_data(df: DataFrame) -> DataFrame:`).
*   **Docstrings**: Use short Google-style docstrings for classes and complex functions.
*   **Imports**: Organize imports cleanly. Standard library first, third-party (PySpark, Great Expectations) second, local (`src.*`, `utils.*`) third.
*   **Error Handling**: Use specific exceptions. Leverage the custom logger in `utils/logger.py`.

### Bash (`.sh` in `scripts/`)
*   **Safety First**: Every Bash script must start with `set -euo pipefail`.
*   **Variables**: Quote all variables (e.g., `"${FILE_PATH}"`). Prefer lowercase for local variables and UPPERCASE for environment variables.
*   **Modularity**: Use functions for repetitive logic.
*   **Logging**: Echo informative output with timestamps if the script runs continuously (like `monitor_logs.sh`).

### PowerShell (`.ps1` in `ps1/`)
*   **Safety**: Enforce `Set-StrictMode -Version Latest` and `$ErrorActionPreference = "Stop"`.
*   **Naming**: Use standard `Verb-Noun` conventions for custom functions (e.g., `Invoke-Pipeline`).
*   **Parameters**: Use `[CmdletBinding()]` and strong typing for script parameters `Param([string]$Environment)`.
*   **Paths**: Use `Join-Path` instead of string concatenation for file paths to maintain cross-platform compatibility.

### Makefile
*   **Indentation**: MUST use actual tabs, not spaces.
*   **Phony Targets**: Always declare `.PHONY: target_name` for non-file targets.
*   **Self-Documenting**: Add a `help` target that uses `grep` or `awk` to parse comments and describe what each command does.
*   **Environment**: Load the `.env` file automatically at the top of the Makefile if environment variables are required.

## 4. Package Management & Dependencies (`uv`)
This project strictly uses [uv](https://github.com/astral-sh/uv) by Astral for Python dependency management. 
*   **No pip/conda**: Do not suggest `pip install` or `conda install`.
*   **Running Scripts**: Always prefix Python executions with `uv run` (e.g., `uv run main.py` or `uv run scripts/run_gx.py`).
*   **Adding Dependencies**: 
    *   Standard: `uv add <package>`
    *   **Dev Dependencies**: `uv add --dev <package>` (Use this for linters, formatters, or testing frameworks like `pytest`).
*   **Syncing**: Suggest `uv sync` to install dependencies from `uv.lock` and `pyproject.toml`.

## 5. GitHub Actions & CI/CD workflow
*   **Workflows**: The `.github/workflows` folder contains CI rules (`codeql.yml`, `linting.yml`). Ensure any new code complies with strict linting standards before suggesting a commit.
*   **Pull Requests**: Code changes must not break existing Great Expectations suites (`gx/`) or PySpark DataFrame schemas.
*   **Linting Compliance**: Assume the pipeline enforces `ruff` or `flake8` and `mypy` via `linting.yml`. Code provided must pass these silently.

## 6. ETL Specific Rules
*   **PySpark (`src/pipeline/`)**: Avoid UDFs where standard Spark SQL functions (`pyspark.sql.functions`) can be used. Rely on `src/pipeline/spark_session.py` for context generation.
*   **SQL (`sql/` & `tests/generic/loops/`)**: Use standard PostgreSQL syntax. Avoid reserved keywords as column names. Use explicit `JOIN` syntax rather than implicit `WHERE` clauses.
*   **Great Expectations (`gx/`)**: When updating validations, interact strictly through the `src/validation/` wrappers or `scripts/run_gx.py`.

## 7. Version Control & Git Workflow
When suggesting Git commands or generating commits, strictly adhere to the following rules:

*   **Staging**: Prefer specific file staging (`git add <file>`) over blind blanket additions (`git add .`) to maintain atomic commits.
*   **Conventional Commits**: Commit messages MUST follow the Conventional Commits format to standardize project history:
    *   `feat:` for new pipeline features, scripts, or analytical queries (e.g., `feat: add cohort analysis SQL script`).
    *   `fix:` for bug fixes in ETL logic or configs (e.g., `fix: resolve PySpark memory leak in transform step`).
    *   `docs:` for updating markdown reports or data catalogs (e.g., `docs: update run book for incremental loading`).
    *   `chore:` for routine tasks, dependency updates, or Docker changes (e.g., `chore: add pytest to uv dev dependencies`).
    *   `refactor:` for code restructuring that doesn't alter behavior (e.g., `refactor: modularize mongo_source.py extraction logic`).
    *   `test:` for adding or fixing data quality tests (e.g., `test: add PL/pgSQL loops test for products`).
*   **Commit Style**: Use the imperative mood in the subject line (e.g., "add", not "added" or "adds"). Keep the subject line concise (under 50 characters).