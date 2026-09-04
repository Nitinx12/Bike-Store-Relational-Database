# Run Book: How to Run the Pipeline

## TL;DR

```bash
# 1. Set up environment
cp .env.example .env    # edit .env with your credentials

# 2. Build the Docker image
make build

# 3. Start the full stack (Postgres + MongoDB + monitoring)
make up

# 4. Run the full pipeline
make pipeline

# 5. Or run jobs individually
make etl ARGS="--full-refresh"
make dq-loops
make dq-gx ARGS="orders products"
```

Or locally without Docker:

```bash
uv sync
uv run python scripts/mongo_to_postgres.py --full-refresh
uv run python scripts/plpgsql_loops_tests.py
uv run python tests/data_quality/run.py
```

---

## Prerequisites

- `python >= 3.13`
- `uv` (installed via `pip install uv` or the installer)
- Docker & Docker Compose
- `jars/postgresql.jar` (the Postgres JDBC driver — already committed)

---

## Environment Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=bike_store
POSTGRES_USERNAME=postgres
POSTGRES_PASSWORD=your_password

# MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB=bike_store

# Optional: ETL column name (default: updated_at)
ETL_TS_COL=updated_at
```

All scripts load these from `.env` via `python-dotenv`. **Never commit `.env`.**

---

## Running via Makefile (recommended)

All targets delegate to `docker compose`. See `Makefile` for the full list.

| Target | What it does |
|---|---|
| `make check-env` | Copies `.env.example` → `.env` if `.env` is missing |
| `make build` | Builds the `app` Docker image |
| `make up` | Starts full stack: postgres, mongodb, pushgateway, prometheus, grafana |
| `make down` | Stops the stack (keeps volumes) |
| `make pipeline` | Full pipeline: ETL → PL/pgSQL → GX |
| `make etl ARGS="..."` | ETL only — see ARGS below |
| `make dq-loops` | PL/pgSQL data quality suite |
| `make dq-gx ARGS="..."` | Great Expectations suite |
| `make inspect-schema` | Print Postgres public schema |
| `make monitor-logs ARGS="..."` | Log manager (summary / clean) |
| `make shell` | Debug bash shell inside the app container |
| `make clean` | Stop + remove all containers and volumes |
| `make prune` | Nuclear clean: containers + volumes + images + cache |

### ETL ARGS

```bash
make etl                           # incremental, all collections
make etl ARGS="--full-refresh"    # truncate + reload everything
make etl ARGS="--collection orders --collection products"
```

### GX ARGS

```bash
make dq-gx                          # all 9 tables
make dq-gx ARGS="orders products"  # specific tables
```

### Monitor-logs ARGS

```bash
make monitor-logs              # summary of all log directories
make monitor-logs ARGS="clean --dry-run"   # preview cleanup
make monitor-logs ARGS="clean -y"         # force cleanup
```

---

## Running via Docker Compose directly

```bash
# Build
docker compose build app

# Start infrastructure
docker compose up -d postgres mongodb pushgateway prometheus grafana

# Run a specific job
docker compose --profile jobs run --rm app pipeline
docker compose --profile jobs run --rm app etl -- --full-refresh
docker compose --profile jobs run --rm app dq-loops
docker compose --profile jobs run --rm app dq-gx -- orders products
docker compose --profile jobs run --rm app shell
```

---

## Running via PowerShell (local, no Docker)

```powershell
# Requires PowerShell 7+

.\ps1\local_runner.ps1                          # full pipeline
.\ps1\local_runner.ps1 -FullRefresh            # full refresh
.\ps1\local_runner.ps1 -Collection orders      # one collection, incremental
.\ps1\local_runner.ps1 -SkipGx                # skip GX suite
.\ps1\local_runner.ps1 -ContinueOnError        # run all stages even on failure
```

---

## Running Scripts Directly (uv run)

```bash
# ETL — incremental
uv run python -m scripts.mongo_to_postgres

# ETL — full refresh
uv run python -m scripts.mongo_to_postgres -- --full-refresh

# ETL — specific collections
uv run python -m scripts.mongo_to_postgres -- --collection orders --collection products

# PL/pgSQL suite
uv run python scripts/plpgsql_loops_tests.py

