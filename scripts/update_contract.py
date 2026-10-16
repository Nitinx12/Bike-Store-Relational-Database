"""Update contract YAML files from MongoDB collection schemas.

This script connects to MongoDB and automatically generates or updates
YAML contract files for each collection, including column names and data types
based on actual document structure.

Usage:
    uv run python scripts/update_contract.py              # Update all contracts from MongoDB
    uv run python scripts/update_contract.py --watch        # Watch and update contracts in real-time
    uv run python scripts/update_contract.py --dry-run      # Preview changes without writing
    uv run python scripts/update_contract.py <collection>  # Update single collection only
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.utils.connection import MONGO_DB_NAME, MONGO_URI, require_mongo_env

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"


def load_env() -> dict[str, str]:
    """Load environment variables from .env file."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return {}

    env = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


def get_mongo_client() -> MongoClient:
    """Create and return a MongoDB client connection."""
    try:
        client: Any = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        return client
    except (ServerSelectionTimeoutError, ConnectionFailure) as exc:
        print(f"[FAIL] Cannot connect to MongoDB: {exc}")
        sys.exit(1)


def infer_python_type(value: Any) -> str:
    """Infer Python type from a value for the contract."""
    if value is None:
        return "Any"
    if isinstance(value, str):
        return "str"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def inspect_collection_schema(collection) -> dict[str, Any]:
    """Inspect a MongoDB collection and return schema information with metrics."""
    schema: dict[str, Any] = {
        "description": f"Schema for {collection.name} collection",
        "row_count": 0,
        "column_count": 0,
        "columns": {},
        "sample_documents": [],
    }

    # Get all documents for full count and schema analysis
    try:
        documents = list(collection.find())
        schema["row_count"] = len(documents)
        schema["sample_size"] = min(5, len(documents))
        schema["sample_documents"] = documents[:5]

        # Analyze schema for each field across all documents
        field_data: dict[str, dict[str, Any]] = {}

        for doc in documents:
            for field_name, value in doc.items():
                if field_name not in field_data:
                    field_data[field_name] = {
                        "types": set(),
                        "examples": [],
                        "null_count": 0,
                        "unique_values": set(),
                    }

                data = field_data[field_name]
                data["types"].add(infer_python_type(value))
                data["examples"].append(value) if value is not None else None

                if value is None:
                    data["null_count"] += 1

                data["unique_values"].add(value)

        # Build columns dict with metrics
        schema["column_count"] = len(field_data)
        for field_name, data in field_data.items():
            # Determine primary type (most common)
            type_counts: dict[str, int] = {}
            for t in data["types"]:
                type_counts[t] = type_counts.get(t, 0) + 1
            primary_type = (
                max(type_counts, key=lambda t: type_counts[t]) if type_counts else "Any"
            )

            # Get unique values sample (limit to 5)
            unique_sample = list(data["unique_values"])[:5]

            schema["columns"][field_name] = {
                "type": primary_type,
                "example": data["examples"][0] if data["examples"] else None,
                "nullable": data["null_count"] > 0,
                "unique_values_sample": unique_sample,
                "null_count": data["null_count"],
                "example_count": len(data["examples"]),
            }

    except Exception as e:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"  [!] Could not inspect {collection.name}: {e}")

    return schema


