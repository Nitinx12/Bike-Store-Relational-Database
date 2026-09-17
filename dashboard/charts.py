"""dashboard/charts.py — Plotly figure factory.

No DB, no Streamlit — pure (DataFrame → go.Figure) so charts are
testable and theme-consistent.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

TEAL = "#0F766E"
TEAL_LIGHT = "#CCFBF1"
SLATE = "#1E293B"
GRID = "#E2E8F0"

BASE_LAYOUT = {
    "template": "plotly_white",
    "font": {"family": "Inter, sans-serif", "color": SLATE},
    "paper_bgcolor": "white",
    "plot_bgcolor": "white",
}


def monthly_revenue(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["order_month"],
            y=df["net_revenue"],
            mode="lines+markers",
            name="Net revenue",
            line=dict(color=TEAL, width=3),
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["order_month"],
            y=df["orders"],
            name="Orders",
            yaxis="y2",
            opacity=0.18,
            marker_color=TEAL,
        )
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title="Monthly revenue & orders (Completed)",
        xaxis_title="Month",
        yaxis=dict(title="Net revenue ($)", gridcolor=GRID),
        yaxis2=dict(title="Orders", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.05),
        height=380,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def category_treemap(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return go.Figure()
    fig = px.treemap(
        df,
        path=["category_name"],
        values="revenue",
        color="revenue",
        color_continuous_scale="Teal",
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title="Revenue by category",
        height=380,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def brand_bar(df: pd.DataFrame) -> go.Figure:
    df = df.head(12).sort_values("revenue")
    fig = px.bar(
        df,
        x="revenue",
        y="brand_name",
        orientation="h",
        color="revenue",
        color_continuous_scale="Teal",
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title="Top brands by revenue",
        xaxis_title="Revenue ($)",
        yaxis_title="",
        height=380,
        margin=dict(l=10, r=10, t=40, b=10),
        coloraxis_showscale=False,
    )
    return fig


def store_bar(df: pd.DataFrame) -> go.Figure:
    # expects store_name, total_revenue
    d = df.sort_values("total_revenue")
    fig = px.bar(
        d,
        x="total_revenue",
        y="store_name",
        orientation="h",
        color="total_revenue",
        color_continuous_scale="Teal",
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title="Store performance",
        xaxis_title="Net revenue ($)",
        yaxis_title="",
        height=360,
        coloraxis_showscale=False,
    )
    return fig


def customer_scatter(df: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        df,
        x="total_orders",
        y="lifetime_value",
        size="total_items",
        color="state",
        hover_name="customer_name",
        hover_data=["city", "total_items"],
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title="Customers — orders vs lifetime value",
        xaxis_title="Total orders",
        yaxis_title="Lifetime value ($)",
        height=380,
    )
    return fig


def product_scatter(df: pd.DataFrame) -> go.Figure:
    fig = px.scatter(
        df,
        x="units_sold",
        y="total_revenue",
        size="inventory",
        color="category_name",
        hover_name="product_name",
        hover_data=["brand_name", "list_price"],
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title="Products — units vs revenue (size=inventory)",
        xaxis_title="Units sold",
        yaxis_title="Total revenue ($)",
        height=420,
    )
    return fig


def time_series(df: pd.DataFrame, freq: str = "M") -> go.Figure:
    if df.empty:
        return go.Figure()
    g = (
        df.set_index("order_date")
        .resample(freq)
        .agg({"revenue": "sum", "orders": "sum"})
        .reset_index()
    )
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=g["order_date"],
            y=g["revenue"],
            mode="lines",
            name="Revenue",
            line=dict(color=TEAL, width=2.5),
            fill="tozeroy",
            fillcolor="rgba(15,118,110,0.12)",
        )
    )
    fig.update_layout(
        **BASE_LAYOUT,
        title=f"Revenue — {freq} grain",
        xaxis_title="Date",
        yaxis_title="Revenue ($)",
        yaxis=dict(gridcolor=GRID),
        height=360,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def kpi_sparkline(series: pd.Series) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=list(range(len(series))),
            y=series,
            mode="lines",
            line=dict(color=TEAL, width=2),
            fill="tozeroy",
            fillcolor="rgba(15,118,110,0.15)",
        )
    )
    fig.update_layout(
        **BASE_LAYOUT,
        height=60,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig
