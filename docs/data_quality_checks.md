# Data Quality Checks

## Overview

This document explains the SQL based data quality test suite located in the tests folder. The suite is organized as one file per table (9 files), plus one final cross table file covering orphan rows and business logic rules. Every query in every file follows the same convention: if the dataset is healthy, the query returns zero rows. Any row returned by a query represents a record that failed that specific check, and the row itself shows exactly which record is the problem.

These tests are designed to be run after every load of the mongo to postgres ETL (see run book.md), either manually or as part of an automated pipeline that fails the run if any query returns rows.

## How to Run

Each file can be run directly against the target Postgres database, for example:

```
psql -h host -U user -d database -f tests/test_orders.sql
```

For automated pipelines, each query should be wrapped so that a non zero row count causes the test runner to report a failure for that specific check, ideally tagged with the check name (most queries in the final file already include a check_name column for this purpose).

## Categories of Checks

Across the suite, every test falls into one of these categories.

### Not null and not empty checks

These confirm that required fields actually contain data. A null or empty string in a field like brand_name, product_name, or first_name usually means the source document was incomplete or a field name mismatch occurred during the slugify step in the ETL.

Example, from test_brands.sql, test 3:

```sql
SELECT *
FROM public.brands
WHERE brand_name IS NULL
   OR TRIM(brand_name) = '';
```

Purpose: brand_name is the human readable identifier for a brand. If this is null or blank, any report grouping products by brand will show a blank or null category, which is a visible data quality failure to end users.

### Primary key and uniqueness checks

These confirm that the primary key column (or composite key) has no nulls and no duplicate values. Since the ETL script auto detects a primary key and creates a unique constraint on it, a duplicate here would mean the constraint was bypassed, the table was created before the constraint existed, or rows were loaded outside the normal pipeline.

Example, from test_products.sql, test 1:

```sql
SELECT product_id, COUNT(*) AS cnt
FROM public.products
WHERE product_id IS NOT NULL
GROUP BY product_id
HAVING COUNT(*) > 1
UNION ALL
SELECT product_id, COUNT(*)
FROM public.products
WHERE product_id IS NULL
GROUP BY product_id;
```

Purpose: product_id is the join key used throughout the schema (by order_items and stocks). A duplicate or null product_id would cause incorrect joins, double counted sales, or orphaned references elsewhere.

### Type and format validity checks

Since the ETL writes every column as TEXT, the underlying value still needs to represent a valid number, date, or pattern for its intended meaning. These checks cast the text value to its expected type and verify the result is sensible.

Example, from test_customers.sql, test 4:

```sql
SELECT *
FROM public.customers
WHERE zip_code IS NOT NULL
  AND (zip_code::text !~ '^[0-9]+$'
       OR LENGTH(zip_code::text) NOT BETWEEN 3 AND 10);
```

Purpose: zip_code is stored as bigint in the original schema but as TEXT after the ETL load. This check confirms the value is purely numeric and a realistic length for a postal code. A failure here often indicates a source document had a malformed or non numeric postal code (for example, a postal code from a different country format).

### Range and bounds checks

These confirm that numeric values fall within a realistic business range, catching impossible or nonsensical values that are technically valid numbers but make no business sense.

Example, from test_products.sql, test 5:

```sql
SELECT *
FROM public.products
WHERE list_price IS NULL
   OR list_price::numeric < 0
   OR model_year IS NULL
   OR model_year::bigint < 1900
   OR model_year::bigint > EXTRACT(YEAR FROM CURRENT_DATE)::bigint + 1;
```

Purpose: a negative list_price or a model_year of, say, 1850 or 2099 is technically a valid number but not a valid product. This check catches data entry errors or unit conversion mistakes at the source.

### Referential integrity checks (single table scope)

Within each per table file, any foreign key column is checked against its parent table. These are a lighter version of the orphan checks consolidated in the final file, scoped to that table only.

Example, from test_staffs.sql, test 3:

```sql
SELECT s.*
FROM public.staffs s
WHERE s.store_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.stores st WHERE st.store_id = s.store_id
  );
```

Purpose: every staff member must work at a real store. A staff record pointing at a non existent store_id usually means the stores collection was loaded after the staffs collection on the very first run, or a store was deleted in MongoDB without the deletion propagating to Postgres (a known limitation noted in incremental loading.md, since deletes are never detected by this ETL).

### Generated column consistency checks

For order_items, the total_value column is a Postgres generated, stored column computed from quantity, list_price, and discount. Since the ETL script creates all columns as TEXT (see data catalog.md for why order_items is an exception case), this check independently recomputes the expected value and compares it.

Example, from test_order_items.sql, test 5:

```sql
SELECT *
FROM public.order_items
WHERE total_value IS NULL
   OR ABS(
        total_value::numeric
        - (quantity::numeric * list_price::numeric * (1 - discount::numeric))
      ) > 0.01;
```

Purpose: confirms the line item total was computed correctly and matches the formula quantity times list_price times (1 minus discount). A mismatch beyond a small rounding tolerance points to either a corrupted value or a row where the generated column logic did not apply as expected after the TEXT based load.

