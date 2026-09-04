# Scripts

All executable scripts in the project — ETL, data quality, inspection, and infrastructure management.

---

## Folder Structure

```
scripts/
├── __init__.py                  — Package marker (enables `python -m scripts`)
├── mongo_to_postgres.py         — PySpark incremental ETL: MongoDB → PostgreSQL
├── plpgsql_loops_tests.py       — PL/pgSQL DO-block data quality suite
├── run_gx.py                    — Great Expectations validation runner
├── inspect_schema.py            — Print Postgres public schema to stdout
├── docker_dev.sh                — Docker Compose lifecycle manager
├── monitor_logs.sh              — Operational log monitoring & health checks
└── log_cleanup.sh               — Age/size-based log cleanup utility
```

---

## ETL: `mongo_to_postgres.py`

Loads MongoDB collections into Postgres using a watermark-based incremental strategy — no config files, Postgres itself is the source of truth for what's already loaded.

```mermaid
flowchart TD
    classDef detect fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef compare fill:#fff8e1,stroke:#f9a825,color:#5d4037
    classDef read fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20
    classDef write fill:#fce4ec,stroke:#c2185b,color:#880e4f
    classDef decision fill:#ffffff,stroke:#9e9e9e,color:#424242

    A["Peek Mongo: sample 10 docs"]:::detect
    B["Detect PK column + TS column"]:::detect
    C["MongoDB: count + max(updated_at)"]:::compare
    D["Postgres: count + max(updated_at)"]:::compare
    E{{"Counts match<br/>and timestamps match?"}}:::decision
    F["Skip — nothing changed"]:::compare
    G["Pull delta rows from MongoDB"]:::read
    H["Add loaded_at, de-duplicate via MD5 row_hash"]:::write
    I["JDBC write to table_staging_run_id"]:::write
    J{{"Has primary key?"}}:::decision
    K["Upsert:<br/>ON CONFLICT DO UPDATE"]:::write
    L["Dedup:<br/>ON CONFLICT DO NOTHING"]:::write
    M["Drop staging table"]:::write

    A --> B --> C --> D --> E
    E -->|match| F
    E -->|mismatch| G --> H --> I --> J
    J -->|yes| K
    J -->|no| L
    K --> M
    L --> M
```

**PK detection**, in order: `<collection>_id` exact match → first column ending in `_id` → column named `id` → none found, falls back to MD5 `_row_hash` dedup.

**Timestamp detection**: looks for `updated_at` (configurable via `ETL_TS_COL`). If missing, skips incremental filtering and compares by row count only.

### Run modes

```bash
python -m scripts.mongo_to_postgres                                    # incremental, all collections
python -m scripts.mongo_to_postgres --collection staffs               # incremental, one collection
python -m scripts.mongo_to_postgres --collection staffs --collection orders
python -m scripts.mongo_to_postgres --full-refresh                     # truncate + reload everything
python -m scripts.mongo_to_postgres --collection staffs --full-refresh # truncate + reload one collection
```

### Configuration

| Variable | Default | Description |
|---|---|---|
| `ETL_SCHEMA` | `public` | Target Postgres schema |
| `ETL_TS_COL` | `updated_at` | Timestamp column for incremental comparison |
| `ETL_PK_SUFFIX` | `_id` | Suffix used for heuristic PK detection |
| `JDBC_JAR_PATH` | `jars/postgresql.jar` | Path to the Postgres JDBC driver |

Database credentials come from `utils/connection.py` → `.env`.

### Logs

Written to `logs/extraction/mongo_public_<collection>_<timestamp>.log`. Console shows `INFO`+; the log file has full `DEBUG` detail.

---

## Data Quality: `plpgsql_loops_tests.py`

Runs the entire PL/pgSQL DO-block data quality suite and prints a pass/fail report.

```mermaid
flowchart TD
    classDef scan fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef run fill:#fff8e1,stroke:#f9a825,color:#5d4037
    classDef result fill:#fce4ec,stroke:#c2185b,color:#880e4f
    classDef decision fill:#ffffff,stroke:#9e9e9e,color:#424242

    A["Scan tests/generic/loops/<N>*.sql"]:::scan
    B["Split each file on markers:<br/>-- Test N: / -- Orphan N: / -- Business N:"]:::scan
    C["Execute each test's PL/pgSQL DO block"]:::run
    D{{"Result rows?"}}:::decision
    D -->|0 rows| E["PASS"]:::result
    D -->|1+ rows| F["FAIL"]:::result
    D -->|Query error| G["ERROR"]:::result
    E --> H["Summary table per file + totals"]:::result
    F --> H
    G --> H
    H --> I{{"Any FAIL<br/>or ERROR?"}}:::decision
    I -->|no| J["Exit 0"]:::result
    I -->|yes| K["Exit 1"]:::result

    A --> B --> C --> D
    D --> E
    D --> F
    D --> G
```

Uses the same Postgres connection as the rest of the pipeline (`utils/connection.py` → `.env`) — no flags needed for normal use.

### Run modes

```bash
python scripts/plpgsql_loops_tests.py                                # run all 10 SQL files
python scripts/plpgsql_loops_tests.py --show-failures --max-rows 5  # preview failing rows
python scripts/plpgsql_loops_tests.py --tests-dir ./tests            # custom folder
python scripts/plpgsql_loops_tests.py --dsn "postgresql://user:pass@host:5432/dbname"  # DB override
```

### Logs

Full detail to `logs/tests/<name>_<timestamp>.log`; terminal shows the Rich summary + progress bar.

---

## Validation: `run_gx.py`

Runs Great Expectations suites against Postgres tables. Suites are defined in `gx/`.

### Run modes

```bash
python scripts/run_gx.py                           # all 9 tables
python scripts/run_gx.py orders products           # specific tables
python scripts/run_gx.py --verbose                # full expectation output
```

Results are written to `tests/data_quality/reports/validation_report_<timestamp>.json`.

---

## Inspection: `inspect_schema.py`

Prints the Postgres `public` schema (tables, columns, types, nullable, defaults) as a formatted table. Useful for quick schema verification without a GUI client.

```bash
python scripts/inspect_schema.py
```

---

## Docker: `docker_dev.sh`

Manages the Docker Compose stack for local development. Requires Docker CLI + daemon running.

| Command | Description |
|---|---|
| `./docker_dev.sh up` | Start all containers in background + verify health |
| `./docker_dev.sh down` | Stop and remove containers |
| `./docker_dev.sh restart` | Restart all containers |
| `./docker_dev.sh status` | Show container status + resource usage |
| `./docker_dev.sh logs [svc]` | Tail logs (all or a specific service) |
| `./docker_dev.sh reset` | Stop + purge all named volumes (interactive) |

---

## Monitoring: `monitor_logs.sh`

Operational health check script that verifies logs, git status, database connectivity, and service availability.

```bash
./monitor_logs.sh                  # run checks only (default)
./monitor_logs.sh --check         # same as above
./monitor_logs.sh --cleanup       # delete logs older than retention period
./monitor_logs.sh --full          # run checks AND cleanup
```

Exit codes: `0` = healthy, `1` = warnings, `2` = critical failures.

Checks performed:
- Command dependencies (find, grep, awk, etc.)
- Git repository status (dirty, ahead/behind upstream)
- Log directory presence
- Error detection in pipeline/extraction/test logs
- GX validation report status
- 24-hour global error scan
- Disk usage vs. warning/critical thresholds
- Prometheus, Pushgateway, PostgreSQL, MongoDB connectivity

---

## Cleanup: `log_cleanup.sh`

Age and size based log file cleanup. Always preserves the most recently modified file.

```bash
./log_cleanup.sh                   # read-only summary
./log_cleanup.sh summary          # same as above
./log_cleanup.sh clean            # interactive deletion
./log_cleanup.sh clean --dry-run  # preview what would be deleted
./log_cleanup.sh clean -y         # force deletion (no prompt)
```

Configuration via environment variables:
- `MAX_AGE_DAYS` — default `7`
- `MAX_SIZE_MB` — default `5`

---

## Key Conventions

- All Python scripts locate the project root by walking up from `__file__` until they find `utils/connection.py`.
- All shell scripts use `set -uo pipefail` (per AGENTS.md).
- Scripts return a non-zero exit code on any failure — safe to wire into CI or a scheduler.
- Color output is auto-disabled when stdout is not a TTY (piping to file).
