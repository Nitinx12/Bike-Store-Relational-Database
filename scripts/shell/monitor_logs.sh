#!/usr/bin/env bash

# ============================================================
# Bike Store ETL - Operational Monitoring & Log Maintenance
# ============================================================
#
# Responsibilities:
#   1. Monitor pipeline logs
#   2. Monitor extraction logs
#   3. Monitor data-quality / GX logs
#   4. Detect ERROR / FAILED / EXCEPTION entries
#   5. Detect stale logs
#   6. Check validation reports
#   7. Check Git Status (uncommitted changes, up-to-date)
#   8. Check PostgreSQL & MongoDB availability
#   9. Check Prometheus & Pushgateway
#  10. Check disk usage & log retention cleanup
#
# Usage:
#   ./scripts/monitor_logs.sh
#   ./scripts/monitor_logs.sh --check
#   ./scripts/monitor_logs.sh --cleanup
#   ./scripts/monitor_logs.sh --full
#
# ============================================================

# We intentionally do NOT use `-e` so the script can accumulate errors
# and report them all at the end, rather than crashing on the first failure.
set -uo pipefail

# ------------------------------------------------------------
# Project paths
# ------------------------------------------------------------

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LOG_DIR="$ROOT_DIR/logs"
PIPELINE_LOG_DIR="$LOG_DIR/pipeline"
EXTRACTION_LOG_DIR="$LOG_DIR/extraction"
TEST_LOG_DIR="$LOG_DIR/tests"
REPORT_DIR="$ROOT_DIR/tests/data_quality/reports"

# ------------------------------------------------------------
# Configuration & Defaults
# ------------------------------------------------------------

LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"
LOG_STALE_MINUTES="${LOG_STALE_MINUTES:-60}"

DISK_WARNING_PERCENT="${DISK_WARNING_PERCENT:-80}"
DISK_CRITICAL_PERCENT="${DISK_CRITICAL_PERCENT:-90}"

PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
PUSHGATEWAY_URL="${PUSHGATEWAY_URL:-http://localhost:9091}"

# Database configurations
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USERNAME="${POSTGRES_USERNAME:-postgres}"
POSTGRES_DATABASE="${POSTGRES_DATABASE:-postgres}"
export PGPASSWORD="${POSTGRES_PASSWORD:-}" # Required for non-interactive psql

MONGO_URI="${MONGO_URI:-mongodb://localhost:27017}"

# ------------------------------------------------------------
# Global State Counters
# ------------------------------------------------------------

CHECKS_TOTAL=0
CHECKS_PASSED=0
CHECKS_WARNINGS=0
CHECKS_FAILED=0

# ------------------------------------------------------------
# TTY Color Detection
# ------------------------------------------------------------

if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    # Outputting to a file, disable colors
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' RESET=''
fi

# ------------------------------------------------------------
# Logging Helper Functions
# ------------------------------------------------------------

print_header() {
    echo -e "\n${BOLD}============================================================${RESET}"
    echo -e "${BOLD} $1${RESET}"
    echo -e "${BOLD}============================================================${RESET}"
}

print_section() {
    echo -e "\n${CYAN}--- $1 ---${RESET}"
}

pass() {
    echo -e "${GREEN}[PASS]${RESET} $1"
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
}

warn() {
    echo -e "${YELLOW}[WARN]${RESET} $1"
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    CHECKS_WARNINGS=$((CHECKS_WARNINGS + 1))
}

fail() {
    echo -e "${RED}[FAIL]${RESET} $1"
    CHECKS_TOTAL=$((CHECKS_TOTAL + 1))
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
}

info() {
    echo -e "${BLUE}[INFO]${RESET} $1"
}

# ------------------------------------------------------------
# Command Dependencies
# ------------------------------------------------------------

check_dependencies() {
    print_section "Command Dependencies"

    local commands=("find" "grep" "awk" "sed" "sort" "du" "df" "curl" "git")
    local missing=0

    for cmd in "${commands[@]}"; do
        if command -v "$cmd" >/dev/null 2>&1; then
            pass "$cmd available"
        else
            fail "$cmd is not installed or not in PATH"
            missing=$((missing + 1))
        fi
    done

    [[ "$missing" -eq 0 ]] || return 1
}

# ------------------------------------------------------------
# Git Status Monitoring
# ------------------------------------------------------------

