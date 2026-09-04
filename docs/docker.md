# Docker

The pipeline runs as a multi-container stack. This document explains the image build, service composition, and how to extend it.

---

## Image: `docker/Dockerfile`

The single application image hosts all batch jobs. It's based on `python:3.13-slim` (matches `pyproject.toml` `requires-python = ">=3.13"`) and is built in three stages:

```mermaid
flowchart TD
    classDef stage fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef file fill:#fff8e1,stroke:#f9a825,color:#5d4037
    classDef final fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20

    A["python:3.13-slim"]:::stage
    B["+ uv, Java JRE, psql, mongosh, curl"]:::stage
    C["+ pyproject.toml → uv sync"]:::stage
    D["+ project source<br/>(src/, scripts/, utils/, tests/)"]:::file
    E["+ jars/postgresql.jar"]:::file
    F["+ docker/entrypoint.sh"]:::file
    G["CMD [entrypoint.sh]"]:::final

    A --> B --> C --> D
    A --> B --> C --> E
    A --> B --> C --> F
    D --> G
    E --> G
    F --> G
```

### Why these base tools

- **Java JRE** — PySpark requires a JVM
- **psql** — used by backup/restore and `monitor_logs.sh` health probes
- **mongosh** — used by `docker_dev.sh` and `monitor_logs.sh` MongoDB checks
- **curl** — Prometheus / Pushgateway health probes

### Build it

```bash
make build                          # via Makefile
docker compose build app            # direct
docker build -t bike-store-app docker/  # raw
```

---

## Stack: `docker-compose.yml`

Six services on one `monitoring` network. Profiles separate long-running infrastructure from on-demand batch jobs.

```mermaid
flowchart LR
    classDef db fill:#3367d6,stroke:#1a53b3,color:#ffffff
    classDef monitor fill:#0f9d58,stroke:#0b8043,color:#ffffff
    classDef viz fill:#f4b400,stroke:#d09200,color:#000000
    classDef job fill:#ff6f00,stroke:#c43e00,color:#ffffff

    PG[("postgres:16-alpine<br/>bike_store database")]:::db
    MGO[("mongo:7<br/>source data")]:::db
    PGW["pushgateway<br/>(prom/pushgateway)"]:::monitor
    PROM["prometheus<br/>(prom/prometheus)"]:::monitor
    GRAF["grafana<br/>auto-provisioned dashboards"]:::viz
    APP["app<br/>(batch jobs, jobs profile)"]:::job

    APP -->|"JDBC writes"| PG
    APP -->|"pymongo reads"| MGO
    APP -->|"HTTP push metrics"| PGW
    PGW -->|"scrape every 15s"| PROM
    PROM -->|"PromQL queries"| GRAF
```

### Services

| Service | Image | Port | Healthcheck |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | `pg_isready` |
| `mongodb` | `mongo:7` | 27017 | `mongosh ping` |
| `pushgateway` | `prom/pushgateway` | 9091 | HTTP `/-/healthy` |
| `prometheus` | `prom/prometheus` | 9090 | HTTP `/-/healthy` |
| `grafana` | `grafana/grafana` | 3000 | HTTP `/api/health` |
| `app` | local (`docker/Dockerfile`) | — | jobs profile (on-demand) |

### Profiles

Only `app` uses profiles. `app` is in the `jobs` profile, so it does **not** start with `make up` — it's launched on demand with `make pipeline`, `make etl`, etc.

```yaml
services:
  app:
    profiles: ["jobs"]
    command: ["entrypoint.sh"]   # dispatches to the requested job
```

### Endpoints (after `make up`)

| Service | URL | Default credentials |
|---|---|---|
| Grafana | http://localhost:3000 | `admin` / `${GRAFANA_ADMIN_PASSWORD}` |
| Prometheus | http://localhost:9090 | none |
| Pushgateway | http://localhost:9091 | none |

### Volumes

| Volume | Backed by | Survives `docker compose down`? |
|---|---|---|
| `postgres_data` | `/var/lib/postgresql/data` | yes |
| `mongodb_data` | `/data/db` | yes |
| `prometheus_data` | `/prometheus` | yes |
| `grafana_data` | `/var/lib/grafana` | yes |

Use `make clean` to remove containers + volumes, or `make prune` to nuke everything including images and build cache.

---

## Entry point: `docker/entrypoint.sh`

Dispatches the `docker compose run app <command>` invocation to the correct script. Acts as the bridge between compose services and the project scripts.

```mermaid
flowchart TD
    classDef entry fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    classDef cmd fill:#fff8e1,stroke:#f9a825,color:#5d4037
    classDef default fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20

    A["docker compose run app <cmd>"]:::entry
    B{{"Which command?"}}:::default
    C["pipeline → ETL + PL/pgSQL + GX"]:::cmd
    D["etl → scripts/mongo_to_postgres.py"]:::cmd
    E["dq-loops → scripts/plpgsql_loops_tests.py"]:::cmd
    F["dq-gx → scripts/run_gx.py"]:::cmd
    G["inspect-schema → scripts/inspect_schema.py"]:::cmd
    H["monitor-logs → scripts/monitor_logs.sh"]:::cmd
    I["log-cleanup → scripts/log_cleanup.sh"]:::cmd
    J["shell → bash interactive"]:::cmd
    K["Default → run as Python script"]:::default

    A --> B
    B -->|pipeline| C
    B -->|etl| D
    B -->|dq-loops| E
    B -->|dq-gx| F
    B -->|inspect-schema| G
    B -->|monitor-logs| H
    B -->|log-cleanup| I
    B -->|shell| J
    B -->|anything else| K
```

---

## `.dockerignore`

Excludes local-only files from the build context:
- `__pycache__/`, `.venv/`, `.env` (secrets)
- `.git/` (history)
- `logs/`, `reports/` (artifacts)
- `tests/generic/loops/*.sql` is **not** excluded (PL/pgSQL test files are loaded into the container for the dq-loops job)

---

## Extending the stack

### Add a new service (e.g. Redash, Metabase)

1. Add the service block to `docker-compose.yml` in the `monitoring` network
2. Add a `healthcheck:` (so dependent services wait for it)
3. Document in [docs/ARCHITECTURE.md](ARCHITECTURE.md) Container Topology section

### Add a new job

1. Add a `cmd_<jobname>` branch to `docker/entrypoint.sh`
2. Add a `make <jobname>` target in the Makefile
3. Document in [docs/run_book.md](run_book.md)
