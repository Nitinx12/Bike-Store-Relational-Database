#!/usr/bin/env bash

# ============================================================================
# Bike Store ETL - Postgres Backup
# ============================================================================
#
# Dumps the bike_store database to a timestamped SQL file in the backups/
# directory. Uses docker compose if the postgres service is running, otherwise
# falls back to the local pg_dump binary.
#
# Usage:
#   ./scripts/backup_postgres.sh                          Backup to default location
#   ./scripts/backup_postgres.sh /path/to/dir             Backup to a custom directory
#   ./scripts/backup_postgres.sh --schema-only            Dump schema only
#   ./scripts/backup_postgres.sh --data-only              Dump data only
#   ./scripts/backup_postgres.sh --help
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

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USERNAME="${POSTGRES_USERNAME:-postgres}"
POSTGRES_DATABASE="${POSTGRES_DATABASE:-bike_store}"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"

BACKUP_DIR="${PROJECT_ROOT}/backups/postgres"
EXTRA_ARGS=()

use_docker() {
    command -v docker >/dev/null 2>&1 && docker compose ps postgres 2>/dev/null | grep -q "running"
}

run_pg_dump() {
    if use_docker; then
        docker compose exec -T postgres pg_dump -U "$POSTGRES_USERNAME" "$@"
    else
        pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME" "$@"
    fi
}

usage() {
    cat <<EOF
${BOLD}Postgres Backup Utility${RESET}

Usage:
  $(basename "$0") [TARGET_DIR] [--schema-only] [--data-only]

Arguments:
  TARGET_DIR     Output directory (default: ${BACKUP_DIR})
  --schema-only  Dump schema only (no data)
  --data-only    Dump data only (no schema)

Examples:
  $(basename "$0")
  $(basename "$0") /tmp/pg-backups
  $(basename "$0") --schema-only
  $(basename "$0") /var/backups/bike_store --data-only
EOF
}

main() {
    local target_dir=""
    for arg in "$@"; do
        case "$arg" in
            --help|-h) usage; exit 0 ;;
            --schema-only|--data-only) EXTRA_ARGS+=("$arg") ;;
            -*) fail "Unknown option: $arg"; usage; exit 1 ;;
            *) target_dir="$arg" ;;
        esac
    done

    [[ -n "$target_dir" ]] && BACKUP_DIR="$target_dir"
    mkdir -p "$BACKUP_DIR"

    local ts
    ts=$(date +"%Y%m%d_%H%M%S")
    local fname="${POSTGRES_DATABASE}_${ts}.sql.gz"
    local fpath="${BACKUP_DIR}/${fname}"

    info "Dumping '${POSTGRES_DATABASE}' from ${POSTGRES_HOST}:${POSTGRES_PORT}"
    info "Target file: ${fpath}"

    if run_pg_dump -d "$POSTGRES_DATABASE" "${EXTRA_ARGS[@]}" | gzip > "$fpath"; then
        local size
        size=$(du -h "$fpath" | cut -f1)
        pass "Backup complete (${size}): ${fpath}"
    else
        fail "Backup failed"
        rm -f "$fpath"
        exit 1
    fi
}

main "$@"
