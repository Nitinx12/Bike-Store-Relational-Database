"""Customers page — RFM portfolio, leaders, geography, and retention."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.express as px
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
from dashboard.helpers.theme import get_theme, inject_css, style
from dashboard.lib.charts import cohort_heatmap, rfm_scatter
from dashboard.lib.filter import sidebar_filters
from dashboard.lib.queries import get_customer_rfm, get_first_order_cohorts


def segment_rfm(df: pd.DataFrame) -> pd.Series:
    """Transparent rule-based segments (documented, no black box).

    - Champions: frequent AND top-quartile spend
    - Loyal: frequent, lower spend
    - Big spenders: top-quartile spend, infrequent
    - Occasional: a single order
    - Potential: everyone else
    """
    if df.empty:
        return pd.Series(dtype=str)
    spend_q3 = df["monetary"].quantile(0.75)

    def label(row) -> str:
        frequent = row["frequency"] >= 3
        big = row["monetary"] >= spend_q3
        if frequent and big:
            return "Champions"
        if frequent:
            return "Loyal"
        if big:
            return "Big spenders"
        if row["frequency"] <= 1:
            return "Occasional"
        return "Potential"

    return df.apply(label, axis=1)


st.set_page_config(page_title="Customers", page_icon="👥", layout="wide")
plotly_template.apply_default_template(get_theme())
st.markdown(inject_css(), unsafe_allow_html=True)
st.title("Customers")

filters, _meta = sidebar_filters()
filter_chips(filters)

try:
    rfm = get_customer_rfm(filters)
    cohorts = get_first_order_cohorts()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load customer data: {exc}")
    st.stop()

if rfm.empty:
    empty_state("No customers for the current filters.")
    st.stop()

rfm = rfm.copy()
rfm["segment"] = segment_rfm(rfm)

card_header("Customer portfolio", "Frequency vs spend, colored by segment")
st.plotly_chart(rfm_scatter(rfm), width="stretch", config={"displayModeBar": False})

c1, c2 = st.columns(2)
with c1:
    card_header("Top customers", "By spend in the selected window")
    top = rfm.head(50).copy()
    top["monetary"] = top["monetary"].map(lambda v: f"${v:,.0f}")
    dataframe_with_download(top, "top_customers.csv", key="dl_top_customers")
with c2:
    card_header("Where customers live", "Customer count by state")
    by_state = rfm.groupby("state").size().reset_index(name="customers")
    fig = px.bar(
        by_state,
        x="state",
        y="customers",
        labels={"state": "", "customers": "Customers"},
    )
    fig.update_traces(
        hovertemplate="%{x}: %{y:,} customers<extra></extra>", marker_line_width=0
    )
    st.plotly_chart(
        style(fig, currency=False, height=360),
        width="stretch",
        config={"displayModeBar": False},
    )

card_header(
    "Retention cohorts", "Share of each first-order cohort still buying, by month"
)
if cohorts.empty:
    empty_state("Not enough history for cohorts.")
else:
    st.plotly_chart(
        cohort_heatmap(cohorts), width="stretch", config={"displayModeBar": False}
    )
    st.caption(
        "Cohorts are all-time (first-ever order month), independent of sidebar filters."
    )

footer()
