#!/usr/bin/env bash
# Internal wrapper: restore PostgreSQL dump into Docker container via compose exec.
# Handles the DROP + RESTORE in a single non-interactive call.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_DIR="${PROJECT_ROOT}"

SRC_FILE="${1:-${PROJECT_ROOT}/backups/postgres/bike_store_20260905_101833.sql.gz}"

if [[ ! -f "${SRC_FILE}" ]]; then
    echo "[FAIL] Source file not found: ${SRC_FILE}"
    exit 1
fi

cd "${COMPOSE_DIR}" || exit 1

echo "[WARN] This will DROP all tables in 'bike_store' and restore from:"
echo "[WARN]   ${SRC_FILE}"
echo ""

PGUSER="${POSTGRES_USERNAME:-postgres}"
PGDB="${POSTGRES_DATABASE:-bike_store}"

echo "[INFO] Dropping and recreating database '${PGDB}' ..."
if ! docker compose exec -T postgres psql -U "${PGUSER}" -c "DROP DATABASE IF EXISTS \"${PGDB}\";" 2>&1; then
    echo "[FAIL] Could not drop database"
    exit 1
fi
if ! docker compose exec -T postgres psql -U "${PGUSER}" -c "CREATE DATABASE \"${PGDB}\";" 2>&1; then
    echo "[FAIL] Could not create database"
    exit 1
fi

echo "[INFO] Restoring from ${SRC_FILE} ..."
if ! gunzip -c "${SRC_FILE}" | docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" 2>&1; then
    echo "[FAIL] Restore failed"
    exit 1
fi

echo ""
echo "[PASS] PostgreSQL restore complete"
echo ""
echo "[INFO] Verification: tables in Docker PostgreSQL '${PGDB}':"
docker compose exec -T postgres psql -U "${PGUSER}" -d "${PGDB}" -c \
    "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;" 2>&1