# pulls new rows from mongo and upserts into postgres, uses updated_at + pk
from datetime import UTC, datetime

import polars as pl
from sqlalchemy import text

from src.utils.connection import DB_SCHEMA
from src.utils.engine import mongo_db, postgres_engine
from src.utils.logger import get_logger

log = get_logger("mongo_incremental")

# collection -> pk columns, all have updated_at
TABLES = {
    "brands": ["brand_id"],
    "categories": ["category_id"],
    "customers": ["customer_id"],
    "stores": ["store_id"],
    "staffs": ["staff_id"],
    "products": ["product_id"],
    "orders": ["order_id"],
    "order_items": ["order_id", "item_id"],
    "stocks": ["store_id", "product_id"],
}

TS_COL = "updated_at"


# mongo and pg mirror each other in wall time, so just drop tz (no convert)
def _naive_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is not None:
        return dt.replace(tzinfo=None)
    return dt


# last loaded point, watermarks table first then max in target
def get_watermark(conn, table):
    row = conn.execute(
        text("SELECT last_max_ts FROM public.etl_watermarks WHERE table_name = :t"),
        {"t": table},
    ).scalar()
    if row is not None:
        return row
    try:
        return conn.execute(
            text(f'SELECT MAX("{TS_COL}") FROM "{DB_SCHEMA}"."{table}"')
        ).scalar()
    except Exception:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        return None


# save one line in etl_logs, trigger moves etl_watermarks forward
def write_log(
    conn,
    run_id,
    collection,
    table,
    status,
    rows_mongo,
    rows_loaded,
    rows_failed,
    mongo_ts,
    pg_ts,
    err=None,
):
    conn.execute(
        text("""
            INSERT INTO public.etl_logs
                (run_id, collection_name, table_name, mode, status,
                 rows_mongo, rows_loaded, rows_failed,
                 mongo_max_ts, pg_max_ts, finished_at, error_message)
            VALUES
                (:run_id, :col, :tbl, 'INCREMENTAL', :status,
                 :rm, :rl, :rf, :mts, :pts, now(), :err)
        """),
        {
            "run_id": run_id,
            "col": collection,
            "tbl": table,
            "status": status,
            "rm": rows_mongo,
            "rl": rows_loaded,
            "rf": rows_failed,
            "mts": mongo_ts,
            "pts": pg_ts,
            "err": err,
        },
    )


