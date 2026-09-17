<-- Thank you for contributing! Delete sections that don't apply. -->

## Summary

<!-- What does this PR change and why? Link issues: Closes #123 -->

## Type

- [ ] `feat:` new pipeline / query / script
- [ ] `fix:` bug fix (link bug issue)
- [ ] `chore:` tooling / deps / Docker
- [ ] `refactor:` no behavior change
- [ ] `docs:` / `test:` only
- [ ] `BREAKING CHANGE:`

## Checklist

- [ ] `uv lock` is in sync (`make check-deps` passes)
- [ ] `uv run ruff check . && uv run mypy . && uv run pytest` passes
- [ ] `uv run sqlfluff lint sql/ --dialect postgres` passes (if `sql/` touched)
- [ ] GX suites / PL/pgSQL loops still pass (`uv run python main.py` or `make run`)
- [ ] No secrets or `.env` values committed
- [ ] Commit messages follow Conventional Commits (`feat:`, `fix:` …)

## Screenshots / Logs

<!-- Paste relevant `main.py` summary, GX report, or Grafana screenshot -->

## Risk & Rollback

<!-- What could break (schema, incremental watermark, volume)? How to revert? -->
