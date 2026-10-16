"""Shared Postgres engine for dashboard pages.

Settings precedence: Streamlit secrets (`.streamlit/secrets.toml` or
Cloud secret store) > process environment / `.env` > built-in defaults.

The URL is built here instead of reusing ``src.utils.connection``
constants because those are frozen at import time, while Streamlit
secrets only become available at page runtime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from sqlalchemy import create_engine


def _setting(name: str, default: str = "") -> str:
    """Read one setting from secrets first, then the environment."""
    try:
        value = st.secrets.get(name)
    except Exception:  # noqa: BLE001 -- no Streamlit runtime / no secrets file
        value = None
    if value is None or value == "":
        value = os.getenv(name, default)
    return str(value)


def apply_secrets() -> None:
    """Export secrets into the environment for libraries that read os.environ.

    Kept for backwards compatibility with pages that call it first thing;
    ``get_engine`` / ``db_schema`` already read secrets directly.
    """
    for name in (
        "DATABASE_URL",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_SCHEMA",
        "DB_USER",
        "DB_PASSWORD",
        "DB_SSLMODE",
    ):
        try:
            value = st.secrets.get(name)
        except Exception:  # noqa: BLE001
            value = None
        if value not in (None, ""):
            os.environ.setdefault(name, str(value))


def db_schema() -> str:
    """Target Postgres schema (almost always ``public``)."""
    return _setting("DB_SCHEMA", "public") or "public"


@st.cache_resource
def get_engine():
    """Process-wide pooled SQLAlchemy engine (one per Streamlit worker).

    Prefers a full ``DATABASE_URL`` (what Neon/Supabase hand you, including
    ``?sslmode=require``) and otherwise builds the URL from the DB_* parts.
    """
    direct = _setting("DATABASE_URL", "")
    if direct:
        return create_engine(direct, pool_pre_ping=True, pool_size=5, max_overflow=10)
    user = quote_plus(_setting("DB_USER", "postgres"))
    password = quote_plus(_setting("DB_PASSWORD", ""))
    host = _setting("DB_HOST", "localhost")
    port = _setting("DB_PORT", "5432") or "5432"
    database = _setting("DB_NAME", "bike_store")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    sslmode = _setting("DB_SSLMODE", "")
    if sslmode:
        url += f"?sslmode={sslmode}"
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