check_git_status() {
    print_section "Git Repository Status"

    # Ensure we are inside a Git repo
    if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        warn "Directory is not a valid Git repository: $ROOT_DIR"
        return
    fi

    local branch
    branch="$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
    info "Current active branch: $branch"

    # 1. Check for uncommitted/dirty files
    if [[ -n "$(git -C "$ROOT_DIR" status --porcelain 2>/dev/null)" ]]; then
        warn "Git working directory is dirty (uncommitted changes detected)"
    else
        pass "Git working directory is clean"
    fi

    # 2. Check sync status with upstream remote (silent fetch first)
    git -C "$ROOT_DIR" fetch --quiet 2>/dev/null || true
    
    local upstream
    upstream="$(git -C "$ROOT_DIR" rev-parse --abbrev-ref @{u} 2>/dev/null || echo '')"
    
    if [[ -n "$upstream" ]]; then
        local behind
        behind="$(git -C "$ROOT_DIR" rev-list --count HEAD.."$upstream" 2>/dev/null || echo 0)"
        if [[ "$behind" -gt 0 ]]; then
            warn "Branch is behind $upstream by $behind commit(s)"
        else
            pass "Branch is up-to-date with $upstream"
        fi
    else
        info "No upstream tracking configured for branch $branch"
    fi
}

# ------------------------------------------------------------
# Core Monitors
# ------------------------------------------------------------

check_directories() {
    print_section "Log Directories"
    local directories=("$LOG_DIR" "$PIPELINE_LOG_DIR" "$EXTRACTION_LOG_DIR" "$TEST_LOG_DIR" "$REPORT_DIR")

    for dir in "${directories[@]}"; do
        if [[ -d "$dir" ]]; then
            pass "Directory verified: $dir"
        else
            warn "Directory missing: $dir"
        fi
    done
}

latest_log() {
    local directory="$1"
    [[ ! -d "$directory" ]] && return 1
    
    # Leverages GNU find for accurate timestamp sorting
    find "$directory" -type f -name "*.log" -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr | head -1 | cut -d' ' -f2-
}

check_log_age() {
    local name="$1"
    local directory="$2"
    local latest

    latest="$(latest_log "$directory")"

    if [[ -z "$latest" ]]; then
        warn "$name: no log files found"
        return
    fi

    local modified
    # GNU/Linux stat. Fallback if macOS (BSD stat)
    modified="$(stat -c %Y "$latest" 2>/dev/null || stat -f %m "$latest" 2>/dev/null || echo 0)"
    local now="$(date +%s)"
    local age_minutes=$(( (now - modified) / 60 ))

    if [[ "$age_minutes" -le "$LOG_STALE_MINUTES" ]]; then
        pass "$name logs are fresh (${age_minutes}m old)"
    else
        warn "$name logs are stale (${age_minutes}m old. Threshold: ${LOG_STALE_MINUTES}m)"
    fi
}

check_pipeline_logs() {
    print_section "Pipeline & Extraction Logs"
    
    for category in "Pipeline:$PIPELINE_LOG_DIR" "Extraction:$EXTRACTION_LOG_DIR" "Data-Quality:$TEST_LOG_DIR"; do
        local name="${category%%:*}"
        local dir="${category##*:}"
        
        local latest="$(latest_log "$dir")"
        if [[ -z "$latest" ]]; then
            warn "$name: No logs found."
            continue
        fi

        local errors
        errors="$(grep -Ein "ERROR|CRITICAL|EXCEPTION|FAILED|FAILURE" "$latest" 2>/dev/null | tail -10 || true)"

        if [[ -n "$errors" ]]; then
            fail "$name contains errors:"
            echo "$errors" | sed 's/^/    /' # indent errors cleanly
        else
            pass "$name logs have no recent errors"
        fi
        
        check_log_age "$name" "$dir"
    done
}

check_validation_report() {
    [[ ! -d "$REPORT_DIR" ]] && return

    local latest_report="$(find "$REPORT_DIR" -type f -name "validation_report_*.json" -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)"
    
    if [[ -z "$latest_report" ]]; then
        warn "No GX validation reports found"
        return
    fi

    if grep -q '"success": false' "$latest_report" 2>/dev/null; then
        fail "Latest GX data validation report FAILED"
    elif grep -q '"success": true' "$latest_report" 2>/dev/null; then
        pass "Latest GX data validation report PASSED"
    else
        warn "Could not determine GX validation status"
    fi
}

check_recent_errors() {
    print_section "24-Hour Global Error Scan"
    [[ ! -d "$LOG_DIR" ]] && return

    # xargs -r prevents hanging if no files are found
    local errors
    errors="$(find "$LOG_DIR" -type f -name "*.log" -mmin -1440 -print0 2>/dev/null \
        | xargs -0 -r grep -Ein "ERROR|CRITICAL|EXCEPTION|FAILED|FAILURE" 2>/dev/null \
        | tail -20 || true)"

    if [[ -n "$errors" ]]; then
        warn "Errors detected globally in the last 24 hours"
    else
        pass "No errors detected in global logs in the last 24 hours"
    fi
}

