"""
Data-quality runner for the Bike Store schema.

Builds an Expectation Suite for every table in
tests/data_quality/suites/validation.py, validates the live Postgres
table against it using the shared GX context from
tests/data_quality/context.py, and logs/reports the outcome.

Usage:
    python run.py                 # validate every table in TABLE_SUITES
    python run.py orders products # validate only these tables

Exit code is 0 if every requested table's suite passed, 1 otherwise, so
this plugs straight into a CI job or orchestrator step.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
ROOT_DIR = THIS_DIR.parents[1]
for p in (THIS_DIR, ROOT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import great_expectations as gx

from context import get_context, get_datasource
from suites.validation import TABLE_SUITES
from utils.logger import get_logger

logger = get_logger("tests", "validation")

REPORT_DIR = THIS_DIR / "reports"


def validate_table(context, datasource, table_name: str) -> dict:
    """Build a suite for one table from TABLE_SUITES, run it against the
    live Postgres table, and return a JSON-serializable summary. Never
    raises: failures are captured in the returned dict so one bad table
    doesn't stop the rest of the run."""
    try:
        suite_builder = TABLE_SUITES[table_name]

        data_asset = datasource.add_table_asset(name=table_name, table_name=table_name)
        batch_definition = data_asset.add_batch_definition_whole_table(f"{table_name}_batch")

        suite = context.suites.add(gx.ExpectationSuite(name=f"{table_name}_suite"))
        for expectation in suite_builder():
            suite.add_expectation(expectation)

        batch = batch_definition.get_batch()
        result = batch.validate(suite)
        result_dict = result.to_json_dict()

        stats = result_dict.get("statistics", {})
        failed = [
            {
                "expectation_type": r["expectation_config"]["type"],
                "kwargs": r["expectation_config"]["kwargs"],
            }
            for r in result_dict.get("results", [])
            if not r.get("success", False)
        ]

        if result.success:
            logger.info(
                f"[{table_name}] PASSED "
                f"({stats.get('successful_expectations')}/{stats.get('evaluated_expectations')} expectations)"
            )
        else:
            logger.error(
                f"[{table_name}] FAILED "
                f"({stats.get('successful_expectations')}/{stats.get('evaluated_expectations')} expectations) "
                f"-> {', '.join(f['expectation_type'] for f in failed)}"
            )

        return {
            "table": table_name,
            "success": result.success,
            "statistics": stats,
            "failed_expectations": failed,
        }

    except Exception as e:
        logger.error(f"[{table_name}] ERROR while validating: {e}")
        return {"table": table_name, "success": False, "error": str(e)}


def main() -> int:
    requested = sys.argv[1:]
    tables = requested if requested else list(TABLE_SUITES.keys())

    unknown = [t for t in tables if t not in TABLE_SUITES]
    if unknown:
        logger.error(f"Unknown table(s), not in TABLE_SUITES: {unknown}")
        return 1

    try:
        context = get_context()
        datasource = get_datasource()
    except Exception:
        # get_context() already logged the specific error
        return 1

    run_started = datetime.now()
    results = [validate_table(context, datasource, table) for table in tables]
    run_finished = datetime.now()

    all_passed = all(r["success"] for r in results)
    summary = {
        "run_started": run_started.isoformat(),
        "run_finished": run_finished.isoformat(),
        "overall_success": all_passed,
        "tables_validated": len(results),
        "tables_passed": sum(1 for r in results if r["success"]),
        "results": results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"validation_report_{run_started.strftime('%Y-%m-%d_%H-%M')}.json"
    report_path.write_text(json.dumps(summary, indent=2, default=str))
    logger.info(f"Report written to {report_path}")

    if all_passed:
        logger.info(f"All {len(results)} table suite(s) passed.")
        return 0

    failed_tables = [r["table"] for r in results if not r["success"]]
    logger.error(f"{len(failed_tables)}/{len(results)} table suite(s) failed: {failed_tables}")
    return 1


if __name__ == "__main__":
    sys.exit(main())