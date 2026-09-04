"""
src/pipeline/config.py

Central pipeline configuration — every env-var-driven constant the
Mongo → Postgres ETL depends on, in one place instead of scattered at
the top of a 900-line script.

NOTE: this module imports utils.connection at load time, so whatever
calls it first (a scripts/ entry point) must already have added the
repo root to sys.path — same bootstrap pattern the scripts already use.
"""

from __future__ import annotations

import os
from pathlib import Path

from utils.connection import POSTGRES_DATABASE, POSTGRES_HOST, POSTGRES_PORT


def _repo_root() -> Path:
    """
    Walk upward from this file until we find utils/connection.py — that
    directory is the project root. Same heuristic the scripts already
    use, centralised here so every src/ and scripts/ module agrees on it.
    """
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "utils" / "connection.py").exists():
            return current
        current = current.parent
    raise RuntimeError(
        "Could not locate project root.\n"
        f"Searched upward from: {Path(__file__).resolve()}\n\n"
        "Expected to find  utils/connection.py  somewhere in the parent tree."
    )


REPO_ROOT = _repo_root()

ETL_SCHEMA = os.getenv("ETL_SCHEMA", "public")  # target schema
ETL_TS_COL = os.getenv("ETL_TS_COL", "updated_at")  # incremental timestamp
ETL_PK_SUFFIX = os.getenv("ETL_PK_SUFFIX", "_id")  # heuristic PK suffix

JDBC_JAR_PATH = os.getenv(
    "JDBC_JAR_PATH",
    str(REPO_ROOT / "jars" / "postgresql.jar"),
)

ISO_FMT = "%Y-%m-%dT%H:%M:%S"
JDBC_URL = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"


def require_jdbc_jar() -> None:
    """Fail fast, with a helpful message, if the JDBC driver isn't where expected."""
    if not Path(JDBC_JAR_PATH).is_file():
        raise FileNotFoundError(
            f"\n\nPostgreSQL JDBC JAR not found at:\n  {JDBC_JAR_PATH}\n\n"
            "Fix options:\n"
            "  1. Place the JAR at the path above (jars/postgresql.jar)\n"
            "  2. Or point to an existing JAR via env var:\n"
            "       Windows : set JDBC_JAR_PATH=C:\\path\\to\\postgresql-42.x.x.jar\n"
            "       Mac/Linux: export JDBC_JAR_PATH=/path/to/postgresql-42.x.x.jar\n"
            "  Download from: https://jdbc.postgresql.org/download/\n"
        )
