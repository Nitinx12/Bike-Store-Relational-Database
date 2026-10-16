"""
dashboard/helpers/queries.py — all SQL against the warehouse lives here.

Two design choices drive this file:

1. Every query is parameterized via SQLAlchemy ``text()`` + bound params —
   never f-string-interpolated filter values — so the dashboard stays
   immune to SQL injection no matter what lands in a widget.
2. Filtering AND aggregation both happen in Postgres, not pandas. Only
   the already-summarized rows a chart needs come back over the wire.

Revenue is ``SUM(order_items.total_value)`` (line-level actuals), joined
through ``orders`` so every date/status/store filter applies uniformly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

import pandas as pd
import streamlit as st
from sqlalchemy import text

from dashboard.lib.db import db_schema, get_engine

_CACHE_TTL = 600  # seconds; warehouse loads are batch, not streaming


# ---------------------------------------------------------------------------
# Filter model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Filters:
    """One immutable filter selection. Empty tuple == "all"."""

    start_date: date
    end_date: date  # exclusive
    stores: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    brands: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()

    def with_prior_window(self) -> Filters:
        """Same-length window immediately before the current one (for deltas)."""
        length = self.end_date - self.start_date
        return replace(
            self,
            start_date=self.start_date - length,
            end_date=self.start_date,
        )


def _schema() -> str:
    schema = db_schema()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise ValueError(f"Refusing suspicious schema name: {schema!r}")
    return schema


def _base_clauses(f: Filters, order_alias: str = "o") -> tuple[list[str], dict]:
    """Shared WHERE fragment for order-grained queries + its bound params."""
    clauses = [
        f'"{order_alias}"."order_date" >= :start_date',
        f'"{order_alias}"."order_date" < :end_date',
    ]
    params: dict = {"start_date": f.start_date, "end_date": f.end_date}
    optionals = (
        (f.statuses, f'"{order_alias}"."order_status"', "statuses"),
        (f.stores, '"s"."store_name"', "stores"),
        (f.categories, '"c"."category_name"', "categories"),
        (f.brands, '"b"."brand_name"', "brands"),
    )
    for values, column, key in optionals:
        if values:
            clauses.append(
                f"{column} IN ({', '.join(f':{key}_{i}' for i in range(len(values)))})"
            )
            params.update({f"{key}_{i}": v for i, v in enumerate(values)})
    return clauses, params


def _run(sql: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=list(result.keys()))
    # psycopg2 returns NUMERIC as Decimal, which breaks pandas/plotly
    # arithmetic downstream — normalize to float once, here.
    for column in df.columns:
        values = df[column]
        if (
            values.dtype == object
            and values.map(lambda v: isinstance(v, Decimal)).any()
        ):
            df[column] = values.astype(float)
    return df


# ---------------------------------------------------------------------------
# Filter options / bounds
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_filter_options() -> dict:
    """Distinct sidebar values + dataset date range (cached)."""
    s = _schema()
    engine = get_engine()
    with engine.connect() as conn:
        opts = {
            "stores": [
                r[0]
                for r in conn.execute(
                    text(f'SELECT "store_name" FROM "{s}"."stores" ORDER BY 1')
                )
            ],
            "categories": [
                r[0]
                for r in conn.execute(
                    text(f'SELECT "category_name" FROM "{s}"."categories" ORDER BY 1')
                )
            ],
            "brands": [
                r[0]
                for r in conn.execute(
                    text(f'SELECT "brand_name" FROM "{s}"."brands" ORDER BY 1')
                )
            ],
            "statuses": [
                r[0]
                for r in conn.execute(
                    text(
                        f'SELECT DISTINCT "order_status" FROM "{s}"."orders" ORDER BY 1'
                    )
                )
            ],
        }
        bounds = conn.execute(
            text(f'SELECT MIN("order_date"), MAX("order_date") FROM "{s}"."orders"')
        ).one()
    opts["min_date"] = bounds[0]
    opts["max_date"] = bounds[1]
    return opts


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_kpis(f: Filters) -> dict:
    """Revenue, orders, customers, AOV for one window."""
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    df = _run(
        f"""SELECT COALESCE(SUM("i"."total_value"), 0) AS revenue,
                   COUNT(DISTINCT "o"."order_id") AS orders,
                   COUNT(DISTINCT "o"."customer_id") AS customers
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}""",
        params,
    )
    revenue = float(df["revenue"][0])
    orders = int(df["orders"][0])
    customers = int(df["customers"][0])
    return {
        "revenue": revenue,
        "orders": orders,
        "customers": customers,
        "aov": (revenue / orders) if orders else 0.0,
    }


def period_deltas(current: dict, prior: dict) -> dict[str, float | None]:
    """Percent change per KPI; None when the prior window is empty."""
    out: dict[str, float | None] = {}
    for key in ("revenue", "orders", "customers", "aov"):
        base = prior.get(key) or 0
        out[key] = ((current[key] - base) / base * 100) if base else None
    return out


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_revenue_trend(f: Filters, granularity: str = "week") -> pd.DataFrame:
    trunc = {"day": "day", "week": "week", "month": "month"}.get(granularity, "week")
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT date_trunc('{trunc}', "o"."order_date")::date AS period,
                   SUM("i"."total_value") AS revenue,
                   COUNT(DISTINCT "o"."order_id") AS orders
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1 ORDER BY 1""",
        params,
    )


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_revenue_by(f: Filters, dim: str) -> pd.DataFrame:
    """Revenue/orders split by store | category | brand | status."""
    columns = {
        "store": '"s"."store_name"',
        "category": '"c"."category_name"',
        "brand": '"b"."brand_name"',
        "status": '"o"."order_status"',
    }
    if dim not in columns:
        raise ValueError(f"Unknown dimension: {dim!r}")
    label = columns[dim]
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT {label} AS name,
                   SUM("i"."total_value") AS revenue,
                   COUNT(DISTINCT "o"."order_id") AS orders
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1 ORDER BY 2 DESC""",
        params,
    )


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_category_monthly_revenue(f: Filters) -> pd.DataFrame:
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT date_trunc('month', "o"."order_date")::date AS month,
                   "c"."category_name" AS category_name,
                   SUM("i"."total_value") AS revenue
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1, 2 ORDER BY 1, 2""",
        params,
    )


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_dow_revenue(f: Filters) -> pd.DataFrame:
    """Revenue by ISO weekday. (order_date is a DATE: no hourly grain exists.)"""
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT EXTRACT(ISODOW FROM "o"."order_date")::int AS dow,
                   SUM("i"."total_value") AS revenue,
                   COUNT(DISTINCT "o"."order_id") AS orders
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1 ORDER BY 1""",
        params,
    )


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_order_status_counts(f: Filters) -> pd.DataFrame:
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT "o"."order_status" AS order_status,
                   COUNT(DISTINCT "o"."order_id") AS orders,
                   SUM("i"."total_value") AS revenue
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1""",
        params,
    )


