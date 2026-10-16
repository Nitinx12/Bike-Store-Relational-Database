"""Plotly chart helpers shared by every page."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from dashboard.helpers.theme import BRAND_BLUE, PALETTE, style


def revenue_trend_chart(trend: pd.DataFrame, granularity: str = "week"):
    df = trend.copy()
    df["period"] = pd.to_datetime(df["period"])
    fig = px.area(
        df, x="period", y="revenue", labels={"period": "", "revenue": "Revenue"}
    )
    fig.update_traces(
        line={"color": BRAND_BLUE, "width": 2.6},
        fillcolor="rgba(0,113,206,0.12)",
        hovertemplate="Revenue: $%{y:,.0f}<br>%{x|%b %d, %Y}<extra></extra>",
    )
    return style(fig, height=360)


def bar_by(df: pd.DataFrame, x: str, title: str = ""):
    fig = px.bar(
        df,
        x=x,
        y="revenue",
        color="revenue",
        color_continuous_scale=["#DBEAFE", BRAND_BLUE],
        labels={x: "", "revenue": "Revenue"},
        title=title,
    )
    fig.update_layout(coloraxis_showscale=False)
    fig.update_traces(
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>", marker_line_width=0
    )
    return style(fig, height=360)


def donut(df: pd.DataFrame, names: str):
    fig = px.pie(
        df, names=names, values="revenue", hole=0.58, color_discrete_sequence=PALETTE
    )
    fig.update_traces(
        textposition="outside",
        textinfo="percent+label",
        hovertemplate="%{label}: $%{value:,.0f}<extra></extra>",
        marker={"line": {"color": "white", "width": 2}},
    )
    return style(fig, currency=False, height=360)


def treemap(df: pd.DataFrame):
    fig = px.treemap(
        df,
        path=[px.Constant("All"), "category_name", "brand_name"],
        values="revenue",
        color="revenue",
        color_continuous_scale=["#DCEBFA", BRAND_BLUE, "#0B1F3A"],
    )
    fig.update_traces(
        textinfo="label+percent root",
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percentRoot:.1%} of total<extra></extra>",
        marker={"cornerradius": 6, "line": {"width": 2, "color": "white"}},
    )
    fig.update_layout(
        coloraxis_showscale=False, height=460, margin={"t": 8, "l": 0, "r": 0, "b": 0}
    )
    return style(fig, currency=False, legend=False)


def pareto(df: pd.DataFrame):
    """80/20 chart: bars for revenue plus cumulative share line.

    Expects product_name + revenue columns sorted desc (see
    get_product_revenue). Returns (fig, products_for_80_pct).
    """
    df = df.copy()
    df["cum"] = df.revenue.cumsum() / df.revenue.sum() * 100
    n80 = int((df["cum"] < 80).sum()) + 1 if not df.empty else 0
    fig = go.Figure()
    fig.add_bar(
        x=df.product_name,
        y=df.revenue,
        name="Revenue",
        marker_color=BRAND_BLUE,
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
    )
    fig.add_scatter(
        x=df.product_name,
        y=df.cum,
        name="Cumulative %",
        yaxis="y2",
        mode="lines+markers",
        line={"color": "#FFC220", "width": 3},
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    )
    fig.update_layout(
        yaxis2={
            "overlaying": "y",
            "side": "right",
            "range": [0, 105],
            "ticksuffix": "%",
            "showgrid": False,
        },
        height=420,
        xaxis={"tickangle": -35},
        showlegend=True,
    )
    return style(fig), n80


def bubble(df: pd.DataFrame):
    """Product portfolio: units vs revenue, size = revenue, color = category."""
    df = df.copy()
    df["avg_price"] = df.revenue / df.units_sold.replace(0, float("nan"))
    fig = px.scatter(
        df,
        x="units_sold",
        y="revenue",
        size="revenue",
        color="category_name",
        hover_name="product_name",
        hover_data={"units_sold": True, "revenue": ":$,.0f", "avg_price": ":$,.2f"},
        size_max=48,
        labels={
            "units_sold": "Units sold",
            "revenue": "Revenue",
            "category_name": "Category",
        },
    )
    return style(fig, height=420)


def weekday_revenue_chart(df: pd.DataFrame):
    """Revenue bars by weekday. order_date is a DATE, so no hourly grain exists."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    df = df.copy()
    df["weekday"] = pd.Categorical(
        df["dow"].map(dict(zip(range(1, 8), days))), categories=days, ordered=True
    )
    fig = px.bar(
        df.sort_values("weekday"),
        x="weekday",
        y="revenue",
        color="revenue",
        color_continuous_scale=["#DBEAFE", BRAND_BLUE],
        labels={"weekday": "", "revenue": "Revenue"},
    )
    fig.update_layout(coloraxis_showscale=False)
    fig.update_traces(
        hovertemplate="%{x}: $%{y:,.0f}<extra></extra>", marker_line_width=0
    )
    return style(fig, height=340)


