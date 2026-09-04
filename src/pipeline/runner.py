"""
src/pipeline/runner.py

Orchestrates one full ETL pass: for every requested MongoDB collection,
peek → compare → (maybe) extract → stage → merge. This module returns
plain data (dicts) — it never prints to a console or calls sys.exit.
Presentation (Rich banners/progress/tables) and process exit codes live
in scripts/mongo_to_postgres.py, so run_pipeline() can equally be called
from a test, a notebook, or an Airflow task later without dragging a
terminal UI along with it.

Optional on_start / on_collection_done callbacks let a caller (like the
CLI script) hook in a progress bar without this module knowing Rich exists.
"""
from __future__ import annotations

import traceback
from datetime import datetime

import pandas as pd
from pymongo import MongoClient
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from sqlalchemy import text

from utils.connection import MONGO_URI, MONGO_DB, POSTGRES_USERNAME, POSTGRES_PASSWORD
from utils.engine import postgres_engine
from utils.logger import get_logger

from src.database.jdbc_writer import write_to_staging
from src.database.schema import ensure_schema, ensure_target_table
from src.database.staging import staging_name, merge_staging_to_target, drop_staging, truncate_table
from src.database.stats import get_postgres_stats
from src.pipeline.config import ETL_SCHEMA, ISO_FMT, JDBC_URL
from src.pipeline.decision import needs_load
from src.pipeline.mongo_source import mongo_collection_stats, read_mongo_incremental
from src.pipeline.spark_session import get_spark
from src.pipeline.transform import add_row_hash, detect_pk_col, detect_ts_col, slugify


def process_collection(
    collection: str,
    spark: SparkSession,
    engine,
    full_load: bool = False,
) -> dict:
    """
    Incremental load for one MongoDB collection into the target schema.

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
    log     = get_logger(stage="extraction", name=collection)
    table   = slugify(collection)
    schema  = ETL_SCHEMA
    run_id  = datetime.now().strftime("%Y%m%d%H%M%S")
    staging = staging_name(table, run_id)

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
    slug_columns = [slugify(c) for c in raw_columns]

    pk_col = detect_pk_col(slug_columns, collection, log)
    ts_col = detect_ts_col(slug_columns, log)

    ts_col_raw: str | None = None
    if ts_col:
        for raw, slug in zip(raw_columns, slug_columns):
            if slug == ts_col:
                ts_col_raw = raw
                break

    # ── Step 2: Mongo stats ────────────────────────────────────────────────
    mongo_stats = mongo_collection_stats(collection, ts_col_raw, log)
    base["rows_mongo"] = mongo_stats["count"]

    if mongo_stats["count"] == 0:
        log.warning("Collection '%s' is empty — skipping", collection)
        base["skipped"] = True
        return base

    # ── Step 3: Postgres stats ──────────────────────────────────────────────
    pg_stats = get_postgres_stats(engine, schema, table, ts_col, log)

    # ── Step 4: Decide whether to load ──────────────────────────────────────
    if not full_load and not needs_load(mongo_stats, pg_stats, ts_col, log):
        log.info("SKIP        : %s — no new data detected", collection)
        base["skipped"] = True
        return base

    if full_load:
        log.info("FULL REFRESH: ignoring comparison, will truncate and reload")

    # ── Step 5: Read incremental delta from Mongo ───────────────────────────
    pg_max_ts = None if full_load else pg_stats.get("max_ts")
    sdf = read_mongo_incremental(spark, collection, ts_col_raw, pg_max_ts, log)
    if sdf is None:
        log.info("No new rows returned from Mongo — skipping %s", collection)
        base["skipped"] = True
        return base

    rows_new = sdf.count()
    base["rows_new"] = rows_new
    log.info("DELTA       : %d rows to load", rows_new)

    sdf = sdf.withColumn(
        "loaded_at",
        F.lit(datetime.now().strftime(ISO_FMT)).cast("timestamp"),
    )
    columns = sdf.columns

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
        sdf     = add_row_hash(sdf, exclude_cols=["loaded_at"])
        columns = sdf.columns
        log.info("ROW HASH    : added _row_hash column for no-PK dedup")

    # ── Ensure schema exists before JDBC write ──────────────────────────────
    try:
        with engine.connect() as _conn:
            with _conn.begin():
                ensure_schema(_conn, schema, log)
    except Exception as exc:
        log.error("Could not create schema '%s': %s", schema, exc)
        base["failed"] = rows_new
        return base

    # ── Step 6: Write to staging via JDBC ───────────────────────────────────
    try:
        write_to_staging(sdf, schema, staging, rows_new, JDBC_URL, POSTGRES_USERNAME, POSTGRES_PASSWORD, log)
    except Exception as exc:
        log.error("JDBC staging write failed: %s", exc)
        log.debug(traceback.format_exc())
        base["failed"] = rows_new
        return base

    # ── Step 7: Merge staging → target table ────────────────────────────────
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
                # ── Step 8: Drop staging ────────────────────────────────────
                drop_staging(conn, schema, staging, log)

        base["rows_loaded"] = rows_loaded

    except Exception as exc:
        log.error("Merge failed for '%s': %s", collection, exc)
        log.debug(traceback.format_exc())
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


def run_pipeline(
    collections: list[str] | None = None,
    full_load: bool = False,
    on_start=None,
    on_collection_done=None,
) -> dict:
    """
    Runs a full pass over `collections` (auto-discovered from MongoDB if
    empty) and returns:

        {"summaries": [...], "totals": {...}, "skipped_count": int,
         "collections": [...], "mode": "INCREMENTAL" | "FULL REFRESH"}

    `on_start(collections, mode)` fires once, right after collection
    discovery — useful for printing a banner or sizing a progress bar.
    `on_collection_done(collection, summary)` fires after each collection
    — useful for advancing a progress bar. Both are optional.
    """
    log = get_logger(stage="extraction", name="mongo_public_main")

    if not collections:
        with MongoClient(MONGO_URI) as client:
            collections = client[MONGO_DB].list_collection_names()
        log.info("Discovered %d collections: %s", len(collections), collections)

    mode = "FULL REFRESH" if full_load else "INCREMENTAL"
    log.info("Collections : %d", len(collections))
    log.info("Mode        : %s", mode)

    if on_start:
        on_start(collections, mode)

    spark  = get_spark()
    engine = postgres_engine()

    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    log.info("Postgres connected ✓")

    summaries: list[dict] = []
    for col in collections:
        summary = process_collection(col, spark, engine, full_load=full_load)
        summaries.append(summary)
        if on_collection_done:
            on_collection_done(col, summary)

    spark.stop()
    engine.dispose()
    log.info("Spark stopped. Engine disposed.")

    totals = dict(rows_mongo=0, rows_new=0, rows_loaded=0, failed=0)
    skipped_count = 0
    for s in summaries:
        for k in totals:
            totals[k] += s.get(k, 0)
        if s.get("skipped"):
            skipped_count += 1

    log.info(
        "RUN SUMMARY : collections=%d skipped=%d mongo=%d new=%d loaded=%d failed=%d",
        len(summaries), skipped_count,
        totals["rows_mongo"], totals["rows_new"],
        totals["rows_loaded"], totals["failed"],
    )

    return {
        "summaries": summaries,
        "totals": totals,
        "skipped_count": skipped_count,
        "collections": collections,
        "mode": mode,
    }
