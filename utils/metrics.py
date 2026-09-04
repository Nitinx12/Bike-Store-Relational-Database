"""
metrics.py
Prometheus Pushgateway helper for the ETL / data-quality pipeline.

Why Pushgateway (not a scrape target)
--------------------------------------
Every script that would use this module — main.py, mongo_to_postgres.py,
plpgsql_loops_tests.py, run_gx.py — is a batch job: it starts, does its
work, and exits. Prometheus's normal model is to *pull* metrics from a
long-running process's `/metrics` endpoint; a script that has already
exited has nothing left to scrape. The standard fix for batch/cron-style
jobs is the Prometheus Pushgateway: the job pushes its final metrics to
the gateway right before exiting, the gateway holds them (it's the
long-running piece), and Prometheus scrapes the gateway on its normal
interval. Grafana then reads from Prometheus as usual.[cite: 7]

    main.py / mongo_to_postgres.py   ─┐
    plpgsql_loops_tests.py            ─┼─ push (HTTP) ─▶ Pushgateway ◀── scrape ── Prometheus ◀── query ── Grafana
    run_gx.py                         ─┘

This module intentionally does NOT expose a `/metrics` HTTP endpoint of
its own — that pattern only works for long-running services, and would
be a dead end here.[cite: 7]

Usage
-----
    from utils.metrics import ETLRunMetrics, ValidationRunMetrics

    # main.py / mongo_to_postgres.py — one instance per run, one record_collection()
    # call per collection processed
    metrics = ETLRunMetrics(job="mongo_to_postgres")
    for col in collections:
        summary = process_collection(col, spark, engine, full_load=full_load)
        metrics.record_collection(col, summary)
    metrics.finalize(failed=bool(totals["failed"]))
    metrics.push()   # never raises — logs and swallows push errors[cite: 7]

    # main.py / plpgsql_loops_tests.py / run_gx.py — one instance per run, one
    # record_test() call per test file / expectation
    metrics = ValidationRunMetrics(job="plpgsql_loops_tests")
    for name, ok in results:
        metrics.record_test(name, ok)
    metrics.finalize()
    metrics.push()

Configuration (env vars)
-------------------------
    PUSHGATEWAY_URL       default "localhost:9091"[cite: 7]
    PUSHGATEWAY_TIMEOUT   default 5 (seconds)[cite: 7]

Design notes
------------
- A fresh CollectorRegistry is created per *instance* (i.e. per run),
  never the global default registry. Pushgateway's model is "one job
  pushes one complete snapshot"; reusing a shared registry across runs
  would leak stale label combinations (e.g. a collection that no longer
  exists) into every later push.[cite: 7]
- push() never raises. A metrics backend being down must never fail the
  pipeline it's trying to observe — it logs a warning and returns False
  instead.[cite: 7]
- Every gauge here is a *value at last run*, not a running total, which
  is the right shape for Pushgateway (it replaces, not appends, per
  job/grouping-key). Use Prometheus `increase()`/`rate()` in Grafana over
  the `_total`-suffixed gauges if you want trends across runs.[cite: 7]
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

import os

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "localhost:9091")
PUSHGATEWAY_TIMEOUT = float(os.getenv("PUSHGATEWAY_TIMEOUT", "5"))

_module_logger = logging.getLogger("metrics")


class _BaseRunMetrics:
    """Shared timing/outcome gauges and push machinery for a single batch-job run."""

    def __init__(self, job: str, extra_grouping: Optional[dict] = None):
        self.job = job
        self.registry = CollectorRegistry()
        self.extra_grouping = extra_grouping or {}
        self._start = time.monotonic()
        self._finalized = False

        self.duration_seconds = Gauge(
            "batch_job_duration_seconds",
            "Wall-clock duration of the last run of this job.",
            registry=self.registry,
        )
        self.last_run_timestamp = Gauge(
            "batch_job_last_run_timestamp_seconds",
            "Unix timestamp when this job last completed (success or failure).",
            registry=self.registry,
        )
        self.last_success_timestamp = Gauge(
            "batch_job_last_success_timestamp_seconds",
            "Unix timestamp when this job last completed successfully. Stops "
            "advancing while the job keeps failing, so alerting on a stale "
            "value catches silent failures between runs.",
            registry=self.registry,
        )
        self.run_failed = Gauge(
            "batch_job_failed",
            "1 if the last run of this job ended in failure, else 0.",
            registry=self.registry,
        )

    def finalize(self, failed: bool = False) -> None:
        """Freeze the run's timing/outcome gauges. Call once, right before push()."""
        now = time.time()
        self.duration_seconds.set(time.monotonic() - self._start)
        self.last_run_timestamp.set(now)
        self.run_failed.set(1 if failed else 0)
        if not failed:
            self.last_success_timestamp.set(now)
        self._finalized = True

    def push(self) -> bool:
        """
        Push this run's metrics to the Pushgateway. Never raises. Returns
        True on success, False if the push failed (also logged as a warning
        so it shows up in the script's own log file without stopping it).
        """
        if not self._finalized:
            self.finalize()
        try:
            push_to_gateway(
                PUSHGATEWAY_URL,
                job=self.job,
                registry=self.registry,
                grouping_key=self.extra_grouping or None,
                timeout=PUSHGATEWAY_TIMEOUT,
            )
            return True
        except Exception as exc:
            _module_logger.warning(
                "Could not push metrics for job '%s' to %s: %s",
                self.job, PUSHGATEWAY_URL, exc,
            )
            return False


