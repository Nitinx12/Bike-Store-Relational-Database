#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# entrypoint.sh
# ----------------------------------------------------------------------------
# Single dispatcher for the image built by Dockerfile. One image, one
# entrypoint, and the first argument to `docker run` picks which of the
# project's batch jobs actually runs — instead of five separate images
# (one per script) that would each need their own build/tag/push cycle.
#
# Usage:
#   docker run <image> <job> [job-specific args...]
#
# Examples:
#   docker run myimg pipeline                     # full pipeline run
#   docker run myimg etl                          # incremental, all collections
#   docker run myimg etl --collection orders       # incremental, one collection
#   docker run myimg etl --full-refresh
#   docker run myimg dq-loops
#   docker run myimg dq-gx orders products
#   docker run myimg monitor-logs clean --dry-run
#   docker run myimg shell                         # debugging
# ============================================================================

JOB="${1:-}"
shift || true

# ----------------------------------------------------------------------------
# Optional: wait for the Pushgateway to accept connections before running a
# metrics-emitting job, so the first run right after `docker compose up`
# doesn't just silently miss its push while Pushgateway is still starting.
# This is a convenience, not a requirement — utils/metrics.py already fails
# soft (logs + returns False) if the gateway is unreachable, so timing out
# here just prints a warning and the job still runs.
# ----------------------------------------------------------------------------
wait_for_pushgateway() {
    if [[ "${WAIT_FOR_PUSHGATEWAY:-true}" != "true" ]]; then
        return 0
    fi

    local target="${PUSHGATEWAY_URL:-pushgateway:9091}"
    local host="${target%%:*}"
    local port="${target##*:}"
    local timeout="${PUSHGATEWAY_WAIT_TIMEOUT:-30}"
    local waited=0

    echo "[entrypoint] Waiting up to ${timeout}s for Pushgateway at ${target}..."
    while (( waited < timeout )); do
        if (exec 3<>"/dev/tcp/${host}/${port}") 2>/dev/null; then
            exec 3>&- 3<&- 2>/dev/null || true
            echo "[entrypoint] Pushgateway is reachable."
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done

    echo "[entrypoint] WARNING: Pushgateway not reachable after ${timeout}s — continuing anyway (metrics push will fail soft, see utils/metrics.py)." >&2
    return 0
}

usage() {
    cat <<'EOF'
Usage: docker run <image> <job> [job-specific args...]

Jobs:
  pipeline [--full-refresh] [--collections ...] [--gx-tables ...] [--skip-plpgsql] [--skip-gx]
      main.py — Runs the full Mongo -> Postgres load, PL/pgSQL suite, and GX suite in one process.

  etl [--collection NAME ...] [--full-refresh]
      scripts/mongo_to_postgres.py — incremental by default; pass one or
      more --collection flags to restrict to specific collections, or
      --full-refresh to truncate and reload.

  dq-loops
      scripts/plpgsql_loops_tests.py — runs the PL/pgSQL DO-block tests
      under tests/generic/loops/*.sql.

  dq-gx [table ...]
      tests/data_quality/run.py — Great Expectations suite; validates every table
      if none are named.

  inspect-schema
      scripts/inspect_schema.py — prints the public schema's tables,
      columns, and data types.

  monitor-logs [summary|clean] [--dry-run|-y]
      scripts/monitor_logs.sh — defaults to a read-only summary; see the
      script's own --help for the full option list.

  shell
      Drop into bash inside the container (debugging).

Env vars:
  DB connection   — see utils/connection.py (POSTGRES_*, MONGO_*)
  Metrics         — PUSHGATEWAY_URL (default pushgateway:9091),
                    PUSHGATEWAY_TIMEOUT, WAIT_FOR_PUSHGATEWAY,
                    PUSHGATEWAY_WAIT_TIMEOUT (see utils/metrics.py)
EOF
}

case "$JOB" in
    pipeline)
        wait_for_pushgateway
        exec uv run python main.py "$@"
        ;;
    etl)
        wait_for_pushgateway
        exec uv run python -m scripts.mongo_to_postgres "$@"
        ;;
    dq-loops)
        wait_for_pushgateway
        exec uv run python scripts/plpgsql_loops_tests.py "$@"
        ;;
    dq-gx)
        wait_for_pushgateway
        exec uv run python tests/data_quality/run.py "$@"
        ;;
    inspect-schema)
        exec uv run python scripts/inspect_schema.py "$@"
        ;;
    monitor-logs)
        exec bash scripts/monitor_logs.sh "$@"
        ;;
    shell|bash)
        exec bash
        ;;
    -h|--help|help|"")
        usage
        ;;
    *)
        echo "[entrypoint] Unknown job: '${JOB}'" >&2
        echo >&2
        usage >&2
        exit 1
        ;;
esac