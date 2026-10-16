"""Sales page — trend, mix, weekday rhythm, and month-over-month movers."""

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
from dashboard.lib.charts import (
    bar_by,
    donut,
    revenue_trend_chart,
    waterfall,
    weekday_revenue_chart,
)
from dashboard.lib.filter import sidebar_filters
from dashboard.lib.queries import (
    get_category_monthly_revenue,
    get_dow_revenue,
    get_revenue_by,
    get_revenue_trend,
)

st.set_page_config(page_title="Sales", page_icon="📊", layout="wide")
plotly_template.apply_default_template(get_theme())
st.markdown(inject_css(), unsafe_allow_html=True)
st.title("Sales")

filters, _meta = sidebar_filters()
filter_chips(filters)
granularity = st.radio(
    "Trend granularity", ["Day", "Week", "Month"], index=1, horizontal=True
).lower()

try:
    trend = get_revenue_trend(filters, granularity)
    by_store = get_revenue_by(filters, "store")
    by_category = get_revenue_by(filters, "category")
    by_status = get_revenue_by(filters, "status")
    dow = get_dow_revenue(filters)
    cat_monthly = get_category_monthly_revenue(filters)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load sales data: {exc}")
    st.stop()

card_header("Revenue trend", f"By {granularity}")
if trend.empty:
    empty_state("No revenue in this window.", "Try widening the date range.")
else:
    st.plotly_chart(
        revenue_trend_chart(trend, granularity),
        width="stretch",
        config={"displayModeBar": False},
    )

c1, c2 = st.columns(2)
with c1:
    card_header("Revenue by store", "Same filters, all stores")
    if by_store.empty:
        empty_state("No rows for the current filters.")
    else:
        named = by_store.rename(columns={"name": "store_name"})
        st.plotly_chart(
            bar_by(named, "store_name"),
            width="stretch",
            config={"displayModeBar": False},
        )
        dataframe_with_download(named, "revenue_by_store.csv", key="dl_sales_store")
with c2:
    card_header("Revenue by category", "Mix for the selected window")
    if by_category.empty:
        empty_state("No rows for the current filters.")
    else:
        named = by_category.rename(columns={"name": "category_name"})
        st.plotly_chart(
            donut(named, "category_name"),
            width="stretch",
            config={"displayModeBar": False},
        )
        dataframe_with_download(named, "revenue_by_category.csv", key="dl_sales_cat")

c3, c4 = st.columns(2)
with c3:
    card_header("Revenue by order status", "Completed dominates by design")
    if by_status.empty:
        empty_state("No rows for the current filters.")
    else:
        st.plotly_chart(
            bar_by(by_status.rename(columns={"name": "order_status"}), "order_status"),
            width="stretch",
            config={"displayModeBar": False},
        )
with c4:
    card_header("When shoppers buy", "Weekday pattern (dates carry no time of day)")
    if dow.empty:
        empty_state("No rows for the current filters.")
    else:
        st.plotly_chart(
            weekday_revenue_chart(dow),
            width="stretch",
            config={"displayModeBar": False},
        )

card_header(
    "What moved month over month", "Category change between the last two months"
)
months = sorted(cat_monthly["month"].unique()) if not cat_monthly.empty else []
if len(months) >= 2:
    last, prev = months[-1], months[-2]
    cur = cat_monthly[cat_monthly["month"] == last].set_index("category_name")[
        "revenue"
    ]
    old = cat_monthly[cat_monthly["month"] == prev].set_index("category_name")[
        "revenue"
    ]
    delta = cur.sub(old, fill_value=0.0).reset_index()
    delta.columns = ["category_name", "delta"]
    delta = delta.sort_values("delta", ascending=False)
    st.plotly_chart(waterfall(delta), width="stretch", config={"displayModeBar": False})
    st.caption(f"Category change from {prev:%b %Y} to {last:%b %Y}.")
else:
    st.caption("Pick a window spanning two months to see movement.")

footer()
