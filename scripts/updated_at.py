import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=os.getenv("POSTGRES_PORT"),
    database=os.getenv("POSTGRES_DATABASE"),
    user=os.getenv("POSTGRES_USERNAME"),
    password=os.getenv("POSTGRES_PASSWORD")
)

cur = conn.cursor()

# Create trigger function
cur.execute("""
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")

# Get all tables in public schema
cur.execute("""
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE';
""")

tables = [row[0] for row in cur.fetchall()]

for table in tables:
    print(f"Processing {table}")

    cur.execute(f"""
    ALTER TABLE public.{table}
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """)

    cur.execute(f"""
    DROP TRIGGER IF EXISTS trg_{table}_updated_at
    ON public.{table};
    """)

    cur.execute(f"""
    CREATE TRIGGER trg_{table}_updated_at
    BEFORE UPDATE ON public.{table}
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
    """)

conn.commit()
cur.close()
conn.close()

print("Done.")