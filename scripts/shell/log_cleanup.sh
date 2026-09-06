#!/usr/bin/env bash

# ============================================================================
# LOG CLEANUP UTILITY
# ============================================================================
# Responsibilities:
#   1. Flag and delete files older than MAX_AGE_DAYS.
#   2. Flag and delete files larger than MAX_SIZE_MB.
#   3. ALWAYS preserve the most recently modified log file.
#
# Usage:
#   ./scripts/log_cleanup.sh                 (Show read-only summary)
#   ./scripts/log_cleanup.sh clean           (Interactive deletion)
#   ./scripts/log_cleanup.sh clean --dry-run (Preview deletions)
#   ./scripts/log_cleanup.sh clean -y        (Force deletion)
# ============================================================================

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
MAX_AGE_DAYS="${MAX_AGE_DAYS:-7}"
MAX_SIZE_MB="${MAX_SIZE_MB:-5}"

# ----------------------------------------------------------------------------
# TTY Color Formatting
# ----------------------------------------------------------------------------
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' RESET=''
fi

# ----------------------------------------------------------------------------
# Output Helpers
# ----------------------------------------------------------------------------
info()   { printf "${BLUE}[INFO]${RESET} %s\n" "$1"; }
notify() { printf "${GREEN}[DELETED]${RESET} %s\n" "$1"; }
warn()   { printf "${YELLOW}[WARNING]${RESET} %s\n" "$1" >&2; }
err()    { printf "${RED}[ERROR]${RESET} %s\n" "$1" >&2; }

usage() {
    cat <<EOF
${BOLD}Log Cleanup Utility${RESET}

Usage:
  $(basename "$0")                 Show a summary report of all logs (default, read-only)
  $(basename "$0") summary         Same as above
  $(basename "$0") clean           Delete logs older than ${MAX_AGE_DAYS}d or larger than ${MAX_SIZE_MB}MB
  $(basename "$0") clean --dry-run Preview what 'clean' would delete
  $(basename "$0") clean -y        Skip the confirmation prompt
  $(basename "$0") -h | --help     Show this help

${CYAN}Configuration:${RESET}
  Target Dir : ${LOG_DIR}
  Age Limit  : ${MAX_AGE_DAYS} days
  Size Limit : ${MAX_SIZE_MB} MB
EOF
}

# ----------------------------------------------------------------------------
# Portable File Stats (Linux/GNU + macOS/BSD)
# ----------------------------------------------------------------------------
file_mtime_epoch() { stat -c '%Y' "$1" 2>/dev/null || stat -f '%m' "$1" 2>/dev/null; }
file_size_bytes()  { stat -c '%s' "$1" 2>/dev/null || stat -f '%z' "$1" 2>/dev/null; }

file_mtime_ns() {
    local out
    if out=$(stat -c '%.9Y' "$1" 2>/dev/null); then
        printf '%s' "${out/./}"
    elif out=$(stat -f '%m' "$1" 2>/dev/null); then
        printf '%s000000000' "$out"
    else
        return 1
    fi
}

file_size_mb() {
    local bytes
    bytes=$(file_size_bytes "$1") || { echo 0; return 1; }
    echo $(( bytes / 1024 / 1024 ))
}

file_age_days() {
    local mtime now
    mtime=$(file_mtime_epoch "$1") || { echo 0; return 1; }
    now=$(date +%s)
    echo $(( (now - mtime) / 86400 ))
}

find_latest_log() {
    local latest="" latest_ns="" f mtime_ns
    while IFS= read -r -d '' f; do
        mtime_ns=$(file_mtime_ns "$f") || continue
        if [[ -z "$latest" ]] || (( 10#$mtime_ns > 10#$latest_ns )); then
            latest_ns=$mtime_ns
            latest="$f"
        fi
    done < <(find "$LOG_DIR" -type f -print0 2>/dev/null)
    printf '%s' "$latest"
}

require_log_dir() {
    if [[ ! -d "$LOG_DIR" ]]; then
        warn "Log directory does not exist: $LOG_DIR"
        exit 0
    fi
}

classify_file() {
    local f="$1" latest="$2" size age status is_old=0 is_large=0
    size=$(file_size_mb "$f")
    age=$(file_age_days "$f")
    
    if [[ "$f" == "$latest" ]]; then
        status="LATEST"
    else
        (( age  > MAX_AGE_DAYS  )) && is_old=1
        (( size > MAX_SIZE_MB   )) && is_large=1
        
        if   (( is_old && is_large )); then status="OLD+LARGE"
        elif (( is_old ));             then status="OLD"
        elif (( is_large ));           then status="LARGE"
        else                                status="OK"
        fi
    fi
    printf '%s %s %s' "$size" "$age" "$status"
}

# ----------------------------------------------------------------------------
# Command: Summary
# ----------------------------------------------------------------------------
cmd_summary() {
    require_log_dir
    local latest
    latest=$(find_latest_log)

    if [[ -z "$latest" ]]; then
        info "No log files found in $LOG_DIR"
        return 0
    fi

    echo -e "\n${BOLD}$(printf '%-40s %10s %10s %-12s' "FILE" "SIZE(MB)" "AGE(days)" "STATUS")${RESET}"
    echo "------------------------------------------------------------------------------"

    local files_count=0 total_mb=0 n_old=0 n_large=0 n_oldlarge=0
    local f size age status

    while IFS= read -r -d '' f; do
        read -r size age status <<< "$(classify_file "$f" "$latest")"
        
        # Colorize status output
        local status_colored="$status"
        case "$status" in
            LATEST)    status_colored="${GREEN}LATEST${RESET}" ;;
            OK)        status_colored="${GREEN}OK${RESET}" ;;
            OLD)       status_colored="${YELLOW}OLD${RESET}"; n_old=$((n_old + 1)) ;;
            LARGE)     status_colored="${YELLOW}LARGE${RESET}"; n_large=$((n_large + 1)) ;;
            OLD+LARGE) status_colored="${RED}OLD+LARGE${RESET}"; n_oldlarge=$((n_oldlarge + 1)) ;;
        esac

        printf '%-40s %10s %10s %b\n' "$(basename "$f")" "$size" "$age" "$status_colored"
        files_count=$((files_count + 1))
        total_mb=$((total_mb + size))
    done < <(find "$LOG_DIR" -type f -print0 2>/dev/null)

    local would_delete=$((n_old + n_large + n_oldlarge))

    echo -e "\n${BOLD}============================================================${RESET}"
    echo -e "${BOLD}                    LOG SUMMARY${RESET}"
    echo -e "${BOLD}============================================================${RESET}"
    echo -e "Log directory        : ${CYAN}$LOG_DIR${RESET}"
    echo -e "Total log files      : $files_count"
    echo -e "Total size (approx)  : ${total_mb} MB"
    echo -e "Latest (preserved)   : ${GREEN}$(basename "$latest")${RESET}"
    echo -e "Flagged - old only   : $n_old"
    echo -e "Flagged - large only : $n_large"
    echo -e "Flagged - old+large  : $n_oldlarge"
    echo -e "Would be deleted     : ${RED}$would_delete${RESET}"
    echo -e "${BOLD}============================================================${RESET}\n"

    if (( would_delete > 0 )); then
        info "Run '$(basename "$0") clean' to remove flagged logs, or 'clean --dry-run' to preview."
    else
        info "Nothing needs cleanup."
    fi
}

# ----------------------------------------------------------------------------
# Command: Clean
# ----------------------------------------------------------------------------
cmd_clean() {
    require_log_dir

    local dry_run=0 assume_yes=0 arg
    for arg in "$@"; do
        case "$arg" in
            --dry-run) dry_run=1 ;;
            -y|--yes)  assume_yes=1 ;;
            *) err "Unknown option for 'clean': $arg"; usage; exit 1 ;;
        esac
    done

    local latest
    latest=$(find_latest_log)
    if [[ -z "$latest" ]]; then
        info "No log files found in $LOG_DIR"
        return 0
    fi

    info "Log directory : $LOG_DIR"
    info "Age limit     : ${MAX_AGE_DAYS} days"
    info "Size limit    : ${MAX_SIZE_MB} MB"
    info "Latest log    : ${GREEN}$(basename "$latest")${RESET} (Always Kept)"

    local -a to_delete=() reasons=()
    local f size age status

    while IFS= read -r -d '' f; do
        [[ "$f" == "$latest" ]] && continue
        read -r size age status <<< "$(classify_file "$f" "$latest")"
        case "$status" in
            OLD)       to_delete+=("$f"); reasons+=("Older than ${MAX_AGE_DAYS} days") ;;
            LARGE)     to_delete+=("$f"); reasons+=("${size} MB") ;;
            OLD+LARGE) to_delete+=("$f"); reasons+=("Older than ${MAX_AGE_DAYS} days, ${size} MB") ;;
        esac
    done < <(find "$LOG_DIR" -type f -print0 2>/dev/null)

    if (( ${#to_delete[@]} == 0 )); then
        echo
        info "Nothing to delete."
        return 0
    fi

    echo
    info "${#to_delete[@]} file(s) flagged for deletion:"
    for i in "${!to_delete[@]}"; do
        echo -e "  ${RED}-${RESET} $(basename "${to_delete[$i]}") ${YELLOW}(${reasons[$i]})${RESET}"
    done

    if (( dry_run )); then
        echo
        info "Dry run - no files were deleted."
        return 0
    fi

    if (( ! assume_yes )); then
        local confirm=""
        read -r -p $'\nProceed with deletion? [y/N] ' confirm
        case "$confirm" in
            y|Y|yes|YES) ;;
            *) info "Aborted. No files were deleted."; return 0 ;;
        esac
    fi

    local deleted_count=0 failed_count=0
    for f in "${to_delete[@]}"; do
        if rm -f "$f" 2>/dev/null; then
            notify "$(basename "$f")"
            deleted_count=$((deleted_count + 1))
        else
            warn "Could not delete: $f"
            failed_count=$((failed_count + 1))
        fi
    done

    find "$LOG_DIR" -mindepth 1 -type d -empty -delete 2>/dev/null || true

    echo -e "\n${BOLD}============================================================${RESET}"
    echo -e "${BOLD}                 LOG CLEANUP SUMMARY${RESET}"
    echo -e "${BOLD}============================================================${RESET}"
    echo -e "Log directory        : $LOG_DIR"
    echo -e "Files deleted        : ${GREEN}$deleted_count${RESET}"
    if (( failed_count > 0 )); then
        echo -e "Failed to delete     : ${RED}$failed_count${RESET}"
    fi
    echo -e "Latest log preserved : ${CYAN}$(basename "$latest")${RESET}"
    echo -e "${BOLD}============================================================${RESET}"
}

# ----------------------------------------------------------------------------
# Entry Point
# ----------------------------------------------------------------------------
main() {
    local cmd="${1:-summary}"
    case "$cmd" in
        summary|"") cmd_summary ;;
        clean)      shift; cmd_clean "$@" ;;
        -h|--help|help) usage ;;
        *) err "Unknown command: $cmd"; usage; exit 1 ;;
    esac
}

main "$@"