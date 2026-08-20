# Architecture

This project moves retail data from **MongoDB** to **PostgreSQL** on a schedule, checks it for quality, then turns it into reports. This page is the simple, visual entry point for column-level detail, see [`data_catlog.md`](./data_catlog.md), [`incremental_loading.md`](./incremental_loading.md), and [`run_book.md`](./run_book.md).

---

## 1. System at a Glance

```mermaid
flowchart TD
    A[("MongoDB<br/>source")] --> B["Change Detection<br/>(row count + max updated_at)"]
    B -->|no change| C["Skip collection"]
    B -->|new or changed data| D["PySpark reads only the delta"]
    D --> E["Stage in Postgres<br/>(temporary table)"]
    E --> F["Upsert into target table"]
    F --> G[("PostgreSQL<br/>target")]
    G --> H["Data Quality Tests<br/>10 SQL files"]
    H --> I["SQL Analytics Library<br/>21 scripts"]
    I --> J["Reports & Charts"]
```

One collection can be skipped while another loads — each of the 9 collections goes through this decision independently, every run.

---

## 2. How the ETL Decides What to Load

This is the part that makes it "incremental" no checkpoint files, no watermark tables. PostgreSQL's own data is compared against MongoDB every time.

```mermaid
flowchart TD
    A[Peek at collection] --> B["Detect primary key column<br/>and updated_at column"]
    B --> C["MongoDB: count + max(updated_at)"]
    C --> D["Postgres: count + max(updated_at)"]
    D --> E{Counts match<br/>and timestamps match?}
    E -->|yes| F["Skip — nothing changed"]
    E -->|no| G["Pull only rows newer<br/>than Postgres' max timestamp"]
    G --> H["Add loaded_at, de-duplicate"]
    H --> I["Write to staging table"]
    I --> J{Has a primary key?}
    J -->|yes| K["Upsert:<br/>ON CONFLICT DO UPDATE"]
    J -->|no| L["Insert:<br/>ON CONFLICT DO NOTHING<br/>(row hash)"]
    K --> M["Drop staging table"]
    L --> M
```

`--full-refresh` skips straight from the top to step **G**, reading everything instead of just the delta.

---

## 3. Data Model

Nine tables, three layers: reference data (`brands`, `categories`), operational masters (`customers`, `stores`, `staffs`, `products`), and transactions (`orders`, `order_items`, `stocks`).

```mermaid
erDiagram
    CUSTOMERS ||--o{ ORDERS : places
    STAFFS ||--o{ ORDERS : handles
    STORES ||--o{ ORDERS : fulfills
    ORDERS ||--o{ ORDER_ITEMS : contains
    PRODUCTS ||--o{ ORDER_ITEMS : "ordered as"
    PRODUCTS }o--|| BRANDS : "belongs to"
    PRODUCTS }o--|| CATEGORIES : "belongs to"
    STORES ||--o{ STOCKS : holds
    PRODUCTS ||--o{ STOCKS : "stocked as"
    STORES ||--o{ STAFFS : employs
    STAFFS ||--o{ STAFFS : "reports to (self)"
```

`order_items` and `stocks` are the two junction tables with composite keys — everything else has a plain `<table>_id` primary key.

---

## 4. Pipeline Automation

`pipeline/run_pipeline.ps1` runs the ETL and the test suite back to back, so a single command gives you a load-and-verify cycle.

```mermaid
flowchart TD
    A[["run_pipeline.ps1"]] --> B["Stage 1<br/>mongo_to_postgres.py (ETL)"]
    B --> C{ETL succeeded?}
    C -->|no| D["Stop —<br/>skip tests"]
    C -->|yes| E["Stage 2<br/>plpgsql_tests.py<br/>(Data Quality Tests)"]
    E --> F["Print summary table<br/>+ write log file"]
    D --> F
```

`-ContinueOnError` overrides the stop-on-failure behavior if you want the tests to run against data that failed to load anyway.

---

## Known Limitations

A few things this architecture intentionally does **not** handle — see `incremental_loading.md` for the full explanation of each:

- **No delete propagation** — rows deleted in MongoDB stay in Postgres. The orphan checks in test file `06` are what catch this.
- **`order_items` composite key** — the ETL's auto-detection only finds single-column keys, so this table needs separate handling.
- **Same-timestamp edge case** — a row sharing the exact max `updated_at` with Postgres can be missed; a targeted `--full-refresh` fixes it.
- **Everything is stored as `TEXT`** — type and range validation happens entirely in the test suite, not the database schema.