"""
src/validation/plpgsql_loops.py

Core logic for running the PL/pgSQL DO-block data-quality tests under
tests/generic/loops/*.sql against a live Postgres connection. No Rich,
no logging, no sys.exit — pure functions so this can be called from the
CLI script (scripts/plpgsql_loops_tests.py), a future combined
validation report alongside the GX suite, or a test.

Moved out of scripts/plpgsql_loops_tests.py unchanged in behaviour.
"""

from __future__ import annotations

from pathlib import Path

import psycopg2


def discover_test_files(loops_dir: Path) -> list[Path]:
    if not loops_dir.is_dir():
        raise FileNotFoundError(str(loops_dir))
    return sorted(loops_dir.glob("*.sql"))


def get_dbapi_connection(raw_conn):
    """Resolve the real driver connection behind SQLAlchemy's pool wrapper,
    so we can read psycopg2's .notices (RAISE NOTICE output)."""
    return (
        getattr(raw_conn, "dbapi_connection", None)
        or getattr(raw_conn, "driver_connection", None)
        or getattr(raw_conn, "connection", raw_conn)
    )


def run_test_file(dbapi_conn, sql_path: Path) -> tuple[bool, str]:
    """Runs a single .sql DO-block test file. Returns (passed, message)."""
    sql = sql_path.read_text(encoding="utf-8")
    notices = getattr(dbapi_conn, "notices", None)
    if notices is not None and hasattr(notices, "clear"):
        try:
            notices.clear()
        except Exception:  # noqa: BLE001, S110 - notices optional per driver
            pass
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute(sql)
        dbapi_conn.commit()
        notices = getattr(dbapi_conn, "notices", None) or []
        try:
            message = "".join(str(n) for n in notices).strip()
        except Exception:  # noqa: BLE001 - notices may be non-iterable
            message = ""
        return True, message
    except psycopg2.Error as exc:
        dbapi_conn.rollback()
        message = getattr(exc, "pgerror", None) or str(exc)
        return False, message.strip()
    finally:
        cursor.close()


def run_all(engine, loops_dir: Path) -> list[dict]:
    """
    Runs every discovered test file against `engine` and returns a list
    of {"name": str, "passed": bool, "message": str} — the shared result
    shape used by both the CLI script and any future combined validation
    report (this suite + the GX suite in tests/data_quality/).
    """
    test_files = discover_test_files(loops_dir)
    raw_conn = None
    try:
        raw_conn = engine.raw_connection()
        dbapi_conn = get_dbapi_connection(raw_conn)

        results: list[dict] = []
        for sql_path in test_files:
            passed, message = run_test_file(dbapi_conn, sql_path)
            results.append(
                {"name": sql_path.name, "passed": passed, "message": message}
            )
    finally:
        if raw_conn is not None:
            try:
                raw_conn.close()
            except Exception:  # noqa: BLE001, S110 - best-effort cleanup
                pass

    return results
