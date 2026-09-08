# Bike Store Pipeline — Bug & Fix Register

> Generated: 2026-09-08 — full repo audit.
> Order: Critical (breaks pipeline) → High (ops/CLI/deps/Docker) → Medium (SQL/GX/docs) → Low (hygiene).
> Format per item: Location | Issue | Impact | Fix.

---

## P0 — Critical (fix first, pipeline broken otherwise)

### P0-1 — Composite PK returns `list` where `str|None` expected
- **Location:** `src/pipeline/transform.py:56,68-73`
- **Issue:** `detect_pk_col() -> str | None` returns `list(composite)` for `stocks` (`store_id,product_id`) and `order_items` (`order_id,item_id`) with `# type: ignore[return-value]`.
- **Impact:** Callers `src/pipeline/runner.py:155`, `src/database/schema.py:49`, `src/database/staging.py:36` do `pk_col in columns` / `ON CONFLICT (pk_col)` — list-in-list is always `False`, falls through to `_row_hash` path without `_row_hash` column → `CREATE TABLE` / merge fails.
- **Fix:**
  1. Change signature to `-> str | tuple[str, ...] | None` OR return single surrogate (e.g. keep `detect_pk_col` single-col + add `detect_pk_cols` for composites).
  2. Update `schema.py:ensure_target_table`, `staging.py:merge_staging_to_target`, `runner.py` to handle `tuple` → `ON CONFLICT (a,b)` / `PRIMARY KEY (a,b)`.
  3. Remove `# type: ignore[return-value]`, add mypy test for `stocks`/`order_items`.

### P0-2 — `merge_staging_to_target` returns total table count, not rows merged
- **Location:** `src/database/staging.py:28,54-58`
- **Issue:** Docstring says “rows attempted” but code does `SELECT COUNT(*) FROM target` (full table size).
- **Impact:** Inflates `runner.py:217 totals["rows_loaded"]`, metrics, Rich summary; incremental loads look huge.
- **Fix:** Return `GET DIAGNOSTICS` / `result.rowcount` from the `INSERT`, or `SELECT COUNT(*) FROM staging`. Update log line and `runner.py` totals.

### P0-3 — Mongo source stringifies all values
- **Location:** `src/pipeline/mongo_source.py:93-94` — `pdf[col].where(isna(), astype(str))`
- **Issue:** Casts every non-null to `str`, destroying numeric/date types.
- **Impact:** Contradicts `transform.py:28-45 COLUMN_TYPE_MAP` (`NUMERIC, DATE, TIMESTAMPTZ`); Postgres gets TEXT, downstream `SUM()`/date math breaks.
- **Fix:** Drop blanket cast; let Spark infer types, only cast genuinely mixed-type columns. Add dtype test.

### P0-4 — Naive datetime handling crashes on string/date watermarks
- **Location:** `src/pipeline/mongo_source.py:44,77` (`strftime(ISO_FMT)`), `src/database/stats.py:65-71` (`isoformat()`)
- **Issue:** Assumes `datetime`; Mongo `MAX(updated_at)` or Postgres `MAX()` returning `str/date` raises `AttributeError` uncaught (`except PyMongoError/SQLAlchemyError` only).
- **Impact:** Incremental watermark lookup crashes whole collection.
- **Fix:** Add helper `to_iso(ts: datetime|date|str|None) -> str|None` with `isinstance` checks; catch `(AttributeError, TypeError, ValueError)`; normalize to UTC (`config.py:50 ISO_FMT` is naive, loses UTC from `runner.py:70,150`).

### P0-5 — Wrong exception type around Spark JDBC write
- **Location:** `src/pipeline/runner.py:196` — `except SQLAlchemyError` around `write_to_staging()` (Spark raises `Py4J/Java` errors)
- **Issue:** Real write failures escape, no `failed` accounting, no staging cleanup.
- **Impact:** Partial runs reported as success; orphan staging tables.
- **Fix:** Catch `Exception` (or `Py4JJavaError + SQLAlchemyError`), log, mark `failed`, `drop_staging` in `finally`.

---

## P1 — High (ops / CLI / deps / Docker — fix next)

