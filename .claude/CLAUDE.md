# CLAUDE.md

Guidance for Claude Code when working in **Bike-Store-Relational-Database** (MongoDB → PostgreSQL ETL pipeline built with PySpark).

## Project Snapshot
- Pipeline: `mongo_to_postgres.py` — PySpark, incremental loads, Rich terminal output
- Data quality: `plpgsql_tests.py` (PL/pgSQL test runner) + Great Expectations
- Orchestration: `scripts/ps1/local_runner.ps1` — color-coded summary table, `uv run`, UTF-8 fixes, `find_project_root()`
- Docs: `ARCHITECTURE.md` (Mermaid diagrams), `README.md` (~60 lines, skillicons.dev badges)
- CI: `.github/workflows/linting.yml`, `docker-build.yml`, `python-ci.yml`, `deploy.yml`
- Package manager: `uv` only — never call `pip install` directly

## Known Issues (current)
- None

When you fix one of the items above, update this section (move it to a "Resolved" note or delete the line) in the same commit that fixes it.

## Changelog Discipline
Every change touching pipeline behavior, schema, CI, or docs gets an entry in `CHANGELOG.md`, in the same commit:
- Add entries under `## [Unreleased]`, grouped as `### Added / Changed / Fixed / Removed`
- One line per change, imperative mood, name the file(s) touched
  - e.g. `- Fixed: cast updated_at to timestamp in mongo_to_postgres.py`
- Do not batch unrelated changes into one changelog line
- Never commit a fix without a matching changelog line

## Git Workflow
- Stage intentionally: `git add <specific files>` — avoid `git add .` unless you just reviewed the full diff
- Commit message format: `<type>: <short summary>` (types: feat, fix, chore, docs, ci, test)
- One logical change per commit; `CHANGELOG.md` update goes in the same commit, not a follow-up
- Sequence before every push: `git status` → `git diff --staged` → confirm `CHANGELOG.md` updated → commit → push
- Never force-push to `main`

```bash
git add src/mongo_to_postgres.py CHANGELOG.md
git commit -m "fix: cast updated_at/shipped_date to proper types"
git push origin <branch>
```

## Code Style

**Python**
- `uv run` for execution, `uv add` / `uv remove` for dependencies — never edit `requirements.txt` by hand
- Type hints on every function signature; `ruff` + `mypy` must pass (see `python-ci.yml`)
- Rich for terminal output, not bare `print()`

**PowerShell (.ps1)**
- Set UTF-8 output explicitly at the top of the script
- Use the `find_project_root()` pattern instead of hardcoded paths
- Color-coded summary table for pipeline results; wrap external calls in try/catch

**Bash**
- `set -euo pipefail` at the top of every script
- Quote all variable expansions

**SQL**
- Dialect: `postgres` (SQLFluff `dialect = postgres`, not `ansi`)
- Cast style: `column::VARCHAR`, not `CAST(column AS VARCHAR)`
- snake_case for all identifiers, consistent keyword casing per file

**Docs**
- No hyphens in prose sentences (list dashes are fine)