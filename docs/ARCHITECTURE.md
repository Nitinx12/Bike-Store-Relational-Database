# Architecture

This project moves retail data from **MongoDB** to **PostgreSQL** on a schedule, checks it for quality, then turns it into reports. This page is the simple, visual entry point. For column-level detail, see [`data_catlog.md`](./data_catlog.md), [`incremental_loading.md`](./incremental_loading.md), and [`run_book.md`](./run_book.md).

---

## 1. System at a Glance

```mermaid
flowchart TD
    classDef source fill:#0f9d58,stroke:#0b8043,color:#ffffff,stroke-width:2px
    classDef etl fill:#f4b400,stroke:#d09200,color:#000000,stroke-width:2px
    classDef target fill:#4285f4,stroke:#1a73e8,color:#ffffff,stroke-width:2px
    classDef qa fill:#9c27b0,stroke:#6a1b9a,color:#ffffff,stroke-width:2px
    classDef output fill:#db4437,stroke:#a52714,color:#ffffff,stroke-width:2px
    classDef decision fill:#ffffff,stroke:#202124,color:#202124,stroke-width:2px

    A[("MongoDB<br/>source collections")]:::source
    B["Change Detection<br/>(row count + max updated_at)"]:::etl
    C{{"Skip collection<br/>no change"}}:::decision
    D["PySpark reads only the delta"]:::etl
    E["Stage in Postgres<br/>(temporary table)"]:::etl
    F["Upsert into target table"]:::etl
    G[("PostgreSQL<br/>public schema")]:::target
    H["Data Quality Tests<br/>10 PL/pgSQL files"]:::qa
    I["Great Expectations<br/>9 table suites"]:::qa
    J["SQL Analytics Library<br/>21 scripts"]:::output
    K["Reports & Charts"]:::output

    A --> B
    B -->|"no change"| C
    B -->|"new or changed"| D
    D --> E
    E --> F
    F --> G
    G --> H
    G --> I
    G --> J
    J --> K
```

One collection can be skipped while another loads — each of the 9 collections goes through this decision independently, every run.

---

## 2. Container Topology

```mermaid
flowchart LR
    classDef db fill:#3367d6,stroke:#1a53b3,color:#ffffff,stroke-width:2px
    classDef app fill:#ff6f00,stroke:#c43e00,color:#ffffff,stroke-width:2px
    classDef monitor fill:#0f9d58,stroke:#0b8043,color:#ffffff,stroke-width:2px
    classDef viz fill:#f4b400,stroke:#d09200,color:#000000,stroke-width:2px

    APP["app<br/>(batch job, on-demand)"]:::app
    PG[("PostgreSQL<br/>postgres:16")]:::db
    MGO[("MongoDB<br/>mongo:7")]:::db
    PGW["Pushgateway<br/>prom/pushgateway"]:::monitor
    PROM["Prometheus<br/>prom/prometheus"]:::monitor
    GRAF["Grafana<br/>grafana/grafana"]:::viz

    APP -->|"JDBC writes<br/>target table"| PG
    APP -->|"pymongo reads<br/>source collections"| MGO
    APP -->|"HTTP push<br/>after every run"| PGW
    PGW -->|"scraped every 15s<br/>honor_labels: true"| PROM
    PROM -->|"PromQL queries"| GRAF
```

All services share one `monitoring` Docker network and reach each other by hostname.

---

## 3. How the ETL Decides What to Load

This is the part that makes it "incremental" — no checkpoint files, no watermark tables. PostgreSQL's own data is compared against MongoDB every time.

```mermaid
flowchart TD
    classDef detect fill:#e3f2fd,stroke:#1976d2,color:#0d47a1
    classDef compare fill:#fff8e1,stroke:#f4b400,color:#5d4037
    classDef read fill:#e8f5e9,stroke:#0f9d58,color:#1b5e20
    classDef write fill:#fce4ec,stroke:#c2185b,color:#880e4f
    classDef decision fill:#ffffff,stroke:#202124,color:#202124

    A["Peek at collection<br/>sample 10 docs"]:::detect
    B["Detect primary key column<br/>and updated_at column"]:::detect
    C["MongoDB:<br/>count + max(updated_at)"]:::compare
    D["Postgres:<br/>count + max(updated_at)"]:::compare
    E{{"Counts match<br/>and timestamps match?"}}:::decision
    F["Skip — nothing changed"]:::compare
    G["Pull only rows newer<br/>than Postgres' max timestamp"]:::read
    H["Add loaded_at, de-duplicate"]:::write
    I["Write to staging table<br/>{table}_staging_{run_id}"]:::write
    J{{"Has a primary key?"}}:::decision
    K["Upsert:<br/>ON CONFLICT DO UPDATE"]:::write
    L["Insert:<br/>ON CONFLICT DO NOTHING<br/>(row hash)"]:::write
    M["Drop staging table"]:::write

    A --> B
    B --> C
    C --> D
    D --> E
    E -->|yes| F
    E -->|no| G
    G --> H
    H --> I
    I --> J
    J -->|yes| K
    J -->|no| L
    K --> M
    L --> M
```

`--full-refresh` skips straight from the top to step **G**, reading everything instead of just the delta.

---

## 4. Data Model

Nine tables, three layers: reference data (`brands`, `categories`), operational masters (`customers`, `stores`, `staffs`, `products`), and transactions (`orders`, `order_items`, `stocks`).

