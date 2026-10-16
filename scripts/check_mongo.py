"""Check MongoDB connectivity and list collections with document counts.

Usage:
    uv run python scripts/check_mongo.py              # DB from the URI
    uv run python scripts/check_mongo.py --db walmart # a specific DB
    uv run python scripts/check_mongo.py --all        # every DB
    uv run python scripts/check_mongo.py "<uri>"      # custom URI
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:
    from pymongo import MongoClient
    from pymongo.errors import (
        ConfigurationError,
        ConnectionFailure,
        OperationFailure,
        ServerSelectionTimeoutError,
    )
except ImportError as exc:
    print(f"[FAIL] pymongo is required: {exc}")
    print("       Install with: uv add pymongo")
    sys.exit(1)

# System databases hidden when using --all
SKIP_DBS = frozenset({"admin", "config", "local"})


def load_env() -> dict[str, str]:
    """Read simple KEY=VALUE pairs from the repo's .env file."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return {}
    env: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


def format_uri(uri: str) -> str:
    """Mask credentials so passwords never get printed."""
    parts = urlsplit(uri)
    if parts.username or parts.password:
        host = parts.netloc.rsplit("@", 1)[-1]
        return urlunsplit(parts._replace(netloc=f"***:***@{host}"))
    return uri


def print_db(client: MongoClient, db_name: str) -> None:
    """Print one database's collections and document counts."""
    db = client[db_name]
    try:
        coll_names = sorted(db.list_collection_names())
    except (ConnectionFailure, OperationFailure, ServerSelectionTimeoutError) as exc:
        print(f"  [!] Could not list collections for '{db_name}': {exc}")
        return

    if not coll_names:
        print(f"  {db_name}: (empty - no collections)")
        return

    # Count each collection once and reuse the result
    counts = {col: db[col].count_documents({}) for col in coll_names}
    print(
        f"  {db_name}  [{len(coll_names)} collections, {sum(counts.values()):,} docs]"
    )
    for col, count in counts.items():
        print(f"    {col}: {count:,}")


def probe(uri: str, db_name: str | None = None, show_all: bool = False) -> bool:
    """Ping the server, then print the requested database(s)."""
    try:
        client: Any = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except (ServerSelectionTimeoutError, ConnectionFailure, OperationFailure) as exc:
        print(f"[FAIL] Cannot connect to {format_uri(uri)}: {exc}")
        return False

    version = client.admin.command("buildInfo").get("version", "unknown")
    print(f"\n[OK] Connected to {format_uri(uri)}")
    print(f"    MongoDB version: {version}\n")

    if show_all:
        targets = [n for n in sorted(client.list_database_names()) if n not in SKIP_DBS]
    else:
        # Fall back to the database named in the URI
        if not db_name:
            try:
                db_name = client.get_default_database().name
            except ConfigurationError:
                print("[!] No database in the URI; use --db NAME or --all.")
                return False
        targets = [db_name]

    for name in targets:
        print_db(client, name)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Check MongoDB connectivity.")
    parser.add_argument(
        "uri", nargs="?", help="Mongo URI (default: MONGO_URI from .env)"
    )
    parser.add_argument(
        "--db", help="Database to inspect (default: the one in the URI)"
    )
    parser.add_argument("--all", action="store_true", help="List every database")
    args = parser.parse_args()

    # Catch typos like --bike_store instead of treating them as a URI
    if args.uri and args.uri.startswith("-"):
        parser.error(f"unknown option {args.uri!r}; did you mean --db NAME?")

    env = load_env()
    uri = args.uri or env.get("MONGO_URI", "mongodb://localhost:27017")
    sys.exit(0 if probe(uri, args.db, args.all) else 1)


if __name__ == "__main__":
    main()
