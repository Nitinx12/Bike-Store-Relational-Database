#!/usr/bin/env bash

# ============================================================================
# Bike Store ETL - First-Run Database Initializer
# ============================================================================
#
# Responsibilities:
#   1. Wait for the Postgres container to be ready
#   2. Create the bike_store database (idempotent)
#   3. Create the bike_store_mongo collection group on Mongo (no-op if present)
#   4. Verify connectivity from the app's perspective
#
# Usage:
#   ./scripts/init_db.sh                Run against the docker-compose stack
#   ./scripts/init_db.sh --local        Run against a local install (no docker)
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
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN='' RED='' YELLOW='' BLUE='' CYAN='' BOLD='' RESET=''
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

MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
MONGO_DB="${MONGO_DB:-bike_store}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

run_psql() {
    if command -v docker >/dev/null 2>&1 && docker compose ps postgres >/dev/null 2>&1; then
        docker compose exec -T postgres psql -U "$POSTGRES_USERNAME" "$@"
    else
        psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME" "$@"
    fi
}

run_mongosh() {
    if command -v docker >/dev/null 2>&1 && docker compose ps mongodb >/dev/null 2>&1; then
        docker compose exec -T mongodb mongosh "$MONGO_DB" --quiet "$@"
    else
        mongosh "$MONGO_URI/$MONGO_DB" --quiet "$@"
    fi
}

wait_for_postgres() {
    info "Waiting for PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}..."
    local i=0
    while (( i < 30 )); do
        if run_psql -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
            pass "PostgreSQL is responding"
            return 0
        fi
        sleep 1
        i=$(( i + 1 ))
    done
    fail "PostgreSQL did not become ready in 30s"
    return 1
}

wait_for_mongo() {
    info "Waiting for MongoDB at ${MONGO_URI}..."
    local i=0
    while (( i < 30 )); do
        if run_mongosh --eval "db.adminCommand({ ping: 1 })" >/dev/null 2>&1; then
            pass "MongoDB is responding"
            return 0
        fi
        sleep 1
        i=$(( i + 1 ))
    done
    fail "MongoDB did not become ready in 30s"
    return 1
}

# ---------------------------------------------------------------------------
# Provision
# ---------------------------------------------------------------------------

create_postgres_db() {
    local exists
    exists=$(run_psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DATABASE}'" 2>/dev/null || echo "")
    if [[ "$exists" == "1" ]]; then
        pass "Postgres database '${POSTGRES_DATABASE}' already exists"
        return 0
    fi
    info "Creating Postgres database '${POSTGRES_DATABASE}'..."
    if run_psql -d postgres -c "CREATE DATABASE \"${POSTGRES_DATABASE}\";" >/dev/null 2>&1; then
        pass "Postgres database '${POSTGRES_DATABASE}' created"
    else
        fail "Failed to create Postgres database"
        return 1
    fi
}

verify_mongo() {
    info "Verifying MongoDB database '${MONGO_DB}'..."
    if run_mongosh --eval "db.runCommand({ dbStats: 1 }).db" 2>/dev/null | grep -q "$MONGO_DB"; then
        pass "MongoDB database '${MONGO_DB}' is reachable"
    else
        # Mongo creates the DB on first write — it's reachable even if empty
        if run_mongosh --eval "db.getName()" >/dev/null 2>&1; then
            pass "MongoDB database '${MONGO_DB}' is reachable (will be created on first write)"
        else
            fail "MongoDB database '${MONGO_DB}' is not reachable"
            return 1
        fi
    fi
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

usage() {
    cat <<EOF
${BOLD}Bike Store ETL - First-Run Initializer${RESET}

Usage:
  $(basename "$0")            Initialize Postgres + MongoDB for first run
  $(basename "$0") --local    Force local mode (skip docker compose detection)
  $(basename "$0") --help     Show this help
EOF
}

main() {
    local mode="${1:-}"
    case "$mode" in
        --local) DOCKER_MODE=0 ;;
        --help|-h) usage; exit 0 ;;
        *) DOCKER_MODE=1 ;;
    esac

    echo -e "${BOLD}=== Bike Store ETL - First-Run Init ===${RESET}"
    wait_for_postgres || exit 1
    wait_for_mongo || exit 1
    create_postgres_db || exit 1
    verify_mongo || exit 1

    echo
    pass "Database initialization complete"
    info "Next: run 'make etl ARGS=\"--full-refresh\"' to load the first batch"
}

main "$@"
