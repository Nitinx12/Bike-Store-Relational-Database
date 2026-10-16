# runs the dq checks in fk order, parents before children
import sys
from pathlib import Path

import psycopg2

from src.utils.connection import postgres_psycopg_kwargs
from src.utils.logger import get_logger

log = get_logger("run_dq")

# parents first so orphans fail on the child, not the parent
ORDER = [
    "brands",
    "categories",
    "customers",
    "stores",
    "staffs",
    "products",
    "orders",
    "order_items",
    "stocks",
]

DQ_DIR = Path(__file__).resolve().parents[2] / "tests" / "dq"


# run one table file, returns True when every check passes
def run_one(conn, table):
    sql = (DQ_DIR / f"{table}.sql").read_text(encoding="utf-8")
    conn.notices.clear()
    with conn.cursor() as cur:
        cur.execute(sql)
    notes = list(conn.notices)
    conn.notices.clear()
    for note in notes:
        log.info(f"[{table}] {note.strip()}")
    return True


# run tables in ORDER, skips unknown names quietly
def main(tables=None, stop_on_fail=False):
    wanted = [t for t in ORDER if tables is None or t in tables]
    conn = psycopg2.connect(**postgres_psycopg_kwargs())
    conn.autocommit = True
    conn.notices = []
    passed, failed = [], []
    try:
        for table in wanted:
            try:
                run_one(conn, table)
                passed.append(table)
            except Exception as e:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
                log.error(f"[{table}] FAILED: {str(e).strip().splitlines()[0]}")
                failed.append(table)
                if stop_on_fail:
                    break
    finally:
        conn.close()
    log.info(f"done: passed={len(passed)} failed={len(failed)}")
    return {"passed": passed, "failed": failed}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    stop = "--stop" in sys.argv
    result = main(args or None, stop)
    if result["failed"]:
        sys.exit(1)
