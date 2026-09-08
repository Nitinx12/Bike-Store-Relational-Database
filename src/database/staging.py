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
    conn,
    schema: str,
    table: str,
    staging: str,
    columns: list[str],
    pk_col: str | tuple[str, ...] | list[str] | None,
    log,
) -> int:
    """
    INSERT … SELECT from staging into the target table.
      Has-PK  → ON CONFLICT (pk_col[, ...]) DO UPDATE SET …   (upsert)
      No-PK   → ON CONFLICT (_row_hash) DO NOTHING        (dedup)
    Returns rows inserted/updated (source: staging row count / rowcount).
    """
    col_list = ", ".join(f'"{c}"' for c in columns)

    if isinstance(pk_col, (list, tuple)):
        pk_cols = [c for c in pk_col if c in columns]
    elif pk_col and pk_col in columns:
        pk_cols = [pk_col]
    else:
        pk_cols = []
    if pk_cols:
        conflict = ", ".join(f'"{c}"' for c in pk_cols)
        update_set = (
            ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns if c not in pk_cols)
            or f'"{pk_cols[0]}" = EXCLUDED."{pk_cols[0]}"'
        )
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {col_list} FROM "{schema}"."{staging}"
            ON CONFLICT ({conflict}) DO UPDATE SET {update_set}
        """
    else:
        sql = f"""
            INSERT INTO "{schema}"."{table}" ({col_list})
            SELECT {col_list} FROM "{schema}"."{staging}"
            ON CONFLICT ("_row_hash") DO NOTHING
        """

    result = conn.execute(text(sql))
    try:
        count = result.rowcount
    except Exception:  # noqa: BLE001 - rowcount may raise per DBAPI
        count = None
    if count is None or count < 0:
        count = conn.execute(
            text(f'SELECT COUNT(*) FROM "{schema}"."{staging}"')
        ).scalar() or 0
    log.info("MERGE       : %d rows → %s.%s", count, schema, table)
    return int(count)


def drop_staging(conn, schema: str, staging: str, log) -> None:
    conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{staging}"'))
    log.debug("Staging dropped → %s.%s", schema, staging)


def truncate_table(conn, schema: str, table: str, log) -> None:
    conn.execute(text(f'TRUNCATE TABLE "{schema}"."{table}" RESTART IDENTITY'))
    log.info("TRUNCATED   → %s.%s  (full-refresh)", schema, table)
