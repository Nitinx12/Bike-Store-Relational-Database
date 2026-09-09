"""
src/database/schema.py

DDL helpers: schema creation, target-table creation with an auto UNIQUE
constraint (pk_col or _row_hash), and additive schema evolution
(ALTER TABLE ADD COLUMN) when new fields show up in MongoDB.

Per-column Postgres types come from src.pipeline.transform.COLUMN_TYPE_MAP
so the schema matches the typed DDL produced by scripts/python/mongo_to_postgres.py.
Columns not in the map default to TEXT.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.pipeline.transform import COLUMN_TYPE_MAP


def _pg_type_for(table: str, col: str) -> str:
    """Look up the Postgres type for (table, col) in COLUMN_TYPE_MAP, default TEXT."""
    return COLUMN_TYPE_MAP.get((table, col), "TEXT")


def ensure_schema(conn, schema: str, log) -> None:
    """CREATE SCHEMA IF NOT EXISTS."""
    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    log.info("Schema ready → %s", schema)


def ensure_target_table(
    conn,
    schema: str,
    table: str,
    columns: list[str],
    pk_col: str | tuple[str, ...] | None,
    log,
) -> None:
    """
    CREATE TABLE IF NOT EXISTS with a UNIQUE constraint on pk_col (or
    _row_hash for no-PK collections). Also applies schema evolution
    (ALTER TABLE ADD COLUMN) so new MongoDB fields are automatically
    added to the Postgres table with their declared Postgres type.
    """
    col_defs = ",\n    ".join(f'"{c}" {_pg_type_for(table, c)}' for c in columns)

    if isinstance(pk_col, (list, tuple)):
        pk_cols = [c for c in pk_col if c in columns]
    elif pk_col and pk_col in columns:
        pk_cols = [pk_col]
    else:
        pk_cols = []
    if pk_cols:
        cols_sql = ", ".join(f'"{c}"' for c in pk_cols)
        unique_clause = (
            f',\n    CONSTRAINT "{table}_{"_".join(pk_cols)}_uq" UNIQUE ({cols_sql})'
        )
    else:
        unique_clause = f',\n    CONSTRAINT "{table}_row_hash_uq" UNIQUE ("_row_hash")'

    conn.execute(
        text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (
            _etl_id  SERIAL,
            {col_defs}{unique_clause}
        )
    """)
    )

    existing = {
        row[0]
        for row in conn.execute(
            text("""
            SELECT column_name
            FROM   information_schema.columns
            WHERE  table_schema = :schema
            AND    table_name   = :table
        """),
            {"schema": schema, "table": table},
        )
    }
    for col in columns:
        if col not in existing:
            pg_type = _pg_type_for(table, col)
            conn.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'ADD COLUMN "{col}" {pg_type}'
                )
            )
            log.info(
                "Schema evolution → added column '%s' (%s) to %s.%s",
                col,
                pg_type,
                schema,
                table,
            )

    # Type migration: promote existing TEXT columns to their target Postgres
    # type. One-time fix-up for tables created before COLUMN_TYPE_MAP existed
    # and now hold typed data in TEXT columns. Wrapped per-column in a
    # savepoint so one bad column doesn't abort the whole migration.
    type_rows = conn.execute(
        text("""
            SELECT column_name, data_type
            FROM   information_schema.columns
            WHERE  table_schema = :schema
            AND    table_name   = :table
        """),
        {"schema": schema, "table": table},
    ).fetchall()

    for col, actual_type in type_rows:
        if col == "_etl_id":
            continue
        target_type = _pg_type_for(table, col)
        if target_type == "TEXT":
            continue
        actual_norm = actual_type.lower().split("(")[0].strip()
        target_norm = target_type.lower().split("(")[0].strip()
        if actual_norm == target_norm:
            continue

        savepoint = f"sp_mig_{col}"
        try:
            conn.execute(text(f"SAVEPOINT {savepoint}"))
            conn.execute(
                text(
                    f'ALTER TABLE "{schema}"."{table}" '
                    f'ALTER COLUMN "{col}" TYPE {target_type} '
                    f'USING "{col}"::{target_type}'
                )
            )
            conn.execute(text(f"RELEASE SAVEPOINT {savepoint}"))
            log.info(
                "Type migration → %s.%s  %s → %s",
                schema,
                table,
                actual_type,
                target_type,
            )
        except SQLAlchemyError as exc:
            conn.execute(text(f"ROLLBACK TO SAVEPOINT {savepoint}"))
            log.warning(
                "Type migration FAILED for %s.%s (%s → %s): %s — column left as %s",
                schema,
                table,
                actual_type,
                target_type,
                exc,
                actual_type,
            )

    log.info("Table ready → %s.%s  (pk=%s)", schema, table, pk_col or "row_hash")
