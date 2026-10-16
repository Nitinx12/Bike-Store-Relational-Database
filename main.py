"""main.py - single entry point for a full Bike Store pipeline pass.

Runs, in order:
  0. Preflight - .env values present, Postgres + Mongo reachable (fail fast).
  1. Contracts refresh (opt-in, --contracts) - snapshot Mongo source
     schemas to contracts/ BEFORE moving data.
  2. Mongo -> Postgres incremental load (src/jobs/incremental_load.main).
  3. SQL data-quality suite in FK/parent-first order (src/jobs/run_dq.main).
  4. Great Expectations suite (scripts/run_gx pieces, called directly -
     run_gx.main() is not used because it parses sys.argv itself).

Nothing here shells out to sub-scripts; it calls the same underlying
functions those scripts call, in one process.

Exit code is 0 only if every stage that ran succeeded.

Usage:
    uv run python main.py
    uv run python main.py --full
    uv run python main.py --collections orders products --tables orders products
    uv run python main.py --skip-dq --skip-gx
    uv run python main.py --contracts
    uv run python main.py --fail-fast
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.connection import require_mongo_env, require_pg_env
from src.utils.logger import get_logger

log = get_logger("pipeline")


def load_script(name: str):
    """Import a scripts/*.py file that is not part of a package."""
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"scripts_{name}", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full Bike Store pipeline.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Truncate and reload every collection instead of an incremental load.",
    )
    parser.add_argument(
        "--collections",
        nargs="+",
        default=None,
        metavar="COLLECTION",
        help="Only load these Mongo collections (default: every collection).",
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        default=None,
        metavar="TABLE",
        help="Only validate these tables in the DQ and GX stages (default: all).",
    )
    parser.add_argument(
        "--contracts",
        action="store_true",
        help="Refresh contracts/*.yml from Mongo source schemas before loading.",
    )
    parser.add_argument(
        "--skip-dq",
        action="store_true",
        help="Skip the SQL data-quality suite.",
    )
    parser.add_argument(
        "--skip-gx",
        action="store_true",
        help="Skip the Great Expectations suite.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing stage instead of running all stages.",
    )
    return parser.parse_args()


# ── Stage 0: preflight ────────────────────────────────────────────────────


def stage_preflight() -> bool:
    """Check env vars and database connectivity. Always runs, fails fast."""
    print("=== Stage 0: preflight ===")
    try:
        require_pg_env()
        require_mongo_env()
    except ValueError as exc:
        print(f"[FAIL] environment: {exc}")
        return False

    try:
        from sqlalchemy import text

        from src.utils.engine import mongo_db, postgres_engine

        with postgres_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[OK] Postgres reachable")
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] Postgres: {exc}")
        return False

    try:
        mongo_db().client.admin.command("ping")
        print("[OK] MongoDB reachable")
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] MongoDB: {exc}")
        return False

    return True


# ── Stage 1: contracts refresh (opt-in) ───────────────────────────────────


def stage_contracts() -> bool:
    """Snapshot Mongo source schemas into contracts/. Runs before the load."""
    print("=== Stage 1: contracts refresh ===")
    try:
        update_contract = load_script("update_contract")
        update_contract.update_all_contracts()
    except SystemExit as exc:
        # update_contract calls sys.exit(1) when Mongo is unreachable.
        print(f"[FAIL] contracts: exited with code {exc.code}")
        return False
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] contracts: {exc}")
        return False
    print("[OK] contracts refreshed")
    return True


# ── Stage 2: Mongo -> Postgres load ───────────────────────────────────────


def stage_load(collections: list[str] | None, full: bool) -> bool:
    """Incremental (or full-refresh) load of every collection, in TABLES order."""
    print("=== Stage 2: Mongo -> Postgres load ===")
    from src.jobs.incremental_load import TABLES
    from src.jobs.incremental_load import main as etl_main

    unknown = [c for c in (collections or []) if c not in TABLES]
    if unknown:
        print(f"[FAIL] unknown collection(s): {', '.join(unknown)}")
        print(f"       known: {', '.join(TABLES)}")
        return False

    try:
        results = etl_main(collections, full)
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] load: {exc}")
        return False

    failed = [r["table"] for r in results if r.get("status") == "FAILED"]
    if failed:
        print(f"[FAIL] load failed for: {', '.join(failed)}")
        return False
    print(f"[OK] load finished ({len(results)} table(s))")
    return True


# ── Stage 3: SQL data-quality suite ───────────────────────────────────────


def stage_dq(tables: list[str] | None) -> bool:
    """Run tests/dq/*.sql in FK parent-first ORDER."""
    print("=== Stage 3: SQL data-quality suite ===")
    from src.jobs.run_dq import ORDER
    from src.jobs.run_dq import main as dq_main

    unknown = [t for t in (tables or []) if t not in ORDER]
    if unknown:
        print(f"[FAIL] unknown table(s): {', '.join(unknown)}")
        return False

    try:
        result = dq_main(tables)
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] DQ suite: {exc}")
        return False

    if result["failed"]:
        print(f"[FAIL] DQ failed for: {', '.join(result['failed'])}")
        return False
    print(f"[OK] DQ passed ({len(result['passed'])} table(s))")
    return True


# ── Stage 4: Great Expectations suite ─────────────────────────────────────


def stage_gx(tables: list[str] | None) -> bool:
    """Validate each table with the suite scripts/run_gx builds per table."""
    print("=== Stage 4: Great Expectations suite ===")
    try:
        run_gx = load_script("run_gx")
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] GX import: {exc}")
        return False

    unknown = [t for t in (tables or []) if t not in run_gx.TABLE_RULES]
    if unknown:
        print(f"[FAIL] unknown table(s): {', '.join(unknown)}")
        return False

    try:
        context = run_gx.get_context()
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] GX configuration: {exc}")
        return False

    try:
        datasource = run_gx.get_datasource(context)
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] GX datasource: {exc}")
        return False

    failed = [
        table
        for table in (tables or list(run_gx.TABLE_RULES))
        if not run_gx.validate_table(context, datasource, table)
    ]
    if failed:
        print(f"[FAIL] GX validation failed for: {', '.join(failed)}")
        return False
    print("[OK] GX validation passed")
    return True


# ── Orchestration ─────────────────────────────────────────────────────────


def main() -> int:
    args = parse_args()
    status: dict[str, str] = {}

    if not stage_preflight():
        print("\nPIPELINE FAILED at preflight.")
        return 1

    stages = []
    if args.contracts:
        stages.append(("contracts", lambda: stage_contracts()))
    stages.append(("load", lambda: stage_load(args.collections, args.full)))
    if not args.skip_dq:
        stages.append(("dq", lambda: stage_dq(args.tables)))
    if not args.skip_gx:
        stages.append(("gx", lambda: stage_gx(args.tables)))

    for name, run in stages:
        ok = run()
        status[name] = "PASS" if ok else "FAIL"
        if not ok and args.fail_fast:
            break

    print("\n=== Pipeline summary ===")
    for name, result in status.items():
        print(f"  {name}: {result}")

    failed = [name for name, result in status.items() if result == "FAIL"]
    if failed:
        print(f"\nPIPELINE FAILED at: {', '.join(failed)}")
        return 1
    print("\nPIPELINE PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
