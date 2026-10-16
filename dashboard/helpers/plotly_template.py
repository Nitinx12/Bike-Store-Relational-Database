"""
dashboard/helpers/plotly_template.py — Shared Plotly figure template.

Registers the "bikestore" (light) and "bikestore_dark" figure templates and
exposes apply_default_template(), which pages call once so every figure —
including any built inline without style() — inherits the look. Per-figure
details (currency axis, height, grids) still live in theme.style(), which
is theme-aware and wins over the template for the figures it touches.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

PALETTE = [
    "#0071CE",
    "#FFC220",
    "#00A9E0",
    "#0E9F6E",
    "#7B5CFF",
    "#E7462A",
    "#004C91",
    "#64748B",
]

_BASE_LAYOUT = {
    "font": {"family": "Inter, system-ui, sans-serif", "size": 13},
    "colorway": PALETTE,
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": {"l": 8, "r": 8, "t": 48, "b": 8},
    "title": {"font": {"size": 16}, "x": 0.0, "xanchor": "left"},
    "hoverlabel": {"font_size": 13},
    "legend": {"orientation": "h", "y": 1.08, "x": 0, "font": {"size": 12}},
    "xaxis": {
        "showgrid": False,
        "ticks": "outside",
    },
    "yaxis": {"zeroline": False},
}

_LIGHT_OVERRIDES = {
    "font": {"family": "Inter, system-ui, sans-serif", "size": 13, "color": "#0B1F3A"},
    "hoverlabel": {
        "font_size": 13,
        "bgcolor": "#0B1F3A",
        "font_color": "#FFFFFF",
        "bordercolor": "#0B1F3A",
    },
    "legend": {
        "orientation": "h",
        "y": 1.08,
        "x": 0,
        "font": {"size": 12, "color": "#0B1F3A"},
    },
    "xaxis": {
        "showgrid": False,
        "ticks": "outside",
        "linecolor": "#E2E8F0",
        "tickcolor": "#E2E8F0",
        "tickfont": {"color": "#64748B"},
    },
    "yaxis": {
        "zeroline": False,
        "gridcolor": "#EEF2F7",
        "tickfont": {"color": "#64748B"},
    },
}

_DARK_OVERRIDES = {
    "font": {"family": "Inter, system-ui, sans-serif", "size": 13, "color": "#E6EDF7"},
    "hoverlabel": {
        "font_size": 13,
        "bgcolor": "#E6EDF7",
        "font_color": "#0B1220",
        "bordercolor": "#E6EDF7",
    },
    "legend": {
        "orientation": "h",
        "y": 1.08,
        "x": 0,
        "font": {"size": 12, "color": "#E6EDF7"},
    },
    "xaxis": {
        "showgrid": False,
        "ticks": "outside",
        "linecolor": "#1E2A44",
        "tickcolor": "#1E2A44",
        "tickfont": {"color": "#94A3B8"},
    },
    "yaxis": {
        "zeroline": False,
        "gridcolor": "#1E2A44",
        "tickfont": {"color": "#94A3B8"},
    },
}

pio.templates["bikestore"] = go.layout.Template(
    layout=go.Layout(**{**_BASE_LAYOUT, **_LIGHT_OVERRIDES})
)

pio.templates["bikestore_dark"] = go.layout.Template(
    layout=go.Layout(**{**_BASE_LAYOUT, **_DARK_OVERRIDES})
)

pio.templates.default = "bikestore"


def apply_default_template(theme: str = "light") -> str:
    """Point the process-wide Plotly default at the active theme template.

    Returns the template name applied. Called once per page load; style()
    still overrides per-figure details afterwards.
    """
    name = "bikestore_dark" if theme == "dark" else "bikestore"
    pio.templates.default = name
    return name
