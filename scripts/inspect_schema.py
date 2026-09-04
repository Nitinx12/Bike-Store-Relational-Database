"""
This script inspects the schema of a PostgreSQL database and prints the table names along with their columns and data types.
NOTE: Make sure to set the environment variables for the database connection before running this script.
NOTE: usage: uv run scripts/inspect_schema.py
"""

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.connection import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DATABASE,
    POSTGRES_USERNAME,
    POSTGRES_PASSWORD,
)

engine = create_engine(
    f"postgresql+psycopg2://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
)

query = """
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
"""
df = pd.read_sql(query, engine)

if df.empty:
    print("No tables found in the database.")

else:
    for table_name, group in df.groupby("table_name"):
        print(f"\nTable: {table_name}")
        print("-" * len(table_name))

        for _, row in group.iterrows():
            print(f" {row['column_name']:<30} {row['data_type']}")

engine.dispose()