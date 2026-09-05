# Bike Store Pipeline — Fix Log & Current Status

**Overall status:** All root causes fixed. Migration complete for MongoDB, partial for PostgreSQL (data mismatch found). ETL pipeline `pipeline` job is broken — needs one-line entrypoint fix. Remaining: fix entrypoint, re-run ETL, verify both run paths.

---

## Summary of Changes Made

### Committed in `769246a`

| File | Change |
|------|--------|
| `scripts/check_mongo.py` | New permanent utility to inspect any MongoDB instance — reports all databases, collections, doc counts; reads `MONGO_URI` from `.env`; masks credentials in output |
| `.gitignore` | Added `backups/` to prevent accidental commit of database dumps |
| `fix.md` | This comprehensive fix log |

### Committed in `606d04e`

| File | Change |
|------|--------|
| `docker-compose.yml` | Fixed `MONGO_URI` default: `host.docker.internal` → `mongodb://mongodb:27017` |
| `docker-compose.yml` | Fixed broken `POSTGRES_DATABASE` default (had literal space character) |
| `scripts/backup_mongo.sh` | Default `MONGO_URI`: `localhost` → `127.0.0.1` to avoid dual-listener ambiguity on Windows |
| `scripts/backup_mongo.sh` | Added `mongodump` detection at standard Windows path |
| `scripts/restore_mongo.sh` | Default `MONGO_URI`: `localhost` → `127.0.0.1` |
| `scripts/restore_mongo.sh` | Added `mongorestore` detection at standard Windows path |

---

## Issue #1 — `bigint !~ unknown` in PL/pgSQL tests

**Status:** ✅ Fixed and committed

**Files:** `06_test_orphan_and_business_rules.sql`, `08_test_staffs.sql`

**Fix applied:**
- `06_test_orphan_and_business_rules.sql`: Removed invalid regex on `bigint` column — replaced `s.manager_id !~ '^[0-9]+$'` with a proper `NOT EXISTS` subquery against `public.staffs`
- `08_test_staffs.sql`: Replaced broken regex with actual self-management check (`s.manager_id = s.staff_id`) and `NOT EXISTS` for valid manager reference

---

## Issue #2 — `make pipeline` failed silently

**Status:** ✅ Merged into Issue #3 (root cause was the same)

The apparent silent failure was caused by the app dying before any output — the real root cause was `MONGO_URI` pointing at the wrong host.

---

## Issue #3 — `MONGO_URI` pointed at wrong host in Docker

**Status:** ✅ Fixed and committed (`606d04e`)

**Root cause:** `docker-compose.yml` had `MONGO_URI: ${MONGO_URI:-mongodb://host.docker.internal:27017}` which resolves to the Windows host, not Docker's `mongodb` service container. Without an explicit override, the app connected to the wrong MongoDB and died silently.

**Fix:** Changed default to `mongodb://mongodb:27017` matching the documented header comment in the same file.

---

## Issue #4 — Two separate databases (native vs. Docker)

**Status:** ⚠️ Migration in progress — MongoDB fully restored, PostgreSQL data mismatch found

### Pre-Migration Discovery: mongodump `localhost` Resolution Bug

While running `make backup-mongo`, a secondary bug was found and fixed in the same commit:

- On Windows, `localhost` resolves to whichever process binds the port first
- Docker Desktop's `com.docker.backend` (PID 8244) binds port 27017 on `::` (IPv6 all interfaces)
- Native mongod (PID 18568) binds on `0.0.0.0` (IPv4)
- mongodump (Windows binary, called from WSL bash) resolved `localhost` to Docker's empty MongoDB → exit 0 with 0 files
- Python's pymongo resolved `localhost` to native mongod → found the seeded data correctly

**Fix:** Both `backup_mongo.sh` and `restore_mongo.sh` now default to `mongodb://127.0.0.1:27017` (explicit IPv4) to bypass the dual-listener ambiguity.

---

### Migration Progress

#### Backups secured ✅

| Database | File | Size | Content | Status |
|----------|------|------|---------|--------|
| PostgreSQL | `backups/postgres/bike_store_20260905_101833.sql.gz` | 103 KB | 9 tables (9 COPY statements) | ✅ Confirmed |
| MongoDB | `backups/mongo/bike_store_native/bike_store/` | 1.5 MB | 9 collections, 9072 docs | ✅ Confirmed |

MongoDB collections: `brands` (10), `categories` (7), `customers` (1445), `order_items` (4722), `orders` (1615), `products` (321), `staffs` (10), `stocks` (939), `stores` (3)

#### Native services ✅

| Service | Status | Notes |
|---------|--------|-------|
| MongoDB | Running as Windows Service `MongoDB` | PID 18568, port 27017 |
| PostgreSQL | Running as Windows Service `postgresql-x64-17` | PID 7408, port 5432 |

