# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- Fixed: Cast `updated_at` to proper types in `scripts/python/mongo_to_postgres.py`
- Fixed: Resolved data casting errors (empty string to NULL) in `scripts/python/mongo_to_postgres.py`
- Fixed: Corrected `tests/generic/loops/01_test_brands.sql` to reference `brands` instead of `categories`

### Changed
- Refactored: Reorganized `scripts/` folder into language-specific subdirectories (`python/`, `ps1/`, `shell/`)
- Changed: Updated `docker/entrypoint.sh` and `scripts/ps1/local_runner.ps1` to reflect new script paths
- Changed: Updated `docs/scripts.md` and `.claude/CLAUDE.md` to reflect new organization
