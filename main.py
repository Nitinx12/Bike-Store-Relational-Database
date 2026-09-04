"""
main.py — single entry point for a full pipeline pass, with a combined
Rich summary across all three stages.

Runs, in one process:
  1. Mongo -> Postgres load        (src/pipeline/runner.py :: run_pipeline)[cite: 2]
  2. PL/pgSQL data-quality suite   (src/validation/plpgsql_loops.py :: run_all)[cite: 2]
  3. Great Expectations suite      (tests/data_quality/run.py)[cite: 2]

Nothing here shells out to scripts/mongo_to_postgres.py,
scripts/plpgsql_loops_tests.py, or tests/data_quality/run.py — it calls
the same underlying functions/objects those scripts call, directly.[cite: 2]
tests/data_quality/run.py's own main() isn't called because it reads
table names from sys.argv, which this script's own flags occupy; Stage
3 below calls the pieces main() calls instead (get_context,
get_datasource, validate_table, TABLE_SUITES) and writes the same JSON
report main() would have.[cite: 2]

Overall exit code is 0 only if every stage that ran succeeded.[cite: 2]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def _find_repo_root() -> Path:
    """Walk upward from this file until utils/connection.py is found.
    Same heuristic src/pipeline/config.py uses, duplicated here because
    this file must be able to put the repo root on sys.path *before* it
    can import anything under utils/ or src/."""
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "utils" / "connection.py").exists():
            return current
        current = current.parent
    raise RuntimeError(
        "Could not locate project root (utils/connection.py not found "
        f"upward from {Path(__file__).resolve()})."
    )


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

GX_DIR = REPO_ROOT / "tests" / "data_quality"
if str(GX_DIR) not in sys.path:
    sys.path.insert(0, str(GX_DIR))

import run as gx_run

from src.pipeline.runner import run_pipeline
from src.validation.plpgsql_loops import run_all
from utils.engine import postgres_engine
from utils.metrics import ETLRunMetrics, ValidationRunMetrics

LOOPS_DIR = REPO_ROOT / "tests" / "generic" / "loops"

console = Console()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the Mongo -> Postgres load, the PL/pgSQL suite, "
        "and the GX suite, in one process."
    )
    p.add_argument(
        "--full-refresh",
        action="store_true",
        help="Truncate and reload every collection instead of an incremental load.",
    )
    p.add_argument(
        "--collections",
        nargs="+",
        default=None,
        help="Only load these collections (default: every collection in MongoDB).",
    )
    p.add_argument(
        "--gx-tables",
        nargs="+",
        default=None,
        help="Only run the GX suite against these tables (default: every table in TABLE_SUITES).",
    )
    p.add_argument(
        "--skip-plpgsql",
        action="store_true",
        help="Skip the PL/pgSQL data-quality suite.",
    )
    p.add_argument(
        "--skip-gx", action="store_true", help="Skip the Great Expectations suite."
    )
    return p.parse_args()


# ── Stage 1: Mongo -> Postgres load ─────────────────────────────────────────


def run_load_stage(args: argparse.Namespace) -> dict:
    console.rule("[bold]Stage 1/3 — Mongo -> Postgres load[/bold]")

    def on_start(cols, mode):
        console.print(f"[dim]{len(cols)} collection(s), mode = {mode}[/dim]")

    def on_collection_done(col, summary):
        status = (
            "[red]failed[/red]"
            if summary["failed"]
            else "[yellow]skipped[/yellow]"
            if summary["skipped"]
            else "[green]loaded[/green]"
        )
        console.print(
            f"  {col:<24} {status}  new={summary['rows_new']} loaded={summary['rows_loaded']}"
        )

    result = run_pipeline(
        collections=args.collections,
        full_load=args.full_refresh,
        on_start=on_start,
        on_collection_done=on_collection_done,
    )

    metrics = ETLRunMetrics(job="mongo_to_postgres")
    for s in result["summaries"]:
        metrics.record_collection(s["collection"], s)
    metrics.finalize(failed=result["totals"]["failed"] > 0)
    metrics.push()

    table = Table(title="Load summary")
    table.add_column("Collection")
    table.add_column("Mongo", justify="right")
    table.add_column("New", justify="right")
    table.add_column("Loaded", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Skipped", justify="center")
    for s in result["summaries"]:
        table.add_row(
            s["collection"],
            str(s["rows_mongo"]),
            str(s["rows_new"]),
            str(s["rows_loaded"]),
            f"[red]{s['failed']}[/red]" if s["failed"] else "0",
            "yes" if s["skipped"] else "",
        )
    console.print(table)

    return result


# ── Stage 2: PL/pgSQL data-quality suite ────────────────────────────────────


def run_plpgsql_stage() -> list[dict]:
    console.rule("[bold]Stage 2/3 — PL/pgSQL data-quality suite[/bold]")

    engine = postgres_engine()
    try:
        results = run_all(engine, LOOPS_DIR)
    finally:
        engine.dispose()

    metrics = ValidationRunMetrics(job="plpgsql_loops_tests")
    for r in results:
        metrics.record_test(r["name"], r["passed"])
    metrics.finalize(failed=not all(r["passed"] for r in results))
    metrics.push()

    table = Table(title="PL/pgSQL test results")
    table.add_column("Test file")
    table.add_column("Result")
    table.add_column("Message")
    for r in results:
        status = "[green]PASS[/green]" if r["passed"] else "[red]FAIL[/red]"
        table.add_row(r["name"], status, r["message"] or "")
    console.print(table)

    return results


# ── Stage 3: Great Expectations suite ───────────────────────────────────────


def run_gx_stage(tables: list[str] | None) -> list[dict] | None:
    console.rule("[bold]Stage 3/3 — Great Expectations suite[/bold]")

    table_names = tables if tables else list(gx_run.TABLE_SUITES.keys())
    unknown = [t for t in table_names if t not in gx_run.TABLE_SUITES]
    if unknown:
        console.print(f"[red]Unknown table(s), not in TABLE_SUITES: {unknown}[/red]")
        return None

    try:
        context = gx_run.get_context()
        datasource = gx_run.get_datasource()
    except Exception as exc:
        console.print(f"[red]Could not set up GX context/datasource: {exc}[/red]")
        return None

    run_started = datetime.now()
    results = [gx_run.validate_table(context, datasource, t) for t in table_names]
    run_finished = datetime.now()

    metrics = ValidationRunMetrics(job="run_gx")
    for r in results:
        metrics.record_test(r["table"], r.get("success", False))
    metrics.finalize(failed=not all(r.get("success", False) for r in results))
    metrics.push()

    summary = {
        "run_started": run_started.isoformat(),
        "run_finished": run_finished.isoformat(),
        "overall_success": all(r.get("success", False) for r in results),
        "tables_validated": len(results),
        "tables_passed": sum(1 for r in results if r.get("success", False)),
        "results": results,
    }
    gx_run.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = (
        gx_run.REPORT_DIR
        / f"validation_report_{run_started.strftime('%Y-%m-%d_%H-%M')}.json"
    )
    report_path.write_text(json.dumps(summary, indent=2, default=str))
    console.print(f"[dim]Report written to {report_path}[/dim]")

    table = Table(title="GX suite results")
    table.add_column("Table")
    table.add_column("Result")
    table.add_column("Expectations", justify="right")
    for r in results:
        if "error" in r:
            table.add_row(r["table"], "[red]ERROR[/red]", r["error"])
            continue
        stats = r.get("statistics", {})
        ratio = f"{stats.get('successful_expectations', 0)}/{stats.get('evaluated_expectations', 0)}"
        status = "[green]PASS[/green]" if r.get("success", False) else "[red]FAIL[/red]"
        table.add_row(r["table"], status, ratio)
    console.print(table)

    return results


# ── Orchestration ────────────────────────────────────────────────────────────


def main() -> int:
    args = parse_args()
    console.print(Panel.fit("Bike Store pipeline — full run", style="bold blue"))

    load_result = run_load_stage(args)
    load_ok = load_result["totals"]["failed"] == 0

    plpgsql_results: list[dict] | None = None
    plpgsql_ok = True
    if not args.skip_plpgsql:
        plpgsql_results = run_plpgsql_stage()
        plpgsql_ok = all(r["passed"] for r in plpgsql_results)
    else:
        console.rule("[dim]Stage 2/3 — PL/pgSQL data-quality suite (skipped)[/dim]")

    gx_results: list[dict] | None = None
    gx_ok = True
    if not args.skip_gx:
        gx_results = run_gx_stage(args.gx_tables)
        gx_ok = gx_results is not None and all(
            r.get("success", False) for r in gx_results
        )
    else:
        console.rule("[dim]Stage 3/3 — Great Expectations suite (skipped)[/dim]")

    overall_ok = load_ok and plpgsql_ok and gx_ok
    totals = load_result["totals"]
    lines = [
        f"Load    : loaded={totals['rows_loaded']} new={totals['rows_new']} failed={totals['failed']}"
    ]
    if plpgsql_results is not None:
        passed = sum(1 for r in plpgsql_results if r["passed"])
        lines.append(f"PL/pgSQL: {passed}/{len(plpgsql_results)} passed")
    if gx_results is not None:
        passed = sum(1 for r in gx_results if r.get("success", False))
        lines.append(f"GX      : {passed}/{len(gx_results)} passed")
    lines.append("")
    lines.append("RESULT: " + ("PASSED" if overall_ok else "FAILED"))

    console.print(
        Panel(
            "\n".join(lines),
            title="Pipeline summary",
            style="bold green" if overall_ok else "bold red",
        )
    )

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
