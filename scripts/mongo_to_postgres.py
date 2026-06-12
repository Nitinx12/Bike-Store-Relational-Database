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
import sys
import re
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
from pymongo import MongoClient
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from sqlalchemy import text

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
    MONGO_URI,
    MONGO_DB,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DATABASE,
    POSTGRES_USERNAME,
    POSTGRES_PASSWORD,
)
from utils.engine import postgres_engine
from utils.logger import get_logger

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

ETL_SCHEMA    = os.getenv("ETL_SCHEMA",  "public")      # ← public schema
ETL_TS_COL    = os.getenv("ETL_TS_COL",  "updated_at")  # incremental timestamp
ETL_PK_SUFFIX = os.getenv("ETL_PK_SUFFIX", "_id")       # heuristic PK suffix

JDBC_JAR_PATH = os.getenv(
    "JDBC_JAR_PATH",
    str(_root / "driver" / "postgresql.jar"),   # matches your driver/ folder
)

if not Path(JDBC_JAR_PATH).is_file():
    raise FileNotFoundError(
        f"\n\nPostgreSQL JDBC JAR not found at:\n  {JDBC_JAR_PATH}\n\n"
        "Fix options:\n"
        "  1. Place the JAR at the path above (driver/postgresql.jar)\n"
        "  2. Or point to an existing JAR via env var:\n"
        "       Windows : set JDBC_JAR_PATH=C:\\path\\to\\postgresql-42.x.x.jar\n"
        "       Mac/Linux: export JDBC_JAR_PATH=/path/to/postgresql-42.x.x.jar\n"
        "  Download from: https://jdbc.postgresql.org/download/\n"
    )

ISO_FMT  = "%Y-%m-%dT%H:%M:%S"
JDBC_URL = (
    f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
)

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

# ─────────────────────────────────────────────────────────────────────────────
# Column detection
# ─────────────────────────────────────────────────────────────────────────────

def detect_pk_col(columns: list[str], collection: str, log) -> str | None:
    """
    Heuristic PK detection from slugified column names.

    Priority:
      1. Exact match for the collection name + '_id'
         e.g.  collection='artist'  → 'artist_id'
      2. Any column that ends with '_id'
      3. Exact column named 'id'

    Returns the column name or None if nothing matches.
    """
    slug  = _slugify(collection)
    exact = f"{slug}_id"

    if exact in columns:
        log.info("PK DETECT : '%s'  (exact match for collection name)", exact)
        return exact

    candidates = [c for c in columns if c.endswith("_id")]
    if candidates:
        log.info("PK DETECT : '%s'  (first *_id column)", candidates[0])
        return candidates[0]

    if "id" in columns:
        log.info("PK DETECT : 'id'  (fallback)")
        return "id"

    log.warning("PK DETECT : no PK column found in %s — will use row-hash dedup", collection)
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
    skip      = set(exclude_cols or []) | {"_row_hash"}
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
    os.environ["PYSPARK_PYTHON"]        = os.getenv("PYSPARK_PYTHON",        sys.executable)
    os.environ["PYSPARK_DRIVER_PYTHON"] = os.getenv("PYSPARK_DRIVER_PYTHON", sys.executable)

    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.driver.extraClassPath",     JDBC_JAR_PATH)
        .config("spark.executor.extraClassPath",   JDBC_JAR_PATH)
        .config("spark.driver.extraJavaOptions",   "--add-modules jdk.incubator.vector")
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
        coll   = client[MONGO_DB][collection]
        count  = coll.count_documents({})
        max_ts = None

        if ts_col_raw:
            # Aggregate pipeline: $group → $max
            pipeline = [{"$group": {"_id": None, "max_ts": {"$max": f"${ts_col_raw}"}}}]
            result   = list(coll.aggregate(pipeline))
            if result and result[0].get("max_ts"):
                max_ts = result[0]["max_ts"]

        client.close()
        log.info(
            "MONGO STATS : %s  count=%d  max_ts=%s",
            collection, count,
            max_ts.strftime(ISO_FMT) if max_ts else "N/A",
        )
        return {"count": count, "max_ts": max_ts}

    except Exception as exc:
        log.error("Failed to get Mongo stats for '%s': %s", collection, exc)
        return {"count": 0, "max_ts": None}


