#!/usr/bin/env bash

# ============================================================================
# Bike Store ETL - One-Shot Health Check
# ============================================================================
#
# Quick liveness probe for CI, monitoring, or pre-flight checks. Returns:
#   0  = everything healthy
#   1  = one or more warnings
#   2  = one or more critical failures
#
# Usage:
#   ./scripts/health_check.sh
#   ./scripts/health_check.sh --quiet     Suppress OK lines, only show issues
#   ./scripts/health_check.sh --json      Emit JSON instead of human output
# ============================================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

QUIET=0
JSON=0
for arg in "$@"; do
    case "$arg" in
        --quiet|-q) QUIET=1 ;;
        --json) JSON=1 ;;
        --help|-h) echo "Usage: $0 [--quiet] [--json]"; exit 0 ;;
    esac
done

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USERNAME="${POSTGRES_USERNAME:-postgres}"
POSTGRES_DATABASE="${POSTGRES_DATABASE:-bike_store}"
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
PUSHGATEWAY_URL="${PUSHGATEWAY_URL:-http://localhost:9091}"

if [[ -t 1 ]]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN='' RED='' YELLOW='' BOLD='' RESET=''
fi

use_docker() {
    command -v docker >/dev/null 2>&1 && docker compose ps 2>/dev/null | grep -q "running"
}

# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

probe_postgres() {
    if use_docker; then
        docker compose exec -T postgres pg_isready -U "$POSTGRES_USERNAME" >/dev/null 2>&1
    else
        psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME" -d "$POSTGRES_DATABASE" \
            -c "SELECT 1;" >/dev/null 2>&1
    fi
}

probe_mongo() {
    if use_docker; then
        docker compose exec -T mongodb mongosh --quiet --eval "db.adminCommand({ ping: 1 })" >/dev/null 2>&1
    else
        command -v mongosh >/dev/null 2>&1 && \
            mongosh "$MONGO_URI" --quiet --eval "db.adminCommand({ ping: 1 })" >/dev/null 2>&1
    fi
}

probe_http() {
    local url="$1"
    command -v curl >/dev/null 2>&1 && \
        curl --silent --fail --max-time 3 "$url" >/dev/null 2>&1
}

probe_disk() {
    local usage
    usage=$(df -P "$PROJECT_ROOT" 2>/dev/null | awk 'NR==2 {gsub("%","",$5); print $5}')
    [[ -n "$usage" && "$usage" -lt 90 ]]
}

# ---------------------------------------------------------------------------
# Result aggregation
# ---------------------------------------------------------------------------

declare -a JSON_RESULTS=()
declare -a FAILURES=()

run_check() {
    local name="$1"; shift
    local fn="$1"; shift
    local desc="$1"
    if "$fn" "$@" 2>/dev/null; then
        JSON_RESULTS+=("\"$name\": \"ok\"")
        (( QUIET == 0 )) && echo -e "${GREEN}[OK]${RESET}   $desc"
    else
        JSON_RESULTS+=("\"$name\": \"fail\"")
        FAILURES+=("$name")
        echo -e "${RED}[FAIL]${RESET} $desc" >&2
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

run_check postgres  probe_postgres "PostgreSQL at ${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DATABASE}"
run_check mongodb   probe_mongo   "MongoDB at ${MONGO_URI}"
run_check prometheus probe_http "${PROMETHEUS_URL}/-/healthy" "Prometheus at ${PROMETHEUS_URL}"
run_check pushgateway probe_http "${PUSHGATEWAY_URL}/-/healthy" "Pushgateway at ${PUSHGATEWAY_URL}"
run_check disk      probe_disk   "Disk usage on ${PROJECT_ROOT}"

if (( JSON == 1 )); then
    local_status="ok"
    (( ${#FAILURES[@]} > 0 )) && local_status="fail"
    printf '{ "status": "%s", "checks": { %s } }\n' "$local_status" \
        "$(IFS=,; echo "${JSON_RESULTS[*]}")"
fi

(( ${#FAILURES[@]} > 0 )) && exit 2 || exit 0