# Great Expectations suite
uv run python scripts/run_gx.py orders products

# Inspect schema
uv run python scripts/inspect_schema.py
```

---

## What Happens During a Run

```mermaid
flowchart TD
    classDef start fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef connect fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    classDef process fill:#fff8e1,stroke:#f9a825,color:#3e2723
    classDef check fill:#fce4ec,stroke:#c2185b,color:#880e4f
    classDef end fill:#e8f5e9,stroke:#1b5e20,color:#1b5e20

    A["Init logger + Rich console"]:::start
    B{{"Collections named on CLI?"}}:::start
    C["Auto-discover all Mongo collections"]:::connect
    D["Use given collection list"]:::connect
    E["Create Spark session + Postgres engine"]:::connect
    F{{"SELECT 1 check?"}}:::check
    G["Process each collection<br/>skip → no-op | load → upsert"]:::process
    H["Stop Spark, dispose engine,<br/>push metrics → Pushgateway"]:::end
    I["Print Rich summary table<br/>log totals to file"]:::end
    J{{"Any failed rows?"}}:::check
    K["Exit code 0<br/>Pipeline PASSED"]:::end
    L["Exit code 1<br/>Pipeline FAILED"]:::check

    A --> B
    B -->|No| C
    B -->|Yes| D
    C --> E
    D --> E
    E --> F
    F -->|fails| L
    F -->|ok| G
    G --> H
    H --> I
    I --> J
    J -->|No failures| K
    J -->|Failed rows| L
```

---

## Key Functions

| Function | File | Responsibility |
|---|---|---|
| `_find_project_root()` | `scripts/mongo_to_postgres.py` | Walks up 8 dirs to find `utils/connection.py` |
| `_slugify(s)` | `src/pipeline/transform.py` | Normalizes field/collection names to safe Postgres identifiers |
| `detect_pk_col()` | `src/pipeline/transform.py` | Heuristic PK: `<collection>_id` → `*_id` → `id` → row_hash |
| `detect_ts_col()` | `src/pipeline/transform.py` | Finds `updated_at` (configurable via `ETL_TS_COL`) |
| `needs_load()` | `src/pipeline/decision.py` | Core skip/load decision |
| `read_mongo_incremental()` | `src/pipeline/mongo_source.py` | Pulls delta (or full collection) from MongoDB |
| `ensure_target_table()` | `src/database/schema.py` | Creates table, unique constraint, schema evolution |
| `merge_staging_to_target()` | `src/database/staging.py` | Upsert (`ON CONFLICT DO UPDATE`) or dedup (`DO NOTHING`) |
| `write_to_staging()` | `src/database/jdbc_writer.py` | JDBC overwrite of the staging table |

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ETL_SCHEMA` | `public` | Target Postgres schema for all tables |
| `ETL_TS_COL` | `updated_at` | Timestamp column used for incremental comparison |
| `ETL_PK_SUFFIX` | `_id` | Suffix used for heuristic PK detection |
| `JDBC_JAR_PATH` | `jars/postgresql.jar` | Postgres JDBC driver location |
| `PYSPARK_PYTHON` | system python | Interpreter Spark workers and driver use |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `FileNotFoundError: postgresql.jar` | Already at `jars/postgresql.jar` — confirm the file exists there |
| `RuntimeError: project root not found` | Run from inside the project tree, e.g. `cd bike-store-relational-database` |
| Fails at Postgres connectivity check | Verify `POSTGRES_HOST/PORT/DATABASE/USERNAME/PASSWORD` in `.env` |
| Collection always skipped despite changes | Confirm `updated_at` is updated on writes; run `--full-refresh` once to resync |
| Staging/merge failure | Usually a constraint or Postgres permissions issue; staging is auto-cleaned — safe to re-run |
| `order_items` (composite key) loads oddly | Auto-detection finds the first `*_id` column only; handle `order_items` via `--collection order_items --full-refresh` or exclude it |

---

## Common Tasks

- **Add a new Mongo field**: nothing to do — `ensure_target_table` auto-adds it as TEXT on the next run.
- **Full backfill**: `make etl ARGS="--full-refresh"`
- **Inspect the schema**: `make inspect-schema`
- **Debug inside the container**: `make shell`
- **Check log health**: `make monitor-logs`