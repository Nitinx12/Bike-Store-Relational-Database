"""Run Great Expectations checks against the Bike Store PostgreSQL tables.

Examples:
    uv run python scripts/run_gx.py
    uv run python scripts/run_gx.py orders products
    uv run python scripts/run_gx.py --list
    uv run python scripts/run_gx.py --config-check

The script reads PostgreSQL settings from the repository's ``.env`` file.
It creates a suite for each requested table covering key uniqueness, required
fields, whitespace, future dates, referential integrity, formats, ranges, and
the order-item pricing calculations.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import great_expectations as gx
import great_expectations.expectations as gxe
from dotenv import load_dotenv
from sqlalchemy import URL

ROOT_DIR = Path(__file__).resolve().parents[1]
GX_DIR = ROOT_DIR / "gx"
DATASOURCE_NAME = "bike_store_postgres"

# Table name -> primary-key columns. The two composite keys are intentional.
TABLE_RULES: dict[str, tuple[str, ...]] = {
    "brands": ("brand_id",),
    "categories": ("category_id",),
    "customers": ("customer_id",),
    "stores": ("store_id",),
    "staffs": ("staff_id",),
    "products": ("product_id",),
    "orders": ("order_id",),
    "order_items": ("order_id", "item_id"),
    "stocks": ("store_id", "product_id"),
}

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "brands": ("brand_id", "brand_name", "updated_at"),
    "categories": ("category_id", "category_name", "updated_at"),
    "customers": (
        "customer_id",
        "first_name",
        "last_name",
        "email",
        "street",
        "city",
        "state",
        "zip_code",
        "updated_at",
    ),
    "stores": (
        "store_id",
        "store_name",
        "phone",
        "email",
        "street",
        "city",
        "state",
        "zip_code",
        "updated_at",
    ),
    "staffs": (
        "staff_id",
        "first_name",
        "last_name",
        "email",
        "active",
        "store_id",
        "updated_at",
    ),
    "products": (
        "product_id",
        "product_name",
        "brand_id",
        "category_id",
        "model_year",
        "list_price",
        "updated_at",
    ),
    "orders": (
        "order_id",
        "customer_id",
        "order_status",
        "order_date",
        "required_date",
        "store_id",
        "staff_id",
        "updated_at",
    ),
    "order_items": (
        "order_id",
        "item_id",
        "product_id",
        "quantity",
        "list_price",
        "discount",
        "total_value",
        "updated_at",
    ),
    "stocks": ("store_id", "product_id", "quantity", "updated_at"),
}

TEXT_COLUMNS: dict[str, tuple[str, ...]] = {
    "brands": ("brand_name",),
    "categories": ("category_name",),
    "customers": (
        "first_name",
        "last_name",
        "phone",
        "email",
        "street",
        "city",
        "state",
    ),
    "stores": ("store_name", "phone", "email", "street", "city", "state"),
    "staffs": ("first_name", "last_name", "email", "phone"),
    "products": ("product_name",),
    "orders": ("order_status",),
}

FOREIGN_KEYS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "staffs": (
        ("store_id", "stores", "store_id"),
        ("manager_id", "staffs", "staff_id"),
    ),
    "products": (
        ("brand_id", "brands", "brand_id"),
        ("category_id", "categories", "category_id"),
    ),
    "orders": (
        ("customer_id", "customers", "customer_id"),
        ("store_id", "stores", "store_id"),
        ("staff_id", "staffs", "staff_id"),
    ),
    "order_items": (
        ("order_id", "orders", "order_id"),
        ("product_id", "products", "product_id"),
    ),
    "stocks": (
        ("store_id", "stores", "store_id"),
        ("product_id", "products", "product_id"),
    ),
}

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Bike Store GX validations.")
    parser.add_argument(
        "tables",
        nargs="*",
        metavar="TABLE",
        help="Tables to validate (default: every configured table).",
    )
    parser.add_argument("--list", action="store_true", help="List supported tables.")
    parser.add_argument(
        "--config-check",
        action="store_true",
        help="Validate the GX file context without connecting to PostgreSQL.",
    )
    return parser.parse_args()


def get_connection_string() -> str:
    """SQLAlchemy URL for Postgres, honouring DATABASE_URL (e.g. Neon) first."""
    load_dotenv(ROOT_DIR / ".env")
    if os.getenv("DATABASE_URL"):
        from src.utils.connection import normalize_db_url

        return normalize_db_url(os.environ["DATABASE_URL"])

    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise ValueError(f"Missing required .env value(s): {', '.join(missing)}")

    return URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.getenv("DB_PASSWORD", ""),
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    ).render_as_string(hide_password=False)


def get_context():
    """Load the repository's file-backed GX context."""
    if not (GX_DIR / "great_expectations.yml").is_file():
        raise FileNotFoundError(f"GX configuration not found: {GX_DIR}")
    return gx.get_context(context_root_dir=GX_DIR)


