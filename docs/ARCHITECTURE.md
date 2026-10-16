# Architecture

How data flows from MongoDB to the public dashboard, and which piece
owns each step.

## Big picture

```
MongoDB (source of truth, local)
  │  src/jobs/incremental_load.py — watermarked upserts on updated_at
  ▼
PostgreSQL warehouse (local создано dev, Neon in prod)
  │  tests/dq/*.sql via src/jobs/run_dq.py — FK-ordered checks
  │  scripts/run_gx.py — 121 Great Expectations checks
  ▼
Streamlit dashboard (dashboard/home.py + pages/*)
  local:  uv run streamlit run dashboard/home.py
  public: Streamlit Cloud → Neon Postgres
```

## Pipeline (`main.py`)

Single entrypoint, stages run in this order and the exit code is 0
only if every executed stage passes:

0. **Preflight** — env present, Postgres + Mongo reachable. Fails fast.
1. **Contracts** (opt-in `--contracts`) — snapshot Mongo schemas to
   `contracts/` before moving data.
2. **Load** — `src/jobs/incremental_load.main(collections, full)`.
   Per collection: read rows newer than the `etl_watermarks` mark,
   de-dupe in Polars, stage + `ON CONFLICT` upsert, write `etl_logs`
   (a trigger advances the watermark). `--full` reloads everything.
3. **SQL checks** — `src/jobs/run_dq.main()` executes `tests/dq/*.sql`
   in parent-first order (brands → … → order_items → stocks).
4. **GX** — `scripts/run_gx.py` builds one suite per table
   (`*_quality`): row counts, not-null PKs, single/composite uniqueness,
   whitespace, future dates, FK resolution, formats, ranges and the
   `total_value = qty × price × (1 − discount)` arithmetic.

Flags: `--collections`, `--tables`, `--skip-dq`, `--skip-gx`,
`--fail-fast`, `--contracts`. Runners: `make <target>` (Unix),
`tasks.bat <target>` (Windows).

## Warehouse

9 business tables in `public` — see `docs/Data-Catlog.md` for the full
column reference. Cross-cutting objects:

- `etl_logs` / `etl_watermarks` + `fn_sync_etl_watermark()` — load
  bookkeeping; the trigger moves watermarks forward, never backward.
- `trg_<table>_updated_at` — touch `updated_at` on UPDATE; the loader
  disables them during bulk upserts to preserve source timestamps.
- `fn_store_performance()` et al. in `sql/functions/` — reporting
  functions backing `reports/store_performance.md`.

## Dashboard

`dashboard/lib/db.py` builds a pooled engine per worker. Secrets
precedence: Streamlit secrets → env → localhost defaults, with a full
`DATABASE_URL` (Neon `?sslmode=require`) winning over `DB_*` parts.
All SQL lives in `dashboard/helpers/queries.py`: parameterized,
aggregated in Postgres, cached 10 min. One immutable `Filters`
(date window, stores, categories, brands, statuses) drives every page.
Revenue is always `SUM(order_items.total_value)`.

## Quality gates

| Gate | Where | When |
|---|---|---|
| ruff + format + mypy | `.githooks/pre-commit` | every commit |
| sqlfluff | pre-commit, only if `sql/` staged | every commit |
| pytest unit (14) | pre-commit via CI / `make test-unit` | every push |
| pytest all (18) + import smoke + lock check | `.githooks/pre-push`, CI | every push |
| Image builds | CI `docker-build` | every push/PR |
| GHCR publish | `cd.yml` | merge to `main` |

Direct commits to `main` are blocked by the hook — work on
`type/slug` branches (`ALLOW_COMMIT_TO_MAIN=1` bypasses in emergencies).

## Deployment topology

- **App**: Streamlit Community Cloud, entry `dashboard/home.py`,
  redeploys itself on each `main` push. Secrets in the Cloud UI.
- **Data**: Neon Postgres (free tier sleeps when idle — first visit
  after idle takes ~10–30 s). Loaded once via
  `DATABASE_URL=<neon> main.py --full`.
- **Images**: `ghcr.io/<repo>-dashboard` and `-pipeline` published by CD.
- **Local prod-like**: `docker compose up --build` (Postgres 16,
  MongoDB 7, dashboard).
