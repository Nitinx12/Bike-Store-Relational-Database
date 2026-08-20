# Data Quality Checks

## Overview
SQL test suite in `tests/`: one file per table (9 files) + one cross-table file for orphans and business rules. **Convention: every query returns zero rows when healthy.** Any row returned = that specific record failed that check.

Run after every `mongo_to_postgres.py` load (see `run_book.md`), manually or in an automated pipeline that fails the run on any non-empty result.

## How to run
```
psql -h host -U user -d database -f tests/test_orders.sql
```
Wrap each query so a non-zero row count fails that check. Most queries in the final file already return a `check_name` column for this.

## Check categories

| Category | What it catches | Example |
|---|---|---|
| Not null / not empty | Missing required fields (e.g. `brand_name`) — usually incomplete source doc or a slugify mismatch | `WHERE brand_name IS NULL OR TRIM(brand_name)=''` |
| Primary key / uniqueness | Nulls or duplicates on the pk — means the unique constraint was bypassed or rows loaded outside the pipeline | `GROUP BY product_id HAVING COUNT(*)>1` |
| Type / format validity | Since every column is TEXT, casts must still be valid (numeric, date, pattern) | `zip_code !~ '^[0-9]+$'` |
| Range / bounds | Technically valid numbers that make no business sense (negative price, year 1850) | `list_price::numeric < 0` |
| Referential integrity (per table) | FK pointing at a missing parent, scoped to one table | staff → nonexistent `store_id` |
| Generated column consistency | `order_items.total_value` recomputed and compared, since generated columns don't survive the TEXT load | `total_value` vs `qty * price * (1-discount)` |

## The final file: orphans + business rules

`test_orphans_and_business_rules.sql` is the primary post-load health check — it spans tables, which the per-table files can't.

```mermaid
flowchart TD
    A[Run 9 per-table files] --> B[Run orphans and business rules file]
    B --> C[Section 1: Orphan checks]
    B --> D[Section 2: Business logic checks]
    C --> C1[Every FK in the ERD checked both directions]
    D --> D1[Order has at least one item]
    D --> D2[Staff store matches order store]
    D --> D3[Order total is greater than zero]
    C1 --> E{Any rows returned?}
    D1 --> E
    D2 --> E
    D3 --> E
    E -->|Yes| F[Log check_name + file, investigate]
    E -->|No| G[Clean run]
```

**Orphan checks (Section 1):** a child row whose FK points at a parent that no longer exists — covers orders↔customers/staffs/stores, order_items↔orders/products, products↔brands/categories, staffs↔stores/manager, stocks↔stores/products. This is the *only* mechanism that catches deletes, since the ETL never propagates them.

**Business logic checks (Section 2):** structurally valid data that's still nonsensical — an order with zero items, a staff member's store not matching the order's store, an order whose line items sum to ≤ 0.

## Why these checks are shaped this way

| ETL behavior | Resulting test design |
|---|---|
| No delete detection | Orphan checks (Section 1) are the main safeguard against stale child rows |
| All columns are TEXT | Every numeric/date/pattern check must explicitly cast and validate |
| `order_items` has a composite key + generated column | Gets extra checks: composite-key uniqueness and independent recomputation of `total_value` |
| Same-timestamp edge case can silently drop a record | Running the full suite (especially orphans) after every load is what catches it |

## Automated runner: `plpgsql_tests.py`

Instead of running each `.sql` file by hand, `plpgsql_tests.py` runs the whole suite and prints a summary report.

- Parses each `.sql` file into individual tests, split on comment markers like `-- Test 3:`, `-- Orphan 4:`, `-- Business 7:`.
- Runs every test's query: **0 rows → PASS**, **1+ rows → FAIL**, a raised error (e.g. missing table/column) → **ERROR** (kept separate from FAIL).
- Uses the same Postgres connection as the rest of the pipeline (`utils/connection.py` → `utils/engine.py`, from `.env`) — no flags needed for normal use.
- Prints a per-file pass/fail/error summary table, plus a detail table for anything that didn't pass.
- Logs full detail to `logs/tests/<name>_<timestamp>.log`; the terminal shows only the summary.
- Exit code 0 if everything passed, 1 otherwise — safe to drop into CI.

```Python
python plpgsql_tests.py                                                             # run everything in tests/
python plpgsql_tests.py --show-failures --max-rows 5                                # preview offending rows
python plpgsql_tests.py --tests-dir ./tests                                         # point at a different folder
python plpgsql_tests.py --dsn "postgresql://user:pass@host:5432/dbname"             # one-off DB override
```

Requires `psycopg2-binary` and `rich` (`uv add psycopg2-binary rich`).

## Operating procedure
1. Run `python plpgsql_tests.py` (recommended), or run the 9 per-table files then the orphans/business-rules file manually.
2. Log any returned rows with their source file and `check_name`.
3. A clean run = zero rows across all 10 files.
4. A check that fails right after a full refresh of one collection but clears after refreshing related collections → load-order or timestamp edge case, not a real data problem.