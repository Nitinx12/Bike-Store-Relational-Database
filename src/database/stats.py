"""
src/database/stats.py

Reads target-table state from Postgres (row count + MAX(ts_col)) so the
pipeline can decide whether a collection needs loading, without this
module ever touching MongoDB.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations

from sqlalchemy import text


def get_postgres_stats(
    engine, schema: str, table: str, ts_col: str | None, log
) -> dict:
    """Returns {"count": int, "max_ts": datetime | None, "table_exists": bool}."""
    result = {"count": 0, "max_ts": None, "table_exists": False}
    try:
        with engine.connect() as conn:
            exists = conn.execute(
                text("""
                SELECT 1
                FROM   information_schema.tables
                WHERE  table_schema = :schema
                AND    table_name   = :table
            """),
                {"schema": schema, "table": table},
            ).fetchone()

            if not exists:
                log.info("PG STATS    : %s.%s does not exist yet", schema, table)
                return result

            result["table_exists"] = True
            result["count"] = (
                conn.execute(
                    text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                ).scalar()
                or 0
            )

            if ts_col:
                col_exists = conn.execute(
                    text("""
                    SELECT 1
                    FROM   information_schema.columns
                    WHERE  table_schema  = :schema
                    AND    table_name    = :table
                    AND    column_name   = :col
                """),
                    {"schema": schema, "table": table, "col": ts_col},
                ).fetchone()

                if col_exists:
                    row = conn.execute(
                        text(f'SELECT MAX("{ts_col}") FROM "{schema}"."{table}"')
                    ).fetchone()
                    if row and row[0]:
                        result["max_ts"] = row[0]

        log.info(
            "PG STATS    : %s.%s  count=%d  max_ts=%s",
            schema,
            table,
            result["count"],
            result["max_ts"].isoformat() if result["max_ts"] else "N/A",
        )
    except Exception as exc:
        log.error("Failed to get Postgres stats for %s.%s: %s", schema, table, exc)

    return result
