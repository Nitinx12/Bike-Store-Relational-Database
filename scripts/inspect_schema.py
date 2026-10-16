"""
This script inspects the schema of a PostgreSQL database and prints the table names along with their columns and data types.
NOTE: Make sure to set the environment variables for the database connection before running this script.
NOTE: usage: uv run python scripts/inspect_schema.py
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.utils.connection import (
    DB_SCHEMA,
    postgres_url,
    require_pg_env,
)


def main() -> int:
    require_pg_env()
    engine = create_engine(postgres_url())
    try:
        query = f"""
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = '{DB_SCHEMA}'
    ORDER BY table_name, ordinal_position;
    """
        df = pd.read_sql(query, engine)

        if df.empty:
            print("No tables found in the database.")
        else:
            for table_name, group in df.groupby("table_name"):
                print(f"\nTable: {table_name}")
                print("-" * len(str(table_name)))

                for _, row in group.iterrows():
                    print(f" {row['column_name']:<30} {row['data_type']}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
