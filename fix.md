# Bike Store Pipeline — Fix Log & Current Status

**Overall status:** 3 of 3 root causes fixed. Data migration (steps 3–7) pending user execution.

---

## Summary of Changes Made

### Committed in `606d04e`

| File | Change |
|------|--------|
| `docker-compose.yml` | Fixed `MONGO_URI` default: `host.docker.internal` → `mongodb://mongodb:27017` |
| `docker-compose.yml` | Fixed broken `POSTGRES_DATABASE` default (had literal space character) |
| `scripts/backup_mongo.sh` | Default `MONGO_URI`: `localhost` → `127.0.0.1` to avoid dual-listener ambiguity on Windows |
| `scripts/backup_mongo.sh` | Added `mongodump` detection at standard Windows path (`C:\Program Files\MongoDB\Tools\100\bin\`) |
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

**Status:** ⚠️ Partial — backups secured, migration pending

**Root cause:** Native PostgreSQL (PID 7408) and MongoDB (PID 18568) Windows Services were binding ports 5432/27017 alongside Docker's proxies. Both `uv run main.py` and `docker compose run` worked — they just talked to different databases.

---

### Pre-Migration Discovery: mongodump `localhost` Resolution Bug

While running `make backup-mongo`, a secondary bug was found and fixed in the same commit:

- On Windows, `localhost` resolves to whichever process binds the port first
- Docker Desktop's `com.docker.backend` (PID 8244) binds port 27017 on `::` (IPv6 all interfaces)
- Native mongod (PID 18568) binds on `0.0.0.0` (IPv4)
- mongodump (Windows binary, called from WSL bash) resolved `localhost` to Docker's empty MongoDB → exit 0 with 0 files
- Python's pymongo resolved `localhost` to native mongod → found the seeded data correctly

**Fix:** Both `backup_mongo.sh` and `restore_mongo.sh` now default to `mongodb://127.0.0.1:27017` (explicit IPv4) to bypass the dual-listener ambiguity.

---

### What Was Done

#### Backups secured (Step 1 ✅)

| Database | File | Size | Tables/Collections | Status |
|----------|------|------|---------------------|--------|
| PostgreSQL | `backups/postgres/bike_store_20260905_101833.sql.gz` | 103 KB | 9 tables | ✅ 9 COPY statements confirmed |
| MongoDB | `backups/mongo/bike_store_native/bike_store/` | 1.5 MB | 9 collections, 9072 docs | ✅ All 9 collections dumped |

MongoDB collections: `brands` (10), `categories` (7), `customers` (1445), `order_items` (4722), `orders` (1615), `products` (321), `staffs` (10), `stocks` (939), `stores` (3)

---

## Current Pipeline State

### Test/query logic
- ✅ `06_test_orphan_and_business_rules.sql` — fixed (removed invalid regex on bigint)
- ✅ `08_test_staffs.sql` — fixed (added actual self-management check)
- ✅ All 10 SQL loop tests (01–10) — committed

### Docker networking
- ✅ `docker-compose.yml` `MONGO_URI` default fixed
- ✅ `backup_mongo.sh` / `restore_mongo.sh` patched for Windows path detection

### Data source of truth
- ⚠️ **Still split** — native Windows services (PostgreSQL PID 7408, MongoDB PID 18568) vs Docker containers
- Until migration steps 3–7 are executed, `docker compose run` and `uv run main.py` will report different results

---

## Next Steps (Steps 3–7 — User Manual Execution)

These must be done manually with verification at each step:

### Step 3 — Stop native Windows services
```powershell
# Find service names
Get-Service | Where-Object {$_.Name -match 'MongoDB|PostgreSQL'}

# Stop each (replace <name> with actual service name)
Stop-Service -Name "<name>" -Force

# Verify only Docker remains listening
netstat -ano | findstr ":5432 :27017"
```
Expected: Only PID 8244 (Docker) on `0.0.0.0` for each port.

### Step 4 — Confirm `localhost` is now unambiguous
```bash
# Should show only Docker's proxy
netstat -ano | findstr ":5432 :27017"
```

### Step 5 — Restore real data into Docker containers (DESTRUCTIVE)
```bash
# Restore MongoDB
make restore-mongo ARGS="backups/mongo/bike_store_native"

# Restore PostgreSQL
make restore-postgres ARGS="backups/postgres/bike_store_20260905_101833.sql.gz"
```
⚠️ Both prompts will ask for confirmation — this is expected for destructive operations.

### Step 6 — Verify both run paths agree
```bash
# Docker run
docker compose --profile jobs run --rm app pipeline

# Local run
uv run main.py
```
Expected: 10/10 PL/pgSQL checks + 9/9 GX suites passing on both.

### Step 7 — Prevent port conflict recurrence
```powershell
# Set native services to Manual startup
Set-Service -Name "<MongoDB_service>" -StartupType Manual
Set-Service -Name "<PostgreSQL_service>" -StartupType Manual
```

---

## Optional Cleanup

The `backups/` directory is not currently in `.gitignore`. Consider adding:
```
backups/
```
to prevent accidentally committing dump files.

---

*Last updated: 2026-09-05*
