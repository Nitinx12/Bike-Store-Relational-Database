"""
mongo_to_postgres.py
PySpark incremental ETL: MongoDB → PostgreSQL

Watermark strategy — Postgres-native, zero config files:
  ┌──────────────────────────────────────────────────────────────────────┐
  │  1. Peek MongoDB (1 doc)  →  auto-detect PK col + TS col             │
  │  2. MongoDB stats via PyMongo  →  count  +  MAX(updated_at)          │
  │  3. Postgres stats via SQLAlchemy  →  count  +  MAX(updated_at)      │
  │  4. count match  AND  max_ts match  →  SKIP, next collection         │
  │  5. Diff found  →  Spark reads full collection                       │
  │  6. Filter: updated_at > pg_max_ts                                   │
  │  7. JDBC write  →  {table}_staging_{run_id}                          │
  │  8. Upsert staging  →  target table                                  │
  │     Has-PK : ON CONFLICT (pk) DO UPDATE                              │
  │              WHERE EXCLUDED.updated_at > table.updated_at            │
  │     No-PK  : ON CONFLICT (_row_hash) DO NOTHING                      │
  │  9. DROP staging                                                     │
  └──────────────────────────────────────────────────────────────────────┘

PK  : auto-detected as the first column ending in '_id'
TS  : ETL_TS_COL env var  (default: updated_at)

Run modes
  python -m scripts.mongo_to_postgres
      Incremental — all collections

  python -m scripts.mongo_to_postgres --collection staffs [--collection orders]
      Incremental — named collection(s) only

  python -m scripts.mongo_to_postgres --full-refresh
      Full refresh — truncate all tables, reload everything

  python -m scripts.mongo_to_postgres --collection staffs --full-refresh
      Full refresh — named collection(s) only
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from pymongo import MongoClient
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.traceback import install as install_rich_traceback
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# ─────────────────────────────────────────────────────────────────────────────
# Project-root bootstrap  (same pattern as extract.py)
# ─────────────────────────────────────────────────────────────────────────────


def _find_project_root() -> Path | None:
    """
    Walk upward from this file until we find a directory that contains
    utils/connection.py — that is the project root.
    Handles running from any sub-folder (scripts/, notebooks/, etc.).
    """
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "utils" / "connection.py").exists():
            return current
        current = current.parent
    return None


_root = _find_project_root()
if _root is None:
    raise RuntimeError(
        "Could not locate project root.\n"
        f"Searched upward from: {Path(__file__).resolve()}\n\n"
        "Expected to find  utils/connection.py  somewhere in the parent tree.\n"
        "Make sure you run from inside the project folder, e.g.:\n"
        "  python scripts/mongo_to_postgres.py\n"
        "  python -m scripts.mongo_to_postgres        (no .py suffix)\n"
    )
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Project imports  (utils/ lives at the project root)
from utils.connection import (
    MONGO_DB,
    MONGO_URI,
    POSTGRES_DATABASE,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USERNAME,
)
from utils.engine import postgres_engine
from utils.logger import get_logger

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

ETL_SCHEMA = os.getenv("ETL_SCHEMA", "public")  # ← public schema
ETL_TS_COL = os.getenv("ETL_TS_COL", "updated_at")  # incremental timestamp
ETL_PK_SUFFIX = os.getenv("ETL_PK_SUFFIX", "_id")  # heuristic PK suffix

JDBC_JAR_PATH = os.getenv(
    "JDBC_JAR_PATH",
    str(_root / "jars" / "postgresql.jar"),  # matches your jars/ folder
)

if not Path(JDBC_JAR_PATH).is_file():
    raise FileNotFoundError(
        f"\n\nPostgreSQL JDBC JAR not found at:\n  {JDBC_JAR_PATH}\n\n"
        "Fix options:\n"
        "  1. Place the JAR at the path above (jars/postgresql.jar)\n"
        "  2. Or point to an existing JAR via env var:\n"
        "       Windows : set JDBC_JAR_PATH=C:\\path\\to\\postgresql-42.x.x.jar\n"
        "       Mac/Linux: export JDBC_JAR_PATH=/path/to/postgresql-42.x.x.jar\n"
        "  Download from: https://jdbc.postgresql.org/download/\n"
    )

ISO_FMT = "%Y-%m-%dT%H:%M:%S"
JDBC_URL = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"

# ─────────────────────────────────────────────────────────────────────────────
# Column type map  (table_slug, column) → Postgres type string
# Columns not in this map default to TEXT.
# ─────────────────────────────────────────────────────────────────────────────

COLUMN_TYPE_MAP: dict[tuple[str, str], str] = {
    # timestamps / dates
    ("categories", "updated_at"): "TIMESTAMPTZ",
    ("customers", "updated_at"): "TIMESTAMPTZ",
    ("orders", "order_date"): "DATE",
    ("orders", "required_date"): "DATE",
    ("orders", "shipped_date"): "DATE",
    ("orders", "updated_at"): "TIMESTAMPTZ",
    ("products", "updated_at"): "TIMESTAMPTZ",
    ("staffs", "updated_at"): "TIMESTAMPTZ",
    ("stocks", "updated_at"): "TIMESTAMPTZ",
    ("stores", "updated_at"): "TIMESTAMPTZ",
    # numeric / boolean
    ("staffs", "active"): "SMALLINT",
    # order_items totals
    ("order_items", "total_value"): "NUMERIC(14,2)",
}


# Composite (multi-column) primary key overrides — (table_slug, columns)
COMPOSITE_PK: dict[str, tuple[str, ...]] = {
    "stocks": ("store_id", "product_id"),
}


def _pg_type_for(table: str, col: str) -> str:
    """Return the Postgres type for (table, column), or 'TEXT' as safe fallback."""
    return COLUMN_TYPE_MAP.get((table, col), "TEXT")


# Map Postgres type name → Spark DataFrame cast type (SQL type string).
# DATE and TIMESTAMPTZ are parsed from the ISO-8601 string produced by MongoDB.
_PG_TO_SPARK_CAST: dict[str, str] = {
    "TIMESTAMPTZ": "TIMESTAMP",
    "DATE": "DATE",
    "SMALLINT": "SMALLINT",
    "INTEGER": "INTEGER",
    "BIGINT": "BIGINT",
    "NUMERIC": "DECIMAL(20,6)",
    "NUMERIC(14,2)": "DECIMAL(14,2)",
    "DOUBLE PRECISION": "DOUBLE",
    "REAL": "FLOAT",
}


def _cast_typed_columns(
    sdf: DataFrame, table: str, log
) -> DataFrame:
    """
    Apply per-column type casts so JDBC writes typed values, not blind strings.

    Only columns listed in COLUMN_TYPE_MAP are cast; all others stay as strings.
    Casting failures (e.g. malformed timestamp strings) fall back to NULL so the
    pipeline never aborts on a single bad row.
    """
    result = sdf
    for col in sdf.columns:
        pg_type = _pg_type_for(table, col)
        spark_cast = _PG_TO_SPARK_CAST.get(pg_type)
        if spark_cast is None:
            continue  # stays as string
        try:
            result = result.withColumn(col, F.col(col).cast(spark_cast))
            log.debug("TYPE CAST  : %s.%s → %s", table, col, spark_cast)
        except (ValueError, TypeError) as exc:
            log.warning(
                "TYPE CAST FAILED for %s.%s (%s → %s): %s — column left as string",
                table, col, pg_type, spark_cast, exc,
            )
    return result

# ─────────────────────────────────────────────────────────────────────────────
# Rich console setup — pretty tracebacks + terminal-facing banner/summary
# (purely presentational; all utils.logger calls throughout the script are
# left exactly as-is so file logging behaviour is unchanged)
# ─────────────────────────────────────────────────────────────────────────────

console = Console()
install_rich_traceback(show_locals=False, suppress=[pd])


def _print_banner(collections: list[str], mode: str) -> None:
    """Startup banner summarising the run configuration."""
    body = (
        f"[bold]Mode[/bold]        : {mode}\n"
        f"[bold]Collections[/bold] : {len(collections)}\n"
        f"[bold]Schema[/bold]      : {ETL_SCHEMA}\n"
        f"[bold]TS col[/bold]      : {ETL_TS_COL}\n"
        f"[bold]JDBC JAR[/bold]    : {JDBC_JAR_PATH}"
    )
    console.print(
        Panel(body, title="Mongo → Postgres ETL", border_style="cyan", box=box.ROUNDED)
    )


def _print_summary_table(
    summaries: list[dict], totals: dict, skipped_count: int
) -> None:
    """Run-summary table (replaces the old ASCII '═'/'─' block on screen)."""
    table = Table(title="Run Summary", box=box.SIMPLE_HEAVY)
    table.add_column("Collection", style="bold")
    table.add_column("Status")
    table.add_column("Mongo", justify="right")
    table.add_column("New", justify="right")
    table.add_column("Loaded", justify="right")
    table.add_column("Failed", justify="right")

    for s in summaries:
        failed = s.get("failed", 0)
        if failed:
            status = "[red]FAILED[/red]"
        elif s.get("skipped"):
            status = "[yellow]SKIPPED[/yellow]"
        else:
            status = "[green]LOADED[/green]"
        table.add_row(
            s["collection"],
            status,
            str(s.get("rows_mongo", 0)),
            str(s.get("rows_new", 0)),
            str(s.get("rows_loaded", 0)),
            str(failed),
        )

    table.add_section()
    table.add_row(
        "TOTAL",
        f"{len(summaries)} collections, {skipped_count} skipped",
        str(totals["rows_mongo"]),
        str(totals["rows_new"]),
        str(totals["rows_loaded"]),
        str(totals["failed"]),
        style="bold",
    )

    console.print(table)


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────


def _slugify(s: str) -> str:
    """Normalise a field name to a safe Postgres column identifier."""
    s = str(s).strip().lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"[\s\-]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_") or "col"


def _staging_name(table: str, run_id: str) -> str:
    return f"{table}_staging_{run_id}"


def _fmt_ts(val: object) -> str:
    """Format a timestamp value (datetime or str) for logging, or 'N/A'."""
    if val is None:
        return "N/A"
    if hasattr(val, "strftime"):
        return val.strftime(ISO_FMT)
    return str(val)


def _to_datetime(val: object) -> datetime | None:
    """Coerce a datetime/str to a datetime for comparison, or None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Column detection
