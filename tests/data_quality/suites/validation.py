"""
Great Expectations suite definitions for the Bike Store schema.

Each `*_suite()` function returns a fresh list of Expectation objects for
one table. Keeping them here (instead of inline in the runner) makes it
easy to see, review, and edit the business rules table by table.

A few of these rules are *assumptions* based only on column names/types
(we don't have access to your real data) -- they're flagged with TODO
comments below. Run once, see what (if anything) fails, and tighten or
loosen the relevant expectation.
"""

from __future__ import annotations

import great_expectations.expectations as gxe

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_REGEX = r"^[0-9()+\-.\s]{7,20}$"


def _not_null(*columns: str) -> list:
    return [gxe.ExpectColumnValuesToNotBeNull(column=c) for c in columns]


def _fk_check(
    description: str,
    child_column: str,
    parent_table: str,
    parent_column: str,
    nullable: bool = False,
):
    """Referential-integrity check: every non-null `child_column` value in
    the current (child) table's batch must exist in
    `parent_table.parent_column`.

    GX substitutes `{batch}` with the batch currently being validated, so
    this always checks the child table against the live parent table.
    """
    null_guard = f"child.{child_column} IS NOT NULL AND " if nullable else ""
    query = f"""
        SELECT child.*
        FROM {{batch}} child
        LEFT JOIN {parent_table} parent
            ON child.{child_column} = parent.{parent_column}
        WHERE {null_guard}parent.{parent_column} IS NULL
    """
    return gxe.UnexpectedRowsExpectation(
        unexpected_rows_query=query, description=description
    )


def brands_suite() -> list:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectColumnValuesToBeUnique(column="brand_id"),
        *_not_null("brand_id", "brand_name", "updated_at"),
    ]


def categories_suite() -> list:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectColumnValuesToBeUnique(column="category_id"),
        *_not_null("category_id", "category_name", "updated_at"),
    ]


def customers_suite() -> list:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectColumnValuesToBeUnique(column="customer_id"),
        *_not_null(
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
        gxe.ExpectColumnValuesToMatchRegex(column="email", regex=EMAIL_REGEX),
        # phone is allowed to be NULL, but if present should look like a phone number
        gxe.ExpectColumnValuesToMatchRegex(column="phone", regex=PHONE_REGEX),
        gxe.ExpectColumnValueLengthsToEqual(column="state", value=2),
        # NOTE: zip_code is stored as bigint, so it can't preserve leading
        # zeros (e.g. "02138" -> 2138). That's a schema smell worth fixing
        # upstream; for now we just check it's a plausible positive value.
        gxe.ExpectColumnValuesToBeBetween(
            column="zip_code", min_value=1, max_value=99999
        ),
    ]


def staffs_suite() -> list:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectColumnValuesToBeUnique(column="staff_id"),
        *_not_null(
            "staff_id",
            "first_name",
            "last_name",
            "email",
            "active",
            "store_id",
            "updated_at",
        ),
        gxe.ExpectColumnValuesToMatchRegex(column="email", regex=EMAIL_REGEX),
        gxe.ExpectColumnValuesToMatchRegex(column="phone", regex=PHONE_REGEX),
        gxe.ExpectColumnValuesToBeInSet(column="active", value_set=[0, 1]),
        _fk_check(
            "staffs.store_id must reference an existing stores.store_id",
            "store_id",
            "stores",
            "store_id",
        ),
        _fk_check(
            "staffs.manager_id, if set, must reference an existing staffs.staff_id",
            "manager_id",
            "staffs",
            "staff_id",
            nullable=True,
        ),
    ]


def stores_suite() -> list:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectColumnValuesToBeUnique(column="store_id"),
        *_not_null(
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
        gxe.ExpectColumnValuesToMatchRegex(column="email", regex=EMAIL_REGEX),
        gxe.ExpectColumnValuesToMatchRegex(column="phone", regex=PHONE_REGEX),
        gxe.ExpectColumnValueLengthsToEqual(column="state", value=2),
        gxe.ExpectColumnValuesToBeBetween(
            column="zip_code", min_value=1, max_value=99999
        ),
    ]


