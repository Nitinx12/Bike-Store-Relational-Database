@echo off
rem Bike Store — Windows mirror of the Makefile targets.
rem Usage: tasks.bat <target>   (run "tasks.bat" with no args to list targets)
setlocal
if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="setup" goto setup
if "%1"=="pipeline" goto pipeline
if "%1"=="pipeline-full" goto pipeline-full
if "%1"=="dq" goto dq
if "%1"=="gx" goto gx
if "%1"=="contracts" goto contracts
if "%1"=="dashboard" goto dashboard
if "%1"=="test" goto test
if "%1"=="test-unit" goto test-unit
if "%1"=="test-smoke" goto test-smoke
if "%1"=="lint" goto lint
if "%1"=="sql-lint" goto sql-lint
if "%1"=="lock" goto lock
if "%1"=="clean" goto clean
echo Unknown target: %1
goto help

:help
echo   setup           install dependencies
echo   pipeline        full pass: preflight, load, SQL checks, GX
echo   pipeline-full   truncate and reload every collection, then validate
echo   dq              SQL data-quality suite in FK order
echo   gx              Great Expectations suite (9 tables)
echo   contracts       refresh contracts/*.yml from Mongo schemas
echo   dashboard       local Streamlit dashboard
echo   test            unit + smoke suites
echo   test-unit       fast unit suite, no database needed
echo   test-smoke      live smoke suite (needs Postgres + MongoDB)
echo   lint            ruff, format check and mypy
echo   sql-lint        sqlfluff on every sql/ file
echo   lock            re-resolve dependencies
echo   clean           drop caches and bytecode
exit /b 0

:setup
uv sync
exit /b %errorlevel%

:pipeline
uv run python main.py
exit /b %errorlevel%

:pipeline-full
uv run python main.py --full
exit /b %errorlevel%

:dq
uv run python src/jobs/run_dq.py
exit /b %errorlevel%

:gx
uv run python scripts/run_gx.py
exit /b %errorlevel%

:contracts
uv run python scripts/update_contract.py
exit /b %errorlevel%

:dashboard
uv run streamlit run dashboard/home.py
exit /b %errorlevel%

:test
uv run pytest -q
exit /b %errorlevel%

:test-unit
uv run pytest tests/unit -q
exit /b %errorlevel%

:test-smoke
uv run pytest tests/smoke -q
exit /b %errorlevel%

:lint
uv run ruff check . && uv run ruff format --check . && uv run mypy .
exit /b %errorlevel%

:sql-lint
uv run sqlfluff lint sql/ --dialect postgres
exit /b %errorlevel%

:lock
uv lock && uv sync
exit /b %errorlevel%

:clean
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
if exist .pytest_cache rd /s /q .pytest_cache
exit /b 0