# ─────────────────────────────────────────────────────────────────────────────


def detect_pk_col(
    columns: list[str], collection: str, log
) -> list[str] | None:
    """
    Heuristic PK detection from slugified column names.

    Priority:
      1. Explicit composite-PK override in COMPOSITE_PK (e.g. stocks)
      2. Exact match for the collection name + '_id'
         e.g.  collection='artist'  → 'artist_id'
      3. Any column that ends with '_id'
      4. Exact column named 'id'

    Returns a list of PK column names (1 for single-key, 2+ for composite),
    or None if nothing matches.
    """
    slug = _slugify(collection)

    composite = COMPOSITE_PK.get(slug)
    if composite and all(c in columns for c in composite):
        log.info(
            "PK DETECT : %s  (composite key from COMPOSITE_PK)", list(composite)
        )
        return list(composite)

    exact = f"{slug}_id"

    if exact in columns:
        log.info("PK DETECT : '%s'  (exact match for collection name)", exact)
        return [exact]

    candidates = [c for c in columns if c.endswith("_id")]
    if candidates:
        log.info("PK DETECT : '%s'  (first *_id column)", candidates[0])
        return [candidates[0]]

    if "id" in columns:
        log.info("PK DETECT : 'id'  (fallback)")
        return ["id"]

    log.warning(
        "PK DETECT : no PK column found in %s — will use row-hash dedup", collection
    )
    return None


