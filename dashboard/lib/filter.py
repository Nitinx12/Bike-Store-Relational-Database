"""Shared sidebar: date window, dimension multiselects, theme toggle."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import timedelta

import streamlit as st

from dashboard.helpers.queries import Filters, get_filter_options


def sidebar_filters() -> tuple[Filters, dict]:
    """Render the global filter sidebar; returns (filters, meta).

    Stops the page with an explanatory error when the date window is
    invalid or the warehouse is unreachable.
    """
    try:
        opts = get_filter_options()
    except Exception as exc:  # noqa: BLE001 -- warehouse down: fail loudly, not blank
        st.error(f"Could not reach Postgres: {exc}")
        st.stop()

    st.sidebar.header("Filters")

    min_date, max_date = opts["min_date"], opts["max_date"]
    # End is exclusive, so default to the day AFTER the last order date
    # to include the final day in the window.
    default_end = max_date + timedelta(days=1)
    start = st.sidebar.date_input(
        "From", value=min_date, min_value=min_date, max_value=max_date
    )
    end = st.sidebar.date_input(
        "To (exclusive)", value=default_end, min_value=min_date, max_value=default_end
    )
    if start >= end:
        st.error("Start date must be before the end date.")
        st.stop()

    stores = st.sidebar.multiselect("Stores", opts["stores"], default=opts["stores"])
    categories = st.sidebar.multiselect(
        "Categories", opts["categories"], default=opts["categories"]
    )
    brands = st.sidebar.multiselect("Brands", opts["brands"], default=opts["brands"])
    statuses = st.sidebar.multiselect(
        "Order status", opts["statuses"], default=opts["statuses"]
    )

    st.sidebar.divider()
    theme = st.sidebar.radio("Theme", ["Light", "Dark"], index=0, horizontal=True)
    st.session_state["theme"] = theme.lower()

    filters = Filters(
        start_date=start,
        end_date=end,
        stores=tuple(stores),
        categories=tuple(categories),
        brands=tuple(brands),
        statuses=tuple(statuses),
    )
    meta = {"min_date": min_date, "max_date": max_date, "theme": theme.lower()}
    return filters, meta
