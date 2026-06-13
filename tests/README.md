# Tests

SQL data quality checks for the retail Postgres schema loaded by the mongo to postgres ETL.

Each file contains queries that should return zero rows if the data is healthy. Any returned row is a failing record.

- test_brands.sql
- test_categories.sql
- test_customers.sql
- test_stores.sql
- test_staffs.sql
- test_products.sql
- test_orders.sql
- test_order_items.sql
- test_stocks.sql
- test_orphans_and_business_rules.sql

See data quality checks.md for details on each check.