# Runbook — operating the pipeline and dashboard

## Daily operation

```bash
tasks.bat pipeline        # or: make pipeline
```

Reads the last lines of `logs/pipeline_*.log` — every stage prints
`[OK]` / `[FAIL]` plus a final summary with a non-zero exit on failure.

## Common recoveries

| Symptom | Cause | Fix |
|---|---|---|
| `[FAIL] Postgres/Mongo` at preflight | DB down or `.env` wrong | Start services; verify `DB_HOST/DB_PORT/DB_*` |
| `load: FAILED` for a table | Usually a trigger/DDL drift or bad row | Read the error in the log; fix source; rerun (incremental resumes from watermarks) |
| `DQ failed for: X` | Data violates a `tests/dq/` rule | Inspect the rule file, fix data or rule, rerun `tasks.bat dq` |
| `GX validation failed` | Same, at expectation level | `tasks.bat gx <table>` shows the failing expectation descriptions |
| Dashboard shows connection error | Secrets/env point nowhere | Check Cloud Secrets or local `.env`/`secrets.toml` |
| Cloud app slow on first visit | Neon free tier sleeping | Normal — ~10–30 s wake-up, then fast (10-min query cache) |
| Stale dashboard numbers | Cache or old load | Wait ≤10 min for cache expiry, or rerun the pipeline |

## Full refresh (rewrites every table)

```bash
tasks.bat pipeline-full   # or: make pipeline-full
```

Use after schema changes, bulk source fixes, or bootstrapping a new
database (e.g. Neon). Watermarks advance automatically.

## Single-table revalidation

```bash
uv run python main.py --collections orders --tables orders
uv run python scripts/run_gx.py orders products
```

## Logs

- Pipeline/ETL/DQ logs: `logs/<name>_YYYYMMDD_HHMMSS.log` (gitignored).
- `etl_logs` table: one row per collection per run — query it to audit
  any past load (`status`, `rows_loaded`, `error_message`).
- GX suites on disk (`gx/expectations/*_quality.json`) are rewritten by
  every run via `add_or_update` — they double as the current contract.

## Smoke checks after any change

```bash
tasks.bat test-unit     # fast, no DB
tasks.bat test-smoke    # live DBs, scoped brands run
tasks.bat lint          # ruff + format + mypy
```

## Cloud / Neon notes

- Secrets live in the Streamlit Cloud UI (`DATABASE_URL`, `DB_SCHEMA`) —
  never in the repo. `.env` and `secrets.toml` are gitignored.
- Reloading Neon data: set `DATABASE_URL` to the pooled Neon string and
  run `main.py --full` from any machine with Mongo access.
- If a password contains `@ : / ? #`, percent-encode it in `DATABASE_URL`.
