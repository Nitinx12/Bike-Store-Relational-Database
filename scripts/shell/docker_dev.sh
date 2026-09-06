#!/usr/bin/env bash

# ============================================================================
# Bike Store ETL - Docker Development Infrastructure Manager
# ============================================================================
#
# Responsibilities:
#   1. Manage Docker Compose stack (PostgreSQL, MongoDB, Prometheus, Pushgateway, PgAdmin)
#   2. Perform automated health checks on listening ports & endpoints
#   3. Tail multi-service container logs
#   4. Wipe named persistent volumes on demand for clean resets
#
# Usage:
#   ./scripts/docker_dev.sh up         Start containers in background & verify health
#   ./scripts/docker_dev.sh down       Stop & remove container stack
#   ./scripts/docker_dev.sh restart    Restart all services
#   ./scripts/docker_dev.sh status     Display container status & stats
#   ./scripts/docker_dev.sh logs [svc] Tail logs (optional: pass service name like 'postgres')
#   ./scripts/docker_dev.sh reset      Stop containers & PURGE all database/metric volumes
# ============================================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"

# Load environment overrides
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# ----------------------------------------------------------------------------
# TTY Color Formatting
# ----------------------------------------------------------------------------
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

info()   { printf "${BLUE}[INFO]${RESET} %s\n" "$1"; }
pass()   { printf "${GREEN}[PASS]${RESET} %s\n" "$1"; }
warn()   { printf "${YELLOW}[WARN]${RESET} %s\n" "$1" >&2; }
fail()   { printf "${RED}[FAIL]${RESET} %s\n" "$1" >&2; }

# ----------------------------------------------------------------------------
# Pre-flight Checks
# ----------------------------------------------------------------------------
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        fail "Docker CLI is not installed or not in PATH."
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        fail "Docker daemon is not running. Please start Docker Engine / Desktop."
        exit 1
    fi

    if [[ ! -f "$COMPOSE_FILE" ]]; then
        fail "Compose file not found at: $COMPOSE_FILE"
        exit 1
    fi
}

compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        docker compose -f "$COMPOSE_FILE" "$@"
    else
        docker-compose -f "$COMPOSE_FILE" "$@"
    fi
}

# ----------------------------------------------------------------------------
# Endpoint Health Probes
# ----------------------------------------------------------------------------
check_service_health() {
    info "Verifying service endpoints..."
    sleep 2 # Brief pause to let container sockets bind

    # PostgreSQL Check
    local pg_port="${POSTGRES_PORT:-5432}"
    if compose_cmd exec -T postgres pg_isready -U "${POSTGRES_USERNAME:-postgres}" >/dev/null 2>&1; then
        pass "PostgreSQL container is ready on port $pg_port"
    elif command -v nc >/dev/null 2>&1 && nc -z localhost "$pg_port" 2>/dev/null; then
        pass "PostgreSQL TCP port $pg_port is open"
    else
        warn "PostgreSQL is not responding on port $pg_port"
    fi

    # MongoDB Check
    local mongo_port="27017"
    if compose_cmd exec -T mongodb mongosh --eval "db.adminCommand({ ping: 1 })" --quiet >/dev/null 2>&1; then
        pass "MongoDB ping successful on port $mongo_port"
    elif command -v nc >/dev/null 2>&1 && nc -z localhost "$mongo_port" 2>/dev/null; then
        pass "MongoDB TCP port $mongo_port is open"
    else
        warn "MongoDB is not responding on port $mongo_port"
    fi

    # Prometheus Check
    local prom_url="${PROMETHEUS_URL:-http://localhost:9090}"
    if command -v curl >/dev/null 2>&1 && curl --silent --fail --max-time 3 "${prom_url}/-/healthy" >/dev/null 2>&1; then
        pass "Prometheus healthy at $prom_url"
    else
        warn "Prometheus endpoint unavailable at $prom_url"
    fi

    # Pushgateway Check
    local push_url="${PUSHGATEWAY_URL:-http://localhost:9091}"
    if command -v curl >/dev/null 2>&1 && curl --silent --fail --max-time 3 "${push_url}/-/healthy" >/dev/null 2>&1; then
        pass "Pushgateway healthy at $push_url"
    else
        warn "Pushgateway endpoint unavailable at $push_url"
    fi
}

# ----------------------------------------------------------------------------
# Command Operations
# ----------------------------------------------------------------------------
cmd_up() {
    info "Spinning up local development infrastructure..."
    compose_cmd up -d
    echo
    check_service_health
}

cmd_down() {
    info "Stopping local infrastructure containers..."
    compose_cmd down
    pass "Containers stopped."
}

cmd_restart() {
    info "Restarting local infrastructure..."
    compose_cmd restart
    echo
    check_service_health
}

cmd_status() {
    echo -e "\n${BOLD}=== Container Status ===${RESET}"
    compose_cmd ps

    local running_containers
    running_containers="$(compose_cmd ps -q)"

    if [[ -n "$running_containers" ]]; then
        echo -e "\n${BOLD}=== Resource Utilization ===${RESET}"
        docker stats --no-stream $running_containers
    fi
}

cmd_logs() {
    local service="${1:-}"
    if [[ -n "$service" ]]; then
        info "Tailing logs for service: $service"
        compose_cmd logs -f --tail=100 "$service"
    else
        info "Tailing all infrastructure logs..."
        compose_cmd logs -f --tail=50
    fi
}

cmd_reset() {
    warn "This will DELETE all container volumes (Postgres database, Mongo collections, Prometheus data)!"
    read -r -p "Are you sure you want to purge local storage? [y/N] " confirm
    case "$confirm" in
        y|Y|yes|YES)
            info "Tearing down stack and purging named volumes..."
            compose_cmd down -v
            pass "Development environment completely reset."
            ;;
        *)
            info "Reset operation canceled."
            ;;
    esac
}

# ----------------------------------------------------------------------------
# Entry Point
# ----------------------------------------------------------------------------
usage() {
    cat <<EOF
${BOLD}Bike Store ETL - Docker Infrastructure Utility${RESET}

Usage:
  $(basename "$0") COMMAND [SERVICE]

Commands:
  up         Start all dev services in background & verify health
  down       Stop and remove container stack
  restart    Restart all container services
  status     Display running containers and memory/CPU usage
  logs       Tail logs across all containers (or specify a single service)
  reset      Stop containers and wipe named persistent volumes
  help       Show this help menu
EOF
}

main() {
    check_docker
    local cmd="${1:-status}"

    case "$cmd" in
        up)            cmd_up ;;
        down)          cmd_down ;;
        restart)       cmd_restart ;;
        status|ps)     cmd_status ;;
        logs)          shift; cmd_logs "$@" ;;
        reset)         cmd_reset ;;
        -h|--help|help) usage ;;
        *) fail "Unknown command: $cmd"; usage; exit 1 ;;
    esac
}

main "$@"