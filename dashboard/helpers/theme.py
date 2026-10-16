"""
dashboard/helpers/theme.py — Design system for the Bike Store Dashboard.

Single source of truth for colors, typography, spacing and Plotly styling
so every chart/table/metric shares the same professional look.

Palette is a sporty blue + gold (primary blue, gold accent, neutral
slate) — tuned for white-background readability and WCAG AA contrast.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Brand & semantic tokens
# ---------------------------------------------------------------------------
BRAND_BLUE = "#0071CE"
BRAND_GOLD = "#FFC220"
DEEP_NAVY = "#0B1F3A"
APP_BG = "#F4F7FB"

# Extended palette — ordered for sequential colorway assignment.
PALETTE = [
    "#0071CE",  # brand blue — primary
    "#FFC220",  # gold — highlight / accent
    "#00A9E0",  # sky — secondary series
    "#0E9F6E",  # teal / success
    "#7B5CFF",  # violet — tertiary series
    "#E7462A",  # coral / alert
    "#004C91",  # deep blue
    "#64748B",  # slate
    "#94A3B8",  # muted slate (for "other" slices)
]

# Semantic aliases (used by KPI deltas & status badges)
SEMANTIC = {
    "success": "#0E9F6E",
    "danger": "#DC2626",
    "warning": "#D97706",
    "neutral": "#64748B",
    "border": "rgba(15,23,42,0.08)",
    "border_strong": "rgba(15,23,42,0.12)",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "surface_muted": "#F1F5F9",
    "text": "#0F172A",
    "text_muted": "#64748B",
    "text_faint": "#94A3B8",
}

# Dark-mode overrides, applied on top of the base CSS when the sidebar
# "Dark mode" toggle is on. Keys mirror SEMANTIC + app/sidebar surfaces.
DARK = {
    "app_bg": "#0B1220",
    "surface": "#111B2E",
    "surface_alt": "#0B1220",
    "surface_muted": "#16213A",
    "border": "#1E2A44",
    "border_strong": "#2A3A58",
    "text": "#E6EDF7",
    "text_muted": "#94A3B8",
    "text_faint": "#64748B",
    "grid": "#1E2A44",
}


def get_theme() -> str:
    """Return the active theme ("light" or "dark") from session state.

    Safe to call outside a Streamlit runtime (bare python): session_state
    is empty there, so it falls back to "light".
    """
    try:
        return "dark" if st.session_state.get("theme") == "dark" else "light"
    except Exception:  # noqa: BLE001 -- no runtime yet, light is the safe default
        return "light"


FONT_FAMILY = "'Inter','Segoe UI',Helvetica,Arial,sans-serif"
FONT_MONO = "'JetBrains Mono','SF Mono',Consolas,monospace"

# Sequential scales for continuous charts
SCALE_BLUE = ["#DBEAFE", "#93C5FD", "#3B82F6", "#1D4ED8", "#1E3A5F"]
SCALE_BLUE_YELLOW = ["#DBEAFE", "#93C5FD", "#0071CE", "#FFC220", "#B45309"]


# ---------------------------------------------------------------------------
# Plotly figure styling
# ---------------------------------------------------------------------------
def style(
    fig: go.Figure,
    *,
    currency: bool = True,
    legend: bool = True,
    height: int = 380,
    show_grid_y: bool = True,
) -> go.Figure:
    """Apply the shared professional look to any Plotly figure.

    - Transparent plot/paper bg so the surrounding card provides the surface.
    - Consistent font, colorway, margins, hoverlabel.
    - Subtle grid only on Y (X grid is noise for most dashboards).
    - Currency-formatted Y axis when ``currency`` is True.
    - Theme-aware: text/grid colors follow the sidebar theme toggle.
    """
    dark = get_theme() == "dark"
    ink = DARK["text"] if dark else DEEP_NAVY
    muted = DARK["text_muted"] if dark else SEMANTIC["text_muted"]
    grid = DARK["grid"] if dark else "rgba(15,23,42,0.06)"
    fig.update_layout(
        font={"family": FONT_FAMILY, "size": 13, "color": ink},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 8, "r": 8, "t": 48, "b": 8},
        showlegend=legend,
        colorway=PALETTE,
        height=height,
        hoverlabel={
            "font_size": 13,
            "font_family": FONT_FAMILY,
            "bgcolor": "#0B1F3A",
            "font_color": "#FFFFFF",
            "bordercolor": "rgba(255,255,255,0.15)",
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 11, "color": muted},
        },
        bargap=0.22,
        uniformtext_minsize=10,
        uniformtext_mode="hide",
    )
    fig.update_xaxes(
        showgrid=False,
        showline=False,
        tickfont={"size": 11, "color": muted},
        title_font={"size": 11, "color": muted},
    )
    fig.update_yaxes(
        showgrid=show_grid_y,
        gridcolor=grid,
        gridwidth=1,
        zeroline=False,
        showline=False,
        tickfont={"size": 11, "color": muted},
        title_font={"size": 11, "color": muted},
    )
    if currency:
        fig.update_yaxes(tickprefix="$", tickformat=",.0f", hoverformat=",.2f")
    for trace in fig.data:
        if (
            getattr(trace, "type", None) == "bar"
            and hasattr(trace, "marker")
            and trace.marker is not None
        ):
            trace.marker.line = {"width": 0}  # type: ignore[attr-defined]
    return fig


# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------
def inject_css(theme: str | None = None) -> str:
    """Return a <style> block that upgrades Streamlit's default chrome to a
    professional dashboard shell: card surfaces, metric styling, tab polish,
    table polish, and subtle motion.

    ``theme`` defaults to the sidebar toggle ("light"/"dark"); "dark"
    appends an override block that re-skins surfaces and text.
    """
    active = theme or get_theme()
    base = f"""
    <style>
    /* -- Google Font (Inter) — loaded once, cached by browser -- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    /* -- App background -- */
    .stApp {{
        background: {APP_BG};
    }}
    /* Hide default Streamlit header / footer chrome */
    header[data-testid="stHeader"] {{
        background: rgba(248,250,252,0.8);
        backdrop-filter: blur(8px);
    }}
    footer {{visibility: hidden;}}

    /* -- Typography -- */
    html, body, [class*="st-"] {{
        font-family: {FONT_FAMILY} !important;
    }}
    h1, h2, h3 {{
        letter-spacing: -0.02em;
    }}

    /* -- Sidebar -- */
    section[data-testid="stSidebar"] {{
        background: #FFFFFF;
        border-right: 1px solid {SEMANTIC["border"]};
        box-shadow: 4px 0 24px rgba(15,23,42,0.04);
    }}
    section[data-testid="stSidebar"] .stMarkdown h2 {{
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: {SEMANTIC["text_faint"]};
        margin-top: 0.6rem;
    }}

    /* -- Cards (wrap every chart/table) -- */
    .dash-card {{
        background: {SEMANTIC["surface"]};
        border: 1px solid {SEMANTIC["border"]};
        border-radius: 16px;
        padding: 18px 18px 8px 18px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.04);
        transition: box-shadow 0.2s ease, transform 0.2s ease;
    }}
    .dash-card:hover {{
        box-shadow: 0 4px 12px rgba(15,23,42,0.08), 0 8px 24px rgba(15,23,42,0.06);
    }}
    .dash-card__title {{
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: {SEMANTIC["text"]};
        margin: 0 0 2px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    .dash-card__subtitle {{
        font-size: 0.74rem;
        color: {SEMANTIC["text_muted"]};
        margin: 0 0 12px 0;
    }}
    .dash-card__accent {{
        width: 28px;
        height: 3px;
        border-radius: 999px;
        background: {BRAND_BLUE};
        margin-bottom: 14px;
    }}
    .dash-card__accent--amber {{ background: {BRAND_GOLD}; }}
    .dash-card__accent--teal {{ background: {SEMANTIC["success"]}; }}

    /* -- KPI cards -- */
    .kpi-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 14px;
        margin: 8px 0 4px 0;
    }}
    @media (max-width: 1100px) {{
        .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    @media (max-width: 600px) {{
        .kpi-grid {{ grid-template-columns: 1fr; }}
    }}
    .kpi-card {{
        background: {SEMANTIC["surface"]};
        border: 1px solid {SEMANTIC["border"]};
        border-radius: 16px;
        padding: 16px 18px 14px 18px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.04);
        position: relative;
        overflow: hidden;
    }}
    .kpi-card::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: var(--kpi-accent, {BRAND_BLUE});
    }}
    .kpi-card__label {{
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: {SEMANTIC["text_muted"]};
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 8px;
    }}
    .kpi-card__value {{
        font-size: 1.65rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: {SEMANTIC["text"]};
        line-height: 1;
        margin-bottom: 8px;
        font-variant-numeric: tabular-nums;
    }}
    .kpi-card__delta {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 999px;
        letter-spacing: -0.01em;
    }}
    .kpi-card__delta--up {{
        background: #ECFDF5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }}
    .kpi-card__delta--down {{
        background: #FEF2F2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }}
    .kpi-card__delta--flat {{
        background: #F1F5F9;
        color: #475569;
        border: 1px solid #E2E8F0;
    }}
    .kpi-card__foot {{
        font-size: 0.70rem;
        color: {SEMANTIC["text_faint"]};
        margin-top: 6px;
    }}

    /* -- Section header -- */
    .section-head {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        margin: 22px 0 10px 0;
        flex-wrap: wrap;
    }}
    .section-head h3 {{
        font-size: 0.95rem;
        font-weight: 700;
        color: {SEMANTIC["text"]};
        margin: 0;
    }}
    .section-head p {{
        font-size: 0.78rem;
        color: {SEMANTIC["text_muted"]};
        margin: 0;
    }}

    /* -- Filter chips -- */
    .chip-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 6px 0 2px 0;
    }}
    .chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 999px;
        background: #EFF6FF;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }}
    .chip--amber {{ background: #FFFBEB; color: #92400E; border-color: #FDE68A; }}
    .chip--slate {{ background: #F1F5F9; color: #334155; border-color: #E2E8F0; }}

    /* -- Divider polish -- */
    hr {{
        border: none;
        height: 1px;
        background: {SEMANTIC["border"]};
        margin: 18px 0;
    }}

    /* -- Tabs -- */
    button[data-baseweb="tab"] {{
        font-weight: 600 !important;
        font-size: 0.84rem !important;
        letter-spacing: -0.01em;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color: {BRAND_BLUE} !important;
    }}
    div[data-testid="stTabs"] div[role="tablist"] {{
        gap: 6px;
    }}

    /* -- Metrics fallback (if any st.metric remains) -- */
    div[data-testid="stMetricValue"] {{
        font-size: 1.55rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }}
    div[data-testid="stMetricLabel"] {{
        font-weight: 600;
        color: {SEMANTIC["text_muted"]};
        font-size: 0.78rem;
    }}
    div[data-testid="stMetric"] {{
        background: {SEMANTIC["surface"]};
        border: 1px solid {SEMANTIC["border"]};
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.05);
    }}

    /* -- DataFrames -- */
    div[data-testid="stDataFrame"] {{
        border: 1px solid {SEMANTIC["border"]};
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(15,23,42,0.05);
    }}

    /* -- Expanders -- */
    details[data-testid="stExpander"] {{
        background: {SEMANTIC["surface"]};
        border: 1px solid {SEMANTIC["border"]};
        border-radius: 14px;
        box-shadow: 0 1px 3px rgba(15,23,42,0.04);
    }}

    /* -- Buttons -- */
    .stDownloadButton > button, .stButton > button {{
        border-radius: 10px !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em;
        border: 1px solid {SEMANTIC["border_strong"]} !important;
        box-shadow: 0 1px 2px rgba(15,23,42,0.06);
        transition: all 0.15s ease;
    }}
    .stDownloadButton > button:hover, .stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(15,23,42,0.08);
    }}

    /* -- Alerts / callouts -- */
    div[data-testid="stAlert"] {{
        border-radius: 12px;
        border-width: 1px;
    }}

    /* -- Scrollbar subtle -- */
    ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
    ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 999px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #94A3B8; }}

    /* -- Plotly modebar subtle -- */
    .js-plotly-plot .modebar {{ opacity: 0.55; }}
    .js-plotly-plot .modebar:hover {{ opacity: 1; }}

    /* -- Empty state -- */
    .empty-state {{
        text-align: center;
        padding: 28px 18px;
        background: {SEMANTIC["surface_alt"]};
        border: 1px dashed {SEMANTIC["border_strong"]};
        border-radius: 14px;
        color: {SEMANTIC["text_muted"]};
        font-size: 0.84rem;
    }}
    .empty-state strong {{ color: {SEMANTIC["text"]}; }}

    /* -- Footer -- */
    .dash-footer {{
        margin-top: 28px;
        padding: 16px 0 8px 0;
        border-top: 1px solid {SEMANTIC["border"]};
        display: flex;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        font-size: 0.74rem;
        color: {SEMANTIC["text_faint"]};
    }}
    .dash-footer a {{ color: {BRAND_BLUE}; text-decoration: none; font-weight: 600; }}
    .dash-footer a:hover {{ text-decoration: underline; }}
    </style>
    """
    if active == "dark":
        base += f"""
    <style>
    /* -- Dark mode overrides -- */
    .stApp {{
        background: {DARK["app_bg"]};
    }}
    section[data-testid="stSidebar"] {{
        background: {DARK["surface"]};
        border-right: 1px solid {DARK["border"]};
    }}
    .dash-card, .kpi-card {{
        background: {DARK["surface"]};
        border: 1px solid {DARK["border"]};
    }}
    .kpi-card__value, .dash-card__title, .section-head h3,
    div[data-testid="stMetricValue"] {{
        color: {DARK["text"]};
    }}
    .kpi-card__label, div[data-testid="stMetricLabel"], .section-head p,
    .dash-card__subtitle {{
        color: {DARK["text_muted"]};
    }}
    .kpi-card__foot, .empty-state {{
        color: {DARK["text_muted"]};
    }}
    .empty-state {{
        background: {DARK["surface_alt"]};
        border: 1px dashed {DARK["border_strong"]};
    }}
    .empty-state strong {{ color: {DARK["text"]}; }}
    .kpi-card__delta--flat {{
        background: {DARK["surface_muted"]};
        color: {DARK["text_muted"]};
        border: 1px solid {DARK["border_strong"]};
    }}
    .chip--slate {{
        background: {DARK["surface_muted"]};
        color: {DARK["text_muted"]};
        border-color: {DARK["border_strong"]};
    }}
    div[data-testid="stMetric"] {{
        background: {DARK["surface"]};
        border: 1px solid {DARK["border"]};
    }}
    div[data-testid="stDataFrame"] {{
        border: 1px solid {DARK["border"]};
    }}
    details[data-testid="stExpander"] {{
        background: {DARK["surface"]};
        border: 1px solid {DARK["border"]};
    }}
    .dash-footer {{
        border-top: 1px solid {DARK["border"]};
        color: {DARK["text_faint"]};
    }}
    hr {{
        background: {DARK["border"]};
    }}
    </style>
    """
    return base
