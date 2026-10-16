# Contributing

## Branches and commits

- Work on `type/slug` branches (`feat/…`, `fix/…`, `chore/…`, `docs/…`,
  `test/…`); direct commits to `main` are blocked by `.githooks/pre-commit`
  (emergency bypass: `ALLOW_COMMIT_TO_MAIN=1`).
- Conventional Commits, lowercase subject, no trailing period:
  `feat(pipeline): add retry to loader`, `fix(dashboard): handle empty filter`.
- Order multi-commit work foundation-first: cleanup → pipeline → tests →
  dashboard → sql/docs.

## Gates (run before you push)

```bash
tasks.bat lint        # ruff check + format check + mypy (also on commit)
tasks.bat test        # all 18 tests (also on push)
tasks.bat sql-lint    # if you touched sql/
```

The pre-push hook additionally runs the import smoke test and
`uv lock --check` — keep `uv.lock` in sync (`uv lock`) whenever
`pyproject.toml` changes.

## Conventions

- SQL: `sqlfluff` postgres dialect, UPPER keywords, one statement per
  purpose; analysis queries numbered (`sql/analysis/NN_name.sql`).
- Python: typed function signatures, stage-boundary `try/except` with
  `# noqa: BLE001` and a logged message, no secrets in code.
- Dashboard: SQL only in `dashboard/helpers/queries.py` (parameterized,
  aggregated in Postgres); pages stay thin renderers.
- Never commit `.env`, `secrets.toml`, `logs/`, or `__pycache__/` —
  all gitignored. Check `git status` before every commit.