class ETLRunMetrics(_BaseRunMetrics):
    """
    Per-collection + run-level metrics for mongo_to_postgres.py-style
    incremental ETL jobs. One instance per run; call record_collection()
    once per collection with the dict returned by process_collection().
    """

    def __init__(self, job: str = "mongo_to_postgres", extra_grouping: Optional[dict] = None):
        super().__init__(job, extra_grouping)

        self.rows_source = Gauge(
            "etl_rows_source",
            "Row count in the source collection/table at read time.",
            ["collection"], registry=self.registry,
        )
        self.rows_new = Gauge(
            "etl_rows_new",
            "Rows identified as new/changed since the last run.",
            ["collection"], registry=self.registry,
        )
        self.rows_loaded = Gauge(
            "etl_rows_loaded",
            "Rows successfully merged into the target table.",
            ["collection"], registry=self.registry,
        )
        self.rows_failed = Gauge(
            "etl_rows_failed",
            "Rows that failed to load for this collection.",
            ["collection"], registry=self.registry,
        )
        self.collection_skipped = Gauge(
            "etl_collection_skipped",
            "1 if this collection was skipped (no changes detected), else 0.",
            ["collection"], registry=self.registry,
        )
        self.collections_total = Gauge(
            "etl_collections_total",
            "Total collections considered in this run.",
            registry=self.registry,
        )
        self.collections_skipped_total = Gauge(
            "etl_collections_skipped_total",
            "Number of collections skipped this run.",
            registry=self.registry,
        )

        self._collections_seen = 0
        self._collections_skipped = 0

    def record_collection(self, collection: str, summary: dict) -> None:
        """summary is the per-collection dict produced by process_collection()."""
        self.rows_source.labels(collection=collection).set(summary.get("rows_mongo", 0))
        self.rows_new.labels(collection=collection).set(summary.get("rows_new", 0))
        self.rows_loaded.labels(collection=collection).set(summary.get("rows_loaded", 0))
        self.rows_failed.labels(collection=collection).set(summary.get("failed", 0))
        self.collection_skipped.labels(collection=collection).set(1 if summary.get("skipped") else 0)

        self._collections_seen += 1
        if summary.get("skipped"):
            self._collections_skipped += 1

    def finalize(self, failed: bool = False) -> None:
        self.collections_total.set(self._collections_seen)
        self.collections_skipped_total.set(self._collections_skipped)
        super().finalize(failed=failed)


class ValidationRunMetrics(_BaseRunMetrics):
    """
    Pass/fail metrics for data-quality suites (plpgsql_loops_tests.py,
    run_gx.py). One instance per run; call record_test() once per test
    file / expectation.
    """

    def __init__(self, job: str, extra_grouping: Optional[dict] = None):
        super().__init__(job, extra_grouping)

        self.test_result = Gauge(
            "dq_test_passed",
            "1 if this individual test passed, 0 if it failed.",
            ["test_name"], registry=self.registry,
        )
        self.tests_total = Gauge(
            "dq_tests_total", "Total tests run.", registry=self.registry,
        )
        self.tests_passed_total = Gauge(
            "dq_tests_passed_total", "Total tests passed.", registry=self.registry,
        )
        self.tests_failed_total = Gauge(
            "dq_tests_failed_total", "Total tests failed.", registry=self.registry,
        )

        self._total = 0
        self._passed = 0

    def record_test(self, test_name: str, passed: bool) -> None:
        self.test_result.labels(test_name=test_name).set(1 if passed else 0)
        self._total += 1
        if passed:
            self._passed += 1

    def finalize(self, failed: Optional[bool] = None) -> None:
        self.tests_total.set(self._total)
        self.tests_passed_total.set(self._passed)
        self.tests_failed_total.set(self._total - self._passed)
        if failed is None:
            failed = self._passed < self._total
        super().finalize(failed=failed)