-- one row per mongo collection load into public schema
CREATE TABLE IF NOT EXISTS public.etl_logs (
    log_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'INCREMENTAL',
    status TEXT NOT NULL DEFAULT 'STARTED',
    rows_mongo BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_failed BIGINT NOT NULL DEFAULT 0,
    mongo_max_ts TIMESTAMPTZ,
    pg_max_ts TIMESTAMPTZ,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    error_message TEXT
);

-- faster lookup by run and collection
CREATE INDEX IF NOT EXISTS idx_etl_logs_run_id ON public.etl_logs (run_id);
CREATE INDEX IF NOT EXISTS idx_etl_logs_collection ON public.etl_logs (collection_name, started_at DESC);
