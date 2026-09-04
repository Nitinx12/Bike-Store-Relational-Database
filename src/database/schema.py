"""
src/database/schema.py

DDL helpers: schema creation, target-table creation with an auto UNIQUE
constraint (pk_col or _row_hash), and additive schema evolution
(ALTER TABLE ADD COLUMN) when new fields show up in MongoDB.

Moved out of scripts/mongo_to_postgres.py unchanged in behaviour.
"""
from __future__ import annotations

from sqlalchemy import text


def ensure_schema(conn, schema: str, log) -> None:
    """CREATE SCHEMA IF NOT EXISTS."""
    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    log.info("Schema ready → %s", schema)


def ensure_target_table(
    conn, schema: str, table: str,
    columns: list[str], pk_col: str | None, log,
) -> None:
    """
    CREATE TABLE IF NOT EXISTS with a UNIQUE constraint on pk_col (or
    _row_hash for no-PK collections). Also applies schema evolution
    (ALTER TABLE ADD COLUMN) so new MongoDB fields are automatically
    added to the Postgres table.
    """
    col_defs = ",\n    ".join(f'"{c}" TEXT' for c in columns)

    if pk_col and pk_col in columns:
        unique_clause = f',\n    CONSTRAINT "{table}_{pk_col}_uq" UNIQUE ("{pk_col}")'
    else:
        unique_clause = f',\n    CONSTRAINT "{table}_row_hash_uq" UNIQUE ("_row_hash")'

    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS "{schema}"."{table}" (
            _etl_id  SERIAL,
            {col_defs}{unique_clause}
        )
    """))

    existing = {
        row[0]
        for row in conn.execute(text("""
            SELECT column_name
            FROM   information_schema.columns
            WHERE  table_schema = :schema
            AND    table_name   = :table
        """), {"schema": schema, "table": table})
    }
    for col in columns:
        if col not in existing:
            conn.execute(text(f'ALTER TABLE "{schema}"."{table}" ADD COLUMN "{col}" TEXT'))
            log.info(
                "Schema evolution → added column '%s' to %s.%s", col, schema, table
            )

    log.info("Table ready → %s.%s  (pk=%s)", schema, table, pk_col or "row_hash")
