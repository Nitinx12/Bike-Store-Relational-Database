# SQL Analytics Library

A structured collection of 21 SQL scripts organized to cover the full analytics workflow from raw data exploration through segmentation, reporting, and reusable database functions.

---

## Folder Structure Overview

```
sql/
├── Exploration       (01–04)   — Understand the data before analyzing it
├── Analysis          (05–11)   — Core analytical patterns and techniques
├── Reports           (12–16)   — Ready-to-use business reporting queries
├── Advanced          (17–19)   — Cohort, status, and return-customer logic
└── Functions         (20–21)   — Reusable stored functions / views
```

---

## Data Exploration

Scripts to profile the database structure, available dimensions, date ranges, and key measures before any analysis begins.

| File | Purpose |
|------|---------|
| `01_database_exploration.sql` | Inspect tables, schemas, row counts, and overall database structure |
| `02_dimensions_exploration.sql` | List and profile categorical columns (e.g. region, category, brand) |
| `03_date_range_exploration.sql` | Identify min/max dates, gaps, and time coverage in the dataset |
| `04_measures_exploration.sql` | Summarize numeric columns — nulls, ranges, averages, and outliers |

---

## Core Analysis

Reusable analytical patterns that can be applied across different metrics and business questions.

| File | Purpose |
|------|---------|
| `05_magnitude_analysis.sql` | Measure the size and scale of key metrics (e.g. total sales, volume) |
| `06_ranking_analysis.sql` | Rank entities (products, customers, stores) by performance |
| `07_change_over_time_analysis.sql` | Track how metrics evolve across time periods (MoM, YoY) |
| `08_cumulative_analysis.sql` | Running totals and cumulative growth over time |
| `09_performance_analysis.sql` | Compare actual performance against targets or benchmarks |
| `10_data_segmentation.sql` | Divide data into meaningful groups (e.g. tiers, buckets, bands) |
| `11_part_to_whole_analysis.sql` | Calculate percentage contribution of each segment to the total |

---

## Business Reports

Purpose-built reporting queries for common business stakeholder needs.

| File | Purpose |
|------|---------|
| `12_customer_report.sql` | Customer-level summary: spend, frequency, recency |
| `13_product_report.sql` | Product performance: sales, returns, revenue contribution |
| `14_brand_report.sql` | Brand-level aggregation of sales and market share |
| `15_fn_store_performance.sql` | Store-level KPIs (may be a view or function wrapper) |
| `16_sales_report.sql` | High-level sales dashboard query across all dimensions |

---

## Advanced Analytics

Deeper analytical scripts for behaviour patterns, operational health, and customer lifecycle.

| File | Purpose |
|------|---------|
| `17_new_vs_return.sql` | Compare behaviour and revenue between new and returning customers |
| `18_status_check.sql` | Data quality and pipeline health checks |
| `19_cohort_analysis.sql` | Group customers by acquisition period to track retention over time |

---

## Reusable Functions

Parameterized SQL functions or views designed to be called by other scripts or BI tools.

| File | Purpose |
|------|---------|
| `20_fn_inventory_summary.sql` | Returns inventory levels and stock health metrics |
| `21_fn_staff_performance.sql` | Returns staff-level performance KPIs for HR or operations |

---

## How to Use

1. Start with Exploration (01–04) to understand the dataset structure.
2. Run Core Analysis (05–11) to build insights using standard patterns.
3. Generate Reports (12–16) for stakeholder-ready outputs.
4. Use Advanced scripts (17–19) for customer lifecycle and operational checks.
5. Call Functions (20–21) from dashboards or other queries as needed.

---

## Notes

- Scripts are numbered to reflect a logical execution order.
- Files prefixed with `fn_` are designed as reusable functions or views.
- All scripts are written for analytical use and are read-only (no data modification).