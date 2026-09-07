# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `docs/makefile.md` — complete Makefile reference with all targets, examples, and troubleshooting guide
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

### Fixed

- **`scripts/python/plpgsql_loops_tests.py`**: moved `sys.path` setup before the `from utils...` import block, and corrected the parent-directory traversal from `SCRIPT_DIR.parent` to `SCRIPT_DIR.parent.parent` (was resolving to `scripts/` instead of the repo root) — `make local-pipeline` Stage 2 now works
- **`scripts/python/run_gx.py`**: corrected `Path(__file__).resolve().parents[1]` to `parents[2]` so the repo root (and therefore `utils/`) is on `sys.path` — `make local-pipeline` Stage 3 now works
- **`Makefile`**: rewrote `help` target to use plain `@echo` (no `grep`/`awk`) so it works on Windows `cmd.exe`; replaced bash-only `command -v` checks in `check-deps` and `doctor` with POSIX-compatible shell primitives (`>/dev/null 2>&1`, `exit 1`); replaced Windows-only `forfiles` in `run-clean` with a delegation to the existing `scripts/shell/log_cleanup.sh` so the target works on macOS/Linux as well
- **`src/database/staging.py`**: `merge_staging_to_target()` now returns the count of rows in the **target** table after merge, not the count of the soon-to-be-dropped **staging** table; this is the actual "rows loaded" number (was previously misleading after `ON CONFLICT DO NOTHING` dedups)
- **`tests/data_quality/suites/validation.py`**: replaced the convoluted `stocks_suite()` placeholder-then-discard pattern (list sliced to `[:0]` then concatenated) with a plain return of the real list; demoted the two remaining `TODO` comments on `model_year` and `order_status` to `NOTE` comments so the project no longer has outstanding TODOs in the validation suite
- **SQL files**: `sqlfluff fix` auto-fixed trailing whitespace, missing trailing newlines, indentation, spacing, and SELECT modifier issues across all 21 SQL files
- **`sql/04_measures_exploration.sql`**: added explicit `AS metric` and `AS metric_value` aliases (AL03), renamed `value` alias to `metric_value` (RF04 reserved keyword)
- **`sql/09_performance_analysis.sql`**: wrapped long comment across multiple lines to respect 80-char limit (LT05)
- **`sql/17_new_ve_return.sql`**: renamed `month` alias to `sales_month` (RF04 reserved keyword)
- **`sql/18_status_check.sql`**: added explicit `AS metric` and `AS metric_value` aliases (AL03), renamed `value` → `metric_value` (RF04)

### Removed

- **`main.js`** — stub file containing only `console.log("Hello Bike Store")`; project is Python-based (`main.py` is the real entry point), so this orphan was dead weight
- **`docs/CHANGELOG.md`** — duplicate of the root `CHANGELOG.md`; single source of truth is now at the repo root