# ---------------------------------------------------------------------------
# Stores / staff
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_store_performance(f: Filters) -> pd.DataFrame:
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT "s"."store_name" AS store_name,
                   "s"."city" AS city,
                   "s"."state" AS state,
                   SUM("i"."total_value") AS revenue,
                   COUNT(DISTINCT "o"."order_id") AS orders,
                   COUNT(DISTINCT "o"."customer_id") AS customers,
                   SUM("i"."quantity") AS units
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1, 2, 3 ORDER BY 4 DESC""",
        params,
    )


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_staff_performance(f: Filters) -> pd.DataFrame:
    s = _schema()
    clauses, params = _base_clauses(f)
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT "st"."first_name" || ' ' || "st"."last_name" AS staff_name,
                   "s"."store_name" AS store_name,
                   SUM("i"."total_value") AS revenue,
                   COUNT(DISTINCT "o"."order_id") AS orders
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."staffs" "st" ON "st"."staff_id" = "o"."staff_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1, 2 ORDER BY 3 DESC""",
        params,
    )


# ---------------------------------------------------------------------------
# Products / inventory
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_product_revenue(f: Filters, limit: int = 100) -> pd.DataFrame:
    s = _schema()
    clauses, params = _base_clauses(f)
    params["limit"] = limit
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT "p"."product_name" AS product_name,
                   "b"."brand_name" AS brand_name,
                   "c"."category_name" AS category_name,
                   "p"."list_price" AS list_price,
                   SUM("i"."total_value") AS revenue,
                   SUM("i"."quantity") AS units_sold,
                   COUNT(DISTINCT "o"."order_id") AS orders
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC LIMIT :limit""",
        params,
    )


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_stock_levels() -> pd.DataFrame:
    """Current inventory snapshot (unfiltered: stocks is a point-in-time fact)."""
    s = _schema()
    return _run(
        f"""SELECT "s"."store_name" AS store_name,
                   "p"."product_name" AS product_name,
                   "b"."brand_name" AS brand_name,
                   "c"."category_name" AS category_name,
                   "k"."quantity" AS quantity,
                   "p"."list_price" AS list_price
            FROM "{s}"."stocks" "k"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "k"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "k"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            ORDER BY "k"."quantity" ASC"""
    )


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_customer_rfm(f: Filters, limit: int = 2000) -> pd.DataFrame:
    """Recency (days since last order vs window end), frequency, monetary."""
    s = _schema()
    clauses, params = _base_clauses(f)
    params["end_date_r"] = f.end_date
    params["limit"] = limit
    where = " AND ".join(clauses)
    return _run(
        f"""SELECT "cu"."first_name" || ' ' || "cu"."last_name" AS customer_name,
                   "cu"."city" AS city,
                   "cu"."state" AS state,
                   COUNT(DISTINCT "o"."order_id") AS frequency,
                   SUM("i"."total_value") AS monetary,
                   (CAST(:end_date_r AS date) - MAX("o"."order_date")) AS recency_days
            FROM "{s}"."orders" "o"
            JOIN "{s}"."order_items" "i" ON "i"."order_id" = "o"."order_id"
            JOIN "{s}"."customers" "cu" ON "cu"."customer_id" = "o"."customer_id"
            JOIN "{s}"."stores" "s" ON "s"."store_id" = "o"."store_id"
            JOIN "{s}"."products" "p" ON "p"."product_id" = "i"."product_id"
            JOIN "{s}"."brands" "b" ON "b"."brand_id" = "p"."brand_id"
            JOIN "{s}"."categories" "c" ON "c"."category_id" = "p"."category_id"
            WHERE {where}
            GROUP BY 1, 2, 3 ORDER BY 5 DESC LIMIT :limit""",
        params,
    )


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_first_order_cohorts() -> pd.DataFrame:
    """Retention grid from each customer's first-ever order month (all-time)."""
    s = _schema()
    return _run(
        f"""WITH first_orders AS (
                SELECT "customer_id", date_trunc('month', MIN("order_date"))::date AS cohort
                FROM "{s}"."orders" GROUP BY 1
             ),
             activity AS (
                SELECT DISTINCT "fo"."cohort", date_trunc('month', "o"."order_date")::date AS active_month
                FROM "{s}"."orders" "o" JOIN first_orders "fo" USING ("customer_id")
             ),
             sizes AS (
                SELECT "cohort", COUNT(*) AS cohort_size FROM first_orders GROUP BY 1
             )
             SELECT "a"."cohort",
                    ((EXTRACT(YEAR FROM "a"."active_month") - EXTRACT(YEAR FROM "a"."cohort")) * 12
                     + EXTRACT(MONTH FROM "a"."active_month") - EXTRACT(MONTH FROM "a"."cohort"))::int AS period,
                    COUNT(*)::float / MAX("sz"."cohort_size") AS retention,
                    MAX("sz"."cohort_size") AS cohort_size
             FROM activity "a" JOIN sizes "sz" USING ("cohort")
             GROUP BY 1, 2 ORDER BY 1, 2"""
    )


