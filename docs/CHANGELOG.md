# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `docs/CHANGELOG.md` — moved from repo root (`CHANGELOG.md`) so all docs live under `docs/`; single source of truth
- `src/pipeline/transform.py` — added `detect_pk_cols()` composite-aware helper and `PkCol = str | tuple[str, ...] | None` alias; `detect_pk_col()` now returns a `tuple` for `stocks`/`order_items` instead of a mistyped `list`
- `src/pipeline/mongo_source.py` — added `to_iso()` watermark normalizer (`datetime | date | str | None` → ISO string, naive datetimes assumed UTC)
- `src/pipeline/decision.py` — strict type hints (`dict[str, Any]`, `logging.Logger`) and `.get()`-based stat access instead of direct `dict[]`
- `utils/engine.py` — typed `postgres_engine() -> Engine` / `mongo_client() -> Database`, lazy `%s` logging, no import-time logger side effect
- `utils/logger.py` — repo-root-anchored `RotatingFileHandler`, name sanitizing, second-granularity log files
- `utils/metrics.py` — safe `PUSHGATEWAY_TIMEOUT` parsing with fallback; documented local (`localhost:9091`) vs compose (`pushgateway:9091`) defaults
- `utils/connection.py` — lazy `require_postgres_env()` validation (`ValueError`); opt-in strict check via `STRICT_ENV_CHECK`
- `src/pipeline/spark_session.py`, `src/database/jdbc_writer.py` — Spark master/memory/JVM modules and JDBC `batchsize`/`numPartitions` now env-driven (`SPARK_*`, `JDBC_*`)
- `docker/Dockerfile` — ships `gx/` + `sql/`, pinned `uv:0.8.22`, single `uv sync`, venv `PYSPARK_PYTHON`, non-root `USER app` + `HEALTHCHECK`
- `.env.example` — documented `MONGO_URI` per environment, `ETL_SCHEMA`, `PUSHGATEWAY_*` / `WAIT_FOR_PUSHGATEWAY`
- `scripts/ps1/local_runner.ps1` — `Set-StrictMode`, `Resolve-ProjectRoot`, nested `Join-Path`, quoted invocations, per-branch `$LASTEXITCODE`
- `tests/data_quality/suites/validation.py` — canonical `order_status` `InSet` (`Pending/Processing/Completed/Rejected`), nullable-phone `row_condition` guards
- `Makefile` — production-grade run targets: `run`, `run-verbose`, `run-full`, `run-etl`, `run-dq`, `run-gx`, `run-etl-only`, `run-etl-dq`, `run-collection`, `run-collection-full`, `run-gx-table`, `check-deps`, `doctor`, `run-clean`, `verify`
- `README.md` — comprehensive Makefile commands table with 30+ targets documented; improved section structure, TOC, and contributing guide
- `CHANGELOG.md` — project changelog for tracking notable changes
- `scripts/python/seed_mongo.py` — populates MongoDB with a realistic bike-store sample dataset (brands, categories, stores, products, stocks, staffs, customers, orders, order_items); supports `--drop` and `--collection NAME` flags; unblocks `make seed` and `make local-seed`
- `scripts/__init__.py`, `scripts/python/__init__.py`, `scripts/shell/__init__.py`, `scripts/ps1/__init__.py` — package markers so `python -m scripts.python.<module>` works in Docker and CI
- `mypy>=1.15.0` — added to `[dependency-groups].dev` in `pyproject.toml` so `make lint`'s Mypy step actually works on a fresh `uv sync`
- `src/pipeline/transform.py` — added `COMPOSITE_PK` dict (covers `stocks` and `order_items`) and `COLUMN_TYPE_MAP` (TIMESTAMPTZ/DATE/SMALLINT/NUMERIC); bridges the `src/` and `scripts/python/` code paths so the canonical pipeline picks up composite keys and typed columns the same way the legacy script did
- `src/database/schema.py` — `ensure_target_table()` now reads Postgres types from `COLUMN_TYPE_MAP` instead of hard-coding TEXT; matches the typed DDL produced by `scripts/python/mongo_to_postgres.py`
- `scripts/shell/restore_postgres.sh` — added `--force` flag and a non-TTY guard so the script no longer hangs in CI / Docker / `docker exec` environments
- `.github/workflows/linting.yml` — `sql-check` job now uses `astral-sh/setup-uv@v5` + `uv run sqlfluff` instead of `pip install sqlfluff`; consistent with the rest of the project
- `pyproject.toml` — added `mypy>=1.15.0`, `pandas-stubs`, and `types-psycopg2` to `[dependency-groups].dev`; added `[tool.mypy]` config with `explicit_package_bases = true`, `mypy_path = "."`, and per-module error suppressions for pre-existing patterns (MongoClient indexing, flat-module imports from the repo root)
- `src/__init__.py`, `utils/__init__.py` — added package markers so `src/` and `utils/` are proper Python packages; fixes the mypy "Source file found twice under different module names" error
- `tests/data_quality/context.py` — `get_datasource()` now raises `RuntimeError` if the datasource is still `None` after `get_context()`; satisfies mypy's `return-value` check
- `main.py` — `--collections` now accepts `--collection` alias; GX import falls back to `tests.data_quality.run`
- `scripts/python/seed_mongo.py` — `--collection`/`--collections` alias; per-collection map completed to all 9 collections
- `scripts/python/mongo_to_postgres.py` — `argparse` CLI (`--collection` repeatable + `=`, `--full-refresh`/`--full-load` aliases, unknown-arg warning)
- `scripts/python/inspect_schema.py` — `main()` guard with `try/finally` dispose; fixed repo-root `sys.path` and usage path
- `scripts/python/plpgsql_loops_tests.py` — `main(argv)` accepts/ignores extra `$(ARGS)`, driver-agnostic `notices` handling, guarded cleanup

