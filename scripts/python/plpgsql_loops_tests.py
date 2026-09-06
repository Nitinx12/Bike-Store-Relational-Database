"""
plpgsql_loops_tests.py

Automates the dynamic PL/pgSQL data-quality tests (DO-block loops) that live
under tests/generic/loops/*.sql. Uses the project's own postgres_engine()
and get_logger() so it behaves like the rest of the pipeline, and uses rich
for readable pass/fail output in the terminal. Auto-discovers test files (no
hardcoded names) and exits non-zero if any test fails, so it plugs straight
into CI.
"""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# This file lives in scripts/, so the repo root is one level up. Add it to
# sys.path so `utils.*` resolves no matter where this script is invoked from.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from utils.engine import postgres_engine
from utils.logger import get_logger

logger = get_logger("tests", "plpgsql_loops")

# Rich owns the terminal for this script; mute the logger's plain console
# handler so output isn't printed twice, while the file handler still keeps
# the full plain-text log record.
for _handler in logger.handlers:
    if type(_handler) is logging.StreamHandler:
        _handler.setLevel(logging.CRITICAL + 1)

console = Console()

LOOPS_DIR = REPO_ROOT / "tests" / "generic" / "loops"


def discover_test_files(loops_dir: Path):
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


def run_test_file(dbapi_conn, sql_path: Path):
    """Run a single .sql DO-block test file. Returns (passed, message)."""
    sql = sql_path.read_text(encoding="utf-8")
    del dbapi_conn.notices[:]
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute(sql)
        dbapi_conn.commit()
        message = "".join(dbapi_conn.notices).strip()
        return True, message
    except Exception as exc:
        dbapi_conn.rollback()
        message = getattr(exc, "pgerror", None) or str(exc)
        return False, message.strip()
    finally:
        cursor.close()


def main():
    console.rule("[bold cyan]PL/pgSQL Loop Data Quality Tests[/bold cyan]")

    try:
        engine = postgres_engine()
    except Exception as exc:
        logger.error(f"Could not create Postgres engine: {exc}")
        console.print(
            Panel(
                str(exc),
                title="[bold red]Postgres engine failed[/bold red]",
                border_style="red",
            )
        )
        sys.exit(2)

    try:
        test_files = discover_test_files(LOOPS_DIR)
    except FileNotFoundError as exc:
        logger.error(f"Loops directory not found: {exc}")
        console.print(
            Panel(
                f"Expected folder does not exist:\n  {exc}\n\n"
                "Create it and add your *.sql loop-test files, e.g. in PowerShell:\n\n"
                f'  New-Item -ItemType Directory -Force -Path "{LOOPS_DIR}"\n\n'
                "then copy your 01_test_*.sql ... 10_test_*.sql files into it.",
                title="[bold red]Loops directory not found[/bold red]",
                border_style="red",
            )
        )
        sys.exit(2)

    if not test_files:
        logger.warning(f"No .sql test files found in {LOOPS_DIR}")
        console.print(f"[yellow]No .sql test files found in {LOOPS_DIR}[/yellow]")
        sys.exit(0)

    raw_conn = engine.raw_connection()
    dbapi_conn = get_dbapi_connection(raw_conn)

    table = Table(title=f"Running {len(test_files)} test file(s)")
    table.add_column("Test File", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Details", overflow="fold")

    passed, failed = [], []

    try:
        for sql_path in test_files:
            name = sql_path.name
            ok, message = run_test_file(dbapi_conn, sql_path)
            if ok:
                logger.info(f"[PASS] {name} — {message}")
                table.add_row(name, "[bold green]PASS[/bold green]", message or "-")
                passed.append(name)
            else:
                logger.error(f"[FAIL] {name} — {message}")
                table.add_row(name, "[bold red]FAIL[/bold red]", message)
                failed.append(name)
    finally:
        raw_conn.close()
        engine.dispose()

    console.print(table)

    summary = (
        f"Passed: {len(passed)}   Failed: {len(failed)}   Total: {len(test_files)}"
    )
    logger.info(summary)

    if failed:
        logger.error("Failing files: " + ", ".join(failed))
        console.print(
            Panel(
                summary
                + "\n\nFailing files:\n"
                + "\n".join(f"  - {f}" for f in failed),
                title="[bold red]Some tests failed[/bold red]",
                border_style="red",
            )
        )
        sys.exit(1)

    console.print(
        Panel(
            summary,
            title="[bold green]All tests passed[/bold green]",
            border_style="green",
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
