#!/usr/bin/env python3
"""
Data Quality Test Runner
=========================
Runs SQL data-quality test files (e.g. 01_test_brands.sql ... 10_test_stores.sql,
06_test_orphan_and_business_rules.sql) against a PostgreSQL database, one test
at a time, and prints a rich summary report to the terminal.

Each .sql file may contain several individual "tests" -- each one is a
standalone SELECT statement immediately preceded by a comment line such as:

    -- Test 3: brand_name must not be null or empty
    -- Orphan 4: order_items with an order_id that does not exist in orders
    -- Business 7: an inactive staff member should not be assigned ...

A test PASSES if its query returns 0 rows, and FAILS if it returns 1+ rows.
If the query itself raises an error (e.g. missing table/column), it's
reported separately as ERROR rather than FAIL.

Install requirements:
    pip install psycopg2-binary rich

Connection:
    Uses the same Postgres connection as the rest of the pipeline
    (utils/connection.py -> utils/engine.py, configured via .env). No DB
    flags are required for normal use.

Usage:
    # Run every test in tests/ (default; connects using .env settings)
    python plpgsql_tests.py

    # Show a preview of the offending rows for every failed test
    python plpgsql_tests.py --show-failures --max-rows 5

    # Point at a different folder of *.sql test files
    python plpgsql_tests.py --tests-dir ./tests

    # Override the configured connection for a one-off run against another DB
    python plpgsql_tests.py --dsn "postgresql://user:password@host:5432/dbname"

Logging:
    Each run writes a full DEBUG-level log to logs/tests/<name>_<timestamp>.log
    (same convention as the extraction/transformation/loading stages). The
    terminal only shows the rich summary/progress output plus top-level
    info/error lines; per-test detail goes to the log file.

Exit code is 0 if every test passed, 1 otherwise (handy for CI pipelines).
"""

import argparse
import glob
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

# This script lives at the project root, alongside main.py / health_check.py,
# so utils/ is a direct sibling of this file. Running the script from another
# working directory only puts its own containing folder on sys.path, so
# `import utils` would otherwise fail unless invoked from the project root.
# Insert this file's directory explicitly so it works regardless of cwd.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("This script requires psycopg2-binary. Install it with:\n"
          "    pip install psycopg2-binary")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    )
    from rich import box
except ImportError:
    print("This script requires rich. Install it with:\n"
          "    pip install rich")
    sys.exit(1)

from utils.engine import postgres_engine
from utils.logger import get_logger

logger = get_logger("tests", "plpgsql_tests")


TEST_HEADER_RE = re.compile(
    r'^--\s*(Test|Orphan|Business)\s+(\d+):\s*(.*)$',
    re.IGNORECASE
)


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class TestCase:
    file: str
    kind: str          # "Test" / "Orphan" / "Business"
    number: str
    description: str
    sql: str


@dataclass
class TestResult:
    case: TestCase
    status: str         # "PASS" / "FAIL" / "ERROR"
    row_count: int = 0
    sample_rows: Optional[list] = None
    columns: Optional[list] = None
    error: Optional[str] = None
    duration: float = 0.0


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------

