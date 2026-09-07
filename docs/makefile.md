# Makefile Reference

The `Makefile` is the project's main entry point. Every target uses `uv run` so dependencies are always resolved from `pyproject.toml` and the managed virtual environment — the system Python interpreter is never invoked directly.

> Run `make help` on your machine to see the live, formatted output.

---

## Table of Contents

- [Conventions](#conventions)
- [Quick Start](#quick-start)
- [Targets](#targets)
  - [Quick Start targets](#quick-start-targets)
  - [Per-stage targets](#per-stage-targets)
  - [Collection-level targets](#collection-level-targets)
  - [Docker and local-pipeline targets](#docker-and-local-pipeline-targets)
  - [Quality assurance](#quality-assurance)
  - [Utilities](#utilities)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## Conventions

- **Indentation** uses real TAB characters (Make requires this; spaces will fail).
- **All non-file targets** are declared with `.PHONY` to avoid name collisions with real files.
- **Environment variables** are auto-loaded from `.env` at the top of the Makefile (`include .env` + `export`).
- **Pre-flight checks** (`check-deps`, `doctor`) gate every run target — they fail fast if the environment is broken.
- **No interpreter is ever invoked directly.** Every `uv run` target goes through the managed venv.
- **Help is generated** by `make help` using plain `@echo` (no `grep`/`awk`), so it works on Windows `cmd.exe` and Linux bash alike.

---

## Quick Start

```bash
make doctor          # 1. verify environment + imports
make run             # 2. run the full pipeline (recommended)
```

That's it. `make run` runs all three stages — ETL, PL/pgSQL, and Great Expectations — in a single Python process and prints a Rich-formatted summary.

---

## Targets

### Quick Start targets

| Target | Description | Notes |
| :--- | :--- | :--- |
| `make run` | Run the full pipeline in-process | Calls `uv run python main.py`. Recommended default. |
| `make run-verbose` | Same as `run`, with full Python tracebacks | Sets `PYTHONVERBOSE=1` |
| `make run-full` | Full refresh — truncate and reload every collection | Adds `--full-refresh` |
| `make install` | `uv sync` and verify dependencies | Runs `check-deps` first |
| `make doctor` | Pre-flight check: lockfile + Python imports of all 3 modules | Use before any run target in CI |
| `make check-deps` | Quick `uv` and lockfile sanity check | Lighter-weight than `doctor` |
| `make verify` | Alias for `check-deps` | Same behaviour |

### Per-stage targets

When you only want one stage, use these:

| Target | What it does | Underlying script |
| :--- | :--- | :--- |
| `make run-etl` | MongoDB → Postgres incremental load | `scripts/python/mongo_to_postgres.py` |
| `make run-dq` | PL/pgSQL data-quality suite | `scripts/python/plpgsql_loops_tests.py` |
| `make run-gx` | Great Expectations suite | `scripts/python/run_gx.py` |
| `make run-etl-only` | ETL + skip all validation | `main.py --skip-plpgsql --skip-gx` |
| `make run-etl-dq` | ETL + PL/pgSQL, skip GX | `main.py --skip-gx` |

### Collection-level targets

Useful when developing or when only one collection has new data:

| Target | Example | What it does |
| :--- | :--- | :--- |
| `make run-collection` | `make run-collection ARGS="--collection orders"` | Incremental ETL for specific collection(s) |
| `make run-collection-full` | `make run-collection-full ARGS="--collection orders"` | Full refresh for specific collection(s) |
| `make run-gx-table` | `make run-gx-table GX_TABLES="orders products"` | Run Great Expectations against specific table(s) |

### Docker and local-pipeline targets

| Target | Description |
| :--- | :--- |
| `make build` | Build the Docker app image |
| `make up` | Start Postgres, MongoDB, Pushgateway, Prometheus, Grafana |
| `make down` | Stop the Docker stack |
| `make pipeline` | Full pipeline inside Docker (one container) |
| `make local-pipeline` | Full pipeline via PowerShell — runs each stage in its own `uv` process, writes per-stage logs to `logs/pipeline/`, supports `-SkipExtract`, `-SkipPlpgsql`, `-SkipGx`, `-ContinueOnError` |
| `make etl` | ETL inside Docker |
| `make local-etl` | ETL locally (alias for `make run-etl`) |
| `make dq-loops` | PL/pgSQL DQ inside Docker |
| `make local-dq-loops` | PL/pgSQL DQ locally (alias for `make run-dq`) |
| `make dq-gx` | Great Expectations inside Docker |
| `make local-dq-gx` | Great Expectations locally (alias for `make run-gx`) |
| `make shell` | Open a shell inside the app container |
| `make clean` | Remove containers and volumes |
| `make prune` | Deep prune Docker (system + volumes) |

### Quality assurance

| Target | Description |
| :--- | :--- |
| `make lint` | Run Ruff, Mypy, and SQLFluff |
| `make test` | Run pytest |
| `make format` | Format code with Ruff |

### Utilities

| Target | Description |
| :--- | :--- |
| `make run-clean` | Remove pipeline logs older than 7 days |
| `make backup-postgres` | Backup Postgres database |
| `make restore-postgres` | Restore Postgres from a backup |
| `make backup-mongo` | Backup MongoDB |
| `make restore-mongo` | Restore MongoDB |
| `make health-check` | Liveness probe for Postgres and MongoDB |
| `make seed` | Seed MongoDB with sample data (Docker) |
| `make local-seed` | Seed MongoDB locally |
| `make monitor-logs` | Manage Docker pipeline logs |
| `make log-cleanup` | Local log cleanup |
| `make inspect-schema` | Inspect Postgres schema (Docker) |
| `make local-inspect-schema` | Inspect Postgres schema (locally) |
| `make init-db` | Initialize the database after `make up` |

---

## Common Workflows

### 1. First-time setup

```bash
git clone <repo>
cd bike-store-relational-database
uv sync
cp .env.example .env       # edit with your Postgres + MongoDB credentials
make doctor                # verify environment
make run                   # full pipeline
```

### 2. Daily development loop

```bash
make check-deps            # 5-second sanity check
make run-etl               # load new data
make run-dq                # run PL/pgSQL tests
make run-gx                # run Great Expectations
```

### 3. Investigate a single collection

```bash
make run-collection ARGS="--collection orders"
make run-gx-table GX_TABLES="orders"
```

### 4. Full refresh (e.g. schema change)

```bash
make run-full
```

### 5. Debugging

```bash
make run-verbose           # full Python tracebacks
make doctor                # check imports + lockfile
make run-etl-only          # skip validation suites for faster iteration
```

### 6. Production deployment (Docker)

```bash
make up                    # start the stack
make pipeline              # full pipeline in container
make monitor-logs          # tail logs
make down                  # stop everything
```

### 7. CI gate

```bash
make doctor                # lockfile + import check
make lint                  # Ruff, Mypy, SQLFluff
make test                  # pytest
make run                   # end-to-end pipeline
```

---

## Troubleshooting

### `make: uv: command not found`

Install [uv](https://github.com/astral-sh/uv):

```bash
# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### `make doctor` reports a lockfile mismatch

The lockfile is out of sync with `pyproject.toml`. Run:

```bash
uv sync
```

### `ModuleNotFoundError: No module named 'utils'`

You are running a script directly (e.g. `python scripts/python/plpgsql_loops_tests.py`) instead of through the Makefile or `uv run`. Use one of:

```bash
uv run python scripts/python/plpgsql_loops_tests.py
make run-dq
```

### `make run` succeeds but data is stale

The incremental ETL skips a collection when Mongo's count and `updated_at` match Postgres. To force a reload:

```bash
make run-full                                       # all collections
make run-collection-full ARGS="--collection orders"  # one collection
```

### `make` is not on Windows PATH

Git for Windows ships with `make`. If it's not in your PATH, run:

```bash
# PowerShell
$env:PATH += ";C:\Program Files\Git\usr\bin"
```

Or use the bash shell that comes with Git for Windows.

### `make help` output looks wrong on Windows

The `help` target uses plain `@echo` (no `grep`/`awk`) so it works on both `cmd.exe` and bash. If you see literal `^` characters, your shell is interpreting caret-escapes. Run `make help` from a fresh terminal.

---

## See Also

- [README.md](../README.md) — project overview and quick start
- [docs/run_book.md](run_book.md) — operational run book
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) — system architecture
- [AGENTS.md](../AGENTS.md) — coding standards and conventions
