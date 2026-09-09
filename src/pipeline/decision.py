"""
src/pipeline/decision.py

The one function that decides whether a collection needs loading at all.
Kept isolated from I/O so the load/skip rule can be unit-tested against
plain dicts without a live Mongo or Postgres connection.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any


def _normalize_ts(ts: Any) -> datetime | None:
    """Normalize any datetime/date/string timestamp to UTC-aware datetime."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC)
    if isinstance(ts, date):
        return datetime(ts.year, ts.month, ts.day, tzinfo=UTC)
    if isinstance(ts, str):
        try:
            cleaned = ts.removesuffix("Z")
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except (ValueError, TypeError):
            return None
    return None


def needs_load(
    mongo_stats: dict[str, Any],
    pg_stats: dict[str, Any],
    ts_col: str | None,
    log: logging.Logger,
) -> bool:
    """
    Rules:
      1. Target table doesn't exist in Postgres        → always load
      2. Mongo count > Postgres count                  → new rows added, load
      3. ts_col present AND Mongo max_ts > PG max_ts    → newer records exist, load
      4. Otherwise                                      → nothing changed, skip
    """
    if not pg_stats.get("table_exists", False):
        log.info("DECISION    : table absent in Postgres → LOAD (first run)")
        return True

    if int(mongo_stats.get("count", 0)) > int(pg_stats.get("count", 0)):
        log.info(
            "DECISION    : Mongo count (%d) > PG count (%d) → LOAD",
            mongo_stats.get("count", 0),
            pg_stats.get("count", 0),
        )
        return True

    if ts_col and mongo_stats.get("max_ts"):
        m_ts = _normalize_ts(mongo_stats["max_ts"])
        p_ts = _normalize_ts(pg_stats.get("max_ts"))
        if m_ts and (p_ts is None or m_ts > p_ts):
            log.info(
                "DECISION    : Mongo max_ts (%s) > PG max_ts (%s) → LOAD",
                mongo_stats["max_ts"],
                pg_stats.get("max_ts"),
            )
            return True

    log.info(
        "DECISION    : no changes detected (Mongo count=%d, PG count=%d) → SKIP",
        mongo_stats.get("count", 0),
        pg_stats.get("count", 0),
    )
    return False
