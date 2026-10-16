# reads .env so the rest of the code stays clean
import os

from dotenv import load_dotenv

load_dotenv()

# postgres settings, matches .env names
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "bike_store")
DB_SCHEMA = os.getenv("DB_SCHEMA", "public")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# mongo settings
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/bike_store")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "bike_store")


# full URL wins when set (e.g. Neon pooled string with ?sslmode=require)
DATABASE_URL = os.getenv("DATABASE_URL", "")


def normalize_db_url(url: str) -> str:
    """Accept plain and SQLAlchemy Postgres URLs (e.g. postgres:// legacy)."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


# fail fast if postgres creds are missing
def require_pg_env():
    if DATABASE_URL:
        return
    missing = [
        k
        for k, v in {
            "DB_HOST": DB_HOST,
            "DB_PORT": DB_PORT,
            "DB_NAME": DB_NAME,
            "DB_USER": DB_USER,
        }.items()
        if not v
    ]
    if missing:
        raise ValueError(f"missing env vars: {', '.join(missing)}")


# SQLAlchemy URL for the warehouse, honouring DATABASE_URL first
def postgres_url() -> str:
    if DATABASE_URL:
        return normalize_db_url(DATABASE_URL)
    require_pg_env()
    return (
        f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )


# keyword args for psycopg2.connect, honouring DATABASE_URL first
def postgres_psycopg_kwargs() -> dict:
    if DATABASE_URL:
        from typing import Any
        from urllib.parse import urlparse

        parts = urlparse(normalize_db_url(DATABASE_URL))
        kwargs: dict[str, Any] = {
            "host": parts.hostname,
            "dbname": parts.path.lstrip("/"),
            "user": parts.username,
            "password": parts.password or "",
        }
        if parts.port:
            kwargs["port"] = parts.port
        query = dict(q.split("=", 1) for q in parts.query.split("&") if "=" in q)
        if query.get("sslmode"):
            kwargs["sslmode"] = query["sslmode"]
        return kwargs
    require_pg_env()
    return {
        "host": DB_HOST,
        "port": DB_PORT,
        "dbname": DB_NAME,
        "user": DB_USER,
        "password": DB_PASSWORD,
    }


# fail fast if mongo uri is missing
def require_mongo_env():
    if not MONGO_URI or not MONGO_DB_NAME:
        raise ValueError("missing MONGO_URI or MONGO_DB_NAME")