def get_datasource(context):
    """Return the configured PostgreSQL datasource, registering it if needed."""
    # Set it on every run, including when a persisted datasource already
    # references the placeholder below.
    os.environ["GX_POSTGRES_CONNECTION_STRING"] = get_connection_string()
    try:
        return context.data_sources.get(DATASOURCE_NAME)
    except KeyError:
        # Persist a placeholder rather than writing credentials into
        # gx/great_expectations.yml. GX resolves it at connection time.
        return context.data_sources.add_postgres(
            name=DATASOURCE_NAME,
            connection_string="${GX_POSTGRES_CONNECTION_STRING}",
        )


def get_batch(datasource, table_name: str):
    """Return the whole-table batch for one PostgreSQL table."""
    try:
        asset = datasource.get_asset(table_name)
    except LookupError:
        asset = datasource.add_table_asset(name=table_name, table_name=table_name)

    batch_name = f"{table_name}_whole_table"
    try:
        batch_definition = asset.get_batch_definition(batch_name)
    except KeyError:
        batch_definition = asset.add_batch_definition_whole_table(batch_name)
    return batch_definition.get_batch()


def unexpected_rows(description: str, query: str):
    """Build a SQL-backed expectation for rules GX does not model directly."""
    return gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=query,
        description=description,
    )


def add_whitespace_expectation(suite: gx.ExpectationSuite, table_name: str) -> None:
    """Reject empty, padded, or double-spaced text while allowing nullable fields."""
    conditions = [
        f'''"{column}" IS NOT NULL AND (
            "{column}" <> BTRIM("{column}")
            OR BTRIM("{column}") = ''
            OR POSITION('  ' IN "{column}") > 0
        )'''
        for column in TEXT_COLUMNS.get(table_name, ())
    ]
    if conditions:
        suite.add_expectation(
            unexpected_rows(
                "text fields must not be empty, padded, or contain repeated spaces",
                "SELECT * FROM {batch} WHERE "
                + " OR ".join(f"({item})" for item in conditions),
            )
        )


def add_future_date_expectations(suite: gx.ExpectationSuite, table_name: str) -> None:
    """Reject timestamps/dates later than the database's current time."""
    suite.add_expectation(
        unexpected_rows(
            "updated_at must not be in the future",
            'SELECT * FROM {batch} WHERE "updated_at" > CURRENT_TIMESTAMP',
        )
    )
    if table_name == "orders":
        suite.add_expectation(
            unexpected_rows(
                "order, required, and shipped dates must not be in the future",
                """SELECT * FROM {batch}
                   WHERE "order_date" > CURRENT_DATE
                      OR "required_date" > CURRENT_DATE
                      OR "shipped_date" > CURRENT_DATE""",
            )
        )


def add_foreign_key_expectations(suite: gx.ExpectationSuite, table_name: str) -> None:
    """Ensure every non-null foreign key resolves to an existing parent key."""
    for child_column, parent_table, parent_column in FOREIGN_KEYS.get(table_name, ()):
        suite.add_expectation(
            unexpected_rows(
                f"{child_column} must reference {parent_table}.{parent_column}",
                f'''SELECT * FROM {{batch}}
                    WHERE "{child_column}" IS NOT NULL
                      AND "{child_column}" NOT IN (
                          SELECT "{parent_column}"
                          FROM public."{parent_table}"
                          WHERE "{parent_column}" IS NOT NULL
                      )''',
            )
        )


