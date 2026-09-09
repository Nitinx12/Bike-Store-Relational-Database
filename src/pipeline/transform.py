"""
src/pipeline/transform.py

Column-name normalisation, PK/timestamp-column detection, and typed-column
support for collections whose schema isn't declared anywhere — MongoDB
documents don't carry a schema, so this is the pipeline's substitute for one.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations

import re

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from src.pipeline.config import ETL_TS_COL

# Composite (multi-column) primary key overrides — (table_slug, columns)
COMPOSITE_PK: dict[str, tuple[str, ...]] = {
    "stocks": ("store_id", "product_id"),
    "order_items": ("order_id", "item_id"),
}

# Column type map  (table_slug, column) → Postgres type string.
# Columns not in this map default to TEXT.
COLUMN_TYPE_MAP: dict[tuple[str, str], str] = {
    # primary & foreign keys (bigint)
    ("brands", "brand_id"): "BIGINT",
    ("categories", "category_id"): "BIGINT",
    ("customers", "customer_id"): "BIGINT",
    ("stores", "store_id"): "BIGINT",
    ("staffs", "staff_id"): "BIGINT",
    ("staffs", "store_id"): "BIGINT",
    ("staffs", "manager_id"): "BIGINT",
    ("products", "product_id"): "BIGINT",
    ("products", "brand_id"): "BIGINT",
    ("products", "category_id"): "BIGINT",
    ("stocks", "store_id"): "BIGINT",
    ("stocks", "product_id"): "BIGINT",
    ("orders", "order_id"): "BIGINT",
    ("orders", "customer_id"): "BIGINT",
    ("orders", "store_id"): "BIGINT",
    ("orders", "staff_id"): "BIGINT",
    ("order_items", "order_id"): "BIGINT",
    ("order_items", "item_id"): "BIGINT",
    ("order_items", "product_id"): "BIGINT",
    # timestamps / dates
    ("brands", "updated_at"): "TIMESTAMPTZ",
    ("categories", "updated_at"): "TIMESTAMPTZ",
    ("customers", "updated_at"): "TIMESTAMPTZ",
    ("order_items", "updated_at"): "TIMESTAMPTZ",
    ("orders", "order_date"): "DATE",
    ("orders", "required_date"): "DATE",
    ("orders", "shipped_date"): "DATE",
    ("orders", "updated_at"): "TIMESTAMPTZ",
    ("products", "updated_at"): "TIMESTAMPTZ",
    ("staffs", "updated_at"): "TIMESTAMPTZ",
    ("stocks", "updated_at"): "TIMESTAMPTZ",
    ("stores", "updated_at"): "TIMESTAMPTZ",
    # numeric / boolean / text
    ("customers", "zip_code"): "BIGINT",
    ("stores", "zip_code"): "BIGINT",
    ("staffs", "active"): "SMALLINT",
    ("products", "model_year"): "SMALLINT",
    ("products", "list_price"): "NUMERIC(10,2)",
    ("stocks", "quantity"): "BIGINT",
    ("order_items", "quantity"): "BIGINT",
    ("order_items", "list_price"): "NUMERIC(10,2)",
    ("order_items", "discount"): "NUMERIC(4,2)",
    ("order_items", "total_value"): "NUMERIC(14,2)",
}


def slugify(s: str) -> str:
    """Normalise a field name to a safe Postgres column identifier."""
    s = str(s).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"[^\w]", "", s)
    return re.sub(r"_+", "_", s).strip("_") or "col"


PkCol = str | tuple[str, ...] | None


def detect_pk_col(
    columns: list[str], collection: str, log
) -> str | tuple[str, ...] | None:
    """
    Heuristic PK detection from slugified column names.

    Priority:
      1. Explicit composite-PK override in COMPOSITE_PK (e.g. stocks, order_items)
      2. Singular or exact match for collection name + '_id' (e.g. 'brands' → 'brand_id')
      3. Any column that ends with '_id'
      4. Exact column named 'id'

    Returns a single column, a tuple for composites, or None.
    """
    slug = slugify(collection)

    composite = COMPOSITE_PK.get(slug)
    if composite and all(c in columns for c in composite):
        log.info("PK DETECT : %s  (composite key from COMPOSITE_PK)", list(composite))
        return tuple(composite)

    # Singular form heuristic: 'categories' -> 'category_id', 'brands' -> 'brand_id'
    singular = slug
    if slug.endswith("ies"):
        singular = slug[:-3] + "y"
    elif slug.endswith("s"):
        singular = slug[:-1]

    singular_exact = f"{singular}_id"
    if singular_exact in columns:
        log.info("PK DETECT : '%s'  (singular match for collection name)", singular_exact)
        return singular_exact

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
