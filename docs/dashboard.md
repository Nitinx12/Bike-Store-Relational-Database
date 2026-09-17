# Dashboard — Streamlit + Plotly (Production Grade)

Live operational view of the Postgres warehouse populated by `Mongo → Postgres` ETL. Every chart is Plotly (no matplotlib) and every query is cached.

```
MongoDB ──► PySpark ETL ──► Postgres (public.*) ──► Streamlit + Plotly
                                  ▲
                          GX + PL/pgSQL QA passes before deploy
```

---

## Quick Start (local)

```bash
uv sync                           # installs streamlit, plotly, sqlalchemy, psycopg2-binary
cp .env.example .env              # already has POSTGRES_* / MONGO_* for local docker
make up                           # start postgres + mongodb (if not already)
make run                          # load warehouse (or make run-full on first run)
make dashboard                    # → http://localhost:8501
# or
uv run streamlit run streamlit_app.py
```

Sidebar: time grain (`D/W/M`), `Top customers/products` sliders, **Refresh data** (clears `st.cache_data` TTL 5 min).

If Postgres is down the page shows a banner (`Data unavailable`) instead of a traceback — see `dashboard/data.py:50` fallback.

---

## What it shows (5 tabs, mirrors `sql/` 21-report library)

| Tab | Source | Charts |
|---|---|---|
| **Overview** | `fetch_monthly_sales` (`sql/16_sales_report.sql`) + `fetch_category/brand_mix` | Monthly revenue + orders (dual-axis line+bar), Category treemap, Top-12 brands bar, resampled time series |
| **Sales** | `fetch_monthly_sales` | Sortable table + 3 metrics (avg revenue/month, avg orders, total discounts) |
| **Customers** | `fetch_customer_rfm` (trims `sql/12_customer_report.sql`) | `total_orders` vs `lifetime_value` scatter (size=items, color=state), sortable table + CSV download |
| **Products** | `fetch_product_report` (`sql/13_product_report.sql`) | `units_sold` vs `revenue` scatter (size=inventory, color=category), table + CSV |
| **Stores** | `fetch_store_performance` (`sql/15_fn_store_performance.sql` → `fn_store_performance()`) | Horizontal bar `total_revenue` per store, table |

Header KPIs (`fetch_kpis`): customers, products, orders (with `Completed` split), order_items, gross revenue.

---

## Architecture

```
streamlit_app.py          # page_config, sidebar, 5 tabs, KPI cards (no SQL)
dashboard/data.py         # fetch_kpis(), fetch_monthly_sales(), …  — st.secrets → .env fallback
                          # cached_fetchers() wraps each with @st.cache_data(ttl=300)
dashboard/charts.py       # (DataFrame → go.Figure) — no DB, no Streamlit, testable
.streamlit/config.toml    # teal theme (#0F766E), CORS off, headless
.streamlit/secrets.toml.example  # template for Cloud
```

* **Caching:** every fetcher is `ttl=300` — `Refresh data` button calls `st.cache_data.clear()`.
* **Secrets:** `st.secrets["postgres"]` on Streamlit Cloud, otherwise `utils.connection` (`.env`) locally. Never commit `.streamlit/secrets.toml` (gitignored).
* **Safety:** `_safe()` wrapper in `streamlit_app.py` catches DB errors as `st.warning`; empty DataFrames render `st.info` placeholders.
* **Theme:** Plotly `Teal` scale + `Teal`/`Slate` constants in `charts.py` — consistent with `streamlit/config.toml`.

---

## Deploy on Streamlit Community Cloud

This repo is Cloud-ready — main file is at the repo root (`streamlit_app.py`) as Cloud expects.

**1. Push to GitHub**

```bash
git push origin main
```

**2. Create app on https://share.streamlit.io**

* **Repository:** `Nitinx12/Bike-Store-Relational-Database`
* **Branch:** `main`
* **Main file path:** `streamlit_app.py`
* **Python version:** `3.13` (matches `pyproject.toml:6` `requires-python = ">=3.13"`)

**3. Add Secrets** (App → Settings → Secrets, TOML):

```toml
[postgres]
host = "your-neon-or-rds-host"
port = 5432
database = "bike_store"
username = "postgres"
password = "****"

# DB must be reachable from the public internet — use Neon, Supabase, RDS, or
# an SSH tunnel. Local `localhost` Postgres won't work on Cloud.
```

> **Warehouse must exist on that Postgres.** Run the ETL against the same DB before deploying:
> `POSTGRES_HOST=<cloud-host> uv run python main.py --full-refresh`

**4. Deploy**

Cloud installs from `pyproject.toml` (`streamlit>=1.64`, `plotly>=7.1`, `psycopg2-binary`, `sqlalchemy`, `pandas`) — no `requirements.txt` needed. If you prefer a pinned file:

```bash
uv export --format requirements-txt --no-hashes -o requirements.txt
git add requirements.txt && git commit -m "chore: add requirements.txt for Streamlit Cloud"
```

**5. Verify**

Open the app URL → KPIs should match `make run` logs. Check **Manage app → Logs** if `Data unavailable` — usually a firewall or `secrets.toml` typo.

---

## Alternatives

* **Local Docker:** `docker build -f docker/Dockerfile -t bike-store-app . && docker run -p 8501:8501 -e POSTGRES_HOST=host.docker.internal bike-store-app streamlit run streamlit_app.py`
* **Self-host:** any VM with `uv` — `uv run streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0`

---

## Testing & Lint

```bash
make dashboard-test          # import smoke test (no DB)
make lint && make test       # ruff/mypy/sqlfluff + pytest 16/16
uv run streamlit run streamlit_app.py --server.headless true  # manual visual check
```

Charts are pure functions (`dashboard/charts.py`) — unit-test with synthetic DataFrames without a DB.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Missing Postgres config` | Set `.env` locally or `postgres.*` in Cloud Secrets |
| `Data unavailable` banner | Postgres unreachable — check host/port/firewall |
| `st.cache_data` not updating | Click **Refresh data** in sidebar or wait 5 min TTL |
| `No store data. Did fn_store_performance()…` | Load the function: `psql -h $POSTGRES_HOST -f sql/15_fn_store_performance.sql` |
