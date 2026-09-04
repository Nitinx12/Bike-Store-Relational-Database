"""
src/pipeline/decision.py

The one function that decides whether a collection needs loading at all.
Kept isolated from I/O so the load/skip rule can be unit-tested against
plain dicts without a live Mongo or Postgres connection.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations


def needs_load(mongo_stats: dict, pg_stats: dict, ts_col: str | None, log) -> bool:
    """
    Rules:
      1. Target table doesn't exist in Postgres        → always load
      2. Mongo count > Postgres count                  → new rows added, load
      3. ts_col present AND Mongo max_ts > PG max_ts    → newer records exist, load
      4. Otherwise                                      → nothing changed, skip
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
        if mongo_stats["max_ts"] > pg_stats["max_ts"]:
            log.info(
                "DECISION    : Mongo max_ts (%s) > PG max_ts (%s) → LOAD",
                mongo_stats["max_ts"],
                pg_stats["max_ts"],
            )
            return True

    log.info(
        "DECISION    : no changes detected (Mongo count=%d, PG count=%d) → SKIP",
        mongo_stats["count"],
        pg_stats["count"],
    )
    return False