def parse_sql_file(path: str) -> List[TestCase]:
    """Split a test file into individual TestCase objects based on the
    '-- Test N:' / '-- Orphan N:' / '-- Business N:' comment markers."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    lines = text.splitlines()
    header_idxs = [
        i for i, line in enumerate(lines) if TEST_HEADER_RE.match(line.strip())
    ]

    cases = []
    filename = os.path.basename(path)
    for idx, start in enumerate(header_idxs):
        end = header_idxs[idx + 1] if idx + 1 < len(header_idxs) else len(lines)
        block = lines[start:end]

        header_match = TEST_HEADER_RE.match(block[0].strip())
        kind, number, description = header_match.groups()

        # Fold in any additional leading comment lines as part of the description
        body_start = 1
        while body_start < len(block) and block[body_start].strip().startswith("--"):
            extra = block[body_start].strip().lstrip("-").strip()
            if extra:
                description += " " + extra
            body_start += 1

        sql = "\n".join(block[body_start:]).strip()
        sql = sql.rstrip(";").strip()
        if not sql:
            continue

        cases.append(TestCase(
            file=filename,
            kind=kind,
            number=number,
            description=description.strip(),
            sql=sql,
        ))
    return cases


def load_all_tests(tests_dir: str) -> List[TestCase]:
    files = sorted(glob.glob(os.path.join(tests_dir, "*.sql")))
    if not files:
        raise FileNotFoundError(f"No .sql files found in '{tests_dir}'")
    all_cases = []
    for f in files:
        all_cases.extend(parse_sql_file(f))
    return all_cases


# --------------------------------------------------------------------------
# Execution
# --------------------------------------------------------------------------

def run_tests(conn, cases: List[TestCase], max_rows: int, console: Console) -> List[TestResult]:
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running data quality tests...", total=len(cases))
        for case in cases:
            start = time.time()
            label = f"{case.file} — {case.kind} {case.number}: {case.description}"
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(case.sql)
                    rows = cur.fetchall()
                    row_count = len(rows)
                    status = "PASS" if row_count == 0 else "FAIL"
                    columns = list(rows[0].keys()) if rows else (
                        [d[0] for d in cur.description] if cur.description else []
                    )
                    sample = rows[:max_rows] if rows else []
                conn.commit()
                duration = time.time() - start
                if status == "PASS":
                    logger.debug(f"PASS  ({duration:.3f}s) {label}")
                else:
                    logger.warning(f"FAIL  ({duration:.3f}s) {label} — {row_count} offending row(s)")
                results.append(TestResult(
                    case=case, status=status, row_count=row_count,
                    sample_rows=sample, columns=columns,
                    duration=duration,
                ))
            except Exception as e:
                conn.rollback()
                duration = time.time() - start
                logger.error(f"ERROR ({duration:.3f}s) {label} — {str(e).strip()}")
                results.append(TestResult(
                    case=case, status="ERROR", error=str(e).strip(),
                    duration=duration,
                ))
            progress.advance(task)
    return results


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def print_report(results: List[TestResult], console: Console, show_failures: bool, max_rows: int):
    files = []
    for r in results:
        if r.case.file not in files:
            files.append(r.case.file)

    summary_table = Table(title="Data Quality Test Summary", box=box.ROUNDED)
    summary_table.add_column("File", style="bold")
    summary_table.add_column("Total", justify="right")
    summary_table.add_column("Pass", justify="right", style="green")
    summary_table.add_column("Fail", justify="right")
    summary_table.add_column("Error", justify="right")

    total_pass = total_fail = total_error = 0
    for fname in files:
        subset = [r for r in results if r.case.file == fname]
        p = sum(1 for r in subset if r.status == "PASS")
        f_ = sum(1 for r in subset if r.status == "FAIL")
        e = sum(1 for r in subset if r.status == "ERROR")
        total_pass += p
        total_fail += f_
        total_error += e
        summary_table.add_row(
            fname,
            str(len(subset)),
            str(p),
            f"[bold red]{f_}[/bold red]" if f_ else "0",
            f"[bold yellow]{e}[/bold yellow]" if e else "0",
        )

    total = len(results)
    summary_table.add_section()
    summary_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total}[/bold]",
        f"[bold green]{total_pass}[/bold green]",
        f"[bold red]{total_fail}[/bold red]" if total_fail else "[bold]0[/bold]",
        f"[bold yellow]{total_error}[/bold yellow]" if total_error else "[bold]0[/bold]",
    )

    console.print()
    console.print(summary_table)

    if total_fail == 0 and total_error == 0:
        console.print(Panel.fit(
            f"[bold green]ALL {total} TESTS PASSED[/bold green]",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]{total_fail} FAILED[/bold red]   "
            f"[bold yellow]{total_error} ERRORED[/bold yellow]   "
            f"[bold green]{total_pass} PASSED[/bold green]   out of {total}",
            border_style="red" if total_fail else "yellow"
        ))

    problems = [r for r in results if r.status != "PASS"]
    if problems:
        detail_table = Table(title="Failed / Errored Tests", box=box.ROUNDED, show_lines=True)
        detail_table.add_column("File")
        detail_table.add_column("Check")
        detail_table.add_column("Description")
        detail_table.add_column("Status", justify="center")
        detail_table.add_column("Rows / Error", justify="right")

        for r in problems:
            status_style = "bold red" if r.status == "FAIL" else "bold yellow"
            if r.status == "FAIL":
                rows_or_err = str(r.row_count)
            else:
                err = r.error or ""
                rows_or_err = err[:80] + "..." if len(err) > 80 else err
            detail_table.add_row(
                r.case.file,
                f"{r.case.kind} {r.case.number}",
                r.case.description,
                f"[{status_style}]{r.status}[/{status_style}]",
                rows_or_err,
            )
        console.print()
        console.print(detail_table)

        if show_failures:
            for r in problems:
                if r.status != "FAIL" or not r.sample_rows:
                    continue
                console.print()
                console.print(
                    f"[bold]{r.case.file} — {r.case.kind} {r.case.number}: "
                    f"{r.case.description}[/bold]"
                )
                console.print(
                    f"[dim]{r.row_count} offending row(s), showing up to {max_rows}[/dim]"
                )
                sample_table = Table(box=box.SIMPLE)
                for col in r.columns:
                    sample_table.add_column(str(col))
                for row in r.sample_rows:
                    sample_table.add_row(*[str(row.get(c, "")) for c in r.columns])
                console.print(sample_table)


# --------------------------------------------------------------------------
# CLI / main
# --------------------------------------------------------------------------

def get_connection(dsn_override: Optional[str]):
    """Return a live DBAPI connection.

    By default this reuses the pipeline's shared Postgres engine
    (utils/connection.py -> utils/engine.py, populated from .env), so the
    test runner always points at the same database as the rest of the
    pipeline. Pass --dsn to override that for a one-off run.
    """
    if dsn_override:
        return psycopg2.connect(dsn_override)
    engine = postgres_engine()
    return engine.raw_connection()


def main():
    parser = argparse.ArgumentParser(
        description="Run SQL data-quality tests against Postgres and print a rich report."
    )
    parser.add_argument("--tests-dir", default="tests",
                         help="Folder containing the *.sql test files (default: tests/)")
    parser.add_argument("--dsn",
                         help="Optional override: full libpq connection string, e.g. "
                              "postgresql://user:pass@host:5432/dbname. "
                              "If omitted, uses the shared Postgres connection from utils/connection.py (.env).")
    parser.add_argument("--show-failures", action="store_true",
                         help="Print a preview of the offending rows for each failed test")
    parser.add_argument("--max-rows", type=int, default=5,
                         help="Max sample rows to show per failed test (default 5)")
    args = parser.parse_args()

    console = Console()

    try:
        cases = load_all_tests(args.tests_dir)
    except FileNotFoundError as e:
        logger.error(str(e))
        console.print(f"[bold red]{e}[/bold red]")
        sys.exit(1)

    logger.info(f"Loaded {len(cases)} tests from {len(set(c.file for c in cases))} file(s) in {args.tests_dir}")
    console.print(Panel.fit(
        f"[bold]Loaded {len(cases)} tests[/bold] from "
        f"{len(set(c.file for c in cases))} file(s) in [cyan]{args.tests_dir}[/cyan]",
        border_style="blue"
    ))

    try:
        conn = get_connection(args.dsn)
    except Exception as e:
        logger.error(f"Could not connect to the database: {e}")
        console.print(f"[bold red]Could not connect to the database:[/bold red] {e}")
        sys.exit(1)

    try:
        results = run_tests(conn, cases, args.max_rows, console)
    finally:
        conn.close()

    print_report(results, console, args.show_failures, args.max_rows)

    total_pass = sum(1 for r in results if r.status == "PASS")
    total_fail = sum(1 for r in results if r.status == "FAIL")
    total_error = sum(1 for r in results if r.status == "ERROR")
    logger.info(
        f"Run complete: {total_pass} passed, {total_fail} failed, "
        f"{total_error} errored (of {len(results)} total)"
    )
    sys.exit(1 if (total_fail or total_error) else 0)


if __name__ == "__main__":
    main()