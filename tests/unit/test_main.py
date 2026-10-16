"""Unit tests for main.py — no database required.

Every test here either checks argument handling, module loading, input
validation (which happens before any connection is opened), or the
orchestration logic with the stages mocked out.

Run:
    uv run --with pytest pytest tests/unit -v
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import main

EXPECTED_TABLES = {
    "brands",
    "categories",
    "customers",
    "stores",
    "staffs",
    "products",
    "orders",
    "order_items",
    "stocks",
}


def run_main_with(argv: list[str]) -> int:
    with patch.object(sys, "argv", argv):
        return main.main()


# ── argument parsing ────────────────────────────────────────────────────


def test_parse_args_defaults():
    with patch.object(sys, "argv", ["main.py"]):
        args = main.parse_args()
    assert args.full is False
    assert args.collections is None
    assert args.tables is None
    assert args.contracts is False
    assert args.skip_dq is False
    assert args.skip_gx is False
    assert args.fail_fast is False


def test_parse_args_full_and_filters():
    argv = [
        "main.py",
        "--full",
        "--collections",
        "orders",
        "products",
        "--tables",
        "orders",
        "products",
    ]
    with patch.object(sys, "argv", argv):
        args = main.parse_args()
    assert args.full is True
    assert args.collections == ["orders", "products"]
    assert args.tables == ["orders", "products"]


def test_parse_args_skips_and_flags():
    argv = ["main.py", "--contracts", "--skip-dq", "--skip-gx", "--fail-fast"]
    with patch.object(sys, "argv", argv):
        args = main.parse_args()
    assert args.contracts is True
    assert args.skip_dq is True
    assert args.skip_gx is True
    assert args.fail_fast is True


# ── script loading ──────────────────────────────────────────────────────


def test_load_script_run_gx():
    run_gx = main.load_script("run_gx")
    assert set(run_gx.TABLE_RULES) == EXPECTED_TABLES
    for name in ("get_context", "get_datasource", "validate_table", "make_suite"):
        assert callable(getattr(run_gx, name)), name


def test_load_script_update_contract():
    update_contract = main.load_script("update_contract")
    assert callable(update_contract.update_all_contracts)
    assert callable(update_contract.update_single_contract)


# ── input validation happens before any DB connection ───────────────────


def test_stage_load_rejects_unknown_collection():
    assert main.stage_load(["bogus"], full=False) is False


def test_stage_dq_rejects_unknown_table():
    assert main.stage_dq(["bogus"]) is False


def test_stage_gx_rejects_unknown_table():
    assert main.stage_gx(["bogus"]) is False


def test_stage_preflight_fails_without_env():
    with patch("main.require_pg_env", side_effect=ValueError("missing env vars")):
        assert main.stage_preflight() is False


# ── orchestration ───────────────────────────────────────────────────────


def _all_pass(*args, **kwargs):
    return True


def test_main_all_stages_pass_returns_zero():
    with (
        patch.object(sys, "argv", ["main.py"]),
        patch("main.stage_preflight", return_value=True),
        patch("main.stage_load", return_value=True) as load,
        patch("main.stage_dq", return_value=True) as dq,
        patch("main.stage_gx", return_value=True) as gx,
    ):
        assert main.main() == 0
    load.assert_called_once_with(None, False)
    dq.assert_called_once_with(None)
    gx.assert_called_once_with(None)


def test_main_failure_returns_one_but_runs_all_stages():
    with (
        patch.object(sys, "argv", ["main.py"]),
        patch("main.stage_preflight", return_value=True),
        patch("main.stage_load", return_value=True),
        patch("main.stage_dq", return_value=False),
        patch("main.stage_gx", return_value=True) as gx,
    ):
        assert main.main() == 1
    gx.assert_called_once()  # no --fail-fast: later stages still run


def test_main_fail_fast_stops_after_first_failure():
    with (
        patch.object(sys, "argv", ["main.py", "--fail-fast"]),
        patch("main.stage_preflight", return_value=True),
        patch("main.stage_load", return_value=False),
        patch("main.stage_dq", return_value=True) as dq,
        patch("main.stage_gx", return_value=True) as gx,
    ):
        assert main.main() == 1
    dq.assert_not_called()
    gx.assert_not_called()


def test_main_skips_dq_and_gx():
    with (
        patch.object(sys, "argv", ["main.py", "--skip-dq", "--skip-gx"]),
        patch("main.stage_preflight", return_value=True),
        patch("main.stage_load", return_value=True),
        patch("main.stage_dq") as dq,
        patch("main.stage_gx") as gx,
    ):
        assert main.main() == 0
    dq.assert_not_called()
    gx.assert_not_called()


def test_main_preflight_failure_returns_one():
    with (
        patch.object(sys, "argv", ["main.py"]),
        patch("main.stage_preflight", return_value=False),
        patch("main.stage_load") as load,
    ):
        assert main.main() == 1
    load.assert_not_called()