### P1-1 — Shell scripts missing `set -e`, wrong `PROJECT_ROOT`
- **Location:** `scripts/shell/*.sh:18-20` — `backup_mongo.sh:17,19`, `backup_postgres.sh:19,21`, `restore_*.sh`, `health_check.sh:18,20`, `init_db.sh:18,20`, `log_cleanup.sh:18,20`, `monitor_logs.sh:29,35`, `docker_dev.sh:22,24-25`, `restore_*_docker.sh:4,6-8`. Only `docker/entrypoint.sh:2` correct.
- **Issue:** (a) `set -uo pipefail` missing `-e` violates `AGENTS.md`; (b) `$(dirname "${BASH_SOURCE[0]}")/..` from `scripts/shell/` resolves to `scripts/`, not repo root — needs `/../..`.
- **Impact:** Silent continuation on error; `.env`, `logs/`, `backups/`, `docker-compose.yml` lookups resolve to `scripts/...` and fail.
- **Fix:** All scripts → `set -euo pipefail`; `PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"`. Quote all vars.

### P1-2 — CLI flag drift `--collections` vs `--collection`
- **Location:** `main.py:82` (`--collections` plural) vs `scripts/python/mongo_to_postgres.py:1177`, `seed_mongo.py:345`, `scripts/ps1/local_runner.ps1:195`, `docker/entrypoint.sh:81` (`--collection` singular, `entrypoint.sh:78` even documents `--collections` for `pipeline`).
- **Issue:** `pipeline --collection orders` / `local_runner -Collection` mapping fails on `main.py`.
- **Impact:** Per-collection runs broken via recommended entry point.
- **Fix:** Standardize to one (recommend `--collections` plural, accept `--collection` alias via `argparse`). Update `Makefile:241,245`, `entrypoint.sh`, `local_runner.ps1`, docs. Add `Makefile .PHONY` entries (see P1-6).

### P1-3 — Wrong dependency `dotenv`, `uv.lock` ignored but required
- **Location:** `pyproject.toml:8` (`dotenv>=0.9.9`), `.gitignore:195` (`uv.lock`), `docker/Dockerfile:42`, `.github/workflows/python-ci.yml:24`, `docker-build.yml`
- **Issue:** (a) Should be `python-dotenv`; (b) `uv.lock` is tracked (`git ls-files` shows it) but listed in `.gitignore` + required by `uv sync --frozen`.
- **Impact:** `uv sync` installs wrong package; fresh clones / Docker / CI with `--frozen` fail or drift.
- **Fix:** `uv remove dotenv && uv add python-dotenv`; delete `uv.lock` line from `.gitignore`; `uv sync`; commit lockfile.

### P1-4 — Dockerfile omissions & misconfig
- **Location:** `docker/Dockerfile:29-33,36,42,46-53`
- **Issue:** (a) Copies `utils,scripts,tests,src,jars,main.py` but omits `gx/,sql/` needed by validation/analytics; (b) `COPY --from=ghcr.io/astral-sh/uv:latest` unpinned; (c) double `uv sync --frozen --no-install-project --no-dev` + `uv sync --frozen --no-dev` wasteful layer; (d) `PYSPARK_PYTHON=/usr/local/bin/python` bypasses `/app/.venv/bin/python`; (e) no `USER`/`HEALTHCHECK` (runs as root).
- **Fix:** Add `gx/ sql/` to `COPY`; pin `uv:0.8.x`; collapse to single `uv sync`; point `PYSPARK_PYTHON` to venv python; add non-root `USER app` + `HEALTHCHECK`.

### P1-5 — `.env` drift (local only, not committed — correctly ignored)
- **Location:** `.env:8,13` vs `.env.example:23,29,38,44,47` vs `docker-compose.yml:28,67-68`
- **Issue:** Local `.env` has `POSTGRES_PASSWORD=admin` (example/compose default `postgres`), `MONGO_URI=mongodb://localhost:27017` (compose `app` needs `mongodb://mongodb:27017`), missing `ETL_TS_COL,GRAFANA_ADMIN_USER/PASSWORD,PUSHGATEWAY_*`.
- **Impact:** Works locally, breaks inside `app` container; monitoring disabled.
- **Fix:** Align with `.env.example`; use split `.env.local` vs compose override or document `MONGO_URI` per environment. Do NOT commit `.env`.

