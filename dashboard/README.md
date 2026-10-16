# 🚲 Bike Store Dashboard

Live sales analytics on the Postgres warehouse: revenue, stores, products,
customers, and data health — one shared filter sidebar drives every page.

## Pages

| Page | What's inside |
|---|---|
| **Home** (`dashboard/home.py`) | KPI cards with prior-period deltas + sparklines, weekly revenue trend, category mix, store ranking, order-status funnel |
| **Sales** | Day/week/month trend, revenue by store / category / status, weekday rhythm, month-over-month category waterfall |
| **Stores** | Store scoreboard (revenue, orders, customers, units) + staff leaderboard, both CSV-downloadable |
| **Products** | Category→brand treemap + sunburst, top-30 Pareto with 80% line, portfolio bubble, price histogram, low-stock watch (live `stocks` snapshot) |
| **Customers** | RFM scatter with rule-based segments (Champions / Loyal / Big spenders / Occasional / Potential), top customers, customers by state, first-order retention cohorts |
| **Data Health** | Table volumes + COUNT-based integrity checks mirroring the GX suite (orphan FKs, pricing arithmetic, future dates, negative stock) |

## Run locally

```bash
uv sync
uv run streamlit run dashboard/home.py
```

## Configure the database connection

Precedence: **Streamlit secrets → environment → built-in defaults**
(`localhost:5432/bike_store`).

- Local: `.env` (`DB_HOST/DB_PORT/DB_NAME/DB_SCHEMA/DB_USER/DB_PASSWORD`)
  or `dashboard/.streamlit/secrets.toml` (see `secrets.toml.example`).
- Hosted / Neon: a single `DATABASE_URL`
  (`postgresql://user:pass@host/db?sslmode=require`) beats the parts.

No `.env` file? The app still boots — it just needs one of the above to
actually reach a database, otherwise pages show a connection error
instead of a blank screen.

## How it works

- `dashboard/lib/db.py` — pooled SQLAlchemy engine (`@st.cache_resource`).
  The URL is built at page runtime so Streamlit Cloud secrets work.
- `dashboard/helpers/queries.py` — the only place SQL lives. Every query
  is parameterized (`text()` + bound params, never f-strings) and aggregates
  in Postgres; results are cached 10 minutes (`@st.cache_data`).
- `dashboard/lib/filter.py` — one immutable `Filters` object
  (date window [start, exclusive end), stores, categories, brands, statuses).
- `dashboard/lib/charts.py` + `dashboard/helpers/` — shared Plotly styling,
  cards, chips, light/dark theme. Revenue is always
  `SUM(order_items.total_value)`.
- Dates are static (2016–2018 batch loads), so the freshness pill reads
  “Snapshot · data through …” instead of alarming, and weekday (not hourly)
  patterns are shown because `order_date` carries no time of day.

## Deploy publicly (Streamlit Cloud + Neon)

1. **Neon** — free project at [neon.tech](https://neon.tech); copy the
   pooled connection string.
2. **Database** — the app reads the warehouse directly (no setup queries):
   copy your local Postgres to Neon with `pg_dump` (schema + data), e.g.
   `pg_dump "<local-url>" | psql "<neon-url>"`.
3. **Push** this repo to GitHub.
4. **Deploy** at [share.streamlit.io](https://share.streamlit.io):
   repo → `main` → main file path `dashboard/home.py`; then
   **App settings → Secrets**:
   ```toml
   DATABASE_URL = "<neon pooled connection string>"
   DB_SCHEMA = "public"
   ```
   Root `requirements.txt` and `.streamlit/config.toml` are the Cloud-facing
   config (error details off, usage stats off).

## Docker

```bash
docker build -f dashboard/Dockerfile -t bike-store-dashboard .
docker run -p 8501:8501 -e DATABASE_URL="..." bike-store-dashboard
```

`.env` and secrets are excluded from the image via `.dockerignore`;
the container runs as non-root with a `/_stcore/health` healthcheck.