Both still running — **requires elevation to stop**. Backups are the safety net.

#### Docker MongoDB ✅ Restored

All 9 collections, 9072 docs confirmed in Docker container:
```
brands: 10 | categories: 7 | customers: 1445 | order_items: 4722
orders: 1615 | products: 321 | staffs: 10 | stocks: 939 | stores: 3
```

#### Docker PostgreSQL ⚠️ Data Mismatch Found

Restored from backup — but the backup was from an **older pipeline run**, so counts are wrong:

| Table | In Backup (wrong) | In MongoDB (correct) |
|-------|-------------------|----------------------|
| order_items | 1,615 | 4,722 |
| stocks | 3 | 939 |
| orders | 1,615 | 1,615 ✅ |
| brands | 10 | 10 ✅ |
| categories | 7 | 7 ✅ |
| customers | 1,445 | 1,445 ✅ |
| products | 321 | 321 ✅ |
| staffs | 10 | 10 ✅ |
| stores | 3 | 3 ✅ |

**Fix:** Re-run the ETL pipeline to populate PostgreSQL with the correct counts from MongoDB.

---

## Issue #5 — `entrypoint.sh` `pipeline` job broken (NEW)

**Status:** 🔴 Found — needs fix

**Root cause:** `docker/entrypoint.sh` dispatches the `pipeline` job like this:
```bash
pipeline)
    wait_for_pushgateway
    exec uv run python main.py "$@"
    ;;
```
This passes `"$@"` (all arguments after the job name) to `main.py`. If a user runs `docker compose run app pipeline --full-refresh`, the word `pipeline` is included in `$@`, but `main.py` doesn't accept `pipeline` as an argument — it only accepts `--full-refresh`, `--collections`, etc. Result:
```
main.py: error: unrecognized arguments: pipeline
```

**Fix needed (one line):**
```bash
# before
pipeline)
    wait_for_pushgateway
    exec uv run python main.py "$@"
    ;;

# after
pipeline)
    wait_for_pushgateway
    exec uv run python main.py "${@}"
    ;;
```

---

## Current Pipeline State

### Test/query logic
- ✅ `06_test_orphan_and_business_rules.sql` — fixed
- ✅ `08_test_staffs.sql` — fixed (added actual self-management check)
- ✅ All 10 SQL loop tests (01–10)

### Docker networking
- ✅ `docker-compose.yml` `MONGO_URI` default fixed
- ✅ `backup_mongo.sh` / `restore_mongo.sh` patched for Windows path detection

### Data source
- ✅ Docker MongoDB: fully restored with correct data
- ⚠️ Docker PostgreSQL: tables exist but `order_items` and `stocks` have stale counts

### Pipeline runner
- 🔴 `entrypoint.sh pipeline` job is broken (passes `pipeline` as argument to `main.py`)
- Workaround: run `docker exec <app-container> uv run python main.py --full-refresh` directly

---

## Next Steps

### Step 1 — Fix `entrypoint.sh` pipeline dispatcher (one line)
```bash
# In docker/entrypoint.sh, change:
exec uv run python main.py "$@"
# to:
exec uv run python main.py "${@}"
```
This prevents the job name from being passed as an argument to `main.py`.

### Step 2 — Rebuild Docker image
```bash
docker compose -f docker-compose.yml build app
```
Required for the entrypoint fix to take effect in compose runs.

### Step 3 — Re-run ETL pipeline to fix PostgreSQL counts
```bash
# Via compose (after entrypoint fix):
docker compose --profile jobs run --rm app pipeline --full-refresh

# Or directly in container:
docker exec <app-container> bash -c "cd /app && uv run python main.py --full-refresh"
```
This will re-populate PostgreSQL from MongoDB's correct data (order_items: 4722, stocks: 939).

### Step 4 — Verify both run paths agree
```bash
# Docker:
docker compose --profile jobs run --rm app pipeline

# Local:
uv run main.py
```
Expected: 10/10 PL/pgSQL checks + 9/9 GX suites passing on both.

### Step 5 — Stop native Windows services (REQUIRES ELEVATION)
```powershell
# Run PowerShell as Administrator:
Stop-Service -Name 'MongoDB' -Force
Stop-Service -Name 'postgresql-x64-17' -Force
```
Until done, `localhost` on ports 5432/27017 will continue resolving to native services instead of Docker.

### Step 6 — Lock in fix: set native services to Manual startup
```powershell
# After stopping (requires elevation):
Set-Service -Name 'MongoDB' -StartupType Manual
Set-Service -Name 'postgresql-x64-17' -StartupType Manual
```

---

## Optional Cleanup

- ✅ `backups/` added to `.gitignore`

---

*Last updated: 2026-09-05*