```mermaid
erDiagram
    classDef ref fill:#fff3e0,stroke:#e65100,color:#3e2723
    classDef master fill:#e8f5e9,stroke:#1b5e20,color:#1b5e20
    classDef txn fill:#e3f2fd,stroke:#0d47a1,color:#0d47a1
    classDef junction fill:#fce4ec,stroke:#880e4f,color:#880e4f

    BRANDS ||--o{ PRODUCTS : "owns":::master
    CATEGORIES ||--o{ PRODUCTS : "owns":::master
    CUSTOMERS ||--o{ ORDERS : "places":::master
    STAFFS ||--o{ ORDERS : "handles":::master
    STORES ||--o{ ORDERS : "fulfills":::master
    STORES ||--o{ STAFFS : "employs":::master
    STORES ||--o{ STOCKS : "holds":::master
    PRODUCTS ||--o{ STOCKS : "stocked at":::master
    PRODUCTS ||--o{ ORDER_ITEMS : "appears in":::master
    ORDERS ||--o{ ORDER_ITEMS : "contains":::master
    STAFFS ||--o{ STAFFS : "manages":::master

    BRANDS {
        bigint brand_id PK
        text   brand_name
        timestamp updated_at
    }
    CATEGORIES {
        bigint category_id PK
        text   category_name
        timestamp updated_at
    }
    CUSTOMERS {
        bigint customer_id PK
        text   first_name
        text   last_name
        text   email
        timestamp updated_at
    }
    STORES {
        bigint store_id PK
        text   store_name
        text   city
        timestamp updated_at
    }
    STAFFS {
        bigint staff_id PK
        bigint store_id FK
        bigint manager_id FK
        text   active
        timestamp updated_at
    }
    PRODUCTS {
        bigint product_id PK
        bigint brand_id FK
        bigint category_id FK
        numeric list_price
        timestamp updated_at
    }
    ORDERS {
        bigint order_id PK
        bigint customer_id FK
        bigint store_id FK
        bigint staff_id FK
        date   order_date
        text   order_status
        timestamp updated_at
    }
    ORDER_ITEMS {
        bigint order_id PK,FK
        bigint item_id PK
        bigint product_id FK
        bigint quantity
        numeric list_price
        numeric discount
        numeric total_value
        timestamp updated_at
    }
    STOCKS {
        bigint store_id PK,FK
        bigint product_id PK,FK
        bigint quantity
        timestamp updated_at
    }
```

`order_items` and `stocks` are the two junction tables with composite keys — everything else has a plain `<table>_id` primary key.

---

## 5. Pipeline Automation

Two equivalent entry points run the full load-and-verify cycle:

- **`make pipeline`** → `docker compose --profile jobs run --rm app pipeline` (one image, all stages)
- **`ps1/local_runner.ps1`** → native PowerShell, three stages, optional `-ContinueOnError`

```mermaid
flowchart TD
    classDef entry fill:#e8f5e9,stroke:#1b5e20,color:#1b5e20
    classDef stage fill:#e3f2fd,stroke:#0d47a1,color:#0d47a1
    classDef decision fill:#ffffff,stroke:#202124,color:#202124

    A[["make pipeline<br/>or<br/>ps1/local_runner.ps1"]]:::entry
    B["Stage 1<br/>mongo_to_postgres.py<br/>(ETL)"]:::stage
    C{{"ETL succeeded?"}}:::decision
    D["Stop — skip tests<br/>unless -ContinueOnError"]:::decision
    E["Stage 2<br/>plpgsql_loops_tests.py<br/>(10 PL/pgSQL files)"]:::stage
    F["Stage 3<br/>run_gx.py<br/>(9 Great Expectations suites)"]:::stage
    G["Push metrics → Pushgateway"]:::stage
    H["Print summary table<br/>+ write log files"]:::stage

    A --> B
    B --> C
    C -->|no| D
    C -->|yes| E
    D -.->|skipped| E
    E --> F
    F --> G
    G --> H
```

---

## 6. Quality-Gate Decision Tree

The data-quality layer enforces a strict invariant: **every CI run must end with all three suites green**, or it blocks deployment.

```mermaid
flowchart TD
    classDef ok fill:#e8f5e9,stroke:#1b5e20,color:#1b5e20
    classDef fail fill:#ffebee,stroke:#c62828,color:#b71c1c
    classDef gate fill:#fff8e1,stroke:#f4b400,color:#5d4037

    ETL["ETL run"]:::gate
    ETL_OK{"Rows loaded<br/>no failures?"}:::gate
    PLPG["PL/pgSQL suite"]:::gate
    PLPG_OK{"All 10 files<br/>PASS?"}:::gate
    GX["GX suite"]:::gate
    GX_OK{"All 9 tables<br/>PASS?"}:::gate
    PASS[["PIPELINE PASSED<br/>exit 0"]]:::ok
    BLOCK[["PIPELINE FAILED<br/>exit 1"]]:::fail

    ETL --> ETL_OK
    ETL_OK -->|yes| PLPG
    ETL_OK -->|no| BLOCK
    PLPG --> PLPG_OK
    PLPG_OK -->|yes| GX
    PLPG_OK -->|no| BLOCK
    GX --> GX_OK
    GX_OK -->|yes| PASS
    GX_OK -->|no| BLOCK
```

---

## Known Limitations

A few things this architecture intentionally does **not** handle — see `incremental_loading.md` for the full explanation of each:

- **No delete propagation** — rows deleted in MongoDB stay in Postgres. The orphan checks in test file `06` are what catch this.
- **`order_items` composite key** — the ETL's auto-detection only finds single-column keys, so this table needs separate handling.
- **Same-timestamp edge case** — a row sharing the exact max `updated_at` with Postgres can be missed; a targeted `--full-refresh` fixes it.
- **Everything is stored as `TEXT`** — type and range validation happens entirely in the test suite, not the database schema.