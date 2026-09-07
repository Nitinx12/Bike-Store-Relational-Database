# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `CHANGELOG.md` — project changelog for tracking notable changes

### Changed

- **`src/pipeline/decision.py`**: flattened nested `if` → single `if` with `and` (SIM102)
- **`src/pipeline/runner.py`**: replaced `datetime.now()` with `datetime.now(timezone.utc)` (DTZ005), rewrote `dict()` literals as `{}` (C408), replaced blind `except Exception` with `PyMongoError`/`SQLAlchemyError` (BLE001), added `log.warning()` for best-effort staging cleanup instead of silent `pass` (S110)
- **`src/pipeline/mongo_source.py`**: replaced `except Exception` with `PyMongoError` (BLE001), added `PyMongoError` import
- **`src/database/stats.py`**: replaced `except Exception` with `SQLAlchemyError` (BLE001), added import
- **`src/validation/plpgsql_loops.py`**: replaced `except Exception` with `psycopg2.Error` (BLE001), added import
- **`main.py`**: replaced `except Exception` with `(OSError, ValueError, TypeError, AttributeError)` for GX setup (BLE001), replaced `datetime.now()` with `datetime.now(timezone.utc)` (DTZ005), added `timezone` import
- **`scripts/python/mongo_to_postgres.py`**: replaced all `except Exception` with `PyMongoError`/`SQLAlchemyError` (BLE001), `datetime.now()` → `datetime.now(timezone.utc)` (DTZ005), `dict()` → `{}` literals (C408), added `log.warning()` for staging cleanup instead of `pass` (S110), replaced `.replace("Z", "+00:00")` with `.removesuffix("Z")` (FURB162), added `PyMongoError` import
- **`scripts/python/check_mongo.py`**: sorted imports alphabetically (I001), replaced `except Exception` with `(ConnectionFailure, OperationFailure, ServerSelectionTimeoutError)` (BLE001)
- **`scripts/python/plpgsql_loops_tests.py`**: fixed import order (I001), replaced `except Exception` with `psycopg2.Error`/`SQLAlchemyError` (BLE001)
- **`tests/data_quality/run.py`**: replaced `except Exception` with `(OSError, ValueError, TypeError, RuntimeError)` (BLE001), `datetime.now()` → `datetime.now(timezone.utc)` (DTZ005), added `timezone` import
- **`utils/logger.py`**: replaced `datetime.now()` with `datetime.now(timezone.utc)` (DTZ005), added `timezone` import
- **`utils/metrics.py`**: replaced `except Exception` with `(OSError, ValueError, TimeoutError)` for Prometheus pushgateway errors (BLE001)

### Fixed

- **SQL files**: `sqlfluff fix` auto-fixed trailing whitespace, missing trailing newlines, indentation, spacing, and SELECT modifier issues across all 21 SQL files
- **`sql/04_measures_exploration.sql`**: added explicit `AS metric` and `AS metric_value` aliases (AL03), renamed `value` alias to `metric_value` (RF04 reserved keyword)
- **`sql/09_performance_analysis.sql`**: wrapped long comment across multiple lines to respect 80-char limit (LT05)
- **`sql/17_new_ve_return.sql`**: renamed `month` alias to `sales_month` (RF04 reserved keyword)
- **`sql/18_status_check.sql`**: added explicit `AS metric` and `AS metric_value` aliases (AL03), renamed `value` → `metric_value` (RF04)
