"""
Great Expectations Data Context for the Bike Store data-quality suites.

This is the one place that turns your Postgres credentials into a live
Great Expectations Data Source. Everything under tests/data_quality/
should get its GX context from here rather than building its own, so
every suite validates against the same connection.

It doesn't duplicate any connection logic: it reuses utils.engine's
postgres_engine() to build the connection string, exactly like the rest
of the pipeline does.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# tests/data_quality/context.py -> project root is two levels up. Adding it
# to sys.path lets us import `utils.*` the same way utils/engine.py does,
# regardless of the working directory this is run from.
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import great_expectations as gx
from great_expectations.data_context import AbstractDataContext
from great_expectations.datasource.fluent import PostgresDatasource

from utils.engine import postgres_engine
from utils.logger import get_logger

logger = get_logger("tests", "context")

DATASOURCE_NAME = "postgres_datasource"

# The env var Great Expectations will substitute at connect time - see
# _connection_string() below for why this indirection is needed.
_GX_CONN_VAR = "GX_POSTGRES_CONNECTION_STRING"

_context: AbstractDataContext | None = None
_datasource: PostgresDatasource | None = None


def _connection_string() -> str:
    """Return a ${VAR}-style reference GX will substitute at connect time,
    after first stashing the real connection string in that env var.

    Why the indirection: Great Expectations' add_postgres() runs the
    connection_string through a strict RFC-3986 URL validator if you pass
    it a literal string. A database name with a space in it (like ours -
    "Bike Store Relational Database") fails that check outright, and
    percent-encoding it doesn't help either: SQLAlchemy's Postgres dialect
    passes the database name to psycopg2 unescaped, so an encoded name
    would just be looked up literally and not found.

    Passing "${GX_POSTGRES_CONNECTION_STRING}" instead skips that strict
    validation - GX only checks it matches the ${...} template shape - and
    substitutes the real value from the environment right before calling
    SQLAlchemy's create_engine(), which handles a literal space in the
    database name fine. This is the same mechanism GX uses for keeping
    secrets out of committed config; we're just also using it to route
    around the validator.
    """
    engine = postgres_engine()
    os.environ[_GX_CONN_VAR] = engine.url.render_as_string(hide_password=False)
    return "${" + _GX_CONN_VAR + "}"


def get_context() -> AbstractDataContext:
    """Return a process-wide ephemeral GX Data Context with the Postgres
    Data Source already registered. Cached after the first call, so
    repeated calls within one run reuse the same context/datasource."""
    global _context, _datasource
    if _context is not None:
        return _context

    context = gx.get_context(mode="ephemeral")
    try:
        datasource = context.data_sources.add_postgres(
            DATASOURCE_NAME, connection_string=_connection_string()
        )
    except Exception as e:
        logger.error(
            f"Could not register Postgres data source with Great Expectations: {e}"
        )
        raise

    logger.info("Great Expectations context ready, Postgres data source registered.")
    _context = context
    _datasource = datasource
    return _context


def get_datasource() -> PostgresDatasource:
    """Return the registered Postgres Data Source, building the context
    first if it hasn't been built yet."""
    if _datasource is None:
        get_context()
    return _datasource
