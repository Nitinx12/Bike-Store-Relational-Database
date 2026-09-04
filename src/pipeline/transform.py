"""
src/pipeline/transform.py

Column-name normalisation and PK/timestamp-column detection for
collections whose schema isn't declared anywhere — MongoDB documents
don't carry a schema, so this is the pipeline's substitute for one.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations

import re

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.pipeline.config import ETL_TS_COL


def slugify(s: str) -> str:
    """Normalise a field name to a safe Postgres column identifier."""
    s = str(s).strip().lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"[\s\-]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_") or "col"


def detect_pk_col(columns: list[str], collection: str, log) -> str | None:
    """
    Heuristic PK detection from slugified column names.

    Priority:
      1. Exact match for the collection name + '_id'  e.g. 'artist' → 'artist_id'
      2. Any column that ends with '_id'
      3. Exact column named 'id'

    Returns the column name or None if nothing matches.
    """
    slug = slugify(collection)
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

    log.warning(
        "PK DETECT : no PK column found in %s — will use row-hash dedup", collection
    )
    return None


def detect_ts_col(columns: list[str], log) -> str | None:
    """Check whether ETL_TS_COL (default 'updated_at') is present."""
    ts = slugify(ETL_TS_COL)
    if ts in columns:
        log.info("TS DETECT  : '%s'  found ✓", ts)
        return ts
    log.warning(
        "TS DETECT  : '%s' not found — will skip incremental comparison "
        "and fall back to full-snapshot upsert",
        ts,
    )
    return None


def add_row_hash(sdf: DataFrame, exclude_cols: list[str] | None = None) -> DataFrame:
    """
    Add a deterministic _row_hash TEXT column (MD5 of all data columns).
    Used as a surrogate unique key for no-PK collections so
    ON CONFLICT (_row_hash) DO NOTHING prevents duplicates on re-runs.
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
