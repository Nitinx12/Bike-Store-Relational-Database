"""streamlit_app.py — Bike Store production dashboard.

Entry point for `streamlit run streamlit_app.py` and Streamlit Cloud
(main file path = streamlit_app.py).

- Plotly for every chart (no matplotlib)
- st.cache_data (5-min TTL) via dashboard.data.cached_fetchers
- st.secrets → .env fallback, so Cloud and local `uv run` both work
- Graceful error banners (never a raw traceback to the user)
- Sidebar filters + 5 tabs mirroring the 21-report SQL library
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.charts import (
    brand_bar,
    category_treemap,
    customer_scatter,
    monthly_revenue,
    product_scatter,
    store_bar,
    time_series,
)
from dashboard.data import cached_fetchers

st.set_page_config(
    page_title="Bike Store — Operations Dashboard",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Light CSS polish (production: subtle, not flashy) ──────────
st.markdown(
    """
<style>
  .kpi { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:14px 16px; }
  .kpi .label { color:#64748B; font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
  .kpi .value { color:#0F172A; font-size:28px; font-weight:700; line-height:1.1; }
  .kpi .delta { color:#0F766E; font-size:12px; }
  div[data-testid="stMetric"] { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:12px; padding:8px; }
</style>
""",
    unsafe_allow_html=True,
)

try:
    fetcher = cached_fetchers()
    HAS_DATA = True
except Exception as e:
    fetcher = {}
    HAS_DATA = False
    st.error(f"Dashboard init failed: {e}")

# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.title("🚲 Bike Store")
    st.caption("Mongo → Postgres → GX → Plotly")
    st.divider()
    freq = st.selectbox(
        "Time grain",
        ["D", "W", "ME"],
        index=2,
        format_func=lambda x: {"D": "Daily", "W": "Weekly", "ME": "Monthly"}[x],
    )
    top_n_customers = st.slider("Top customers", 50, 1000, 200, step=50)
    top_n_products = st.slider("Top products", 50, 500, 100, step=50)
    st.divider()
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("TTL 5 min • `uv run streamlit run streamlit_app.py` locally")
    try:
        has_pg = "postgres" in st.secrets  # type: ignore[attr-defined]
    except Exception:
        has_pg = False
    if not has_pg:
        st.info("Using `.env` (local). On Cloud set `postgres.*` in Secrets.", icon="ℹ️")
    else:
        st.success("Using `st.secrets` (Cloud).", icon="✅")


# ── Helpers ───────────────────────────────────────────────────
def _safe(fetch, *args, **kwargs):
    try:
        return fetch(*args, **kwargs)
    except Exception as e:
        st.warning(f"Data unavailable: {e}", icon="⚠️")
        return None


def kpi_card(label: str, value: str, delta: str | None = None):
    delta_html = f'<div class="delta">{delta}</div>' if delta else ""
    st.markdown(
        f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div>{delta_html}</div>',
        unsafe_allow_html=True,
    )


# ── Header KPIs ───────────────────────────────────────────────
st.title("Operations Dashboard")
st.caption("Incremental ETL • Great Expectations • PL/pgSQL loops — live from Postgres")

kpis = _safe(fetcher["kpis"]) if "kpis" in fetcher else None
if kpis and isinstance(kpis, dict) and kpis.get("customers") is not None:
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Customers", f"{kpis['customers']:,}")
    with c2:
        kpi_card("Products", f"{kpis['products']:,}")
    with c3:
        kpi_card(
            "Orders",
            f"{kpis['orders']:,}",
            delta=f"{kpis.get('orders_by_status', {}).get('Completed', 0):,} completed",
        )
    with c4:
        kpi_card("Order items", f"{kpis['order_items']:,}")
    with c5:
        rev = float(kpis.get("gross_revenue") or 0)
        kpi_card("Gross revenue", f"${rev:,.0f}")
else:
    st.info("No KPI data — is the ETL run? `uv run python main.py`", icon="ℹ️")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────
tab_overview, tab_sales, tab_customers, tab_products, tab_stores = st.tabs(
    ["📊 Overview", "📈 Sales", "👥 Customers", "📦 Products", "🏬 Stores"]
)

# ── Overview ──────────────────────────────────────────────────
with tab_overview:
    col_a, col_b = st.columns([1.4, 1])
    with col_a:
        df_m = _safe(fetcher["monthly"]) if "monthly" in fetcher else pd.DataFrame()
        if df_m is not None and not df_m.empty:
            st.plotly_chart(monthly_revenue(df_m), use_container_width=True)
        else:
            st.info("No monthly sales yet.")
    with col_b:
        df_cat = _safe(fetcher["cat_mix"]) if "cat_mix" in fetcher else pd.DataFrame()
        if df_cat is not None and not df_cat.empty:
            st.plotly_chart(category_treemap(df_cat), use_container_width=True)
        else:
            st.info("No category data.")
    df_brand = _safe(fetcher["brand_mix"]) if "brand_mix" in fetcher else pd.DataFrame()
    if df_brand is not None and not df_brand.empty:
        st.plotly_chart(brand_bar(df_brand), use_container_width=True)

    st.divider()
    st.subheader("Revenue time series (resampled)")
    df_ts = _safe(fetcher["ts"]) if "ts" in fetcher else pd.DataFrame()
    if df_ts is not None and not df_ts.empty:
        st.plotly_chart(time_series(df_ts, freq=freq), use_container_width=True)
        with st.expander("Raw daily grain"):
            st.dataframe(df_ts, use_container_width=True, height=240)
    else:
        st.info("No time series data.")

# ── Sales ─────────────────────────────────────────────────────
with tab_sales:
    df_m = _safe(fetcher["monthly"]) if "monthly" in fetcher else pd.DataFrame()
    if df_m is not None and not df_m.empty:
        st.dataframe(
            df_m.assign(order_month=df_m["order_month"].dt.strftime("%Y-%m")).rename(
                columns={
                    "order_month": "Month",
                    "orders": "Orders",
                    "customers": "Customers",
                    "units": "Units",
                    "net_revenue": "Net revenue",
                    "discounts": "Discounts",
                }
            ),
            use_container_width=True,
            height=360,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Avg net revenue / month", f"${df_m['net_revenue'].mean():,.0f}")
        with c2:
            st.metric("Avg orders / month", f"{df_m['orders'].mean():,.0f}")
        with c3:
            st.metric("Total discounts", f"${df_m['discounts'].sum():,.0f}")
    else:
        st.info("No sales data.")

# ── Customers ────────────────────────────────────────────────
with tab_customers:
    df_c = (
        _safe(fetcher["customers"], top_n_customers)
        if "customers" in fetcher
        else pd.DataFrame()
    )
    if df_c is not None and not df_c.empty:
        st.plotly_chart(customer_scatter(df_c), use_container_width=True)
        st.dataframe(df_c, use_container_width=True, height=420)
        st.download_button(
            "Download customers CSV",
            df_c.to_csv(index=False).encode(),
            "customers.csv",
            "text/csv",
            use_container_width=False,
        )
    else:
        st.info("No customer data.")

# ── Products ─────────────────────────────────────────────────
with tab_products:
    df_p = (
        _safe(fetcher["products"], top_n_products)
        if "products" in fetcher
        else pd.DataFrame()
    )
    if df_p is not None and not df_p.empty:
        st.plotly_chart(product_scatter(df_p), use_container_width=True)
        st.dataframe(df_p, use_container_width=True, height=420)
        st.download_button(
            "Download products CSV",
            df_p.to_csv(index=False).encode(),
            "products.csv",
            "text/csv",
        )
    else:
        st.info("No product data.")

# ── Stores ────────────────────────────────────────────────────
with tab_stores:
    df_s = _safe(fetcher["stores"]) if "stores" in fetcher else pd.DataFrame()
    if df_s is not None and not df_s.empty:
        st.plotly_chart(store_bar(df_s), use_container_width=True)
        st.dataframe(df_s, use_container_width=True, height=320)
    else:
        st.info(
            "No store data. Did `fn_store_performance()` get installed? `psql -f sql/15_fn_store_performance.sql`"
        )

st.divider()
st.caption(
    "Built with Streamlit + Plotly • Data from `public.*` via `utils.engine.postgres_engine()` • Cache 5 min • Deploy: Streamlit Cloud → Main file `streamlit_app.py`"
)