## The Final File: Orphan Rows and Business Rules

The file test_orphans_and_business_rules.sql is split into two sections and is meant to be the primary health check run after each ETL cycle, since it covers the relationships and business meaning that span multiple tables.

### Section 1: orphan row checks

An orphan row is a child record whose foreign key value points to a parent record that does not exist. This section systematically checks every foreign key relationship shown in the data catalog ERD: orders to customers, staffs, and stores; order_items to orders and products; products to brands and categories; staffs to stores and to their own manager; and stocks to stores and products.

Example, orphan check 4:

```sql
SELECT 'orphan_order_items_order' AS check_name, oi.*
FROM public.order_items oi
WHERE oi.order_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.orders o WHERE o.order_id = oi.order_id
  );
```

Purpose: an order_item without a matching order is meaningless on its own, since an order_item only makes sense as part of an order. This is one of the most important checks in the suite because order_items has its own primary key (order_id, item_id) and its own updated_at column, so it can be loaded independently by the ETL even if its parent order row was somehow missed, deleted, or delayed.

Why this matters specifically for this ETL: because the incremental loading script has no delete propagation (documented in incremental loading.md), an orphan can appear in either direction. If a parent record is deleted from MongoDB, the child rows in Postgres become orphans pointing at a record that no longer exists anywhere. These orphan checks are the only mechanism in this project that surfaces that situation.

### Section 2: business logic validation

These checks go beyond structural correctness and validate that the data tells a coherent business story.

Example, business check 1:

```sql
SELECT 'business_order_with_no_items' AS check_name, o.order_id
FROM public.orders o
WHERE NOT EXISTS (
    SELECT 1 FROM public.order_items oi WHERE oi.order_id = o.order_id
);
```

Purpose: every order should represent the purchase of at least one product. An order with zero order_items is either an order that was created but never finalized, or a case where the order_items rows for that order were missed during incremental loading (for example, if order_items and orders were loaded in different runs and the order_items run happened first, this is normal and self corrects on the next run; if it persists across multiple runs, it indicates a real gap).

Example, business check 4:

```sql
SELECT 'business_staff_store_mismatch' AS check_name, o.*
FROM public.orders o
JOIN public.staffs s ON s.staff_id = o.staff_id
WHERE o.store_id IS NOT NULL
  AND s.store_id IS NOT NULL
  AND o.store_id <> s.store_id;
```

Purpose: validates a business rule that is not enforced by any database constraint, that the staff member assigned to an order should belong to the store fulfilling that order. A mismatch here does not break any foreign key, so the database itself would never flag it, but it represents a logically inconsistent order (a staff member at store A somehow handling an order being fulfilled by store B), which is worth investigating as either a legitimate cross store assignment or a data entry mistake.

Example, business check 9:

```sql
SELECT 'business_order_total_zero_or_negative' AS check_name, oi.order_id,
       SUM(oi.total_value::numeric) AS order_total
FROM public.order_items oi
GROUP BY oi.order_id
HAVING SUM(oi.total_value::numeric) <= 0;
```

Purpose: an order whose line items sum to zero or a negative value is almost certainly a data problem, either a discount of 100 percent or more was applied, a quantity of zero was recorded, or a negative price entered. This is the kind of check that protects downstream revenue reporting from being silently wrong.

## How These Checks Relate to the ETL Pipeline

The data quality suite is intentionally designed around the specific behaviors and limitations of the mongo to postgres ETL script documented in incremental loading.md and run book.md.

No delete detection: because the ETL never removes rows that were deleted from MongoDB, the orphan checks in section 1 of the final file are the primary safeguard against stale child records pointing at parent records that no longer exist.

TEXT only columns: because every column is created as TEXT regardless of its logical type, every numeric, date, and pattern based check in this suite must explicitly cast and validate the value, rather than relying on the column's declared type to guarantee correctness.

order_items exception: because order_items has a composite primary key and a generated column, both its per table file (test_order_items.sql) and the final file give it extra attention, the composite key uniqueness check and the generated column recomputation check exist specifically because this table does not fit the single column primary key pattern that the rest of the schema follows.

Same timestamp edge case: incremental loading.md notes that a record sharing the exact maximum updated_at timestamp with the current Postgres maximum can be permanently missed by the incremental filter. Running the full suite, especially the orphan checks, after every load is the practical way to catch this, since a missed child record would surface as an orphan in order_items or stocks, or a missed parent record would surface as a foreign key failure in the per table files.

## Suggested Operating Procedure

After every run of mongo_to_postgres.py, whether incremental or full refresh, run the 9 per table files followed by the final orphans and business rules file. Any query that returns rows should be logged with its source file and, where present, its check_name. A clean run is one where every query across all 10 files returns zero rows. If a check consistently fails immediately after a full refresh of a specific collection but passes after a full refresh of its related collections, this points toward the load order or the timestamp edge case described above rather than a genuine source data problem.