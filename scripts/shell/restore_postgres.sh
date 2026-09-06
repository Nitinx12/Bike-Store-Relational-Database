#!/usr/bin/env bash

# ============================================================================
# Bike Store ETL - Postgres Restore
# ============================================================================
#
# Restores a backup file produced by backup_postgres.sh into the bike_store
# database. DESTRUCTIVE — drops the existing database before restoring.
#
# Usage:
#   ./scripts/restore_postgres.sh <backup.sql.gz>
#   ./scripts/restore_postgres.sh /backups/bike_store_20240101_120000.sql.gz
#   ./scripts/restore_postgres.sh --list               List available backups
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

use_docker() {
    command -v docker >/dev/null 2>&1 && docker compose ps postgres 2>/dev/null | grep -q "running"
}

run_psql() {
    if use_docker; then
        docker compose exec -T postgres psql -U "$POSTGRES_USERNAME" "$@"
    else
        psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME" "$@"
    fi
}

run_psql_db() {
    local db="$1"; shift
    if use_docker; then
        docker compose exec -T postgres psql -U "$POSTGRES_USERNAME" -d "$db" "$@"
    else
        psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME" -d "$db" "$@"
    fi
}

list_backups() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        warn "Backup directory not found: $BACKUP_DIR"
        return 0
    fi
    echo -e "${BOLD}Available backups in ${BACKUP_DIR}:${RESET}"
    ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || warn "  (none)"
}

usage() {
    cat <<EOF
${BOLD}Postgres Restore Utility${RESET}

Usage:
  $(basename "$0") <backup.sql.gz>     Restore the named backup (DESTRUCTIVE)
  $(basename "$0") --list              List available backups
  $(basename "$0") --help

WARNING: This script drops the '${POSTGRES_DATABASE}' database before
restoring. All existing data will be lost.
EOF
}

main() {
    local target=""
    for arg in "$@"; do
        case "$arg" in
            --list) list_backups; exit 0 ;;
            --help|-h) usage; exit 0 ;;
            -*) fail "Unknown option: $arg"; usage; exit 1 ;;
            *) target="$arg" ;;
        esac
    done

    if [[ -z "$target" ]]; then
        fail "No backup file specified"
        usage
        exit 1
    fi

    if [[ ! -f "$target" ]]; then
        fail "Backup file not found: $target"
        exit 1
    fi

    warn "This will DROP and RECREATE the '${POSTGRES_DATABASE}' database."
    warn "Source: $target"
    local confirm=""
    read -r -p $'\nProceed? [y/N] ' confirm
    case "$confirm" in
        y|Y|yes|YES) ;;
        *) info "Aborted. No changes made."; exit 0 ;;
    esac

    info "Terminating active connections to '${POSTGRES_DATABASE}'..."
    run_psql -d postgres -c "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '${POSTGRES_DATABASE}' AND pid <> pg_backend_pid();" >/dev/null 2>&1 || true

    info "Dropping database '${POSTGRES_DATABASE}'..."
    run_psql -d postgres -c "DROP DATABASE IF EXISTS \"${POSTGRES_DATABASE}\";" >/dev/null 2>&1
    info "Creating database '${POSTGRES_DATABASE}'..."
    run_psql -d postgres -c "CREATE DATABASE \"${POSTGRES_DATABASE}\";" >/dev/null 2>&1

    info "Restoring from ${target}..."
    if gunzip -c "$target" | run_psql_db "$POSTGRES_DATABASE" >/dev/null 2>&1; then
        pass "Restore complete: ${POSTGRES_DATABASE}"
    else
        fail "Restore failed"
        exit 1
    fi
}

main "$@"
