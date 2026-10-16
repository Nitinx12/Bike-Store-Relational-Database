"""Smoke tests for main.py — require live Postgres + MongoDB.

The full-pipeline test is scoped to the tiny `brands` table so it runs
in seconds while still exercising every stage (load -> DQ -> GX).

Run:
    uv run --with pytest pytest tests/smoke -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import main

ROOT = Path(__file__).resolve().parents[2]


def run_pipeline(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "main.py", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_help_exits_zero():
    proc = run_pipeline("--help", timeout=60)
    assert proc.returncode == 0
    assert "--full" in proc.stdout
    assert "--fail-fast" in proc.stdout


def test_preflight_against_live_databases():
    assert main.stage_preflight() is True


def test_unknown_collection_fails_fast():
    proc = run_pipeline("--collections", "bogus", "--skip-dq", "--skip-gx", timeout=120)
    assert proc.returncode == 1
    assert "unknown collection" in (proc.stdout + proc.stderr).lower()


def test_scoped_pipeline_passes_end_to_end():
    proc = run_pipeline("--collections", "brands", "--tables", "brands")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PIPELINE PASSED" in proc.stdout
