"""Tests for src/pipeline/decision.py."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from src.pipeline.decision import needs_load

logger = logging.getLogger("test")


def test_needs_load_table_does_not_exist():
    mongo = {"count": 10, "max_ts": None}
    pg = {"count": 0, "max_ts": None, "table_exists": False}
    assert needs_load(mongo, pg, "updated_at", logger) is True


def test_needs_load_count_increased():
    mongo = {"count": 15, "max_ts": None}
    pg = {"count": 10, "max_ts": None, "table_exists": True}
    assert needs_load(mongo, pg, "updated_at", logger) is True


def test_needs_load_timestamps_naive_and_aware():
    # Crucial regression test: Mongo naive UTC vs Postgres aware UTC
    now_naive = datetime(2026, 6, 15, 12, 0, 0)  # noqa: DTZ001
    older_aware = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)

    mongo = {"count": 10, "max_ts": now_naive}
    pg = {"count": 10, "max_ts": older_aware, "table_exists": True}
    assert needs_load(mongo, pg, "updated_at", logger) is True


def test_needs_load_pg_ts_none():
    mongo = {"count": 10, "max_ts": datetime(2026, 6, 15, 12, 0, 0)}  # noqa: DTZ001
    pg = {"count": 10, "max_ts": None, "table_exists": True}
    assert needs_load(mongo, pg, "updated_at", logger) is True


def test_needs_load_no_changes():
    dt = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)
    mongo = {"count": 10, "max_ts": dt}
    pg = {"count": 10, "max_ts": dt, "table_exists": True}
    assert needs_load(mongo, pg, "updated_at", logger) is False


def test_needs_load_no_ts_col_equal_counts():
    mongo = {"count": 10, "max_ts": None}
    pg = {"count": 10, "max_ts": None, "table_exists": True}
    assert needs_load(mongo, pg, None, logger) is False
