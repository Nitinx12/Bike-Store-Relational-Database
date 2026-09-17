"""tests/unit/test_dashboard.py — protect dashboard from regressions.

Any change to dashboard/data.py, charts.py, SQL, or DB schema that
breaks the Streamlit app will fail these tests and block the PR
(via CI dashboard job + branch protection).
"""

from __future__ import annotations

import pandas as pd
from unittest.mock import patch


def test_imports():
    import dashboard.charts as ch
    import dashboard.data as d
    import streamlit_app  # noqa: F401

    assert hasattr(ch, "monthly_revenue")
    assert hasattr(d, "fetch_kpis")


def test_sample_fallback_available():
    from dashboard.data import _sample_fallback

    for name in (
        "kpis",
        "monthly",
        "customers",
        "products",
        "stores",
        "categories",
        "brands",
        "timeseries",
    ):
        df = _sample_fallback(name)
        assert df is not None and not df.empty, f"sample {name} missing"
        assert len(df) > 0


def test_kpis_fallback_when_db_down():
    from dashboard.data import fetch_kpis

    with patch("dashboard.data._engine", side_effect=Exception("no db")):
        k = fetch_kpis()
    assert "customers" in k and k["customers"] > 0
    assert "orders_by_status" in k


def test_monthly_fallback_when_db_down():
    from dashboard.data import fetch_monthly_sales

    with patch("dashboard.data._engine", side_effect=Exception("no db")):
        df = fetch_monthly_sales()
    assert not df.empty
    assert "net_revenue" in df.columns


def test_customers_fallback_respects_limit():
    from dashboard.data import fetch_customer_rfm

    with patch("dashboard.data._engine", side_effect=Exception("no db")):
        df = fetch_customer_rfm(limit=50)
    assert len(df) == 50
    assert "lifetime_value" in df.columns


def test_charts_render_with_sample():
    from dashboard.charts import brand_bar, category_treemap, monthly_revenue, store_bar
    from dashboard.data import _sample_fallback

    monthly = _sample_fallback("monthly")
    assert monthly is not None
    fig = monthly_revenue(monthly)
    assert len(fig.data) == 2

    cat = _sample_fallback("categories")
    fig2 = category_treemap(cat)
    assert fig2 is not None

    brand = _sample_fallback("brands")
    fig3 = brand_bar(brand)
    assert len(fig3.data) > 0

    stores = _sample_fallback("stores")
    fig4 = store_bar(stores)
    assert len(fig4.data) > 0


def test_time_series_resample():
    from dashboard.charts import time_series
    from dashboard.data import _sample_fallback

    ts = _sample_fallback("timeseries")
    assert ts is not None
    # ensure date col is datetime after fallback
    assert pd.api.types.is_datetime64_any_dtype(pd.to_datetime(ts["order_date"]))
    fig = time_series(ts, freq="ME")
    assert len(fig.data) == 1
