-- keeps watermarks in sync when a mongo load finishes
CREATE OR REPLACE FUNCTION public.fn_sync_etl_watermark()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- ignore in-progress runs, only react to finished ones
    IF NEW.status NOT IN ('SUCCESS', 'SKIPPED', 'FAILED') THEN
        RETURN NEW;
    END IF;

    -- stamp finish time if caller forgot it
    IF NEW.finished_at IS NULL THEN
        NEW.finished_at := now();
    END IF;

    -- create or move the mark forward, never backwards
    INSERT INTO public.etl_watermarks AS w (
        table_name, 
        collection_name, 
        last_max_ts,
        last_mongo_count, 
        last_pg_count,
        last_run_id, 
        last_status, 
        updated_at
    )
    VALUES (
        NEW.table_name, 
        NEW.collection_name,
        COALESCE(NEW.pg_max_ts, NEW.mongo_max_ts),
        NEW.rows_mongo, 
        NEW.rows_loaded,
        NEW.run_id, 
        NEW.status, 
        now()
    )
    ON CONFLICT (table_name) DO UPDATE SET
        collection_name = EXCLUDED.collection_name,
        last_max_ts = CASE
            WHEN EXCLUDED.last_max_ts IS NULL THEN w.last_max_ts
            WHEN w.last_max_ts IS NULL THEN EXCLUDED.last_max_ts
            WHEN EXCLUDED.last_max_ts > w.last_max_ts THEN EXCLUDED.last_max_ts
            ELSE w.last_max_ts
        END,
        last_mongo_count = EXCLUDED.last_mongo_count,
        last_pg_count = EXCLUDED.last_pg_count,
        last_run_id = EXCLUDED.last_run_id,
        last_status = EXCLUDED.last_status,
        updated_at = now();

    RETURN NEW;
END;
$$;

-- fire before each log insert or status change, so we can stamp finished_at
DROP TRIGGER IF EXISTS trg_etl_logs_sync_watermark ON public.etl_logs;
CREATE TRIGGER trg_etl_logs_sync_watermark
BEFORE INSERT OR UPDATE ON public.etl_logs
FOR EACH ROW
EXECUTE FUNCTION public.fn_sync_etl_watermark();
