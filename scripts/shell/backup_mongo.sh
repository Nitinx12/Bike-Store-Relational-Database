#!/usr/bin/env bash

# ============================================================================
# Bike Store ETL - MongoDB Backup
# ============================================================================
#
# Dumps all collections in the configured Mongo database to a timestamped
# directory under backups/mongo/. Uses mongodump (preferred) or docker compose
# exec if the mongodb service is running.
#
# Usage:
#   ./scripts/backup_mongo.sh
#   ./scripts/backup_mongo.sh /path/to/dir
#   ./scripts/backup_mongo.sh --help
# ============================================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

if [[ -t 1 ]]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN='' RED='' YELLOW='' BLUE='' BOLD='' RESET=''
fi

info() { printf "${BLUE}[INFO]${RESET} %s\n" "$1"; }
pass() { printf "${GREEN}[PASS]${RESET} %s\n" "$1"; }
fail() { printf "${RED}[FAIL]${RESET} %s\n" "$1" >&2; }

MONGO_URI="${MONGO_URI:-mongodb://127.0.0.1:27017}"
MONGO_DB="${MONGO_DB:-bike_store}"
BACKUP_DIR="${PROJECT_ROOT}/backups/mongo"

use_docker() {
    command -v docker >/dev/null 2>&1 && docker compose ps mongodb 2>/dev/null | grep -q "running"
}

mongodump_native() {
    local out_dir="$1"
    local native_bin=""
    if [[ -x "/mnt/c/Program Files/MongoDB/Tools/100/bin/mongodump.exe" ]]; then
        native_bin="/mnt/c/Program Files/MongoDB/Tools/100/bin/mongodump.exe"
    elif command -v mongodump >/dev/null 2>&1; then
        native_bin="mongodump"
    else
        return 1
    fi
    "$native_bin" --uri "$MONGO_URI" --db "$MONGO_DB" --out "$out_dir"
}

run_mongodump() {
    local out_dir="$1"
    if use_docker; then
        docker compose exec -T mongodb mongodump --db "$MONGO_DB" --out "/tmp/mongodump" >/dev/null 2>&1 \
            && docker compose cp mongodb:/tmp/mongodump "$out_dir" >/dev/null 2>&1 \
            && docker compose exec -T mongodb rm -rf /tmp/mongodump >/dev/null 2>&1
    else
        mongodump_native "$out_dir" || { fail "mongodump not installed locally and docker service is not running"; return 1; }
    fi
}

usage() {
    cat <<EOF
${BOLD}MongoDB Backup Utility${RESET}

Usage:
  $(basename "$0") [TARGET_DIR]       Dump to TARGET_DIR (default: ${BACKUP_DIR})
  $(basename "$0") --help
EOF
}

main() {
    local target_dir=""
    for arg in "$@"; do
        case "$arg" in
            --help|-h) usage; exit 0 ;;
            -*) fail "Unknown option: $arg"; usage; exit 1 ;;
            *) target_dir="$arg" ;;
        esac
    done

    [[ -n "$target_dir" ]] && BACKUP_DIR="$target_dir"
    mkdir -p "$BACKUP_DIR"

    local ts
    ts=$(date +"%Y%m%d_%H%M%S")
    local fpath="${BACKUP_DIR}/${MONGO_DB}_${ts}"

    info "Dumping Mongo database '${MONGO_DB}' from ${MONGO_URI}"
    info "Target: ${fpath}/"

    if run_mongodump "$fpath"; then
        pass "Backup complete: ${fpath}"
    else
        fail "Backup failed"
        rm -rf "$fpath"
        exit 1
    fi
}

main "$@"
