"""
dashboard/helpers/components.py — Reusable UI building blocks.

Keeps pages focused on layout/data flow; all HTML card rendering lives here
so it can be tested and restyled in one place.
"""

from __future__ import annotations

import html as html_lib
import textwrap
from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from dashboard.helpers.theme import BRAND_BLUE, BRAND_GOLD


def _safe_html(raw: str) -> str:
    """Collapse an indented HTML template into one markdown-safe line.

    Markdown treats 4+-space-indented lines as code blocks and blank lines
    end an HTML block -- both failure modes render styled cards as literal
    text with a copy button. Stripping every line and dropping blanks keeps
    the fragment a single HTML block that Streamlit passes through intact.
    """
    return "".join(
        line.strip() for line in textwrap.dedent(raw).splitlines() if line.strip()
    )


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
_DELTA_ICON = {"up": "▲", "down": "▼", "flat": "—"}


def _delta_state(pct: float | None) -> str:
    if pct is None:
        return "flat"
    if pct > 0.05:
        return "up"
    if pct < -0.05:
        return "down"
    return "flat"


def sparkline_svg(values: list[float], color: str = "#0071CE") -> str:
    """Tiny inline SVG trend line for KPI cards (no extra dependency).

    Returns "" for fewer than 2 points so empty windows degrade to no
    sparkline instead of a broken image.
    """
    clean = [float(v) for v in values or []]
    if len(clean) < 2:
        return ""
    w, h = 120.0, 32.0
    lo, hi = min(clean), max(clean)
    span = (hi - lo) or 1.0
    pts = " ".join(
        f"{i * w / (len(clean) - 1):.1f},{h - (v - lo) / span * (h - 4) - 2:.1f}"
        for i, v in enumerate(clean)
    )
    return (
        f'<svg width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/></svg>'
    )


def _render_kpi_grid(items: list[dict], delta_label: str) -> None:
    """Render any list of card dicts as one HTML grid (one st.markdown)."""
    cards_html = ""
    for item in items:
        pct = item.get("delta")
        state = _delta_state(pct)
        icon = _DELTA_ICON[state]
        label_e = html_lib.escape(delta_label)
        if pct is None:
            delta_html = '<span class="kpi-card__delta kpi-card__delta--flat">— no prior period</span>'
        else:
            cls = {
                "up": "kpi-card__delta--up",
                "down": "kpi-card__delta--down",
                "flat": "kpi-card__delta--flat",
            }[state]
            # green for up on revenue/orders, but keep same treatment for all 4 for simplicity
            delta_html = f'<span class="kpi-card__delta {cls}">{icon} {pct:+.1f}% {label_e}</span>'

        # Escape dynamic text safely
        label = html_lib.escape(item["label"])
        value = html_lib.escape(item["value"])
        foot = html_lib.escape(item["foot"])
        spark = sparkline_svg(
            item.get("sparkline") or [], item.get("accent", "#0071CE")
        )
        cards_html += f"""
        <div class="kpi-card" style="--kpi-accent:{item["accent"]};">
            <div class="kpi-card__label">{item["icon"]} {label}</div>
            <div class="kpi-card__value">{value}</div>
            {spark}
            {delta_html}
            <div class="kpi-card__foot">{foot}</div>
        </div>
        """

    st.markdown(
        _safe_html(f'<div class="kpi-grid">{cards_html}</div>'), unsafe_allow_html=True
    )


def kpi_cards(
    revenue: float,
    orders: int,
    customers: int,
    aov: float,
    deltas: dict[str, float | None],
    delta_label: str = "vs prior",
    sparklines: dict[str, list[float]] | None = None,
) -> None:
    """Render the 4-card performance KPI row (revenue, orders, customers, AOV)."""
    sparks = sparklines or {}
    items = [
        {
            "label": "Total Revenue",
            "icon": "💰",
            "value": f"${revenue:,.0f}",
            "delta": deltas.get("revenue"),
            "foot": "Sum of order line totals",
            "accent": BRAND_BLUE,
            "sparkline": sparks.get("revenue", []),
        },
        {
            "label": "Orders",
            "icon": "📦",
            "value": f"{orders:,}",
            "delta": deltas.get("orders"),
            "foot": "Distinct order_id",
            "accent": "#0E9F6E",
            "sparkline": sparks.get("orders", []),
        },
        {
            "label": "Customers",
            "icon": "👥",
            "value": f"{customers:,}",
            "delta": deltas.get("customers"),
            "foot": "Unique shoppers",
            "accent": "#7B5CFF",
            "sparkline": sparks.get("customers", []),
        },
        {
            "label": "Avg Order Value",
            "icon": "🧾",
            "value": f"${aov:,.2f}",
            "delta": deltas.get("aov"),
            "foot": "Revenue / orders",
            "accent": BRAND_GOLD,
            "sparkline": sparks.get("aov", []),
        },
    ]
    _render_kpi_grid(items, delta_label)


