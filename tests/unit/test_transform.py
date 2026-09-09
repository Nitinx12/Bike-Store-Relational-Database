"""Tests for src/pipeline/transform.py."""

from __future__ import annotations

import logging

from src.pipeline.transform import detect_pk_col, detect_ts_col, slugify

logger = logging.getLogger("test")


def test_slugify_basic():
    assert slugify("Brand Name") == "brand_name"
    assert slugify("order-items") == "order_items"
    assert slugify("  CUSTOMER_ID  ") == "customer_id"
    assert slugify("special!@#chars$") == "specialchars"
    assert slugify("___extra__underscores___") == "extra_underscores"
    assert slugify("") == "col"


def test_detect_pk_col_composite():
    cols = ["store_id", "product_id", "quantity", "updated_at"]
    assert detect_pk_col(cols, "stocks", logger) == ("store_id", "product_id")

    item_cols = ["order_id", "item_id", "quantity", "list_price"]
    assert detect_pk_col(item_cols, "order_items", logger) == ("order_id", "item_id")


def test_detect_pk_col_singular_match():
    assert detect_pk_col(["brand_id", "brand_name"], "brands", logger) == "brand_id"
    assert detect_pk_col(["category_id", "category_name"], "categories", logger) == "category_id"
    assert detect_pk_col(["customer_id", "email"], "customers", logger) == "customer_id"
    assert detect_pk_col(["customer_id", "store_id", "order_id"], "orders", logger) == "order_id"


def test_detect_pk_col_fallback():
    assert detect_pk_col(["item_id", "desc"], "inventory", logger) == "item_id"
    assert detect_pk_col(["id", "desc"], "other", logger) == "id"
    assert detect_pk_col(["name", "desc"], "tags", logger) is None


def test_detect_ts_col():
    assert detect_ts_col(["order_id", "updated_at"], logger) == "updated_at"
    assert detect_ts_col(["order_id", "created_at"], logger) is None