check_disk_usage() {
    print_section "Infrastructure Constraints (Disk Usage)"

    local usage="$(df -P "$ROOT_DIR" 2>/dev/null | awk 'NR==2 {gsub("%","",$5); print $5}')"
    if [[ -z "$usage" ]]; then
        warn "Unable to determine disk usage"
        return
    fi

    if [[ "$usage" -ge "$DISK_CRITICAL_PERCENT" ]]; then
        fail "Disk usage critical: ${usage}% (Limit: ${DISK_CRITICAL_PERCENT}%)"
    elif [[ "$usage" -ge "$DISK_WARNING_PERCENT" ]]; then
        warn "Disk usage high: ${usage}% (Limit: ${DISK_WARNING_PERCENT}%)"
    else
        pass "Disk usage healthy: ${usage}%"
    fi
}

check_http_service() {
    if curl --silent --fail --max-time 3 "$2" >/dev/null 2>&1; then
        pass "$1 is reachable"
    else
        warn "$1 is unavailable at $2"
    fi
}

check_infrastructure() {
    print_section "Services & Databases"

    check_http_service "Prometheus" "$PROMETHEUS_URL/-/healthy"
    check_http_service "Pushgateway" "$PUSHGATEWAY_URL/-/healthy"

    # PostgreSQL Check
    if command -v psql >/dev/null 2>&1; then
        if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME" -d "$POSTGRES_DATABASE" -c "SELECT 1;" >/dev/null 2>&1; then
            pass "PostgreSQL connected"
        else
            fail "PostgreSQL connection failed"
        fi
    else
        warn "psql CLI missing; skipping Postgres check"
    fi

    # MongoDB Check
    if command -v mongosh >/dev/null 2>&1; then
        if mongosh "$MONGO_URI" --quiet --eval "db.adminCommand({ ping: 1 })" >/dev/null 2>&1; then
            pass "MongoDB connected"
        else
            fail "MongoDB connection failed"
        fi
    else
        warn "mongosh CLI missing; skipping MongoDB check"
    fi
}

cleanup_old_logs() {
    print_section "Log Retention Cleanup"
    [[ ! -d "$LOG_DIR" ]] && return

    local old_logs="$(find "$LOG_DIR" -type f -name "*.log" -mtime +"$LOG_RETENTION_DAYS" -print 2>/dev/null)"
    if [[ -z "$old_logs" ]]; then
        pass "No logs older than ${LOG_RETENTION_DAYS} days require cleanup"
        return
    fi

    local count="$(echo "$old_logs" | wc -l)"
    info "Removing $count log file(s) older than ${LOG_RETENTION_DAYS} days..."

    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        rm -f "$file"
    done <<< "$old_logs"

    pass "Log cleanup completed successfully"
}

print_summary() {
    print_header "MONITORING SUMMARY"

    echo -e "Total Checks : ${BOLD}$CHECKS_TOTAL${RESET}"
    echo -e "Passed       : ${GREEN}$CHECKS_PASSED${RESET}"
    echo -e "Warnings     : ${YELLOW}$CHECKS_WARNINGS${RESET}"
    echo -e "Failed       : ${RED}$CHECKS_FAILED${RESET}"
    echo ""

    if [[ "$CHECKS_FAILED" -gt 0 ]]; then
        echo -e "${RED}${BOLD}OVERALL STATUS: CRITICAL - Immediate Action Required${RESET}"
        return 2
    elif [[ "$CHECKS_WARNINGS" -gt 0 ]]; then
        echo -e "${YELLOW}${BOLD}OVERALL STATUS: WARNING - Requires Observation${RESET}"
        return 1
    else
        echo -e "${GREEN}${BOLD}OVERALL STATUS: HEALTHY - Systems Operational${RESET}"
        return 0
    fi
}

# ------------------------------------------------------------
# Help Menu
# ------------------------------------------------------------

show_help() {
    cat <<EOF
Bike Store ETL - Log Monitoring Utility

Usage:
    $0 [OPTION]

Options:
    --check      Run operational health checks (Default)
    --cleanup    Delete logs older than retention period
    --full       Run checks and cleanup
    --help       Show this help message
EOF
}

# ------------------------------------------------------------
# Main Execution Flow
# ------------------------------------------------------------

main() {
    # BUG FIX: Note the ":-" which ensures empty arguments safely default to --check
    local mode="${1:---check}"

    case "$mode" in
        --help|-h)
            show_help
            exit 0
            ;;
        --check|--full)
            print_header "BIKE STORE ETL MONITORING"
            
            # Abort early if dependencies fail
            check_dependencies || { 
                echo -e "${RED}Critical dependencies missing. Aborting.${RESET}"; 
                exit 1; 
            }
            
            check_git_status
            check_directories
            check_pipeline_logs
            check_validation_report
            check_recent_errors
            check_disk_usage
            check_infrastructure
            
            if [[ "$mode" == "--full" ]]; then
                cleanup_old_logs
            fi
            
            print_summary
            exit $?
            ;;
        --cleanup)
            print_header "BIKE STORE ETL LOG CLEANUP"
            cleanup_old_logs
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $mode${RESET}"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
}

main "$@"