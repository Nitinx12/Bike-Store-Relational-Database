"""Stores page — location scoreboard and staff leaderboard."""

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
    dataframe_with_download,
    empty_state,
    filter_chips,
    footer,
)
from dashboard.helpers.theme import get_theme, inject_css
from dashboard.lib.charts import bar_by
from dashboard.lib.filter import sidebar_filters
from dashboard.lib.queries import get_staff_performance, get_store_performance

st.set_page_config(page_title="Stores", page_icon="🏬", layout="wide")
plotly_template.apply_default_template(get_theme())
st.markdown(inject_css(), unsafe_allow_html=True)
st.title("Stores")

filters, _meta = sidebar_filters()
filter_chips(filters)

try:
    stores = get_store_performance(filters)
    staff = get_staff_performance(filters)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load store data: {exc}")
    st.stop()

card_header("Store scoreboard", "Revenue, orders, customers, and units per location")
if stores.empty:
    empty_state("No rows for the current filters.")
else:
    st.plotly_chart(
        bar_by(stores.rename(columns={"store_name": "store"}), "store"),
        width="stretch",
        config={"displayModeBar": False},
    )
    table = stores.copy()
    table["revenue"] = table["revenue"].map(lambda v: f"${v:,.0f}")
    dataframe_with_download(table, "store_performance.csv", key="dl_store_perf")

card_header("Staff leaderboard", "Revenue and orders handled per staff member")
if staff.empty:
    empty_state("No rows for the current filters.")
else:
    table = staff.copy()
    table["revenue"] = table["revenue"].map(lambda v: f"${v:,.0f}")
    dataframe_with_download(
        table,
        "staff_performance.csv",
        key="dl_staff_perf",
        column_config={"staff_name": "Staff", "store_name": "Store"},
    )

footer()
