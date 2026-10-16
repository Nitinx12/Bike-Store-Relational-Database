"""Products page — catalog mix, winners, portfolio, and inventory."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
from dashboard.lib.charts import bubble, pareto, sunburst, treemap
from dashboard.lib.filter import sidebar_filters
from dashboard.lib.queries import get_product_revenue, get_stock_levels

st.set_page_config(page_title="Products", page_icon="🚲", layout="wide")
plotly_template.apply_default_template(get_theme())
st.markdown(inject_css(), unsafe_allow_html=True)
st.title("Products")

filters, _meta = sidebar_filters()
filter_chips(filters)

try:
    products = get_product_revenue(filters)
    stock = get_stock_levels()
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load product data: {exc}")
    st.stop()

if products.empty:
    empty_state("No product sales for the current filters.")
    st.stop()

card_header("Catalog mix", "Category → brand revenue")
st.plotly_chart(treemap(products), width="stretch", config={"displayModeBar": False})

c1, c2 = st.columns(2)
with c1:
    card_header("Top products (Pareto)", "Bars plus the cumulative 80% line")
    fig, n80 = pareto(products.head(30))
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption(f"{n80} of the top 30 products drive 80% of their revenue.")
with c2:
    card_header("Portfolio", "Units vs revenue, sized by revenue, colored by category")
    st.plotly_chart(
        bubble(products.head(60)), width="stretch", config={"displayModeBar": False}
    )

card_header("Category → brand → product", "Full hierarchy in one view")
st.plotly_chart(sunburst(products), width="stretch", config={"displayModeBar": False})

card_header("List-price distribution", "Catalog pricing shape for filtered products")
price = px.histogram(
    products, x="list_price", nbins=30, labels={"list_price": "List price"}
)
st.plotly_chart(
    style(price, height=320), width="stretch", config={"displayModeBar": False}
)

card_header("Inventory watch", "Lowest-stock lines first (live snapshot, all stores)")
low_at = st.slider("Flag stock at or below", 0, 50, 5)
low = stock[stock["quantity"] <= low_at]
st.caption(
    f"{len(low)} of {len(stock)} store×product lines at or below {low_at} units."
)
dataframe_with_download(
    low.head(200) if not low.empty else low, "low_stock.csv", key="dl_low_stock"
)

footer()