def detect_ts_col(columns: list[str], log) -> str | None:
    """
    Check whether 'updated_at' (or the configured ETL_TS_COL) is present.
    Returns the column name or None.
    """
    ts = _slugify(ETL_TS_COL)
    if ts in columns:
        log.info("TS DETECT  : '%s'  found ✓", ts)
        return ts
    log.warning(
        "TS DETECT  : '%s' not found — will skip incremental comparison "
        "and fall back to full-snapshot upsert",
        ts,
    )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Row-hash helper  (for no-PK collections)
# ─────────────────────────────────────────────────────────────────────────────


def _add_row_hash(sdf: DataFrame, exclude_cols: list[str] | None = None) -> DataFrame:
    """
    Add a deterministic _row_hash TEXT column (MD5 of all data columns).
    Used as a surrogate unique key for no-PK collections so ON CONFLICT
    (_row_hash) DO NOTHING prevents duplicates on re-runs.
    """
    skip = set(exclude_cols or []) | {"_row_hash"}
    hash_cols = [c for c in sdf.columns if c not in skip]
    concat_expr = F.concat_ws(
        "|",
        *[
            F.concat(F.lit(f"{c}="), F.coalesce(F.col(c).cast("string"), F.lit("NULL")))
            for c in hash_cols
        ],
    )
    return sdf.withColumn("_row_hash", F.md5(concat_expr))


# ─────────────────────────────────────────────────────────────────────────────
# Spark session
# ─────────────────────────────────────────────────────────────────────────────


