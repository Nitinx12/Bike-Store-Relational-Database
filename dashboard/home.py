"""
Bike Store home — executive overview.
Note: uv run streamlit run dashboard/home.py to run the dashboard locally.

"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from dashboard.lib.db import apply_secrets

apply_secrets()

from dashboard.helpers import plotly_template
from dashboard.helpers.components import (
    card_header,
    empty_state,
    filter_chips,
    footer,
    freshness_badge,
    kpi_cards,
    section_head,
)
from dashboard.helpers.theme import get_theme, inject_css
from dashboard.lib.charts import bar_by, donut, funnel, revenue_trend_chart
from dashboard.lib.filter import sidebar_filters
from dashboard.lib.queries import (
    get_kpis,
    get_order_status_counts,
    get_revenue_by,
    get_revenue_trend,
    period_deltas,
)

st.set_page_config(page_title="Bike Store Dashboard", page_icon="🚲", layout="wide")
plotly_template.apply_default_template(get_theme())
st.markdown(inject_css(), unsafe_allow_html=True)

st.title("🚲 Bike Store")
st.caption(
    "Sales performance, live from Postgres. Use the sidebar to filter every page at once."
)

filters, meta = sidebar_filters()
filter_chips(filters)

try:
    kpis = get_kpis(filters)
    prior = get_kpis(filters.with_prior_window())
    trend = get_revenue_trend(filters, "week")
    by_category = get_revenue_by(filters, "category")
    by_store = get_revenue_by(filters, "store")
    by_status = get_order_status_counts(filters)
except Exception as exc:  # noqa: BLE001 -- warehouse error: explain, don't traceback
    st.error(f"Could not load dashboard data: {exc}")
    st.stop()

freshness_badge(meta["max_date"])
st.divider()

kpi_cards(
    revenue=kpis["revenue"],
    orders=kpis["orders"],
    customers=kpis["customers"],
    aov=kpis["aov"],
    deltas=period_deltas(kpis, prior),
    delta_label="vs prior period",
    sparklines={
        "revenue": trend["revenue"].tolist() if not trend.empty else [],
        "orders": trend["orders"].tolist() if not trend.empty else [],
    },
)

section_head("Revenue trend", "Weekly line-item totals for the selected window")
if trend.empty:
    empty_state("No revenue in this window.", "Try widening the date range.")
else:
    st.plotly_chart(
        revenue_trend_chart(trend, "week"),
        width="stretch",
        config={"displayModeBar": False},
    )

c1, c2 = st.columns(2)
with c1:
    card_header("Revenue by category", "Share of the selected window")
    if by_category.empty:
        empty_state("No rows for the current filters.")
    else:
        st.plotly_chart(
            donut(
                by_category.rename(columns={"name": "category_name"}), "category_name"
            ),
            width="stretch",
            config={"displayModeBar": False},
        )
with c2:
    card_header("Revenue by store", "All stores, same filters")
    if by_store.empty:
        empty_state("No rows for the current filters.")
    else:
        st.plotly_chart(
            bar_by(by_store.rename(columns={"name": "store_name"}), "store_name"),
            width="stretch",
            config={"displayModeBar": False},
        )

section_head("Order pipeline", "Where orders sit right now")
STATUS_ORDER = ["Pending", "Processing", "Completed", "Rejected"]
if by_status.empty:
    empty_state("No orders for the current filters.")
else:
    ordered = by_status.set_index("order_status").reindex(STATUS_ORDER).reset_index()
    ordered = ordered.dropna(subset=["order_status"])
    st.plotly_chart(
        funnel(ordered),
        width="stretch",
        config={"displayModeBar": False},
    )

footer()