def waterfall(df: pd.DataFrame):
    """Month over month revenue change by category (relative waterfall)."""
    fig = go.Figure(
        go.Waterfall(
            x=df.category_name,
            y=df.delta,
            measure=["relative"] * len(df),
            increasing={"marker": {"color": "#0E9F6E"}},
            decreasing={"marker": {"color": "#E7462A"}},
            connector={"line": {"color": "#CBD5E1"}},
            hovertemplate="%{x}: %{y:+$,.0f}<extra></extra>",
        )
    )
    fig.update_layout(height=380, showlegend=False)
    return style(fig)


def sunburst(df: pd.DataFrame):
    """Category -> brand -> product revenue sunburst."""
    fig = px.sunburst(
        df,
        path=["category_name", "brand_name", "product_name"],
        values="revenue",
        color="category_name",
    )
    fig.update_traces(
        insidetextorientation="radial",
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
    )
    fig.update_layout(height=520)
    return style(fig, currency=False, legend=False)


def funnel(df: pd.DataFrame):
    """Order status funnel (rows must arrive in pipeline order)."""
    fig = px.funnel(
        df,
        x="orders",
        y="order_status",
        labels={"orders": "Orders", "order_status": ""},
    )
    fig.update_traces(
        marker_color=BRAND_BLUE,
        hovertemplate="%{y}: %{x:,} orders<extra></extra>",
    )
    fig.update_layout(
        height=380,
        showlegend=False,
        yaxis={
            "categoryorder": "array",
            "categoryarray": df.order_status.tolist(),
        },
    )
    return style(fig, currency=False)


def share_area(df: pd.DataFrame):
    """100% stacked area: category revenue share over months."""
    fig = px.area(
        df,
        x="month",
        y="revenue",
        color="category_name",
        groupnorm="percent",
        labels={"month": "", "revenue": "Share", "category_name": "Category"},
    )
    fig.update_layout(yaxis={"ticksuffix": "%"}, height=380)
    fig.update_traces(
        hovertemplate="%{fullData.name}<br>%{x|%b %Y}: %{y:.1f}%<extra></extra>"
    )
    return style(fig, currency=False)


def rfm_scatter(df: pd.DataFrame):
    """Customer portfolio: order frequency vs money, colored by segment."""
    fig = px.scatter(
        df,
        x="frequency",
        y="monetary",
        color="segment",
        hover_name="customer_name",
        hover_data={
            "frequency": True,
            "monetary": ":$,.0f",
            "recency_days": True,
            "segment": False,
        },
        labels={"frequency": "Orders", "monetary": "Spend", "segment": "Segment"},
    )
    fig.update_traces(marker={"size": 9, "opacity": 0.75, "line": {"width": 0}})
    return style(fig)


def cohort_heatmap(df: pd.DataFrame):
    """Cohort retention grid: fraction of each cohort active per month offset.

    Takes the long-format output of get_first_order_cohorts and pivots it
    into the cohort x period matrix the heatmap needs.
    """
    if df.empty:
        fig = px.imshow([[0]])
        fig.update_layout(height=380)
        return style(fig, currency=False)
    matrix = df.pivot(index="cohort", columns="period", values="retention").fillna(0)
    matrix.index = pd.to_datetime(matrix.index).strftime("%b %Y")
    fig = px.imshow(
        matrix,
        aspect="auto",
        labels={"x": "Months since first order", "y": "Cohort", "color": "Active"},
        color_continuous_scale=["#F4F7FB", "#9CC9F0", "#0071CE", "#0B1F3A"],
        text_auto=".0%",
        zmin=0,
        zmax=1,
    )
    fig.update_layout(height=380)
    fig.update_traces(
        hovertemplate="Cohort %{y}<br>Month %{x}: %{z:.0%} active<extra></extra>"
    )
    return style(fig, currency=False)
