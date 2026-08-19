# Scripts

Executable ETL pipeline scripts. Each script is a self-contained pipeline stage that can be run directly from the command line or scheduled as a job.

---

## Folder Structure

```
scripts/
├── __init__.py              — Marks the folder as a Python package
├── mongo_to_postgres.py     — PySpark incremental ETL: MongoDB → PostgreSQL
└── __pycache__/             — Auto-generated Python bytecode cache (do not edit)
```

---

## Scripts

### `mongo_to_postgres.py`

A PySpark ETL pipeline that loads data from MongoDB into PostgreSQL using a watermark-based incremental strategy. No config files required — all comparison logic runs directly against the two databases.

**How it works:**

```
1. Peek MongoDB (1 doc)         →  auto-detect PK column + timestamp column
2. MongoDB stats via PyMongo    →  count + MAX(updated_at)
3. Postgres stats via SQLAlchemy →  count + MAX(updated_at)
4. count match AND max_ts match →  SKIP, move to next collection
5. Diff found                   →  Spark reads the full collection
6. Filter: updated_at > pg_max_ts
7. JDBC write                   →  {table}_staging_{run_id}
8. Upsert staging → target table
   Has PK  : ON CONFLICT (pk) DO UPDATE WHERE EXCLUDED.updated_at > table.updated_at
   No PK   : ON CONFLICT (_row_hash) DO NOTHING
9. DROP staging table
```

**PK detection** — auto-detected from column names in this order:
1. `<collection_name>_id` (exact match)
2. First column ending in `_id`
3. Column named `id`
4. No match — falls back to MD5 row-hash deduplication via `_row_hash`

**Timestamp detection** — looks for `updated_at` by default (configurable via `ETL_TS_COL`). If not found, skips incremental comparison and falls back to full-snapshot upsert.

---

## Run Modes

```bash
# Incremental — all collections
python -m scripts.mongo_to_postgres

# Incremental — specific collection(s)
python -m scripts.mongo_to_postgres --collection staffs
python -m scripts.mongo_to_postgres --collection staffs --collection orders

# Full refresh — truncate and reload all collections
python -m scripts.mongo_to_postgres --full-refresh

# Full refresh — specific collection(s) only
python -m scripts.mongo_to_postgres --collection staffs --full-refresh
```

---

## Configuration

Controlled entirely through environment variables. No config files needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `ETL_SCHEMA` | `public` | Target Postgres schema |
| `ETL_TS_COL` | `updated_at` | Timestamp column used for incremental comparison |
| `ETL_PK_SUFFIX` | `_id` | Suffix used for heuristic PK detection |
| `JDBC_JAR_PATH` | `driver/postgresql.jar` | Path to the PostgreSQL JDBC driver JAR |

Database credentials are inherited from `utils/connection.py` and must be set in `.env`.

---

## Requirements

**PostgreSQL JDBC JAR**

The script requires the PostgreSQL JDBC driver to be present before running:

1. Download from: https://jdbc.postgresql.org/download/
2. Place at: `driver/postgresql.jar`

Or point to an existing JAR via environment variable:

```bash
# Mac / Linux
export JDBC_JAR_PATH=/path/to/postgresql-42.x.x.jar

# Windows
set JDBC_JAR_PATH=C:\path\to\postgresql-42.x.x.jar
```

---

## Logs

Logs are written to `logs/extraction/` by the shared logger in `utils/logger.py`.
Each run produces a timestamped file: `logs/extraction/mongo_public_main_YYYY-MM-DD_HH-MM.log`

Console output shows `INFO` and above. The log file captures full `DEBUG` detail.

---

## Notes

- The script auto-discovers all collections in the configured MongoDB database if no `--collection` flag is provided.
- Staging tables are created and dropped within the same transaction per collection.
- A non-zero exit code is returned if any collection fails to load.
- The script must be run from within the project folder so it can locate `utils/connection.py`.