def get_spark(app_name: str = "MongoToPublicETL") -> SparkSession:
    os.environ["PYSPARK_PYTHON"] = os.getenv("PYSPARK_PYTHON", sys.executable)
    os.environ["PYSPARK_DRIVER_PYTHON"] = os.getenv(
        "PYSPARK_DRIVER_PYTHON", sys.executable
    )

    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.driver.extraClassPath", JDBC_JAR_PATH)
        .config("spark.executor.extraClassPath", JDBC_JAR_PATH)
        .config("spark.driver.extraJavaOptions", "--add-modules jdk.incubator.vector")
        .config("spark.executor.extraJavaOptions", "--add-modules jdk.incubator.vector")
        .config("spark.sql.legacy.timeParserPolicy", "LEGACY")
        .config("spark.driver.memory", "2g")
        .config("spark.logConf", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


# ─────────────────────────────────────────────────────────────────────────────
# MongoDB helpers
# ─────────────────────────────────────────────────────────────────────────────


def _mongo_collection_stats(collection: str, ts_col_raw: str | None, log) -> dict:
    """
    Query MongoDB for:
      • total document count
      • MAX(ts_col) — only if ts_col_raw is provided

    Returns  {"count": int, "max_ts": datetime | None}
    """
    try:
        client = MongoClient(MONGO_URI)
        coll = client[MONGO_DB][collection]
        count = coll.count_documents({})
        max_ts = None

        if ts_col_raw:
            # Aggregate pipeline: $group → $max
            pipeline = [{"$group": {"_id": None, "max_ts": {"$max": f"${ts_col_raw}"}}}]
            result = list(coll.aggregate(pipeline))
            if result and result[0].get("max_ts"):
                max_ts = result[0]["max_ts"]

        client.close()
        log.info(
            "MONGO STATS : %s  count=%d  max_ts=%s",
            collection,
            count,
            _fmt_ts(max_ts),
        )
        return {"count": count, "max_ts": max_ts}

    except Exception as exc:
        log.error("Failed to get Mongo stats for '%s': %s", collection, exc)
        return {"count": 0, "max_ts": None}


def read_mongo_incremental(
    spark: SparkSession,
    collection: str,
    ts_col_raw: str | None,
    pg_max_ts: datetime | str | None,
    log,
) -> DataFrame | None:
    """
    Read from MongoDB via PyMongo.
      • If pg_max_ts is provided and ts_col exists → fetch only docs
        WHERE ts_col > pg_max_ts  (true incremental delta)
      • Otherwise → fetch all documents  (first run / fallback)
    Drops _id, slugifies column names, preserves NaN as NULL.
    """
    try:
        client = MongoClient(MONGO_URI)
        coll = client[MONGO_DB][collection]

        mongo_filter: dict = {}
        if ts_col_raw and pg_max_ts:
            ts_val = _to_datetime(pg_max_ts) if isinstance(pg_max_ts, str) else pg_max_ts
            if ts_val:
                mongo_filter = {ts_col_raw: {"$gt": ts_val}}
            log.info(
                "MONGO READ  : %s  filter → %s > %s",
                collection,
                ts_col_raw,
                _fmt_ts(pg_max_ts),
            )
        else:
            log.info("MONGO READ  : %s  filter → none (full snapshot)", collection)

        docs = list(coll.find(mongo_filter, {"_id": 0}))
        client.close()

        if not docs:
            log.info("MONGO READ  : %s  → 0 docs returned", collection)
            return None

        pdf = pd.DataFrame(docs)
        pdf.columns = [_slugify(c) for c in pdf.columns]

        # Preserve NaN/None as SQL NULL. Only non-null values are coerced to
        # string; typed columns (date, timestamp, numeric) get re-cast by the
        # caller via _cast_typed_columns() right after this DataFrame is built.
        for col in pdf.columns:
            pdf[col] = pdf[col].where(pdf[col].isna(), pdf[col].astype(str))

        sdf = spark.createDataFrame(pdf)
        log.info(
            "MONGO READ  : %s  →  %d docs  |  cols: %s",
            collection,
            len(docs),
            sdf.columns,
        )
        return sdf

    except Exception as exc:
        log.error("Failed to read collection '%s': %s", collection, exc)
        log.debug(traceback.format_exc())
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL comparison helpers
# ─────────────────────────────────────────────────────────────────────────────


def get_postgres_stats(
    engine, schema: str, table: str, ts_col: str | None, log
) -> dict:
    """
    Query Postgres for:
      • row count of the target table  (0 if table does not exist)
      • MAX(ts_col)                    (None if table absent or no ts_col)

    Returns  {"count": int, "max_ts": datetime | None, "table_exists": bool}
    """
    result = {"count": 0, "max_ts": None, "table_exists": False}
    try:
        with engine.connect() as conn:
            # Check whether the table exists in the target schema
            exists = conn.execute(
                text("""
                SELECT 1
                FROM   information_schema.tables
                WHERE  table_schema = :schema
                AND    table_name   = :table
            """),
                {"schema": schema, "table": table},
            ).fetchone()

            if not exists:
                log.info("PG STATS    : %s.%s does not exist yet", schema, table)
                return result

            result["table_exists"] = True
            result["count"] = (
                conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                ).scalar()
                or 0
            )

            if ts_col:
                # Check that the ts_col column actually exists in Postgres
                col_exists = conn.execute(
                    text("""
                    SELECT 1
                    FROM   information_schema.columns
                    WHERE  table_schema  = :schema
                    AND    table_name    = :table
                    AND    column_name   = :col
                """),
                    {"schema": schema, "table": table, "col": ts_col},
                ).fetchone()

                if col_exists:
                    row = conn.execute(
                        text(f'SELECT MAX("{ts_col}") FROM "{schema}"."{table}"')
                    ).fetchone()
                    if row and row[0]:
                        result["max_ts"] = row[0]  # returns a datetime object

        log.info(
            "PG STATS    : %s.%s  count=%d  max_ts=%s",
            schema,
            table,
            result["count"],
            _fmt_ts(result["max_ts"]),
        )
    except Exception as exc:
        log.error("Failed to get Postgres stats for %s.%s: %s", schema, table, exc)

    return result


