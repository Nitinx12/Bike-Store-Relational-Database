#!/usr/bin/env python3
"""
MongoDB inspector — probes a MongoDB instance and reports all databases,
collections, and document counts.

Usage:
    uv run python scripts/check_mongo.py [MONGO_URI]
    uv run python scripts/check_mongo.py mongodb://127.0.0.1:27017

Defaults to MONGO_URI from .env if not provided.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
except ImportError as exc:
    print(f"[FAIL] pymongo is required: {exc}")
    print("       Install with: uv add pymongo")
    sys.exit(1)


SKIP_DBS = frozenset({"admin", "config", "local"})


def load_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return {}
    env: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def format_uri(uri: str) -> str:
    return uri.replace("//", "//***:", 1) if "@" in uri else uri


def probe(uri: str) -> bool:
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
        print(f"[FAIL] Cannot connect to {format_uri(uri)}: {exc}")
        return False

    build = client.admin.command("buildInfo")
    version = build.get("version", "unknown")

    print(f"\n[OK] Connected to {format_uri(uri)}")
    print(f"    MongoDB version: {version}")
    print()

    databases = sorted(
        client.admin.command("listDatabases")["databases"],
        key=lambda d: d["name"],
    )

    for db_info in databases:
        db_name = db_info["name"]
        if db_name in SKIP_DBS:
            continue

        db = client[db_name]
        try:
            coll_names = sorted(db.list_collection_names())
        except Exception as exc:
            print(f"  [!] Could not list collections for '{db_name}': {exc}")
            continue

        if not coll_names:
            print(f"  {db_name}: (empty — no collections)")
            continue

        total_docs = sum(db[col].count_documents({}) for col in coll_names)
        print(f"  {db_name}  [{len(coll_names)} collections, {total_docs:,} docs]")

        for col in coll_names:
            count = db[col].count_documents({})
            print(f"    {col}: {count:,}")

    return True


def main() -> None:
    env = load_env()
    uri = sys.argv[1] if len(sys.argv) > 1 else env.get("MONGO_URI", "mongodb://localhost:27017")
    success = probe(uri)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
