-- last loaded point per mongo collection, next run pulls only newer rows
CREATE TABLE IF NOT EXISTS public.etl_watermarks (
    table_name TEXT PRIMARY KEY,
    collection_name TEXT NOT NULL,
    ts_col TEXT NOT NULL DEFAULT 'updated_at',
    last_max_ts TIMESTAMPTZ,
    last_mongo_count BIGINT,
    last_pg_count BIGINT,
    last_run_id TEXT,
    last_status TEXT NOT NULL DEFAULT 'SUCCESS',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- normal lookup by mongo collection name
CREATE INDEX IF NOT EXISTS idx_etl_watermarks_collection ON public.etl_watermarks (collection_name);
