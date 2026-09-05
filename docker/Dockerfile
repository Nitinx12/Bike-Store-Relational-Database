# syntax=docker/dockerfile:1
#
# One image for every batch job in this project (ETL, data-quality suites,
# schema inspection, log cleanup). Which job runs is chosen at `docker run`
# time by entrypoint.sh, not baked into the image — see entrypoint.sh --help.
#
# Assumes a `pyproject.toml` + `uv.lock` at the project root, matching the
# `uv run scripts/...` invocation style used throughout this repo. If you
# don't have those yet, `uv init` / `uv add <deps>` first.
#
# This file lives in docker/, but every COPY below is relative to the
# PROJECT ROOT, not this file's own directory — so build with the root as
# context and point -f at this path:
#   docker build -f docker/Dockerfile -t myimage .        (run from project root)
# or, once docker-compose.yml exists, just:
#   build: { context: ., dockerfile: docker/Dockerfile }

FROM python:3.13-slim

# scripts/mongo_to_postgres.py runs PySpark, which needs a JVM at runtime
# for both the driver and the JDBC write path (jars/postgresql.jar).
RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-21-jre-headless \
        procps \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf "$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")" /opt/java

ENV JAVA_HOME=/opt/java \
    PATH="${JAVA_HOME}/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYSPARK_PYTHON=/usr/local/bin/python \
    PYSPARK_DRIVER_PYTHON=/usr/local/bin/python

# uv: the dependency manager this project already uses (`uv run scripts/...`)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Dependencies first, in their own layer, so editing scripts/ doesn't
# invalidate the (slow) dependency-install cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# App code
COPY utils/   ./utils/
COPY scripts/ ./scripts/
COPY tests/   ./tests/
COPY src/     ./src/
COPY jars/    ./jars/
COPY main.py  ./

RUN uv sync --frozen --no-dev

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]