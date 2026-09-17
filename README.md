<div align="center">

<!-- ── Banner / Logo ── -->
<img src="assets/pyspark-logo.png" width="84" alt="Bike Store Logo" />

# Bike Store Relational Database

**Incremental ETL • SQL Analytics • Live Dashboard**

Incremental data pipeline moving retail data from **MongoDB** to **PostgreSQL**, validated by a SQL data quality suite and surfaced through business reports and a live dashboard.

<!-- ── Badges (shields.io + skillicons + streamlit) — keep on one visual row ── -->
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue?logo=python&logoColor=white)](pyproject.toml)
[![Ubuntu](https://img.shields.io/badge/ubuntu-22.04-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com)
[![PySpark 4.1](https://img.shields.io/badge/PySpark-4.1.2-orange?logo=apachespark&logoColor=white)](https://spark.apache.org)
[![Postgres](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![MongoDB](https://img.shields.io/badge/MongoDB-7-47A248?logo=mongodb&logoColor=white)](https://www.mongodb.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.64-FF4B4B?logo=streamlit&logoColor=white)](streamlit_app.py)
[![Plotly](https://img.shields.io/badge/Plotly-7.1-3F4F75?logo=plotly&logoColor=white)](https://plotly.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Last Release](https://img.shields.io/github/v/release/Nitinx12/Bike-Store-Relational-Database?label=last%20release)](https://github.com/Nitinx12/Bike-Store-Relational-Database/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/Nitinx12/Bike-Store-Relational-Database/ci.yml?branch=main&label=CI)](https://github.com/Nitinx12/Bike-Store-Relational-Database/actions)
[![Ruff](https://img.shields.io/badge/code%20style-Ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=precommit)](.pre-commit-config.yaml)

[![Discord](https://img.shields.io/badge/chat-Discord-5865F2?logo=discord&logoColor=white)](https://discord.com)
[![LinkedIn](https://img.shields.io/badge/follow-LinkedIn-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/nitinx12)
[![Twitter](https://img.shields.io/badge/follow-Twitter-1DA1F2?logo=twitter&logoColor=white)](https://twitter.com)
[![Awesome Python](https://img.shields.io/badge/Awesome-Python-3776AB?logo=python&logoColor=white)](https://github.com/vinta/awesome-python)

[![Live Demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://bike-store-relational-database-grvahmynq59w6zgckat2hx.streamlit.app/)

![Tech Stack](https://skillicons.dev/icons?i=mongodb,postgres,py,docker,git,github,powershell,bash,grafana,prometheus)

</div>

---

## ✨ Live Demo

> **Public dashboard — no localhost needed.**
> On Streamlit Cloud without `postgres` secrets it auto-uses `dashboard/sample/*.csv` demo data. With secrets it hits your live Postgres.

<p align="center">
  <a href="https://bike-store-relational-database-grvahmynq59w6zgckat2hx.streamlit.app/">
    <img src="assets/revenue_by_brand.png" width="720" alt="Dashboard preview — revenue by brand" />
  </a>
</p>

---

## Architecture

```mermaid
flowchart LR
    classDef source fill:#0f9d58,stroke:#0b8043,color:#ffffff
    classDef etl fill:#f4b400,stroke:#d09200,color:#000000
    classDef target fill:#4285f4,stroke:#1a73e8,color:#ffffff
    classDef qa fill:#9c27b0,stroke:#6a1b9a,color:#ffffff
    classDef output fill:#db4437,stroke:#a52714,color:#ffffff
    classDef dash fill:#0F766E,stroke:#0b5c53,color:#ffffff

    A[("MongoDB<br/>source")]:::source --> B["Incremental ETL<br/>(PySpark)"]:::etl
    B --> C[("PostgreSQL")]:::target
    C --> D["Data Quality Tests<br/>(PL/pgSQL + GX)"]:::qa
    D --> E["Analytics & Reports"]:::output
    C --> F["Streamlit + Plotly<br/>Dashboard"]:::dash
```

Stateless incremental load — PostgreSQL is compared against MongoDB by row count + `updated_at` on every run. No watermark tables, no checkpoint files.

---

## Features

| Area | Highlights |
|---|---|
| **ETL** | PySpark `local[*]`, `updated_at` incremental, auto schema evolution, `ON CONFLICT … DO UPDATE WHERE EXCLUDED.updated_at >` upsert, staging `_row_hash` dedup |
| **Quality** | 10-file PL/pgSQL loop suite + Great Expectations (9 suites) — nulls, uniqueness, FK, business rules |
| **Analytics** | 21-script SQL library — exploration, ranking, cohort, `fn_store_performance`, `fn_inventory_summary` |
| **Dashboard** | Streamlit + Plotly 5-tab ops view (`st.cache_data` TTL 5 min, `st.secrets` → `.env` fallback, sample CSV demo) — [Live](https://bike-store-relational-database-grvahmynq59w6zgckat2hx.streamlit.app/) |
| **Ops** | Makefile `check-deps`/`doctor`, Docker + `uv`, Prometheus/Pushgateway/Grafana, `CODEOWNERS` + `pre-commit` + branch protection |

---

## Quick Start

```bash
git clone https://github.com/Nitinx12/Bike-Store-Relational-Database
cd bike-store-relational-database

uv sync                              # install deps (uv, NOT pip)
cp .env.example .env                 # add Postgres + Mongo credentials
make doctor                          # verify setup
make run                             # ETL + PL/pgSQL + GX
make dashboard                       # → http://localhost:8501
```

With Docker:

```bash
make build && make up && make pipeline
```

First run is a full load; every run after is incremental.

---

## Key Makefile Commands

| Target | What it does |
|---|---|
| `make run` | Full pipeline (ETL + DQ + GX) — recommended |
| `make run-etl` | ETL only |
| `make run-dq` / `make run-gx` | PL/pgSQL / GX only |
| `make doctor` | Pre-flight health check |
| `make lint` / `make test` / `make format` | Ruff, Mypy, SQLFluff / pytest / format |
| `make up` / `make down` | Start / stop Docker stack |
| `make dashboard` | Streamlit locally |
| `make dashboard-guard` | Guard — fail if any change breaks dashboard |
| `make backup-postgres` / `make backup-mongo` | Backups |

Full reference: [`docs/makefile.md`](docs/makefile.md)

---

## Project Structure

```
bike-store-relational-database/
├── streamlit_app.py      — Streamlit entry (Cloud main file)
├── dashboard/            — data.py (secrets→env→sample), charts.py (Plotly)
│   └── sample/           — pre-exported CSVs for public demo fallback
├── .streamlit/           — config.toml (teal theme) + secrets.toml.example
├── docker/               — Dockerfile, entrypoint.sh, Prometheus
├── docs/                 — run_book, data_catalog, incremental_loading, dashboard.md
├── ps1/                  — PowerShell automation
├── scripts/              — ETL, DQ, schema, infra
├── sql/                  — 21 analytics scripts
├── src/                  — pipeline, database, validation, utils
├── tests/                — GX runner + 10 PL/pgSQL loops + unit (incl. dashboard)
├── docker-compose.yml
├── Makefile
├── pyproject.toml
└── .env.example
```

---

## Screenshots

<p align="center">
  <img src="assets/revenue_share_donut.png" width="320" alt="Revenue share" />
  <img src="assets/chart_total_revenue.png" width="320" alt="Total revenue" />
  <img src="assets/chart_repeat_customer_rate.png" width="320" alt="Repeat customers" />
</p>

---

## Documentation

| Doc | What's in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System overview, diagrams, container topology |
| [docs/run_book.md](docs/run_book.md) | Running, configuring, troubleshooting |
| [docs/makefile.md](docs/makefile.md) | Complete Makefile reference |
| [docs/data_catalog.md](docs/data_catalog.md) | Schema for all 9 tables |
| [docs/incremental_loading.md](docs/incremental_loading.md) | How incremental works |
| [docs/testing.md](docs/testing.md) | Quality strategy |
| [docs/dashboard.md](docs/dashboard.md) | Dashboard deploy guide |
| [CHANGELOG.md](CHANGELOG.md) | Release history |

---

## Contributing

1. `git checkout -b feat/your-feature`
2. `make format && make lint && make test && make doctor`
3. `git commit -m "feat: describe your change"` — Conventional Commits enforced by `.githooks/commit-msg`
4. Open a PR — `CODEOWNERS` + `Dashboard guard` + `CI` must pass

See [AGENTS.md](AGENTS.md) for conventions.