### P1-6 — Makefile issues
- **Location:** `Makefile:18-19,22,30,34,36-37,74,216,238,258,100,158,164,167`
- **Issue:** (a) `.PHONY` missing `run-full,run-collection,run-collection-full,run-etl-only,run-etl-dq,run-gx-table`; (b) `include .env`/`export` indented with spaces; (c) `^<target^>`, `^(production-grade^)` — `cmd.exe ^` escaping prints literally on bash; (d) unquoted `$(ARGS)/$(GX_TABLES)`; (e) `SHELL:=/bin/bash` but recipes hardcode `bash scripts/...` + `pwsh scripts/ps1/...` (fails on Linux CI without `pwsh`).
- **Fix:** Add missing `.PHONY`; remove `^` escapes; quote `“$(ARGS)”`; use `$(SHELL)` or portable targets; document `GX_TABLES` quoting.

### P1-7 — CI workflow errors
- **Location:** `.github/workflows/codeql.yml:62`, `linting.yml:37,40,55,58,70`, `docker-build.yml:51`, `python-ci.yml:24`
- **Issue:** `checkout@v7` nonexistent (use `v4`); `linting.yml:37 path: .\` Windows sep on `ubuntu-latest`; `:40 severity: '"Error", "Warning"'` over-quoted; `setup-uv@v3` vs `@v5` skew; `sqlfluff lint .` vs `Makefile:142 lint sql/` scope mismatch; `apt-get install checkmake` not in default repos; `docker-build.yml:51 import scripts.mongo_to_postgres` wrong path; `python-ci.yml:24 uv sync --frozen --dev` invalid flag.
- **Fix:** Pin `checkout@v4`, `setup-uv@v5`; `path: ./`; fix severity quoting; unify sqlfluff scope (`sql/`); install `checkmake` via release or drop; fix import to `scripts.python.mongo_to_postgres`; use `uv sync --frozen` (+ `--group dev` if needed).

### P1-8 — PowerShell convention violations
- **Location:** `scripts/ps1/local_runner.ps1:1,61,72,91-92,120,128,143,150,156,164,195,239`
- **Issue:** Missing `Set-StrictMode -Version Latest` (required, only `$ErrorActionPreference="Stop"` present); `Join-Path $ProjectRoot "scripts\python"` embeds `\` instead of nested `Join-Path`; `& uv run python $ScriptPath` unquoted (fails on spaces); `$LASTEXITCODE` clobbered by `ForEach-Object` pipe in venv fallback; non-standard verb `Find-ProjectRoot` (should be `Get-/Resolve-`).
- **Fix:** Add `Set-StrictMode`; nest `Join-Path`; quote `"$ScriptPath"`; capture `$LASTEXITCODE` immediately; rename to `Resolve-ProjectRoot` / `Invoke-Stage` already OK.

### P1-9 — Resource leaks / fragile error paths
- **Location:** `src/pipeline/runner.py:89-91,262-263,273-287`, `src/pipeline/mongo_source.py:28-39,67-83`, `src/validation/plpgsql_loops.py:39,62-73`, `utils/metrics.py:76`, `utils/connection.py:18-50`
- **Issue:** `MongoClient()` + `close()` without `try/finally`/`with` (leaks on `find/count/aggregate` error; `runner.py:262` correctly uses `with` — inconsistent); auto-discovery `list_collection_names()` no `try/except PyMongoError`; no `try/finally` for `spark.stop()/engine.dispose()`; `plpgsql_loops.py:39 del dbapi_conn.notices[:]` assumes `psycopg2` (breaks on `psycopg3`/SQLAlchemy2 `driver_connection`); `finally: raw_conn.close()` with undefined `raw_conn` → `UnboundLocalError`; `float(os.getenv(...))` at import crashes on bad `PUSHGATEWAY_TIMEOUT`; Postgres validated at import (`OSError` — wrong type, should be `ValueError`) but Mongo deferred → cryptic `None` errors.
- **Fix:** Use `with MongoClient(...)` everywhere; wrap discovery; `try/finally` for spark/engine; guard `notices` with `hasattr`; init `raw_conn=None` + `if raw_conn:`; validate env with defaults + `try/except ValueError`; raise `ValueError/EnvironmentError`, validate both DBs symmetrically.

---

## P2 — Medium (SQL / GX / validation logic)

### P2-1 — Discount summed as fraction, not money
- **Location:** `sql/16_sales_report.sql:14,59`, `sql/15_fn_store_performance.sql:95`, `sql/21_fn_staff_performance.sql:116`
- **Issue:** `ROUND(SUM(discount),2) AS Total_discounts/order_discount` sums fraction (`0.1+0.2`).
- **Fix:** `SUM(list_price*quantity*discount)` (check exact column names: `oi.list_price`, `oi.quantity`, `oi.discount`).

### P2-2 — Order-status sets contradict each other, GX doesn’t catch it
- **Location:** `tests/generic/loops/06_test_orphan_and_business_rules.sql:22` (`shipped/delivered/pending/processing`) vs `sql/15_fn_store_performance.sql:44-45` + `sql/18_status_check.sql:3-24` (`Rejected/Processing/Completed/Pending`) vs `docs/testing.md:141` (`Pending/.../Shipped/...`); `tests/data_quality/suites/validation.py:224-228` only length-checks `order_status` (NOTE admits missing `InSet`).
- **Fix:** Decide canonical set from source data; add `ExpectColumnValuesToBeInSet`; align all SQL + docs.

### P2-3 — GX suites ignore `gx/` config (dead config)
- **Location:** `gx/great_expectations.yml:48-65`, `gx/expectations/.ge_store_backend_id` (only file), `gx/checkpoints/`, `gx/validation_definitions/` (empty) vs `tests/data_quality/context.py:79` (`gx.get_context(mode="ephemeral")`), `tests/data_quality/suites/validation.py:308-318`
- **Issue:** File-based checkpoints/expectations referenced but nonexistent; real suites code-defined; `.gitignore:1-7` ignores `uncommitted/` where `validation_results_store` points.
- **Fix:** Either (a) delete `gx/` file config and document code-first GX, or (b) materialize `gx/expectations/*.json` + `checkpoints/*.yml` and switch `context.py` to filesystem mode. Don’t keep both.

### P2-4 — GX nullable-phone regex + missing guards
- **Location:** `tests/data_quality/suites/validation.py:86,111`, `:271-279`, `tests/data_quality/run.py:31,49,54,91`
- **Issue:** `ExpectColumnValuesToMatchRegex(phone)` without `mostly`/null-guard fails on nullable `phone`; `order_items.updated_at NOT NULL` contradicts `docs/data_catalog.md:5` (“every table except order_items has updated_at”); `from context import` fragile; `add_table_asset/.../suites.add` in loop collides on re-run in same process; `except (OSError,ValueError,TypeError,RuntimeError)` misses GX/SQLAlchemy/psycopg2 errors.
- **Fix:** Add `mostly` + `row_condition` for null phones; resolve `updated_at` contradiction (either allow null or fix catalog); use package imports; guard re-add; broaden except.

### P2-5 — Production `SELECT *`, fragile SQL idioms
- **Location:** `sql/12_customer_report.sql:47,62,120` (`SELECT *, r.*, SELECT * FROM customer_analytics` + `NTILE() NULLS FIRST` inverts recency), `sql/16_sales_report.sql:59`, `sql/19_cohort_analysis.sql:65` (`SELECT *`), `sql/13_product_report.sql:22,119,165-186` (inconsistent folding `Orders` vs `orders`, `CROSS JOIN Dataset_date + LEFT JOIN ... AND Rnk=1` fragile, `ROUND(NULL)` on never-sold), `sql/16_sales_report.sql:21 GROUP BY Order_month` (alias, PG-only), `sql/15_fn_store_performance.sql:109 OR2` (reserved prefix), `:74 #variable_conflict` non-standard.
- **Fix:** Enumerate columns; fix recency ordering; `GROUP BY 1`/expr; rename `OR2`; standardize folding (lowercase); handle nulls with `COALESCE`.

---

## P3 — Low (docs / types / perf / logging — cleanup)

### P3-1 — Docs reference wrong paths (stale after `scripts/python/` move)
- **Location:** `docs/SQL.md:69`, `docs/testing.md:34,42-50,74-85,94-96,103,150`, `docs/project_structure.md:84-93,140-150,202,204,221-234`, `docs/run_book.md:28-30,150-156,159,162,165,214`, `docs/docker.md:131-136`, `docs/tests.md:10,27,59-77`, `docs/data_catalog.md:5 vs :142,146`, `README.md:221,230`
- **Issue:** `scripts/*.py` → actual `scripts/python/*.py`; `python -m scripts.mongo_to_postgres` → `scripts.python.*`; `17_new_vs_return.sql` → `17_new_ve_return.sql`; loop filenames `01_unique_constraint_checks.sql...` → `01_test_brands.sql...10_test_stores.sql`; `gx/expectations/*.json`, `checkpoints/*.yml` don’t exist; `src/utils/` → root `utils/`; `psql -f tests/test_orders.sql` no such file; `order_items.updated_at` contradiction; `_find_project_root() walks 8 dirs` stale.
- **Fix:** Global find-replace + verify with `glob`; regenerate `project_structure.md`; fix `README.md:221` (GX code-based, not 9 JSON).

### P3-2 — Strict type hints violated (`AGENTS.md` requires PEP8 + hints)
- **Location:** `runner.py:51-52`, `mongo_source.py:25,58`, `decision.py:14`, `transform.py:56,96`, `schema.py:27,33`, `staging.py:20,61,66`, `stats.py:18`, `plpgsql_loops.py:26,36,54`, `utils/engine.py:24,55`, `decision.py:22,26,36` (direct `dict[]` → `KeyError`)
- **Issue:** Untyped `engine/log/conn/schema/table/...`, `get_spark/postgres_engine/mongo_client` missing `-> Engine/Db`.
- **Fix:** Add hints (`Engine`, `Logger`, `SQLAlchemy Connection`), `TypedDict` for stats dicts, `.get()` with validation. Remove `mypy` `disable_error_code` suppressions in `pyproject.toml:49-67` after fixing.

### P3-3 — Perf / hardcoded values / logging
- **Location:** `src/pipeline/runner.py:144,156-166` (4× `sdf.count()` no `cache`), `src/pipeline/spark_session.py:29,32-35` (`local[*]`, `2g`, `--add-modules jdk.incubator.vector`, `LEGACY`), `utils/logger.py:12,16,26-27` (CWD-relative `logs/`, minute-granularity collision, `if handlers: return` leak, unsanitized `name`), `utils/engine.py:16,42,46,59,63` (import side-effect, f-string logging), `jdbc_writer.py:35-36` (`batchsize=5000,numPartitions=4`), `utils/metrics.py:75` (`pushgateway:9091` vs docstring `localhost:9091`), `transform.py:51-53` (first `re.sub` strips `-` making second alt dead)
- **Fix:** `cache()` before counts; move Spark/memory/JDBC batch to `.env`/`config.py`; `logger.py` → `REPO_ROOT/logs`, `RotatingFileHandler`, sanitize `name`; lazy `%s` logging; fix `metrics.py` default; simplify `slugify`.

### P3-4 — Minor script bugs
- **Location:** `scripts/python/seed_mongo.py:367-371`, `mongo_to_postgres.py:1173-1178`, `inspect_schema.py:23-46`, `plpgsql_loops_tests.py:81`, `check_mongo.py:7-8`
- **Issue:** `collections_map` only `brands,categories,stores` (6/9 `--collection` always unknown); manual `sys.argv` parse only `--collection X` (not `--collection=X`), silently ignores typos, accepts `--full-load` alias `main.py` doesn’t; `inspect_schema.py` runs DB at import; `plpgsql_loops_tests.py:main()` takes no args but `Makefile/entrypoint` pass `$(ARGS)`; docstring path stale.
- **Fix:** Complete map; switch to `argparse`; guard `if __name__=="__main__"`; accept/ignore args explicitly; fix docstring.

---

## Suggested fix order

1. P0-1 → P0-2 → P0-3 → P0-4 → P0-5 (make pipeline correct)
2. P1-1 → P1-2 → P1-3 → P1-4 (make it runnable locally + in Docker + CI)
3. P2-1 → P2-2 → P2-3 → P2-4 (make validation trustworthy)
4. P1-6 → P1-7 → P1-8 → P1-9, then P2-5, P3-* (cleanup + docs)
5. Re-run: `make lint && make test && uv run python main.py --full-refresh` (or `make run-full`), confirm 9/9 GX + PL/pgSQL PASS.
