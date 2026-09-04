#!/usr/bin/env bash

# ============================================================================
# Bike Store ETL - MongoDB Restore
# ============================================================================
#
# Restores a mongodump directory produced by backup_mongo.sh into the
# configured Mongo database. DESTRUCTIVE — drops the database first.
#
# Usage:
#   ./scripts/restore_mongo.sh <backup_dir>
#   ./scripts/restore_mongo.sh /backups/mongo/bike_store_20240101_120000
#   ./scripts/restore_mongo.sh --help
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
warn() { printf "${YELLOW}[WARN]${RESET} %s\n" "$1" >&2; }
fail() { printf "${RED}[FAIL]${RESET} %s\n" "$1" >&2; }

MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
MONGO_DB="${MONGO_DB:-bike_store}"

use_docker() {
    command -v docker >/dev/null 2>&1 && docker compose ps mongodb 2>/dev/null | grep -q "running"
}

run_mongorestore() {
    local src="$1"
    if use_docker; then
        docker compose cp "$src" mongodb:/tmp/mongorestore >/dev/null 2>&1 \
            && docker compose exec -T mongodb mongorestore --drop --db "$MONGO_DB" "/tmp/mongorestore/${MONGO_DB}" >/dev/null 2>&1 \
            && docker compose exec -T mongodb rm -rf /tmp/mongorestore >/dev/null 2>&1
    else
        command -v mongorestore >/dev/null 2>&1 || { fail "mongorestore not installed locally and docker service is not running"; return 1; }
        mongorestore --uri "$MONGO_URI" --drop --db "$MONGO_DB" "${src}/${MONGO_DB}"
    fi
}

usage() {
    cat <<EOF
${BOLD}MongoDB Restore Utility${RESET}

Usage:
  $(basename "$0") <backup_dir>     Restore from the named backup directory
  $(basename "$0") --help

WARNING: DESTRUCTIVE — drops the '${MONGO_DB}' database before restoring.
EOF
}

main() {
    local target=""
    for arg in "$@"; do
        case "$arg" in
            --help|-h) usage; exit 0 ;;
            -*) fail "Unknown option: $arg"; usage; exit 1 ;;
            *) target="$arg" ;;
        esac
    done

    if [[ -z "$target" ]]; then
        fail "No backup directory specified"
        usage
        exit 1
    fi

    if [[ ! -d "$target" ]]; then
        fail "Backup directory not found: $target"
        exit 1
    fi

    warn "This will DROP and RECREATE the '${MONGO_DB}' database."
    warn "Source: $target"
    local confirm=""
    read -r -p $'\nProceed? [y/N] ' confirm
    case "$confirm" in
        y|Y|yes|YES) ;;
        *) info "Aborted. No changes made."; exit 0 ;;
    esac

    info "Restoring '${MONGO_DB}' from ${target}..."
    if run_mongorestore "$target"; then
        pass "Restore complete"
    else
        fail "Restore failed"
        exit 1
    fi
}

main "$@"