def generate_yaml_from_schema(schema: dict[str, Any]) -> str:
    """Convert schema dict to YAML format for contracts."""
    yaml_lines = []

    # Add metadata
    yaml_lines.append("# Contract automatically generated from MongoDB collection")
    yaml_lines.append(f"# Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    yaml_lines.append(f"# Collection: {schema.get('collection_name', 'unknown')}")
    yaml_lines.append("")

    # Add top-level metrics
    yaml_lines.append("metrics:")
    yaml_lines.append(f"  row_count: {schema['row_count']}")
    yaml_lines.append(f"  column_count: {schema['column_count']}")
    yaml_lines.append("")

    # Add description
    yaml_lines.append(f"description: {schema['description']}")
    yaml_lines.append(f"sample_size: {schema.get('sample_size', 0)}")
    yaml_lines.append("")

    # Add columns
    yaml_lines.append("columns:")
    for col_name, col_info in schema["columns"].items():
        yaml_lines.append(f"  {col_name}:")
        yaml_lines.append(f"    type: {col_info['type']}")
        yaml_lines.append(f"    example: {col_info['example']}")
        yaml_lines.append(f"    nullable: {col_info['nullable']}")
        yaml_lines.append(f"    null_count: {col_info.get('null_count', 0)}")
        yaml_lines.append(
            f"    unique_values_sample: {col_info['unique_values_sample']}"
        )
        yaml_lines.append("")

    # Add sample documents (limited)
    if schema["sample_documents"]:
        yaml_lines.append("sample_documents:")
        for i, doc in enumerate(schema["sample_documents"][:2]):
            yaml_lines.append(f"  - id: {i}")
            for key, value in doc.items():
                yaml_lines.append(f"    {key}: {value}")
            yaml_lines.append("")

    return "\n".join(yaml_lines)


def update_single_contract(
    collection_name: str, dry_run: bool = False, watch: bool = False
) -> bool:
    """Update a single contract file from MongoDB collection."""
    client = get_mongo_client()
    db = client[MONGO_DB_NAME]

    # Check if collection exists
    if collection_name not in db.list_collection_names():
        print(
            f"[WARN] Collection '{collection_name}' not found in database '{MONGO_DB_NAME}'"
        )
        return False

    collection = db[collection_name]
    print(f"\n[INFO] Inspecting collection: {collection_name}")

    # Get schema
    schema = inspect_collection_schema(collection)
    schema["collection_name"] = collection_name

    # Convert to YAML
    yaml_content = generate_yaml_from_schema(schema)

    # Write to contract file
    contract_file = CONTRACTS_DIR / f"{collection_name}.yml"

    if dry_run:
        print(f"[DRY-RUN] Would update {contract_file}")
        print(yaml_content[:500] + "..." if len(yaml_content) > 500 else yaml_content)
        return True

    # Write the file
    try:
        contract_file.write_text(yaml_content)
        print(f"[OK] Updated contract: {contract_file}")
        return True
    except Exception as e:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] Could not write {contract_file}: {e}")
        return False


def update_all_contracts(dry_run: bool = False, watch: bool = False) -> None:
    """Update all contract YAML files from MongoDB collections."""
    client = get_mongo_client()
    db = client[MONGO_DB_NAME]

    # Get all collections
    collections = db.list_collection_names()
    print(
        f"\n[INFO] Found {len(collections)} collections in database '{MONGO_DB_NAME}':"
    )

    updated_count = 0
    error_count = 0

    for collection_name in collections:
        # Skip system collections
        if collection_name.startswith("system."):
            continue

        print(f"  - {collection_name}")

        try:
            if update_single_contract(collection_name, dry_run=dry_run):
                updated_count += 1
            else:
                error_count += 1
        except Exception as e:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
            print(f"  [FAIL] Error processing {collection_name}: {e}")
            error_count += 1

        if watch:
            print("  Waiting 5 seconds before next collection...")
            time.sleep(5)

    print(f"\n[SUMMARY] Updated: {updated_count}, Errors: {error_count}")

    # Watch mode - continuously monitor
    if watch:
        print("\n[INFO] Entering watch mode (Ctrl+C to stop)...")
        while True:
            try:
                print(
                    f"\n[INFO] Running contract update cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                # Clear screen
                os.system("cls" if os.name == "nt" else "clear")
                print(
                    f"\n=== Contract Update Cycle - {time.strftime('%Y-%m-%d %H:%M:%S')} ==="
                )

                # Update all contracts
                update_all_contracts(dry_run=False, watch=False)

                # Wait for next cycle
                print("\n[INFO] Next cycle in 60 seconds...")
                time.sleep(60)

            except KeyboardInterrupt:
                print("\n[INFO] Stopping watch mode")
                break
            except Exception as e:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
                print(f"\n[FAIL] Error in watch cycle: {e}")
                time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update contract YAML files from MongoDB collection schemas."
    )
    parser.add_argument(
        "collection", nargs="?", help="Collection name to update (default: all)"
    )
    parser.add_argument(
        "--watch", action="store_true", help="Watch and update contracts in real-time"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without writing"
    )
    args = parser.parse_args()

    require_mongo_env()

    print("\n[INFO] Starting contract update process")
    print(f"[INFO] Contracts directory: {CONTRACTS_DIR}")
    print(f"[INFO] MongoDB database: {MONGO_DB_NAME}")

    if args.collection:
        # Update single collection
        if update_single_contract(
            args.collection, dry_run=args.dry_run, watch=args.watch
        ):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        # Update all collections
        update_all_contracts(dry_run=args.dry_run, watch=args.watch)


if __name__ == "__main__":
    main()