# ---------------------------------------------------------------------------
# Data health
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_table_counts() -> pd.DataFrame:
    s = _schema()
    tables = [
        "brands",
        "categories",
        "customers",
        "stores",
        "staffs",
        "products",
        "orders",
        "order_items",
        "stocks",
    ]
    union = " UNION ALL ".join(
        f'SELECT \'{t}\' AS table_name, COUNT(*) AS rows FROM "{s}"."{t}"'
        for t in tables
    )
    return _run(union)


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def get_data_health_checks() -> list[dict]:
    """Cheap COUNT-based integrity checks; each returns {check, status, detail}."""
    s = _schema()
    engine = get_engine()
    checks: list[dict] = []

    def count(sql: str) -> int:
        with engine.connect() as conn:
            return int(conn.execute(text(sql)).scalar() or 0)

    orphans = [
        (
            "orders with unknown customer",
            f'"{s}"."orders" "o" LEFT JOIN "{s}"."customers" "c" ON "c"."customer_id"="o"."customer_id" WHERE "o"."customer_id" IS NOT NULL AND "c"."customer_id" IS NULL',
        ),
        (
            "orders with unknown store",
            f'"{s}"."orders" "o" LEFT JOIN "{s}"."stores" "s" ON "s"."store_id"="o"."store_id" WHERE "o"."store_id" IS NOT NULL AND "s"."store_id" IS NULL',
        ),
        (
            "orders with unknown staff",
            f'"{s}"."orders" "o" LEFT JOIN "{s}"."staffs" "st" ON "st"."staff_id"="o"."staff_id" WHERE "o"."staff_id" IS NOT NULL AND "st"."staff_id" IS NULL',
        ),
        (
            "line items with unknown order",
            f'"{s}"."order_items" "i" LEFT JOIN "{s}"."orders" "o" ON "o"."order_id"="i"."order_id" WHERE "o"."order_id" IS NULL',
        ),
        (
            "line items with unknown product",
            f'"{s}"."order_items" "i" LEFT JOIN "{s}"."products" "p" ON "p"."product_id"="i"."product_id" WHERE "p"."product_id" IS NULL',
        ),
        (
            "products with unknown brand",
            f'"{s}"."products" "p" LEFT JOIN "{s}"."brands" "b" ON "b"."brand_id"="p"."brand_id" WHERE "b"."brand_id" IS NULL',
        ),
        (
            "products with unknown category",
            f'"{s}"."products" "p" LEFT JOIN "{s}"."categories" "c" ON "c"."category_id"="p"."category_id" WHERE "c"."category_id" IS NULL',
        ),
        (
            "orders without any line item",
            f'"{s}"."orders" "o" LEFT JOIN "{s}"."order_items" "i" ON "i"."order_id"="o"."order_id" WHERE "i"."order_id" IS NULL',
        ),
    ]
    for label, frm in orphans:
        n = count(f"SELECT COUNT(*) FROM {frm}")
        checks.append(
            {
                "check": f"Referential integrity — {label}",
                "status": "PASS" if n == 0 else "FAIL",
                "detail": f"{n:,} violating row(s)",
            }
        )

    arithmetic = count(
        f"""SELECT COUNT(*) FROM "{s}"."order_items"
            WHERE ABS("total_value" - ("quantity" * "list_price" * (1 - "discount"))) >= 0.01"""
    )
    checks.append(
        {
            "check": "Arithmetic — total_value = qty × price × (1 − discount)",
            "status": "PASS" if arithmetic == 0 else "FAIL",
            "detail": f"{arithmetic:,} mismatching line(s)",
        }
    )

    future = count(
        f"""SELECT COUNT(*) FROM "{s}"."orders" WHERE "order_date" > CURRENT_DATE"""
    )
    checks.append(
        {
            "check": "Dates — no future order_date",
            "status": "PASS" if future == 0 else "FAIL",
            "detail": f"{future:,} future-dated order(s)",
        }
    )

    negative = count(f"""SELECT COUNT(*) FROM "{s}"."stocks" WHERE "quantity" < 0""")
    checks.append(
        {
            "check": "Inventory — no negative stock",
            "status": "PASS" if negative == 0 else "FAIL",
            "detail": f"{negative:,} negative stock row(s)",
        }
    )
    return checks
