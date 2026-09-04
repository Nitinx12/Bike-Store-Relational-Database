"""
Convenience entry point for the data-quality suite.

    python scripts/run_gx.py                  # validate every table
    python scripts/run_gx.py orders products   # validate specific tables

All the actual logic (building the GX context, building suites, running
validations, writing the report) lives in tests/data_quality/run.py; this
is a thin wrapper so the suite can be launched from a top-level scripts/
folder - handy for a Makefile target, a CI step, or an IDE run
configuration - without needing to know the tests/data_quality/ internal
package layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_QUALITY_DIR = ROOT_DIR / "tests" / "data_quality"

for p in (DATA_QUALITY_DIR, ROOT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from run import main  # tests/data_quality/run.py

if __name__ == "__main__":
    sys.exit(main())