def kpi_quality_cards(items: list[dict], delta_label: str = "vs prior") -> None:
    """Render the quality and growth KPI row.

    Each item: label, icon, value (preformatted str), delta (pct or None),
    foot, accent, optional sparkline list. Values arrive formatted so this
    stays a pure renderer with no business logic.
    """
    _render_kpi_grid(items, delta_label)


# ---------------------------------------------------------------------------
# Card wrapper helpers
# ---------------------------------------------------------------------------
def card_header(title: str, subtitle: str = "", accent: str = "blue") -> None:
    """Render a card header (title + subtitle + accent bar)."""
    accent_cls = {
        "blue": "",
        "amber": " dash-card__accent--amber",
        "teal": " dash-card__accent--teal",
    }.get(accent, "")
    title_e = html_lib.escape(title)
    sub_e = html_lib.escape(subtitle)
    sub_html = f'<p class="dash-card__subtitle">{sub_e}</p>' if subtitle else ""
    # This is the opening of a card — caller should close with card_footer or just let markdown flow;
    # for Streamlit we render it as a standalone block above the chart.
    st.markdown(
        _safe_html(
            f"""
        <div style="margin-bottom:2px;">
            <div class="dash-card__title">{title_e}</div>
            {sub_html}
            <div class="dash-card__accent{accent_cls}"></div>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def section_head(title: str, subtitle: str = "") -> None:
    st.markdown(
        _safe_html(
            f"""
        <div class="section-head">
            <h3>{html_lib.escape(title)}</h3>
            <p>{html_lib.escape(subtitle)}</p>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )


def filter_chips(filters) -> None:
    """Compact row of active-filter chips (mirrors the Filters model)."""
    chips: list[str] = []
    chips.append(
        f'<span class="chip">📅 {filters.start_date:%b %d, %Y} → {filters.end_date:%b %d, %Y} <span style="opacity:0.6">(exclusive end)</span></span>'
    )
    chips.append(
        f'<span class="chip chip--amber">🏬 {len(filters.stores)} store(s)</span>'
    )
    chips.append(
        f'<span class="chip chip--slate">🚲 {len(filters.categories)} categor(ies)</span>'
    )
    chips.append(
        f'<span class="chip chip--slate">™ {len(filters.brands)} brand(s)</span>'
    )
    chips.append(
        f'<span class="chip chip--slate">● {len(filters.statuses)} status(es)</span>'
    )
    row = "".join(chips)
    st.markdown(
        _safe_html(f'<div class="chip-row">{row}</div>'), unsafe_allow_html=True
    )


def freshness_badge(last_order_ts) -> None:
    """Trust pill for the warehouse snapshot.

    Green < 15 min, amber < 2 h, red beyond that — but data older than
    30 days renders as a neutral "Snapshot" pill instead of a red alarm,
    because this warehouse loads in batches, not as a live stream.
    A timestamp in the future (synthetic demo data) counts as fresh.
    Missing timestamps render grey instead of crashing.
    """
    if last_order_ts is None or pd.isna(last_order_ts):
        dot, text = "#94A3B8", "No orders in view"
    else:
        ts = pd.Timestamp(last_order_ts)
        if ts.tzinfo is not None:
            ts = ts.tz_convert(None)
        lag_min = (
            datetime.now(UTC).replace(tzinfo=None) - ts.to_pydatetime()
        ).total_seconds() / 60
        if lag_min < 15:
            dot, text = "#0E9F6E", f"Fresh · {ts:%b %d, %Y %H:%M}"
        elif lag_min < 120:
            dot, text = "#D97706", f"{lag_min:.0f} min old · {ts:%b %d, %Y %H:%M}"
        elif lag_min < 43200:
            dot, text = "#DC2626", f"{lag_min / 60:.1f} h old · {ts:%b %d, %Y %H:%M}"
        else:
            dot, text = "#64748B", f"Snapshot · data through {ts:%b %d, %Y}"
    st.markdown(
        _safe_html(
            f'<div class="chip-row"><span class="chip">'
            f'<span style="color:{dot}">●</span> {html_lib.escape(text)}</span></div>'
        ),
        unsafe_allow_html=True,
    )


def empty_state(title: str, hint: str = "") -> None:
    st.markdown(
        _safe_html(
            f'<div class="empty-state"><strong>{html_lib.escape(title)}</strong><br/>{html_lib.escape(hint)}</div>'
        ),
        unsafe_allow_html=True,
    )


def dataframe_with_download(
    df: pd.DataFrame, filename: str, key: str, column_config: dict | None = None
) -> None:
    """Render a dataframe + a CSV download button side-by-side."""
    if df.empty:
        empty_state(
            "No rows for the current filters.",
            "Try widening the date range or clearing a filter.",
        )
        return
    st.dataframe(df, width="stretch", hide_index=True, column_config=column_config)  # type: ignore[arg-type]
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Download CSV",
        data=csv,
        file_name=filename,
        mime="text/csv",
        key=key,
        width="content",
    )


def footer() -> None:
    st.markdown(
        _safe_html(
            """
        <div class="dash-footer">
            <span>© 2026 Bike Store · live from Postgres</span>
            <span>Built with Streamlit + Plotly</span>
        </div>
        """
        ),
        unsafe_allow_html=True,
    )