def add_domain_expectations(suite: gx.ExpectationSuite, table_name: str) -> None:
    """Add table-specific format, range, date-order, and arithmetic checks."""
    if table_name in {"customers", "staffs", "stores"}:
        suite.add_expectation(
            gxe.ExpectColumnValuesToMatchRegex(column="email", regex=EMAIL_REGEX)
        )

    if table_name in {"customers", "stores"}:
        suite.add_expectation(
            gxe.ExpectColumnValueLengthsToEqual(column="state", value=2)
        )
        suite.add_expectation(
            unexpected_rows(
                "zip_code must contain exactly five digits",
                'SELECT * FROM {batch} WHERE "zip_code" IS NOT NULL AND LENGTH("zip_code"::TEXT) <> 5',
            )
        )

    if table_name == "staffs":
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(column="active", value_set=[0, 1])
        )
        suite.add_expectation(
            unexpected_rows(
                "a staff member cannot manage themselves",
                'SELECT * FROM {batch} WHERE "manager_id" = "staff_id"',
            )
        )

    if table_name == "products":
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="list_price", min_value=0, strict_min=True
            )
        )
        suite.add_expectation(
            unexpected_rows(
                "model_year must be from 2000 through next calendar year",
                """SELECT * FROM {batch}
                   WHERE "model_year" < 2000
                      OR "model_year" > EXTRACT(YEAR FROM CURRENT_DATE) + 1""",
            )
        )

    if table_name == "stocks":
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(column="quantity", min_value=0)
        )

    if table_name == "orders":
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeInSet(
                column="order_status",
                value_set=["Completed", "Pending", "Processing", "Rejected"],
            )
        )
        suite.add_expectation(
            unexpected_rows(
                "required and shipped dates must not precede order_date",
                """SELECT * FROM {batch}
                   WHERE ("required_date" IS NOT NULL AND "required_date" < "order_date")
                      OR ("shipped_date" IS NOT NULL AND "shipped_date" < "order_date")""",
            )
        )
        suite.add_expectation(
            unexpected_rows(
                "every order must contain at least one line item",
                """SELECT * FROM {batch}
                   WHERE "order_id" NOT IN (
                       SELECT "order_id" FROM public.order_items
                   )""",
            )
        )

    if table_name == "order_items":
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(column="quantity", min_value=1)
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="list_price", min_value=0, strict_min=True
            )
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(
                column="discount", min_value=0, max_value=1
            )
        )
        suite.add_expectation(
            gxe.ExpectColumnValuesToBeBetween(column="total_value", min_value=0)
        )
        suite.add_expectation(
            unexpected_rows(
                "total_value must equal quantity * list_price * (1 - discount), within one cent",
                """SELECT * FROM {batch}
                   WHERE ABS("total_value" - ("quantity" * "list_price" * (1 - "discount"))) >= 0.01""",
            )
        )
        suite.add_expectation(
            unexpected_rows(
                "line-item price must match the product catalog price, within one cent",
                """SELECT * FROM {batch}
                   WHERE NOT EXISTS (
                       SELECT 1
                       FROM (
                           SELECT product_id AS catalog_product_id,
                                  list_price AS catalog_list_price
                           FROM public.products
                       ) AS catalog
                       WHERE catalog.catalog_product_id = product_id
                         AND ABS(catalog.catalog_list_price - list_price) < 0.01
                   )""",
            )
        )


def make_suite(table_name: str) -> gx.ExpectationSuite:
    """Create the GX data-quality suite for one configured table."""
    key_columns = TABLE_RULES[table_name]
    suite = gx.ExpectationSuite(name=f"{table_name}_quality")
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=1))

    for column in REQUIRED_COLUMNS[table_name]:
        suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column=column))

    if len(key_columns) == 1:
        suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column=key_columns[0]))
    else:
        suite.add_expectation(
            gxe.ExpectCompoundColumnsToBeUnique(column_list=list(key_columns))
        )
    add_whitespace_expectation(suite, table_name)
    add_future_date_expectations(suite, table_name)
    add_foreign_key_expectations(suite, table_name)
    add_domain_expectations(suite, table_name)
    return suite


def validate_table(context, datasource, table_name: str) -> bool:
    """Validate one table and print a compact, CI-friendly result."""
    try:
        suite = context.suites.add_or_update(make_suite(table_name))
        result = get_batch(datasource, table_name).validate(suite)
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly  # A connection/schema error is a failed validation.
        print(f"[FAIL] {table_name}: {exc}")
        return False

    stats = result.statistics
    passed = stats.get("successful_expectations", 0)
    evaluated = stats.get("evaluated_expectations", 0)
    status = "PASS" if result.success else "FAIL"
    print(f"[{status}] {table_name}: {passed}/{evaluated} expectations passed")
    if not result.success:
        failed = [
            item.expectation_config.description or item.expectation_config.type
            for item in result.results
            if not item.success
        ]
        print(f"       Failed: {'; '.join(failed)}")
    return bool(result.success)


def main() -> int:
    args = parse_args()
    if args.list:
        print("\n".join(TABLE_RULES))
        return 0

    unknown = [table for table in args.tables if table not in TABLE_RULES]
    if unknown:
        print(f"Unknown table(s): {', '.join(unknown)}", file=sys.stderr)
        print("Use --list to see supported tables.", file=sys.stderr)
        return 2

    try:
        context = get_context()
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] GX configuration: {exc}", file=sys.stderr)
        return 1

    if args.config_check:
        print(f"[PASS] GX configuration loaded from {GX_DIR}")
        return 0

    try:
        datasource = get_datasource(context)
    except Exception as exc:  # noqa: BLE001 -- stage boundary: log and continue/fail cleanly
        print(f"[FAIL] PostgreSQL datasource: {exc}", file=sys.stderr)
        return 1

    tables = args.tables or list(TABLE_RULES)
    failed = [
        table for table in tables if not validate_table(context, datasource, table)
    ]
    if failed:
        print(f"\nGX validation failed for: {', '.join(failed)}", file=sys.stderr)
        return 1

    print(f"\nGX validation passed for {len(tables)} table(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
