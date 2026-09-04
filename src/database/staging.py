"""
src/database/staging.py

Staging-table lifecycle: naming, merge (upsert/dedup) into the target
table, truncate for full-refresh runs, and cleanup.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""
from __future__ import annotations

from sqlalchemy import text


def staging_name(table: str, run_id: str) -> str:
    return f"{table}_staging_{run_id}"


def merge_staging_to_target(
    conn, schema: str, table: str,
    staging: str, columns: list[str],
    pk_col: str | None, log,
) -> int:
    """
    INSERT … SELECT from staging into the target table.
      Has-PK  → ON CONFLICT (pk_col)   DO UPDATE SET …   (upsert)
      No-PK   → ON CONFLICT (_row_hash) DO NOTHING        (dedup)
    Returns the row count of the staging table (= rows attempted).
    """
    col_list = ", ".join(f'"{c}"' for c in columns)

    if pk_col and pk_col in columns:
        update_set = ", ".join(
            f'"{c}" = EXCLUDED."{c}"' for c in columns if c != pk_col
        ) or f'"{pk_col}" = EXCLUDED."{pk_col}"'
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {col_list} FROM "{schema}"."{staging}"
            ON CONFLICT ("{pk_col}") DO UPDATE SET {update_set}
        """
    else:
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {col_list} FROM "{schema}"."{staging}"
            ON CONFLICT ("_row_hash") DO NOTHING
        """

    conn.execute(text(sql))
    count = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{staging}"')).scalar()
    log.info("MERGE       : %d rows → %s.%s", count, schema, table)
    return count


def drop_staging(conn, schema: str, staging: str, log) -> None:
    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{staging}"'))
    log.debug("Staging dropped → %s.%s", schema, staging)


def truncate_table(conn, schema: str, table: str, log) -> None:
    conn.execute(text(f'TRUNCATE TABLE "{schema}"."{table}" RESTART IDENTITY'))
    log.info("TRUNCATED   → %s.%s  (full-refresh)", schema, table)