def needs_load(
    mongo_stats: dict,
    pg_stats: dict,
    ts_col: str | None,
    log,
) -> bool:
    """
    Decide whether to load data for this collection.

    Rules:
      1. Table doesn't exist in Postgres          → always load
      2. Mongo count > Postgres count             → new rows added, load
      3. ts_col present AND Mongo max_ts > PG max_ts  → newer records exist, load
      4. Otherwise                                → nothing changed, skip
    """
    if not pg_stats["table_exists"]:
        log.info("DECISION    : table absent in Postgres → LOAD (first run)")
        return True

    if mongo_stats["count"] > pg_stats["count"]:
        log.info(
            "DECISION    : Mongo count (%d) > PG count (%d) → LOAD",
            mongo_stats["count"],
            pg_stats["count"],
        )
        return True

    if ts_col and mongo_stats["max_ts"] and pg_stats["max_ts"]:
        mongo_ts = _to_datetime(mongo_stats["max_ts"])
        pg_ts = _to_datetime(pg_stats["max_ts"])
        if mongo_ts and pg_ts and mongo_ts > pg_ts:
            log.info(
                "DECISION    : Mongo max_ts (%s) > PG max_ts (%s) → LOAD",
                _fmt_ts(mongo_ts),
                _fmt_ts(pg_ts),
            )
            return True

    log.info(
        "DECISION    : no changes detected (Mongo count=%d, PG count=%d) → SKIP",
        mongo_stats["count"],
        pg_stats["count"],
    )
    return False


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL write helpers
# ─────────────────────────────────────────────────────────────────────────────


def ensure_schema(conn, schema: str, log) -> None:
    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    log.info("Schema ready → %s", schema)