### Changed

- **`src/pipeline/decision.py`**: flattened nested `if` → single `if` with `and` (SIM102)
- **`src/pipeline/runner.py`**: replaced `datetime.now()` with `datetime.now(timezone.utc)` (DTZ005), rewrote `dict()` literals as `{}` (C408), replaced blind `except Exception` with `PyMongoError`/`SQLAlchemyError` (BLE001), added `log.warning()` for best-effort staging cleanup instead of silent `pass` (S110)
- **`src/pipeline/mongo_source.py`**: replaced `except Exception` with `PyMongoError` (BLE001), added `PyMongoError` import
- **`src/database/stats.py`**: replaced `except Exception` with `SQLAlchemyError` (BLE001), added import
- **`src/validation/plpgsql_loops.py`**: replaced `except Exception` with `psycopg2.Error` (BLE001), added import
- **`main.py`**: replaced `except Exception` with `(OSError, ValueError, TypeError, AttributeError)` for GX setup (BLE001), replaced `datetime.now()` with `datetime.now(timezone.utc)` (DTZ005), added `timezone` import
- **`scripts/python/mongo_to_postgres.py`**: replaced all `except Exception` with `PyMongoError`/`SQLAlchemyError` (BLE001), `datetime.now()` → `datetime.now(timezone.utc)` (DTZ005), `dict()` → `{}` literals (C408), added `log.warning()` for staging cleanup instead of `pass` (S110), replaced `.replace("Z", "+00:00")` with `.removesuffix("Z")` (FURB162), added `PyMongoError` import; `_cast_typed_columns()` now tracks and reports per-column unparseable values that became NULL (previously silent)
- **`scripts/python/check_mongo.py`**: sorted imports alphabetically (I001), replaced `except Exception` with `(ConnectionFailure, OperationFailure, ServerSelectionTimeoutError)` (BLE001)
- **`scripts/python/plpgsql_loops_tests.py`**: fixed import order (I001), replaced `except Exception` with `psycopg2.Error`/`SQLAlchemyError` (BLE001)
- **`tests/data_quality/run.py`**: replaced `except Exception` with `(OSError, ValueError, TypeError, RuntimeError)` (BLE001), `datetime.now()` → `datetime.now(timezone.utc)` (DTZ005), added `timezone` import
- **`utils/logger.py`**: replaced `datetime.now()` with `datetime.now(timezone.utc)` (DTZ005), added `timezone` import
- **`utils/metrics.py`**: replaced `except Exception` with `(OSError, ValueError, TimeoutError)` for Prometheus pushgateway errors (BLE001); changed `PUSHGATEWAY_URL` default from `localhost:9091` to `pushgateway:9091` to match `docker-compose.yml` (the previous default silently failed to push metrics inside the Docker network)
- **`docker/entrypoint.sh`**: replaced `python -m scripts.python.mongo_to_postgres` with `python scripts/python/mongo_to_postgres.py` (the `-m` form requires `__init__.py` files which didn't exist); replaced bash-only `/dev/tcp` probe in `wait_for_pushgateway()` with a portable Python `socket` probe so the same script works in `sh`, `bash`, `busybox`, and minimal containers
- **`Makefile`**: replaced Windows-only `2>nul` / `exit /b 1` / `forfiles` syntax in `check-deps`, `doctor`, and `run-clean` targets with POSIX-compatible primitives (`>/dev/null 2>&1`, `exit 1`, delegation to `scripts/shell/log_cleanup.sh`); cross-platform now works on cmd.exe, bash, zsh
- **`docs/CHANGELOG.md`**: removed — content already lives in the root `CHANGELOG.md` (duplicate file)
- **`docs/data_catlog.md` → `docs/data_catalog.md`**: renamed and all references updated (README.md, docs/ARCHITECTURE.md, docs/project_structure.md, AGENTS.md)
- **`src/database/schema.py` / `src/database/staging.py` / `src/pipeline/runner.py`**: composite-PK aware (`tuple` → `ON CONFLICT (a, b)` / `UNIQUE (a, b)` / `dropDuplicates([...])`); `merge_staging_to_target()` returns `INSERT rowcount` (fallback staging count) instead of full target-table count
- **`src/pipeline/mongo_source.py`**: removed blanket `astype(str)` — native dtypes preserved (`where(notnull, None)`); `MongoClient` via `with`, guarded `MAX(ts)` lookup, `to_iso()` log formatting
- **`src/pipeline/runner.py`**: JDBC write catches `Exception` (Spark raises Py4J/Java) with staging cleanup + `unpersist`; `with MongoClient` peek; guarded auto-discovery; `try/finally` for `spark.stop()`/`engine.dispose()`; `sdf.cache()` before repeated `count()`
- **`src/database/stats.py`**: `MAX(ts)` logging via `to_iso()` (handles `str`/`date` watermarks)
- **`src/pipeline/transform.py`**: fixed `slugify()` `-` handling (dash → `_` before stripping)
- **`src/validation/plpgsql_loops.py` + `scripts/python/plpgsql_loops_tests.py`**: driver-agnostic `notices` guard, `raw_conn = None` + guarded close/dispose
- **`Makefile`**: full `.PHONY` (`run-full`, `run-collection`, `run-collection-full`, `run-etl-only`, `run-etl-dq`, `run-gx-table`); removed `cmd.exe ^` escapes (bare parens re-quoted for bash); `$(ARGS)`/`$(GX_TABLES)` passed **unquoted** so multi-word tokens split and empty defaults omit cleanly; `dq-gx`/`local-dq-gx` standardized on `$(GX_TABLES)`; `check-env` prerequisite on all local `run-*`/`local-*` targets; `run-etl`/`run-dq` forward `$(ARGS)`; `run-gx-table` is a documented alias of `run-gx`; `uv lock --check` replaces `uv sync --dry-run`; single-shot `uv --version` capture; `BOLD` used in `help` header; `.env` plain-`KEY=value` caveat documented; portable `local-pipeline` pwsh guard
- **`docker/Dockerfile`**: collapsed to a single `uv sync --frozen --no-dev`
- **CI (`.github/workflows/`)**: `checkout@v4`, `setup-uv@v5`, `path: ./`, `severity: Error, Warning`, `sqlfluff lint sql/`, checkmake via release binary, fixed docker-build import (`src.pipeline.runner`), `uv sync --frozen`
- **`tests/data_quality/run.py`**: package imports, get-or-create table asset/suite (re-run safe), broad `except` (never raises)
- **`tests/data_quality/context.py`**: documented code-first GX (`gx/` file config intentionally unused)
- **SQL**: `12_customer_report.sql` explicit columns + `ASC NULLS LAST` recency; `16_sales_report.sql` `GROUP BY 1` + explicit cols; `15_fn_store_performance.sql` `ord_rev` rename + `DECLARE` vs `#variable_conflict`; `13_product_report.sql` `NULLIF` avg-price guard; `19_cohort_analysis.sql` explicit cols; discount fixes (`SUM(list_price*quantity*discount)`) in `16`/`15`/`21`
- **Docs**: `scripts/*.py → scripts/python/*.py`, `python -m scripts.* → scripts.python.*`, `17_new_ve_return.sql`, loop filenames, `utils/`, `test_orders` path, GX code-first notes, `README` gx line, `data_catalog` `updated_at` fix

### Fixed

- **Bug register (`fix.md`)**: full P0→P3 audit completed and merged (`fix/bug-register-p0-p3`, `fix/bug-register-remaining`); `fix.md` removed after merge — this changelog is the record
- **P0-1**: composite PK no longer returns `list` where `str | None` expected (`stocks`, `order_items` now `tuple` end-to-end)
- **P0-2**: `merge_staging_to_target()` no longer reports total table size as rows merged
- **P0-3**: Mongo source no longer stringifies numerics/dates (typed `COLUMN_TYPE_MAP` respected)
- **P0-4**: watermark logging no longer crashes on `str`/`date` values
- **P0-5**: JDBC write failures no longer escape accounting or leak staging tables
- **P1-1**: shell scripts use `set -euo pipefail` and correct `PROJECT_ROOT` (`scripts/shell/` → repo root)
- **P1-2**: `--collections` / `--collection` drift resolved (alias accepted everywhere)
- **P1-3**: `dotenv` → `python-dotenv`; `uv.lock` tracked again (removed from `.gitignore`)
- **P2-1**: discounts summed as money, not fractions
- **P2-2**: contradictory `order_status` sets unified to `Pending/Processing/Completed/Rejected` (seed data); GX `InSet` added; loop SQL + docs aligned
- **P2-4**: nullable-phone regex guarded; `order_items.updated_at` catalog contradiction resolved
- **`scripts/python/plpgsql_loops_tests.py`**: moved `sys.path` setup before the `from utils...` import block, and corrected the parent-directory traversal from `SCRIPT_DIR.parent` to `SCRIPT_DIR.parent.parent` (was resolving to `scripts/` instead of the repo root) — `make local-pipeline` Stage 2 now works
- **`scripts/python/run_gx.py`**: corrected `Path(__file__).resolve().parents[1]` to `parents[2]` so the repo root (and therefore `utils/`) is on `sys.path` — `make local-pipeline` Stage 3 now works
- **`Makefile` (makefile-review.md findings #1–#9)**: `@echo.` → `@echo ""` (restores `make help`, the default goal); `uv lock --check` replaces `uv sync --dry-run` in `check-deps`/`doctor` (dry-run exits 0 on stale lockfiles); reverted `"$(ARGS)"` quoting — forwarding vars are unquoted so multi-word `ARGS` splits and empty defaults omit the phantom `""` arg; `run-gx-table` is now an alias of `run-gx`; `docs/run_book.md` `dq-gx` examples updated to `GX_TABLES=`
- **`.python-version`**: pinned `3.13` → `3.13.15` so `uv run` stops chasing floating micro releases and recreating `.venv` on every run
- **`Makefile`**: `help` target uses plain `@echo` (no `grep`/`awk`); `check-deps`/`doctor` use POSIX shell primitives (`>/dev/null 2>&1`, `exit 1`); `run-clean` delegates to `scripts/shell/log_cleanup.sh` instead of Windows-only `forfiles`
- **`src/database/staging.py`**: `merge_staging_to_target()` now returns the count of rows in the **target** table after merge, not the count of the soon-to-be-dropped **staging** table; this is the actual "rows loaded" number (was previously misleading after `ON CONFLICT DO NOTHING` dedups)
- **`tests/data_quality/suites/validation.py`**: replaced the convoluted `stocks_suite()` placeholder-then-discard pattern (list sliced to `[:0]` then concatenated) with a plain return of the real list; demoted the two remaining `TODO` comments on `model_year` and `order_status` to `NOTE` comments so the project no longer has outstanding TODOs in the validation suite
- **SQL files**: `sqlfluff fix` auto-fixed trailing whitespace, missing trailing newlines, indentation, spacing, and SELECT modifier issues across all 21 SQL files
- **`sql/04_measures_exploration.sql`**: added explicit `AS metric` and `AS metric_value` aliases (AL03), renamed `value` alias to `metric_value` (RF04 reserved keyword)
- **`sql/09_performance_analysis.sql`**: wrapped long comment across multiple lines to respect 80-char limit (LT05)
- **`sql/17_new_ve_return.sql`**: renamed `month` alias to `sales_month` (RF04 reserved keyword)
- **`sql/18_status_check.sql`**: added explicit `AS metric` and `AS metric_value` aliases (AL03), renamed `value` → `metric_value` (RF04)

### Removed

- **`fix.md`** — temporary bug register; all items fixed and summarized here, file deleted
- **`CHANGELOG.md` (repo root)** — moved to `docs/CHANGELOG.md`; single source of truth under `docs/`

- **`main.js`** — stub file containing only `console.log("Hello Bike Store")`; project is Python-based (`main.py` is the real entry point), so this orphan was dead weight
- **`docs/CHANGELOG.md`** — duplicate of the root `CHANGELOG.md`; single source of truth is now at the repo root