def products_suite() -> list:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectColumnValuesToBeUnique(column="product_id"),
        *_not_null(
            "product_id",
            "product_name",
            "brand_id",
            "category_id",
            "model_year",
            "list_price",
            "updated_at",
        ),
        gxe.ExpectColumnValuesToBeBetween(
            column="list_price", min_value=0, strict_min=True
        ),
        # TODO: adjust the upper bound if you legitimately stock pre-order /
        # next-model-year bikes; this just catches obvious typos (e.g. 2035).
        gxe.ExpectColumnValuesToBeBetween(
            column="model_year", min_value=2000, max_value=2027
        ),
        _fk_check(
            "products.brand_id must reference an existing brands.brand_id",
            "brand_id",
            "brands",
            "brand_id",
        ),
        _fk_check(
            "products.category_id must reference an existing categories.category_id",
            "category_id",
            "categories",
            "category_id",
        ),
    ]


def stocks_suite() -> list:
    return (
        [
            gxe.ExpectColumnValuesToBeUnique(
                column="store_id", mostly=0
            ),  # placeholder, replaced below
        ][:0]
        + [  # keep structure simple: build the real list explicitly
            gxe.ExpectTableRowCountToBeBetween(min_value=1),
            *_not_null("store_id", "product_id", "quantity", "updated_at"),
            gxe.ExpectCompoundColumnsToBeUnique(column_list=["store_id", "product_id"]),
            gxe.ExpectColumnValuesToBeBetween(column="quantity", min_value=0),
            _fk_check(
                "stocks.store_id must reference an existing stores.store_id",
                "store_id",
                "stores",
                "store_id",
            ),
            _fk_check(
                "stocks.product_id must reference an existing products.product_id",
                "product_id",
                "products",
                "product_id",
            ),
        ]
    )


def orders_suite() -> list:
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectColumnValuesToBeUnique(column="order_id"),
        *_not_null(
            "order_id",
            "customer_id",
            "order_status",
            "order_date",
            "required_date",
            "store_id",
            "staff_id",
            "updated_at",
        ),
        # TODO: once you've confirmed the real set of statuses
        # (`SELECT DISTINCT order_status FROM orders;`), replace this with:
        # gxe.ExpectColumnValuesToBeInSet(column="order_status", value_set=[...]))
        gxe.ExpectColumnValueLengthsToBeBetween(
            column="order_status", min_value=1, max_value=50
        ),
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="required_date",
            column_B="order_date",
            or_equal=True,
            ignore_row_if="either_value_is_missing",
        ),
        gxe.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="shipped_date",
            column_B="order_date",
            or_equal=True,
            ignore_row_if="either_value_is_missing",
        ),
        _fk_check(
            "orders.customer_id must reference an existing customers.customer_id",
            "customer_id",
            "customers",
            "customer_id",
        ),
        _fk_check(
            "orders.store_id must reference an existing stores.store_id",
            "store_id",
            "stores",
            "store_id",
        ),
        _fk_check(
            "orders.staff_id must reference an existing staffs.staff_id",
            "staff_id",
            "staffs",
            "staff_id",
        ),
    ]


def order_items_suite() -> list:
    consistency_query = """
        SELECT *
        FROM {batch}
        WHERE ABS(total_value - (list_price * quantity * (1 - discount))) > 0.02
    """
    return [
        gxe.ExpectTableRowCountToBeBetween(min_value=1),
        gxe.ExpectCompoundColumnsToBeUnique(column_list=["order_id", "item_id"]),
        *_not_null(
            "order_id",
            "item_id",
            "product_id",
            "quantity",
            "list_price",
            "discount",
            "total_value",
            "updated_at",
        ),
        gxe.ExpectColumnValuesToBeBetween(column="quantity", min_value=1),
        gxe.ExpectColumnValuesToBeBetween(
            column="list_price", min_value=0, strict_min=True
        ),
        gxe.ExpectColumnValuesToBeBetween(column="discount", min_value=0, max_value=1),
        gxe.ExpectColumnValuesToBeBetween(column="total_value", min_value=0),
        gxe.UnexpectedRowsExpectation(
            unexpected_rows_query=consistency_query,
            description="total_value must equal list_price * quantity * (1 - discount)",
        ),
        _fk_check(
            "order_items.order_id must reference an existing orders.order_id",
            "order_id",
            "orders",
            "order_id",
        ),
        _fk_check(
            "order_items.product_id must reference an existing products.product_id",
            "product_id",
            "products",
            "product_id",
        ),
    ]


# Table name -> suite-builder function. The runner iterates this dict, so
# adding a new table's checks is just adding one more entry here.
TABLE_SUITES = {
    "brands": brands_suite,
    "categories": categories_suite,
    "customers": customers_suite,
    "staffs": staffs_suite,
    "stores": stores_suite,
    "products": products_suite,
    "stocks": stocks_suite,
    "orders": orders_suite,
    "order_items": order_items_suite,
}
