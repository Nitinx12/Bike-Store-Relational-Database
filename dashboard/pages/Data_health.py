"""Data health page — warehouse trust at a glance."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from dashboard.lib.db import apply_secrets

apply_secrets()

from dashboard.helpers import plotly_template
from dashboard.helpers.components import (
    card_header,
    empty_state,
    footer,
)
from dashboard.helpers.theme import get_theme, inject_css
from dashboard.lib.queries import get_data_health_checks, get_table_counts

st.set_page_config(page_title="Data Health", page_icon="🩺", layout="wide")
plotly_template.apply_default_template(get_theme())
st.markdown(inject_css(), unsafe_allow_html=True)
st.title("Data Health")
st.caption("Freshness and integrity of the Postgres warehouse behind this dashboard.")

try:
    counts = get_table_counts()
    checks = get_data_health_checks()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not reach Postgres: {exc}")
    st.stop()

card_header("Table volumes", "Row counts right now")
if counts.empty:
    empty_state("No tables found.")
else:
    st.dataframe(counts, width="stretch", hide_index=True)

card_header("Integrity checks", "Same rules the Great Expectations suite enforces")
failed = [c for c in checks if c["status"] != "PASS"]
if not failed:
    st.success(f"All {len(checks)} checks pass.")
else:
    st.error(f"{len(failed)} of {len(checks)} checks failing.")
for check in checks:
    icon = "✅" if check["status"] == "PASS" else "❌"
    st.write(f"{icon} **{check['check']}** — {check['detail']}")

st.caption(
    "Full history with trends: run `uv run python scripts/run_gx.py` "
    "for the per-table Great Expectations report."
)

footer()
