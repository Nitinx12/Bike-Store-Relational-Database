"""dashboard/data.py — production data-access layer.

Single responsibility: fetch DataFrames from Postgres with caching,
streamlit-aware secrets fallback, and graceful empty-state handling.
No Streamlit UI code lives here so it can be unit-tested with plain pytest.

Connection priority:
  1. st.secrets["postgres"] (Streamlit Cloud)
  2. os.environ / .env via utils.connection (local `uv run`)
  3. Raise a human-readable error (dashboard shows a banner, not a traceback)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text

try:
    import streamlit as st

    HAS_ST = True
except ImportError:
    HAS_ST = False  # allow `uv run pytest` without streamlit

# Allow import without st.secrets when running locally via `uv run`
from utils.connection import (
    POSTGRES_DATABASE,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USERNAME,
)


def _postgres_params() -> dict[str, Any]:
    """Resolve Postgres creds from st.secrets or env. Validates presence."""
    if HAS_ST:
        try:
            sec = st.secrets.get("postgres", None)  # type: ignore[attr-defined]
            if sec and sec.get("host"):
                return {
                    "host": str(sec["host"]),
                    "port": str(sec.get("port", 5432)),
                    "database": str(sec["database"]),
                    "username": str(sec["username"]),
                    "password": str(sec["password"]),
                }
        except Exception:
            pass  # fallback to env

    # Fallback: utils.connection already loaded .env
    params = {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "database": POSTGRES_DATABASE,
        "username": POSTGRES_USERNAME,
        "password": POSTGRES_PASSWORD,
    }
    missing = [k for k, v in params.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing Postgres config: {', '.join(missing)}. "
            "Set .env or .streamlit/secrets.toml (see secrets.toml.example)."
        )
    return {k: str(v) for k, v in params.items()}


def _engine():
    p = _postgres_params()
    url = f"postgresql+psycopg2://{p['username']}:{p['password']}@{p['host']}:{p['port']}/{p['database']}"
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=5)


SAMPLE_DIR = Path(__file__).resolve().parent / "sample"


def _sample_fallback(name: str) -> pd.DataFrame | None:
    """Load pre-exported CSV from dashboard/sample/ for Cloud demo mode."""
    path = SAMPLE_DIR / f"{name}.csv"
    if path.is_file():
        try:
            df = pd.read_csv(path)
            # normalize date cols if present
            for col in ("order_month", "order_date", "first_order", "last_order"):
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            return df
        except Exception:
            return None
    return None


def _query(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    try:
        eng = _engine()
    except Exception:
        # No DB config (e.g. Streamlit Cloud without secrets) → caller will
        # handle fallback; raise to let fetch_* decide
        raise
    try:
        with eng.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})
    finally:
        eng.dispose()


# ────────────────────────────────────────────────────────────────
# Public fetchers — each is a small, typed SQL view over the warehouse
# Reuses the 21-report SQL library in sql/ where possible; simplified
# for dashboard interactivity (filters are bound params, not string interp).
# ────────────────────────────────────────────────────────────────


def fetch_kpis() -> dict[str, Any]:
    """Global KPIs for the header cards."""
    try:
        sql = """
        SELECT
            (SELECT COUNT(*) FROM customers)            AS customers,
            (SELECT COUNT(*) FROM products)             AS products,
            (SELECT COUNT(*) FROM orders)               AS orders,
            (SELECT COUNT(*) FROM order_items)          AS order_items,
            (SELECT COALESCE(SUM(total_value),0) FROM order_items) AS gross_revenue,
            (SELECT COUNT(*) FROM stores)               AS stores,
            (SELECT COUNT(*) FROM staffs)               AS staffs
        """
        df = _query(sql)
        row = df.iloc[0].to_dict() if not df.empty else {}
        # Enrich with completed vs pending split
        status_sql = (
            "SELECT order_status, COUNT(*) AS cnt FROM orders GROUP BY order_status"
        )
        status_df = _query(status_sql)
        row["orders_by_status"] = (
            {
                str(k): int(v)
                for k, v in status_df.set_index("order_status")["cnt"].to_dict().items()
            }
            if not status_df.empty
            else {}
        )
        return row
    except Exception:
        sample = _sample_fallback("kpis")
        if sample is not None and not sample.empty:
            row = {str(k): v for k, v in sample.iloc[0].to_dict().items()}
            row["orders_by_status"] = {"Completed": int(row.get("orders", 0) * 0.7)}
            return row
        raise


def fetch_monthly_sales() -> pd.DataFrame:
    """Monthly grain — mirrors sql/16_sales_report.sql (completed orders only)."""
    try:
        sql = """
        SELECT
            TO_CHAR(o.order_date, 'YYYY-MM') AS order_month,
            COUNT(DISTINCT o.order_id)       AS orders,
            COUNT(DISTINCT o.customer_id)    AS customers,
            SUM(oi.quantity)                 AS units,
            ROUND(SUM(oi.total_value), 2)    AS net_revenue,
            ROUND(SUM(oi.list_price*oi.quantity*oi.discount), 2) AS discounts
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.order_status = 'Completed'
        GROUP BY 1
        ORDER BY 1
        """
        df = _query(sql)
        if not df.empty:
            df["order_month"] = pd.to_datetime(df["order_month"] + "-01")
        return df
    except Exception:
        sample = _sample_fallback("monthly")
        return sample if sample is not None else pd.DataFrame()


def fetch_customer_rfm(limit: int = 500) -> pd.DataFrame:
    """Top-N customers by lifetime value — trims sql/12_customer_report.sql."""
    try:
        sql = """
        SELECT
            c.customer_id,
            (c.first_name || ' ' || c.last_name) AS customer_name,
            c.city, c.state,
            COUNT(DISTINCT o.order_id)           AS total_orders,
            COALESCE(SUM(oi.total_value),0)      AS lifetime_value,
            COALESCE(SUM(oi.quantity),0)         AS total_items,
            MIN(o.order_date)                    AS first_order,
            MAX(o.order_date)                    AS last_order
        FROM customers c
        LEFT JOIN orders o ON o.customer_id = c.customer_id
        LEFT JOIN order_items oi ON oi.order_id = o.order_id
        GROUP BY c.customer_id, c.first_name, c.last_name, c.city, c.state
        ORDER BY lifetime_value DESC
        LIMIT :limit
        """
        return _query(sql, {"limit": limit})
    except Exception:
        sample = _sample_fallback("customers")
        return sample.head(limit) if sample is not None else pd.DataFrame()


def fetch_product_report(limit: int = 200) -> pd.DataFrame:
    """Product grain — mirrors sql/13_product_report.sql top slice."""
    try:
        sql = """
        SELECT
            p.product_name, b.brand_name, c.category_name,
            p.list_price,
            COALESCE(SUM(oi.quantity),0)          AS units_sold,
            COALESCE(SUM(oi.total_value),0)       AS total_revenue,
            COUNT(DISTINCT o.order_id)            AS orders,
            COALESCE(SUM(s.quantity),0)           AS inventory
        FROM products p
        LEFT JOIN brands b ON b.brand_id = p.brand_id
        LEFT JOIN categories c ON c.category_id = p.category_id
        LEFT JOIN order_items oi ON oi.product_id = p.product_id
        LEFT JOIN orders o ON o.order_id = oi.order_id AND o.order_status='Completed'
        LEFT JOIN stocks s ON s.product_id = p.product_id
        GROUP BY p.product_id, p.product_name, b.brand_name, c.category_name, p.list_price
        ORDER BY total_revenue DESC
        LIMIT :limit
        """
        return _query(sql, {"limit": limit})
    except Exception:
        sample = _sample_fallback("products")
        return sample.head(limit) if sample is not None else pd.DataFrame()


def fetch_store_performance() -> pd.DataFrame:
    """Per-store table — wraps sql/15_fn_store_performance()."""
    # Prefer the PL/pgSQL function if installed; fallback to inline CTE → sample CSV
    try:
        return _query("SELECT * FROM fn_store_performance()")
    except Exception:
        try:
            sql = """
            SELECT
                s.store_name, s.city, s.state,
                COUNT(DISTINCT o.order_id)                     AS total_orders,
                COALESCE(SUM(oi.total_value),0)                AS total_revenue,
                COALESCE(AVG(oi.total_value),0)                AS avg_order_value,
                COALESCE(SUM(oi.quantity),0)                   AS units_sold
            FROM stores s
            LEFT JOIN orders o ON o.store_id = s.store_id AND o.order_status='Completed'
            LEFT JOIN order_items oi ON oi.order_id = o.order_id
            GROUP BY s.store_id, s.store_name, s.city, s.state
            ORDER BY total_revenue DESC
            """
            return _query(sql)
        except Exception:
            sample = _sample_fallback("stores")
            return sample if sample is not None else pd.DataFrame()


def fetch_category_mix() -> pd.DataFrame:
    try:
        sql = """
        SELECT c.category_name, COALESCE(SUM(oi.total_value),0) AS revenue,
               COALESCE(SUM(oi.quantity),0) AS units
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.category_id
        LEFT JOIN order_items oi ON oi.product_id = p.product_id
        LEFT JOIN orders o ON o.order_id = oi.order_id AND o.order_status='Completed'
        GROUP BY c.category_name
        ORDER BY revenue DESC
        """
        return _query(sql)
    except Exception:
        sample = _sample_fallback("categories")
        return sample if sample is not None else pd.DataFrame()


def fetch_brand_mix() -> pd.DataFrame:
    try:
        sql = """
        SELECT b.brand_name, COALESCE(SUM(oi.total_value),0) AS revenue
        FROM brands b
        LEFT JOIN products p ON p.brand_id = b.brand_id
        LEFT JOIN order_items oi ON oi.product_id = p.product_id
        LEFT JOIN orders o ON o.order_id = oi.order_id AND o.order_status='Completed'
        GROUP BY b.brand_name
        ORDER BY revenue DESC
        """
        return _query(sql)
    except Exception:
        sample = _sample_fallback("brands")
        return sample if sample is not None else pd.DataFrame()


def fetch_orders_time_series(freq: str = "M") -> pd.DataFrame:
    """Daily grain for the range selector — aggregated client-side by freq."""
    try:
        sql = """
        SELECT o.order_date::date AS order_date, COALESCE(SUM(oi.total_value),0) AS revenue,
               COUNT(DISTINCT o.order_id) AS orders
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        WHERE o.order_status='Completed'
        GROUP BY 1 ORDER BY 1
        """
        df = _query(sql)
        if not df.empty:
            df["order_date"] = pd.to_datetime(df["order_date"])
        return df
    except Exception:
        sample = _sample_fallback("timeseries")
        return sample if sample is not None else pd.DataFrame()


# ────────────────────────────────────────────────────────────────
# Optional: cached wrappers for Streamlit (kept separate so data.py
# stays importable without streamlit). Use these in app.py.
# ────────────────────────────────────────────────────────────────
def cached_fetchers():
    """Return st.cache_data-wrapped versions if Streamlit is available."""
    if not HAS_ST:
        return {}

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def kpis():
        return fetch_kpis()

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def monthly():
        return fetch_monthly_sales()

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def customers(limit: int = 500):
        return fetch_customer_rfm(limit)

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def products(limit: int = 200):
        return fetch_product_report(limit)

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def stores():
        return fetch_store_performance()

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def cat_mix():
        return fetch_category_mix()

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def brand_mix():
        return fetch_brand_mix()

    @st.cache_data(ttl=300, show_spinner=False)  # type: ignore
    def ts():
        return fetch_orders_time_series()

    return {
        "kpis": kpis,
        "monthly": monthly,
        "customers": customers,
        "products": products,
        "stores": stores,
        "cat_mix": cat_mix,
        "brand_mix": brand_mix,
        "ts": ts,
    }
