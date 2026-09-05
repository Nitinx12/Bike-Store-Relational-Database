#!/usr/bin/env bash
# Internal wrapper: restore native MongoDB dump into Docker container via compose exec.
# Bypasses the dual-listener port issue by going through docker compose cp/exec.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_DIR="${PROJECT_ROOT}"

SRC_DIR="${1:-${PROJECT_ROOT}/backups/mongo/bike_store_native}"

if [[ ! -d "${SRC_DIR}" ]]; then
    echo "[FAIL] Source directory not found: ${SRC_DIR}"
    exit 1
fi

if [[ ! -d "${SRC_DIR}/bike_store" ]]; then
    echo "[FAIL] Expected ${SRC_DIR}/bike_store (mongodump output structure)"
    exit 1
fi

cd "${COMPOSE_DIR}" || exit 1

echo "[INFO] Copying ${SRC_DIR} into mongodb:/tmp/mongorestore ..."
if ! docker compose cp "${SRC_DIR}" mongodb:/tmp/mongorestore 2>&1; then
    echo "[FAIL] docker compose cp failed"
    exit 1
fi

echo "[INFO] Running mongorestore --drop --db bike_store ..."
if ! docker compose exec -T mongodb mongorestore --drop --db bike_store "/tmp/mongorestore/bike_store" 2>&1; then
    echo "[FAIL] mongorestore failed"
    docker compose exec -T mongodb rm -rf /tmp/mongorestore 2>&1 || true
    exit 1
fi

echo "[INFO] Cleaning up /tmp/mongorestore in container ..."
docker compose exec -T mongodb rm -rf /tmp/mongorestore 2>&1

echo ""
echo "[PASS] MongoDB restore complete"
echo ""
echo "[INFO] Verification: collections in Docker MongoDB bike_store:"
docker compose exec -T mongodb mongosh --quiet --eval 'db.getCollectionNames().forEach(c => print(c + ": " + db.getCollection(c).countDocuments({}) + " docs"))' bike_store 2>&1