def ensure_target_table(
    conn,
    schema: str,
    table: str,
    columns: list[str],
    pk_col: list[str] | None,
    log,
) -> None:
    """
    CREATE TABLE IF NOT EXISTS with a UNIQUE constraint on pk_col (or _row_hash
    for no-PK collections).  Also applies schema evolution (ALTER TABLE ADD COLUMN)
    so new MongoDB fields are automatically added to the Postgres table.

    Per-column Postgres types are looked up via _pg_type_for(table, col); columns
    not in COLUMN_TYPE_MAP default to TEXT, so existing schemas are unaffected.
    """
    col_defs = ",\n    ".join(
        f'"{c}" {_pg_type_for(table, c)}' for c in columns
    )

    pk_list = pk_col
    if pk_list:
        pk_quoted = ", ".join(f'"{c}"' for c in pk_list)
        constraint_name = "_".join(pk_list)
        unique_clause = (
            f',\n    CONSTRAINT "{table}_{constraint_name}_uq" '
            f'UNIQUE ({pk_quoted})'
        )
    else:
        unique_clause = f',\n    CONSTRAINT "{table}_row_hash_uq" UNIQUE ("_row_hash")'

    conn.execute(
        text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (
            _etl_id  SERIAL,
            {col_defs}{unique_clause}
        )
    """)
    )

    # Schema evolution: add any columns that are new since the last run
    existing = {
        row[0]
        for row in conn.execute(
            text("""
            SELECT column_name
            FROM   information_schema.columns
            WHERE  table_schema = :schema
            AND    table_name   = :table
        """),
            {"schema": schema, "table": table},
        )
    }
    for col in columns:
        if col not in existing:
            pg_type = _pg_type_for(table, col)
            conn.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'ADD COLUMN "{col}" {pg_type}'
                )
            )
            log.info(
                "Schema evolution → added column '%s' (%s) to %s.%s",
                col, pg_type, schema, table,
            )

    # Type migration: promote existing TEXT columns to their target Postgres
    # type.  This is a one-time fix-up for tables that were created before the
    # COLUMN_TYPE_MAP existed and now hold typed data in TEXT columns.
    # Wrapped per-column in a savepoint so one bad column doesn't abort the
    # whole migration.
    type_rows = conn.execute(
        text("""
            SELECT column_name, data_type
            FROM   information_schema.columns
            WHERE  table_schema = :schema
            AND    table_name   = :table
        """),
        {"schema": schema, "table": table},
    ).fetchall()

    for col, actual_type in type_rows:
        if col == "_etl_id":
            continue
        target_type = _pg_type_for(table, col)
        if target_type == "TEXT":
            continue  # nothing to migrate
        # Normalise for comparison: TEXT vs character varying, etc.
        actual_norm = actual_type.lower().split("(")[0].strip()
        target_norm = target_type.lower().split("(")[0].strip()
        if actual_norm == target_norm:
            continue  # already correct

        savepoint = f"sp_mig_{col}"
        try:
            conn.execute(text(f"SAVEPOINT {savepoint}"))
            conn.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'ALTER COLUMN "{col}" TYPE {target_type} '
                    f'USING "{col}"::{target_type}'
                )
            )
            conn.execute(text(f"RELEASE SAVEPOINT {savepoint}"))
            log.info(
                "Type migration → %s.%s  %s → %s",
                schema, table, actual_type, target_type,
            )
        except SQLAlchemyError as exc:
            conn.execute(text(f"ROLLBACK TO SAVEPOINT {savepoint}"))
            log.warning(
                "Type migration FAILED for %s.%s (%s → %s): %s — column left as %s",
                schema, table, actual_type, target_type, exc, actual_type,
            )

    log.info("Table ready → %s.%s  (pk=%s)", schema, table, pk_list or "row_hash")


def merge_staging_to_target(
    conn,
    schema: str,
    table: str,
    staging: str,
    columns: list[str],
    pk_col: list[str] | None,
    log,
) -> int:
    """
    INSERT … SELECT from staging into the target table.
      Has-PK  → ON CONFLICT (pk_col)   DO UPDATE SET …   (upsert)
      No-PK   → ON CONFLICT (_row_hash) DO NOTHING        (dedup)
    Returns the row count of the staging table (= rows attempted).

    Per-column `::type` casts are added on the SELECT side so the TEXT
    columns written by the JDBC writer line up with the typed target
    columns. Columns that are TEXT in both staging and target stay as-is.
    """
    def _select_expr(col: str) -> str:
        target_type = _pg_type_for(table, col)
        if target_type == "TEXT":
            return f'"{col}"'
        return f'NULLIF("{col}", \'\')::{target_type}'

    col_list = ", ".join(f'"{c}"' for c in columns)
    select_list = ", ".join(_select_expr(c) for c in columns)

    pk_list = pk_col
    if pk_list:
        conflict_cols = ", ".join(f'"{c}"' for c in pk_list)
        pk_set = set(pk_list)
        update_set = (
            ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns if c not in pk_set)
            or ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in pk_list)
        )
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {select_list} FROM "{schema}"."{staging}"
            ON CONFLICT ({conflict_cols}) DO UPDATE SET {update_set}
        """
    else:
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {select_list} FROM "{schema}"."{staging}"
            ON CONFLICT ("_row_hash") DO NOTHING
        """

    conn.execute(text(sql))
    count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{staging}"')).scalar()
    log.info("MERGE       : %d rows → %s.%s", count, schema, table)
    return count


def drop_staging(conn, schema: str, staging: str, log) -> None:
    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{staging}"'))
    log.debug("Staging dropped → %s.%s", schema, staging)


def truncate_table(conn, schema: str, table: str, log) -> None:
    conn.execute(
        text(f'TRUNCATE TABLE "{schema}"."{table}" RESTART IDENTITY CASCADE')
    )
    log.info("TRUNCATED   → %s.%s  (full-refresh)", schema, table)


# ─────────────────────────────────────────────────────────────────────────────
# Core per-collection function
# ─────────────────────────────────────────────────────────────────────────────


def process_collection(
    collection: str,
    spark: SparkSession,
    engine,
    full_load: bool = False,
) -> dict:
    """
    Incremental load for one MongoDB collection into public schema.

    Steps:
      1. Peek at the collection to discover pk_col and ts_col
      2. Get Mongo stats (count, max updated_at)
      3. Get Postgres stats (count, max updated_at)
      4. Compare → skip if nothing changed (unless --full-refresh)
      5. Read incremental delta from Mongo
      6. Write to staging via JDBC
      7. Merge staging → target table (upsert / dedup)
      8. Drop staging
    """
    log = get_logger(stage="extraction", name=collection)
    table = _slugify(collection)
    schema = ETL_SCHEMA
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    staging = _staging_name(table, run_id)

    base = dict(
        collection=collection,
        rows_mongo=0,
        rows_new=0,
        rows_loaded=0,
        skipped=False,
        failed=0,
    )

    log.info("=" * 65)
    log.info("COLLECTION  : %s", collection)
    log.info("TARGET      : %s.%s", schema, table)
    log.info("STAGING     : %s.%s", schema, staging)

    # ── Step 1: Peek at Mongo to discover column names ─────────────────────
    try:
        client = MongoClient(MONGO_URI)
        sample = list(client[MONGO_DB][collection].find({}, {"_id": 0}).limit(10))
        client.close()
    except Exception as exc:
        log.error("Cannot connect to Mongo for '%s': %s", collection, exc)
        base["failed"] = 1
        return base

    if not sample:
        log.warning("Collection '%s' is empty — skipping", collection)
        base["skipped"] = True
        return base

    raw_columns = list(pd.DataFrame(sample).columns)
    slug_columns = [_slugify(c) for c in raw_columns]

    # Detect PK and TS column from slugified names
    pk_col = detect_pk_col(slug_columns, collection, log)
    ts_col = detect_ts_col(slug_columns, log)

    # Map back to the original (raw) field name for Mongo queries
    ts_col_raw: str | None = None
    if ts_col:
        for raw, slug in zip(raw_columns, slug_columns):
            if slug == ts_col:
                ts_col_raw = raw
                break

    # ── Step 2: Mongo stats ────────────────────────────────────────────────
    mongo_stats = _mongo_collection_stats(collection, ts_col_raw, log)
    base["rows_mongo"] = mongo_stats["count"]

    if mongo_stats["count"] == 0:
        log.warning("Collection '%s' is empty — skipping", collection)
        base["skipped"] = True
        return base

    # ── Step 3: Postgres stats ─────────────────────────────────────────────
    pg_stats = get_postgres_stats(engine, schema, table, ts_col, log)

    # ── Step 4: Decide whether to load ────────────────────────────────────
    if not full_load and not needs_load(mongo_stats, pg_stats, ts_col, log):
        log.info("SKIP        : %s — no new data detected", collection)
        base["skipped"] = True
        return base

    if full_load:
        log.info("FULL REFRESH: ignoring comparison, will truncate and reload")

    # ── Step 5: Read incremental delta from Mongo ──────────────────────────
    # On full-refresh: pass pg_max_ts=None so we read everything.
    # On incremental: pass the PG max_ts so Mongo returns only the delta.
    pg_max_ts = None if full_load else pg_stats.get("max_ts")

    sdf = read_mongo_incremental(spark, collection, ts_col_raw, pg_max_ts, log)
    if sdf is None:
        log.info("No new rows returned from Mongo — skipping %s", collection)
        base["skipped"] = True
        return base

    rows_new = sdf.count()
    base["rows_new"] = rows_new
    log.info("DELTA       : %d rows to load", rows_new)

    # Add loaded_at audit timestamp
    sdf = sdf.withColumn(
        "loaded_at",
        F.lit(datetime.now().strftime(ISO_FMT)).cast("timestamp"),
    )

    # Apply per-column type casts so JDBC writes typed values
    # (e.g. updated_at → TIMESTAMPTZ, active → SMALLINT, total_value → DECIMAL)
    sdf = _cast_typed_columns(sdf, table, log)

    columns = sdf.columns  # refresh after adding loaded_at + casts

    # Dedup on PK columns (guard against duplicate source docs)
    pk_list = [c for c in (pk_col or []) if c in columns]
    if pk_list:
        before = sdf.count()
        sdf = sdf.dropDuplicates(pk_list)
        dupes = before - sdf.count()
        if dupes > 0:
            log.warning(
                "DEDUP       : removed %d duplicate rows on %s in '%s'",
                dupes,
                pk_list,
                collection,
            )
            rows_new = sdf.count()
            base["rows_new"] = rows_new

    # Row-hash dedup for no-PK collections
    if pk_col is None:
        sdf = _add_row_hash(sdf, exclude_cols=["loaded_at"])
        columns = sdf.columns
        log.info("ROW HASH    : added _row_hash column for no-PK dedup")

    # ── Ensure schema exists before JDBC write ─────────────────────────────
    try:
        with engine.connect() as _conn, _conn.begin():
            ensure_schema(_conn, schema, log)
    except Exception as exc:
        log.error("Could not create schema '%s': %s", schema, exc)
        base["failed"] = rows_new
        return base

    # ── Step 6: Write to staging via JDBC ──────────────────────────────────
    # JDBC writes all columns as TEXT (Spark default). Type alignment
    # is handled via explicit casts in merge_staging_to_target.
    log.info("JDBC WRITE  : %d rows → %s.%s", rows_new, schema, staging)
    try:
        (
            sdf.write.format("jdbc")
            .option("url", JDBC_URL)
            .option("dbtable", f'"{schema}"."{staging}"')
            .option("user", POSTGRES_USERNAME)
            .option("password", POSTGRES_PASSWORD)
            .option("driver", "org.postgresql.Driver")
            .option("batchsize", "5000")
            .option("numPartitions", "4")
            .mode("overwrite")
            .save()
        )
        log.info("Staging write ✓")
    except Exception as exc:
        log.error("JDBC staging write failed: %s", exc)
        log.debug(traceback.format_exc())
        base["failed"] = rows_new
        return base

    # ── Step 7: Merge staging → target table ──────────────────────────────
    try:
        with engine.connect() as conn, conn.begin():
            ensure_schema(conn, schema, log)
            ensure_target_table(conn, schema, table, list(columns), pk_col, log)

            if full_load and pg_stats["table_exists"]:
                truncate_table(conn, schema, table, log)

            rows_loaded = merge_staging_to_target(
                conn, schema, table, staging, list(columns), pk_col, log
            )
            # ── Step 8: Drop staging ───────────────────────────────────
            drop_staging(conn, schema, staging, log)

        base["rows_loaded"] = rows_loaded

    except Exception as exc:
        log.error("Merge failed for '%s': %s", collection, exc)
        log.debug(traceback.format_exc())
        # Best-effort cleanup
        try:
            with engine.connect() as conn, conn.begin():
                drop_staging(conn, schema, staging, log)
        except Exception:
            pass
        base["failed"] = rows_new
        return base

    log.info(
        "DONE        : mongo=%d  new=%d  loaded=%d  failed=%d",
        base["rows_mongo"],
        base["rows_new"],
        base["rows_loaded"],
        base["failed"],
    )
    log.info("=" * 65)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


def main(collections: list[str], full_load: bool = False) -> None:
    log = get_logger(stage="extraction", name="mongo_public_main")

    # Auto-discover collections if none specified
    if not collections:
        with MongoClient(MONGO_URI) as client:
            collections = client[MONGO_DB].list_collection_names()
        log.info("Discovered %d collections: %s", len(collections), collections)

    mode = "FULL REFRESH" if full_load else "INCREMENTAL"
    log.info("Collections : %d", len(collections))
    log.info("Mode        : %s", mode)
    log.info("Schema      : %s", ETL_SCHEMA)
    log.info("TS col      : %s", ETL_TS_COL)
    log.info("JDBC JAR    : %s", JDBC_JAR_PATH)

    _print_banner(collections, mode)

    spark = get_spark()
    engine = postgres_engine()

    # Verify Postgres connectivity before processing any collection
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    log.info("Postgres connected ✓")

    summaries: list[dict] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Processing collections", total=len(collections))
        for col in collections:
            progress.update(task, description=f"[cyan]{col}[/cyan]")
            summary = process_collection(col, spark, engine, full_load=full_load)
            summaries.append(summary)
            progress.advance(task)

    spark.stop()
    engine.dispose()
    log.info("Spark stopped. Engine disposed.")

    # ── Run summary ────────────────────────────────────────────────────────
    totals = dict(rows_mongo=0, rows_new=0, rows_loaded=0, failed=0)
    skipped_count = 0

    for s in summaries:
        for k in totals:
            totals[k] += s.get(k, 0)
        if s.get("skipped"):
            skipped_count += 1

    log.info(
        "RUN SUMMARY : collections=%d skipped=%d mongo=%d new=%d loaded=%d failed=%d",
        len(summaries),
        skipped_count,
        totals["rows_mongo"],
        totals["rows_new"],
        totals["rows_loaded"],
        totals["failed"],
    )

    _print_summary_table(summaries, totals, skipped_count)

    if totals["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    _argv = sys.argv[1:]

    _full_load = "--full-load" in _argv or "--full-refresh" in _argv

    _collections: list[str] = []
    for i, arg in enumerate(_argv):
        if arg == "--collection" and i + 1 < len(_argv):
            _collections.append(_argv[i + 1])

    main(_collections, _full_load)
