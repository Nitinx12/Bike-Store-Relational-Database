# Bike Store Relational Database

A full-stack data engineering and analytics project that incrementally loads retail data from **MongoDB** into **PostgreSQL** using **PySpark**, validates it with a SQL-based quality test suite, and surfaces insights through a structured library of 21 analytical SQL scripts, automated health checks, and pre-generated business reports.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Folder Structure](#folder-structure)
- [Data Model](#data-model)
- [ETL Pipeline](#etl-pipeline)
  - [How Incremental Loading Works](#how-incremental-loading-works)
  - [Run Modes](#run-modes)
  - [Configuration](#configuration)
- [Data Quality Tests](#data-quality-tests)
- [SQL Analytics Library](#sql-analytics-library)
- [Health Check](#health-check)
- [Reports & Charts](#reports--charts)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)

---

## Project Overview

This project solves the problem of keeping a PostgreSQL analytical database in sync with a MongoDB operational database, without reloading everything on every run.

The pipeline uses a **watermark-based incremental strategy**: it compares the `updated_at` timestamp and row counts between both systems on every run, and only moves the rows that are actually new or changed. Once data is in PostgreSQL, a suite of SQL data quality checks validates structural integrity and business logic, and a library of analytical queries transforms the raw tables into actionable business insights.

**Key capabilities:**

- Automated, stateless incremental ETL — no checkpoint files or watermark tables needed
- Schema evolution — new MongoDB fields are automatically added as PostgreSQL columns
- Upsert logic — updates to existing records are correctly reflected without duplication
- 10-file SQL data quality suite covering nulls, uniqueness, type validity, referential integrity, and business rules
- 21 SQL analytical scripts across exploration, analysis, reporting, and advanced segments
- Automated health checks with timestamped last-run records
- Pre-generated brand and store performance reports with supporting charts

---

## Architecture

```
MongoDB (source)
      │
      │  PyMongo (count + MAX timestamp comparison)
      ▼
 Change Detection ──── No change? ──► SKIP collection
      │
      │  Yes: delta only (updated_at > pg_max_ts)
      ▼
 PySpark Read (filtered MongoDB query)
      │
      ▼
 Slugify columns → Deduplicate → Add loaded_at
      │
      ▼
 JDBC Write → Staging Table ({table}_staging_{run_id})
      │
      ▼
 Upsert: INSERT INTO target SELECT FROM staging
   ├── Has PK  →  ON CONFLICT (pk) DO UPDATE
   └── No PK   →  ON CONFLICT (_row_hash) DO NOTHING
      │
      ▼
 DROP staging table
      │
      ▼
PostgreSQL (target)
      │
      ▼
 SQL Data Quality Tests (10 files, zero-row = pass)
      │
      ▼
 SQL Analytics Library (21 scripts)
      │
      ▼
 Reports / Charts / Health Check
```

---

## Folder Structure

```
project-root/
├── charts/                       — Generated charts using seaborn and matplotlib
│   ├── avg_order_value.png
│   ├── chart_cancellation_rate.png
│   ├── chart_on_time_rate.png
│   ├── chart_order_breakdown.png
│   ├── chart_repeat_customer_rate.png
│   ├── chart_revenue_per_staff.png
│   ├── chart_stock_to_sales.png
│   ├── chart_total_revenue.png
│   ├── revenue_by_brand.png
│   ├── revenue_per_product.png
│   ├── revenue_share_donut.png
│   ├── top5_relative_performance.png
│   └── units_vs_customers.png
│
├── docs/                         — Project documentation
│   ├── data_catlog.md            — Full schema reference for all 9 tables
│   ├── data_quality_checks.md    — Explanation of every SQL test and its purpose
│   ├── incremental_loading.md    — Deep-dive into the ETL algorithm
│   └── run_book.md               — Operational run book: how to run, configure, and troubleshoot
│
├── driver/                       — Database driver dependencies
│   ├── postgresql.jar            — PostgreSQL JDBC driver (required by PySpark)
│   └── README.md
│
├── notebooks/
│   └── public.ipynb              — Exploratory analysis notebook
│
├── reports/                      — Markdown business reports
│   ├── brand_performance.md
│   └── store_performance.md
│
├── scripts/                      — Executable ETL pipeline scripts
│   ├── mongo_to_postgres.py      — Main PySpark incremental ETL script
│   └── README.md
│
├── sql/                          — SQL analytics library (21 scripts)
│   ├── 01_database_exploration.sql
│   ├── 02_dimensions_exploration.sql
│   ├── 03_date_range_exploration.sql
│   ├── 04_measures_exploration.sql
│   ├── 05_magnitude_analysis.sql
│   ├── 06_ranking_analysis.sql
│   ├── 07_change_over_time_analysis.sql
│   ├── 08_cumulative_analysis.sql
│   ├── 09_performance_analysis.sql
│   ├── 10_data_segmentation.sql
│   ├── 11_part_to_whole_analysis.sql
│   ├── 12_customer_report.sql
│   ├── 13_product_report.sql
│   ├── 14_brand_report.sql
│   ├── 15_fn_store_performance.sql
│   ├── 16_sales_report.sql
│   ├── 17_new_vs_return.sql
│   ├── 18_status_check.sql
│   ├── 19_cohort_analysis.sql
│   ├── 20_fn_inventory_summary.sql
│   ├── 21_fn_staff_performance.sql
│   └── README.md
│
├── tests/                        — SQL data quality checks (10 files)
│   ├── 01_test_brands.sql
│   ├── 02_test_categories.sql
│   ├── 03_test_customers.sql
│   ├── 04_test_order_items.sql
│   ├── 05_test_orders.sql
│   ├── 06_test_orphan_and_business_rules.sql
│   ├── 07_test_products.sql
│   ├── 08_test_staffs.sql
│   ├── 09_test_stocks.sql
│   ├── 10_test_stores.sql
│   └── README.md
│
├── utils/                        — Shared infrastructure modules
│   ├── connection.py             — Loads and validates credentials from .env
│   ├── engine.py                 — Builds SQLAlchemy (Postgres) and PyMongo clients
│   ├── logger.py                 — Stage-aware logger with console + file output
│	└── README.md
│
├── .env						  —	Not commited					  
├── .health_last_run
├── .python-version
├── health_check.py
├── main.py
├── pyproject.toml
├── README.md
└── uv.lock
```

---

## Data Model

The schema represents a multi-store retail business loaded into the `public` schema in PostgreSQL. It has 9 tables organised into three layers.

### Reference Tables (lookup data)

| Table | Description | Key Relationships |
|-------|-------------|-------------------|
| `brands` | Product brand master | Referenced by `products` |
| `categories` | Product category master | Referenced by `products` |

### Operational Master Tables

| Table | Description | Key Relationships |
|-------|-------------|-------------------|
| `customers` | Customer master data | Referenced by `orders` |
| `stores` | Store locations and contact info | Referenced by `orders`, `staffs`, `stocks` |
| `staffs` | Employee records with self-referencing manager hierarchy | Referenced by `orders`; references `stores` and itself |
| `products` | Product catalogue with pricing | Referenced by `order_items`, `stocks` |

### Transactional / Junction Tables

| Table | Description | Key Relationships |
|-------|-------------|-------------------|
| `orders` | Order header — the central table | References `customers`, `stores`, `staffs` |
| `order_items` | Line items per order (composite PK: `order_id`, `item_id`) | References `orders`, `products`; has a generated `total_value` column |
| `stocks` | Inventory per store/product (composite PK: `store_id`, `product_id`) | References `stores`, `products` |

**Entity relationships at a glance:**

```
customers ──< orders >── staffs
                │
                │
           order_items >── products >── brands
                                   └── categories
stores ──< orders
stores ──< stocks >── products
stores ──< staffs ──< staffs (manager hierarchy)
```

> All tables include an `updated_at` timestamp column used as the incremental watermark by the ETL. Every table except `order_items` has a single-column primary key following the pattern `<table_singular>_id`, which the ETL auto-detects. `order_items` is a special case — see [Known Limitations](#known-limitations).

---

## ETL Pipeline

The ETL script is located at `scripts/mongo_to_postgres.py`. It is a **PySpark-based pipeline** that moves data from MongoDB into PostgreSQL incrementally.

### How Incremental Loading Works

The script uses **PostgreSQL itself as the watermark store** — no external checkpoint files or state tables are required. On each run, for every MongoDB collection:

1. **Peek** — fetch 10 sample documents to discover field names, auto-detect the primary key column and the `updated_at` timestamp column.
2. **MongoDB stats** — query MongoDB (via PyMongo) for document count and `MAX(updated_at)`.
3. **PostgreSQL stats** — query PostgreSQL (via SQLAlchemy) for row count and `MAX(updated_at)`.
4. **Change detection** — compare both systems:
   - If counts match **and** max timestamps match → **skip** the collection entirely.
   - If either differs → proceed with an incremental load.
5. **Filtered read** — read from MongoDB only the documents where `updated_at > pg_max_ts`. This filter runs at the source, minimising data transfer.
6. **Transform** — slugify column names, drop `_id`, preserve nulls, add `loaded_at` audit column, deduplicate by primary key.
7. **Stage** — write the delta to a temporary staging table (`{table}_staging_{run_id}`) via JDBC.
8. **Upsert** — merge staging into the permanent target table:
   - With a primary key: `ON CONFLICT (pk) DO UPDATE` — true upsert, updates existing rows.
   - Without a primary key: `ON CONFLICT (_row_hash) DO NOTHING` — hash-based deduplication.
9. **Cleanup** — drop the staging table regardless of success or failure.

### Run Modes

```bash
# Normal scheduled run — incremental, all collections
python -m scripts.mongo_to_postgres

# Incremental load for specific collections only
python -m scripts.mongo_to_postgres --collection staffs --collection orders

# Full refresh — truncate and reload all collections from scratch
python -m scripts.mongo_to_postgres --full-refresh

# Full refresh for a specific collection only
python -m scripts.mongo_to_postgres --collection staffs --full-refresh
```

> Use `--full-refresh` on first run, after a schema change, or to recover a table that has drifted out of sync.

### Configuration

The script is controlled entirely through environment variables. No config files are required.

| Variable | Default | Description |
|----------|---------|-------------|
| `ETL_SCHEMA` | `public` | Target PostgreSQL schema |
| `ETL_TS_COL` | `updated_at` | Timestamp column used as the incremental watermark |
| `ETL_PK_SUFFIX` | `_id` | Suffix used for heuristic primary key detection |
| `JDBC_JAR_PATH` | `driver/postgresql.jar` | Path to the PostgreSQL JDBC driver JAR |

Database credentials are loaded from `.env` via `utils/connection.py` (see [Environment Variables](#environment-variables)).

---

## Data Quality Tests

The `tests/` folder contains **10 SQL files** that validate the data after every ETL run. The convention is simple: **a healthy dataset returns zero rows from every query**. Any row returned is a failing record, and it contains the exact data needed to investigate the problem.

### Test Files

| File | Scope |
|------|-------|
| `01_test_brands.sql` | Null/empty checks, PK uniqueness |
| `02_test_categories.sql` | Null/empty checks, PK uniqueness |
| `03_test_customers.sql` | Null/empty checks, PK uniqueness, zip code format |
| `04_test_order_items.sql` | Composite PK uniqueness, generated column consistency |
| `05_test_orders.sql` | Null checks, FK integrity, date logic |
| `06_test_orphan_and_business_rules.sql` | Cross-table orphan checks + business rule validation |
| `07_test_products.sql` | PK uniqueness, price/model year range checks |
| `08_test_staffs.sql` | Null checks, FK integrity, active flag validity |
| `09_test_stocks.sql` | Composite PK uniqueness, quantity range |
| `10_test_stores.sql` | Null/empty checks, PK uniqueness |

### Categories of Checks

- **Not null / not empty** — required fields must contain real data
- **Primary key uniqueness** — no duplicate or null PKs allowed
- **Type and format validity** — values must be castable to their intended types (numeric, date, postal code pattern)
- **Range and bounds** — prices must be non-negative; model years must be realistic
- **Referential integrity** — every foreign key must point to an existing parent row
- **Generated column consistency** — `order_items.total_value` is recomputed and compared against `quantity × list_price × (1 − discount)`
- **Orphan row checks** — detects child records whose parent was deleted from MongoDB (the ETL never propagates deletes)
- **Business logic rules** — orders must have at least one item, staff must belong to the store fulfilling their order, order totals must be greater than zero

### Running the Tests

```bash
# Run a single test file
psql -h host -U user -d database -f tests/05_test_orders.sql

# Run the cross-table checks (most important after every ETL run)
psql -h host -U user -d database -f tests/06_test_orphan_and_business_rules.sql
```

A clean run produces **no output rows** from any file. Log any returned rows with their source file and `check_name` for investigation.

---

## SQL Analytics Library

The `sql/` folder contains **21 read-only analytical scripts** organised in a logical progression from raw data exploration through to reusable functions.

### Exploration (01–04)
Profile the database before analysing it.

| Script | Purpose |
|--------|---------|
| `01_database_exploration.sql` | Tables, schemas, row counts, overall structure |
| `02_dimensions_exploration.sql` | Profile categorical columns (brand, category, region) |
| `03_date_range_exploration.sql` | Min/max dates, time coverage, gaps |
| `04_measures_exploration.sql` | Numeric column ranges, nulls, averages, outliers |

### Core Analysis (05–11)
Reusable analytical patterns.

| Script | Purpose |
|--------|---------|
| `05_magnitude_analysis.sql` | Scale and size of key metrics |
| `06_ranking_analysis.sql` | Rank products, customers, stores by performance |
| `07_change_over_time_analysis.sql` | Month-over-month and year-over-year trends |
| `08_cumulative_analysis.sql` | Running totals and cumulative growth |
| `09_performance_analysis.sql` | Actual vs. target or benchmark comparison |
| `10_data_segmentation.sql` | Tier, bucket, and band groupings |
| `11_part_to_whole_analysis.sql` | Percentage contribution per segment |

### Business Reports (12–16)
Stakeholder-ready outputs.

| Script | Purpose |
|--------|---------|
| `12_customer_report.sql` | Customer spend, frequency, recency |
| `13_product_report.sql` | Product performance and revenue contribution |
| `14_brand_report.sql` | Brand-level sales and market share |
| `15_fn_store_performance.sql` | Store-level KPIs |
| `16_sales_report.sql` | High-level sales dashboard across all dimensions |

### Advanced Analytics (17–19)

| Script | Purpose |
|--------|---------|
| `17_new_vs_return.sql` | Revenue and behaviour: new vs. returning customers |
| `18_status_check.sql` | Pipeline and data health checks |
| `19_cohort_analysis.sql` | Customer retention by acquisition cohort |

### Reusable Functions (20–21)

| Script | Purpose |
|--------|---------|
| `20_fn_inventory_summary.sql` | Inventory levels and stock health metrics |
| `21_fn_staff_performance.sql` | Staff-level performance KPIs |

> **Recommended execution order:** start with scripts 01–04 to understand the data, then 05–11 for core patterns, then 12–16 for stakeholder reports.

---

## Health Check

`health_check.py` runs automatically to verify pipeline health. It records the timestamp of the last successful check in `.health_last_run`. Run it after each ETL cycle to confirm the system is operating as expected.

```bash
python health_check.py
```

---

## Reports & Charts

### Reports (`reports/`)

Two pre-generated Markdown reports are included:

- `brand_performance.md` — aggregated brand-level revenue, units sold, and market share metrics
- `store_performance.md` — store-level KPIs including revenue, order counts, and staff metrics

### Charts (`charts/`)

13 pre-generated PNG visualisations covering:

| Chart | Metric |
|-------|--------|
| `chart_total_revenue.png` | Total revenue over time |
| `avg_order_value.png` | Average order value trend |
| `chart_order_breakdown.png` | Order volume by status |
| `chart_cancellation_rate.png` | Order cancellation rate |
| `chart_on_time_rate.png` | On-time fulfilment rate |
| `chart_repeat_customer_rate.png` | Returning customer rate |
| `chart_revenue_per_staff.png` | Revenue attributed per staff member |
| `chart_stock_to_sales.png` | Stock-to-sales ratio |
| `revenue_by_brand.png` | Revenue breakdown by brand |
| `revenue_per_product.png` | Per-product revenue |
| `revenue_share_donut.png` | Revenue share composition |
| `top5_relative_performance.png` | Top 5 entity relative performance |
| `units_vs_customers.png` | Units sold vs. unique customers |

---

## Setup & Installation

### Prerequisites

- Python 3.9+
- Java 8+ (required by PySpark)
- PostgreSQL database (target)
- MongoDB database (source)
- PostgreSQL JDBC driver JAR

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd <project-root>
pip install -e .
```

Or install required packages directly:

```bash
pip install pandas pymongo pyspark sqlalchemy psycopg2-binary python-dotenv
```

### 2. Add the JDBC driver

Download the PostgreSQL JDBC driver from https://jdbc.postgresql.org/download/ and place it at:

```
driver/postgresql.jar
```

Or point to an existing JAR via environment variable:

```bash
export JDBC_JAR_PATH=/path/to/postgresql-42.x.x.jar
```

### 3. Configure credentials

Create a `.env` file at the project root:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=your_database
POSTGRES_USERNAME=your_user
POSTGRES_PASSWORD=your_password

MONGO_URI=mongodb://localhost:27017
MONGO_DB=your_mongo_database
```

> Never commit `.env` to version control. Add it to `.gitignore`.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_HOST` | Yes | — | PostgreSQL host |
| `POSTGRES_PORT` | Yes | — | PostgreSQL port |
| `POSTGRES_DATABASE` | Yes | — | PostgreSQL database name |
| `POSTGRES_USERNAME` | Yes | — | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | — | PostgreSQL password |
| `MONGO_URI` | Yes | — | MongoDB connection URI |
| `MONGO_DB` | Yes | — | MongoDB database name |
| `ETL_SCHEMA` | No | `public` | Target PostgreSQL schema |
| `ETL_TS_COL` | No | `updated_at` | Watermark timestamp column name |
| `ETL_PK_SUFFIX` | No | `_id` | Suffix for PK auto-detection |
| `JDBC_JAR_PATH` | No | `driver/postgresql.jar` | Path to JDBC driver JAR |

---

## Running the Project

### First-time full load

```bash
python -m scripts.mongo_to_postgres --full-refresh
```

### Scheduled incremental run

```bash
python -m scripts.mongo_to_postgres
```

### Run quality tests after every load

```bash
# Run all 10 test files in order
for f in tests/*.sql; do
  echo "Running $f..."
  psql -h $POSTGRES_HOST -U $POSTGRES_USERNAME -d $POSTGRES_DATABASE -f "$f"
done
```

### Health check

```bash
python health_check.py
```

### Run analytical reports

```bash
psql -h $POSTGRES_HOST -U $POSTGRES_USERNAME -d $POSTGRES_DATABASE -f sql/16_sales_report.sql
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `FileNotFoundError` for `postgresql.jar` | JDBC driver is missing | Place JAR at `driver/postgresql.jar` or set `JDBC_JAR_PATH` |
| `RuntimeError` about project root | Script run from outside the project tree | Run with `python -m scripts.mongo_to_postgres` from the project root |
| Postgres connection fails at startup | Wrong credentials or unreachable host | Check all `POSTGRES_*` variables in `.env` |
| Collection always skipped despite data changes | `updated_at` not being updated in MongoDB, or same-timestamp edge case | Run a targeted full refresh: `python -m scripts.mongo_to_postgres --collection <name> --full-refresh` |
| Test file returns rows after a clean load | Load order issue (parent loaded after child) or stale orphan from a MongoDB delete | Re-run the relevant parent collection, then the child; orphans from deletes require a full refresh |
| `order_items` behaves unexpectedly | Composite PK not supported by auto-detection — `order_id` alone is detected as PK | Exclude from automated runs and load with a dedicated handling path (see Known Limitations) |

---

## Known Limitations

**No delete propagation.** The ETL only detects inserts and updates via the `updated_at` watermark. If a document is deleted from MongoDB, the corresponding row remains in PostgreSQL indefinitely. The orphan checks in `tests/06_test_orphan_and_business_rules.sql` are the only mechanism that surfaces this.

**`order_items` composite PK.** The ETL auto-detects a single-column primary key. For `order_items`, it will detect `order_id` alone rather than the correct composite key `(order_id, item_id)`. Additionally, `order_items` has a generated stored column (`total_value`) that cannot be inserted directly. Until a dedicated handling path is built, it is recommended to exclude `order_items` from automated runs and manage it separately.

**Same-timestamp edge case.** If a new or updated MongoDB document shares the exact same `updated_at` timestamp as the current PostgreSQL maximum, it will be missed by the incremental filter (`updated_at > pg_max_ts` is strict). Running a targeted full refresh for affected collections resolves this.

**All columns stored as TEXT.** The ETL writes every column as `TEXT` in PostgreSQL regardless of its logical type. All type validation, casting, and range checking must be done explicitly — which is why the data quality test suite casts values before evaluating them.

**Schema evolution adds columns but does not remove them.** If a field is removed from MongoDB documents, its column remains in PostgreSQL and will simply receive `NULL` values on future loads.