# one collection: mongo delta -> polars -> postgres upsert
def load_table(mdb, engine, collection, table, pk_cols, run_id, full=False):
    mongo_col = mdb[collection]

    with engine.begin() as conn:
        watermark = None if full else _naive_utc(get_watermark(conn, table))

    # only ask mongo for rows newer than last time
    query = {} if watermark is None or full else {TS_COL: {"$gt": watermark}}
    docs = list(mongo_col.find(query, {"_id": 0}))
    rows_mongo = mongo_col.count_documents({})

    if not docs:
        with engine.begin() as conn:
            write_log(
                conn,
                run_id,
                collection,
                table,
                "SKIPPED",
                rows_mongo,
                0,
                0,
                watermark,
                watermark,
            )
        log.info(f"{table}: skipped, nothing new")
        return {"table": table, "status": "SKIPPED", "loaded": 0}

    # make every updated_at naive utc, mongo and pg stay comparable
    for d in docs:
        d[TS_COL] = _naive_utc(d.get(TS_COL))

    # polars does the fast part: drop dupes, keep last, sort by time
    df = pl.DataFrame(docs)
    pk_here = [c for c in pk_cols if c in df.columns]
    if pk_here:
        df = df.unique(subset=pk_here, keep="last", maintain_order=True)
    if TS_COL in df.columns:
        df = df.sort(TS_COL)

    # keep only columns that really exist in postgres
    with engine.begin() as conn:
        pg_cols = [
            r[0]
            for r in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema = :s AND table_name = :t"
                ),
                {"s": DB_SCHEMA, "t": table},
            )
        ]
    df = df.select([c for c in df.columns if c in pg_cols])
    if df.is_empty():
        with engine.begin() as conn:
            write_log(
                conn,
                run_id,
                collection,
                table,
                "SKIPPED",
                rows_mongo,
                0,
                0,
                watermark,
                watermark,
            )
        return {"table": table, "status": "SKIPPED", "loaded": 0}

    cols = df.columns
    col_list = ", ".join(f'"{c}"' for c in cols)
    updates = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in cols if c not in pk_here)
    pk_list = ", ".join(f'"{c}"' for c in pk_here)
    conflict = (
        f"ON CONFLICT ({pk_list}) DO UPDATE SET {updates}"
        if pk_here and updates
        else (
            f"ON CONFLICT ({pk_list}) DO NOTHING"
            if pk_here
            else "ON CONFLICT DO NOTHING"
        )
    )

    # stage then merge, so reruns stay safe
    stage = f"{table}_polars_stage"
    touch_trigger = f"trg_{table}_updated_at"
    try:
        with engine.begin() as conn:
            # pause the auto-touch trigger so source updated_at is kept as-is
            conn.execute(
                text(
                    f'ALTER TABLE "{DB_SCHEMA}"."{table}" DISABLE TRIGGER "{touch_trigger}"'
                )
            )
            conn.execute(text(f'DROP TABLE IF EXISTS "{DB_SCHEMA}"."{stage}"'))
            conn.execute(
                text(
                    f'CREATE TEMP TABLE "{stage}" (LIKE "{DB_SCHEMA}"."{table}" INCLUDING ALL) ON COMMIT DROP'
                )
            )
            df.to_pandas().to_sql(
                stage, conn, schema=DB_SCHEMA, if_exists="append", index=False
            )
            res = conn.execute(
                text(
                    f'INSERT INTO "{DB_SCHEMA}"."{table}" ({col_list}) SELECT {col_list} FROM "{DB_SCHEMA}"."{stage}" {conflict}'
                )
            )
            conn.execute(
                text(
                    f'ALTER TABLE "{DB_SCHEMA}"."{table}" ENABLE TRIGGER "{touch_trigger}"'
                )
            )
            loaded = res.rowcount or len(df)
            pg_max = _naive_utc(df[TS_COL].max()) if TS_COL in cols else None
            mongo_max = mdb[collection].find_one(
                sort=[(TS_COL, -1)], projection={"_id": 0, TS_COL: 1}
            )
            mongo_max = _naive_utc(mongo_max.get(TS_COL)) if mongo_max else pg_max
            write_log(
                conn,
                run_id,
                collection,
                table,
                "SUCCESS",
                rows_mongo,
                loaded,
                0,
                mongo_max,
                pg_max,
            )
        log.info(f"{table}: loaded {loaded} rows")
        return {"table": table, "status": "SUCCESS", "loaded": loaded}
    except Exception as e:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        with engine.begin() as conn:
            write_log(
                conn,
                run_id,
                collection,
                table,
                "FAILED",
                rows_mongo,
                0,
                len(df),
                None,
                watermark,
                str(e)[:1000],
            )
        log.error(f"{table}: failed - {e}")
        return {"table": table, "status": "FAILED", "loaded": 0, "error": str(e)}


# run all collections one by one
def main(collections=None, full=False):
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    mdb = mongo_db()
    engine = postgres_engine()
    targets = collections or list(TABLES)
    out = []
    for col in targets:
        out.append(load_table(mdb, engine, col, col, TABLES[col], run_id, full))
    ok = sum(1 for r in out if r["status"] == "SUCCESS")
    skip = sum(1 for r in out if r["status"] == "SKIPPED")
    fail = sum(1 for r in out if r["status"] == "FAILED")
    log.info(f"done: ok={ok} skipped={skip} failed={fail}")
    return out


if __name__ == "__main__":
    import sys

    full = "--full" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    main(only or None, full)
