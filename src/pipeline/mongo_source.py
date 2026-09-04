"""
src/pipeline/mongo_source.py

All direct MongoDB access for the ETL: collection stats (count + max
timestamp) and the incremental/full-snapshot read itself.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""
from __future__ import annotations

import traceback
from datetime import datetime

import pandas as pd
from pymongo import MongoClient
from pyspark.sql import SparkSession, DataFrame

from utils.connection import MONGO_URI, MONGO_DB
from src.pipeline.config import ISO_FMT
from src.pipeline.transform import slugify


def mongo_collection_stats(collection: str, ts_col_raw: str | None, log) -> dict:
    """Returns {"count": int, "max_ts": datetime | None}."""
    try:
        client = MongoClient(MONGO_URI)
        coll   = client[MONGO_DB][collection]
        count  = coll.count_documents({})
        max_ts = None

        if ts_col_raw:
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
    Reads from MongoDB via PyMongo.
      • pg_max_ts given + ts_col exists → WHERE ts_col > pg_max_ts (true delta)
      • otherwise                       → full snapshot (first run / fallback)
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
        pdf.columns = [slugify(c) for c in pdf.columns]

        # Preserve NaN/None as SQL NULL (do not cast None → string "None")
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