def read_mongo_incremental(
    spark: SparkSession,
    collection: str,
    ts_col_raw: str | None,
    pg_max_ts: datetime | None,
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
        coll   = client[MONGO_DB][collection]

        mongo_filter: dict = {}
        if ts_col_raw and pg_max_ts:
            mongo_filter = {ts_col_raw: {"$gt": pg_max_ts}}
            log.info(
                "MONGO READ  : %s  filter → %s > %s",
                collection, ts_col_raw, pg_max_ts.strftime(ISO_FMT),
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

        # Preserve NaN/None as SQL NULL  (do not cast None → string "None")
        for col in pdf.columns:
            pdf[col] = pdf[col].where(pdf[col].isna(), pdf[col].astype(str))

        sdf = spark.createDataFrame(pdf)
        log.info(
            "MONGO READ  : %s  →  %d docs  |  cols: %s",
            collection, len(docs), sdf.columns,
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
            exists = conn.execute(text("""
                SELECT 1
                FROM   information_schema.tables
                WHERE  table_schema = :schema
                AND    table_name   = :table
            """), {"schema": schema, "table": table}).fetchone()

            if not exists:
                log.info("PG STATS    : %s.%s does not exist yet", schema, table)
                return result

            result["table_exists"] = True
            result["count"] = conn.execute(
                text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            ).scalar() or 0

            if ts_col:
                # Check that the ts_col column actually exists in Postgres
                col_exists = conn.execute(text("""
                    SELECT 1
                    FROM   information_schema.columns
                    WHERE  table_schema  = :schema
                    AND    table_name    = :table
                    AND    column_name   = :col
                """), {"schema": schema, "table": table, "col": ts_col}).fetchone()

                if col_exists:
                    row = conn.execute(
                        text(f'SELECT MAX("{ts_col}") FROM "{schema}"."{table}"')
                    ).fetchone()
                    if row and row[0]:
                        result["max_ts"] = row[0]   # returns a datetime object

        log.info(
            "PG STATS    : %s.%s  count=%d  max_ts=%s",
            schema, table, result["count"],
            result["max_ts"].strftime(ISO_FMT) if result["max_ts"] else "N/A",
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
            mongo_stats["count"], pg_stats["count"],
        )
        return True

    if ts_col and mongo_stats["max_ts"] and pg_stats["max_ts"]:
        if mongo_stats["max_ts"] > pg_stats["max_ts"]:
            log.info(
                "DECISION    : Mongo max_ts (%s) > PG max_ts (%s) → LOAD",
                mongo_stats["max_ts"], pg_stats["max_ts"],
            )
            return True

    log.info(
        "DECISION    : no changes detected (Mongo count=%d, PG count=%d) → SKIP",
        mongo_stats["count"], pg_stats["count"],
    )
    return False

# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL write helpers
# ─────────────────────────────────────────────────────────────────────────────

def ensure_schema(conn, schema: str, log) -> None:
    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    log.info("Schema ready → %s", schema)


def ensure_target_table(
    conn, schema: str, table: str,
    columns: list[str], pk_col: str | None, log,
) -> None:
    """
    CREATE TABLE IF NOT EXISTS with a UNIQUE constraint on pk_col (or _row_hash
    for no-PK collections).  Also applies schema evolution (ALTER TABLE ADD COLUMN)
    so new MongoDB fields are automatically added to the Postgres table.
    """
    col_defs = ",\n    ".join(f'"{c}" TEXT' for c in columns)

    if pk_col and pk_col in columns:
        unique_clause = (
            f',\n    CONSTRAINT "{table}_{pk_col}_uq" UNIQUE ("{pk_col}")'
        )
    else:
        unique_clause = (
            f',\n    CONSTRAINT "{table}_row_hash_uq" UNIQUE ("_row_hash")'
        )

    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (
            _etl_id  SERIAL,
            {col_defs}{unique_clause}
        )
    """))

    # Schema evolution: add any columns that are new since the last run
    existing = {
        row[0]
        for row in conn.execute(text("""
            SELECT column_name
            FROM   information_schema.columns
            WHERE  table_schema = :schema
            AND    table_name   = :table
        """), {"schema": schema, "table": table})
    }
    for col in columns:
        if col not in existing:
            conn.execute(text(
                f'ALTER TABLE "{schema}"."{table}" ADD COLUMN "{col}" TEXT'
            ))
            log.info(
                "Schema evolution → added column '%s' to %s.%s", col, schema, table
            )

    log.info("Table ready → %s.%s  (pk=%s)", schema, table, pk_col or "row_hash")


def merge_staging_to_target(
    conn, schema: str, table: str,
    staging: str, columns: list[str],
    pk_col: str | None, log,
) -> int:
    """
    INSERT … SELECT from staging into the target table.
      Has-PK  → ON CONFLICT (pk_col)   DO UPDATE SET …   (upsert)
      No-PK   → ON CONFLICT (_row_hash) DO NOTHING        (dedup)
    Returns the row count of the staging table (= rows attempted).
    """
    col_list = ", ".join(f'"{c}"' for c in columns)

    if pk_col and pk_col in columns:
        update_set = ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in columns if c != pk_col
        ) or f'"{pk_col}" = EXCLUDED."{pk_col}"'
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {col_list} FROM "{schema}"."{staging}"
            ON CONFLICT ("{pk_col}") DO UPDATE SET {update_set}
        """
    else:
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {col_list} FROM "{schema}"."{staging}"
            ON CONFLICT ("_row_hash") DO NOTHING
        """

    conn.execute(text(sql))
    count = conn.execute(
        text(f'SELECT COUNT(*) FROM "{schema}"."{staging}"')
    ).scalar()
    log.info("MERGE       : %d rows → %s.%s", count, schema, table)
    return count


def drop_staging(conn, schema: str, staging: str, log) -> None:
    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{staging}"'))
    log.debug("Staging dropped → %s.%s", schema, staging)


def truncate_table(conn, schema: str, table: str, log) -> None:
    conn.execute(text(f'TRUNCATE TABLE "{schema}"."{table}" RESTART IDENTITY'))
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
    log    = get_logger(stage="extraction", name=collection)
    table  = _slugify(collection)
    schema = ETL_SCHEMA
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    staging = _staging_name(table, run_id)

    base = dict(
        collection=collection,
        rows_mongo=0, rows_new=0, rows_loaded=0,
        skipped=False, failed=0,
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

    raw_columns  = list(pd.DataFrame(sample).columns)
    slug_columns = [_slugify(c) for c in raw_columns]

    # Detect PK and TS column from slugified names
    pk_col  = detect_pk_col(slug_columns, collection, log)
    ts_col  = detect_ts_col(slug_columns, log)

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
    columns = sdf.columns  # refresh after adding loaded_at

    # Dedup on pk_col (guard against duplicate source docs)
    if pk_col and pk_col in columns:
        before = sdf.count()
        sdf    = sdf.dropDuplicates([pk_col])
        dupes  = before - sdf.count()
        if dupes > 0:
            log.warning(
                "DEDUP       : removed %d duplicate '%s' values in '%s'",
                dupes, pk_col, collection,
            )
            rows_new = sdf.count()
            base["rows_new"] = rows_new

    # Row-hash dedup for no-PK collections
    if pk_col is None:
        sdf     = _add_row_hash(sdf, exclude_cols=["loaded_at"])
        columns = sdf.columns
        log.info("ROW HASH    : added _row_hash column for no-PK dedup")

    # ── Ensure schema exists before JDBC write ─────────────────────────────
    try:
        with engine.connect() as _conn:
            with _conn.begin():
                ensure_schema(_conn, schema, log)
    except Exception as exc:
        log.error("Could not create schema '%s': %s", schema, exc)
        base["failed"] = rows_new
        return base

    # ── Step 6: Write to staging via JDBC ──────────────────────────────────
    log.info("JDBC WRITE  : %d rows → %s.%s", rows_new, schema, staging)
    try:
        (
            sdf.write
            .format("jdbc")
            .option("url",           JDBC_URL)
            .option("dbtable",       f'"{schema}"."{staging}"')
            .option("user",          POSTGRES_USERNAME)
            .option("password",      POSTGRES_PASSWORD)
            .option("driver",        "org.postgresql.Driver")
            .option("batchsize",     "5000")
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
        with engine.connect() as conn:
            with conn.begin():
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
            with engine.connect() as conn:
                with conn.begin():
                    drop_staging(conn, schema, staging, log)
        except Exception:
            pass
        base["failed"] = rows_new
        return base

    log.info(
        "DONE        : mongo=%d  new=%d  loaded=%d  failed=%d",
        base["rows_mongo"], base["rows_new"], base["rows_loaded"], base["failed"],
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

    spark  = get_spark()
    engine = postgres_engine()

    # Verify Postgres connectivity before processing any collection
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    log.info("Postgres connected ✓")

    summaries: list[dict] = []
    for col in collections:
        summary = process_collection(col, spark, engine, full_load=full_load)
        summaries.append(summary)

    spark.stop()
    engine.dispose()
    log.info("Spark stopped. Engine disposed.")

    # ── Run summary ────────────────────────────────────────────────────────
    log.info("")
    log.info("══════════════  RUN SUMMARY  ══════════════")
    totals = dict(rows_mongo=0, rows_new=0, rows_loaded=0, failed=0)
    skipped_count = 0

    for s in summaries:
        status = "SKIPPED" if s.get("skipped") else "LOADED"
        log.info(
            "%-20s  [%s]  mongo=%-6d  new=%-6d  loaded=%-6d  failed=%d",
            s["collection"], status,
            s.get("rows_mongo", 0), s.get("rows_new", 0),
            s.get("rows_loaded", 0), s.get("failed", 0),
        )
        for k in totals:
            totals[k] += s.get(k, 0)
        if s.get("skipped"):
            skipped_count += 1

    log.info("─" * 60)
    log.info(
        "TOTAL  collections=%-3d  skipped=%-3d  mongo=%-6d  "
        "new=%-6d  loaded=%-6d  failed=%d",
        len(summaries), skipped_count,
        totals["rows_mongo"], totals["rows_new"],
        totals["rows_loaded"], totals["failed"],
    )
    log.info("═" * 60)

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