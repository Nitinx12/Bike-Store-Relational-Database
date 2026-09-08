"""
src/pipeline/mongo_source.py

All direct MongoDB access for the ETL: collection stats (count + max
timestamp) and the incremental/full-snapshot read itself.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations

import traceback
from datetime import UTC, date, datetime

import pandas as pd
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pyspark.sql import DataFrame, SparkSession

from src.pipeline.config import ISO_FMT
from src.pipeline.transform import slugify
from utils.connection import MONGO_DB, MONGO_URI


def to_iso(ts: datetime | date | str | None) -> str | None:
    """Normalise datetime/date/str watermark to ISO string. None stays None."""
    if ts is None:
        return None
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.strftime(ISO_FMT)
    if isinstance(ts, date):
        return datetime(ts.year, ts.month, ts.day, tzinfo=UTC).strftime(ISO_FMT)
    return str(ts)


def mongo_collection_stats(collection: str, ts_col_raw: str | None, log) -> dict:
    """Returns {"count": int, "max_ts": datetime | None}."""
    try:
        with MongoClient(MONGO_URI) as client:
            coll = client[MONGO_DB][collection]
            count = coll.count_documents({})
            max_ts = None

            if ts_col_raw:
                try:
                    pipeline = [
                        {"$group": {"_id": None, "max_ts": {"$max": f"${ts_col_raw}"}}}
                    ]
                    result = list(coll.aggregate(pipeline))
                    if result and result[0].get("max_ts"):
                        max_ts = result[0]["max_ts"]
                except (PyMongoError, AttributeError, TypeError, ValueError) as exc:
                    log.warning("Max-ts lookup failed for '%s': %s", collection, exc)

            try:
                max_ts_str = to_iso(max_ts) if max_ts else "N/A"
            except (AttributeError, TypeError, ValueError):
                max_ts_str = str(max_ts)
            log.info(
                "MONGO STATS : %s  count=%d  max_ts=%s",
                collection,
                count,
                max_ts_str,
            )
            return {"count": count, "max_ts": max_ts}

    except PyMongoError as exc:
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
    Reads from MongoDB via PyMongo.
      • pg_max_ts given + ts_col exists → WHERE ts_col > pg_max_ts (true delta)
      • otherwise                       → full snapshot (first run / fallback)
    Drops _id, slugifies column names, preserves NaN as NULL.
    """
    try:
        with MongoClient(MONGO_URI) as client:
            coll = client[MONGO_DB][collection]

            mongo_filter: dict = {}
            if ts_col_raw and pg_max_ts:
                mongo_filter = {ts_col_raw: {"$gt": pg_max_ts}}
                try:
                    pg_ts_str = to_iso(pg_max_ts)
                except (AttributeError, TypeError, ValueError):
                    pg_ts_str = str(pg_max_ts)
                log.info(
                    "MONGO READ  : %s  filter → %s > %s",
                    collection,
                    ts_col_raw,
                    pg_ts_str,
                )
            else:
                log.info("MONGO READ  : %s  filter → none (full snapshot)", collection)

            docs = list(coll.find(mongo_filter, {"_id": 0}))

        if not docs:
            log.info("MONGO READ  : %s  → 0 docs returned", collection)
            return None

        pdf = pd.DataFrame(docs)
        pdf.columns = [slugify(c) for c in pdf.columns]

        # Keep native dtypes (numeric/date); only normalise NaN/NaT → None
        # so Spark infers correct types instead of all-TEXT.
        pdf = pdf.where(pd.notnull(pdf), None)

        sdf = spark.createDataFrame(pdf)
        log.info(
            "MONGO READ  : %s  →  %d docs  |  cols: %s",
            collection,
            len(docs),
            sdf.columns,
        )
        return sdf

    except PyMongoError as exc:
        log.error("Failed to read collection '%s': %s", collection, exc)
        log.debug(traceback.format_exc())
        return None
