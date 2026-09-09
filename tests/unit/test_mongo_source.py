"""Tests for src/pipeline/mongo_source.py."""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.pipeline.mongo_source import to_iso


def test_to_iso_none():
    assert to_iso(None) is None


def test_to_iso_string():
    assert to_iso("2026-06-15T12:00:00") == "2026-06-15T12:00:00"


def test_to_iso_datetime_naive():
    dt = datetime(2026, 6, 15, 12, 30, 45)  # noqa: DTZ001
    assert to_iso(dt) == "2026-06-15T12:30:45"


def test_to_iso_datetime_aware():
    dt = datetime(2026, 6, 15, 12, 30, 45, tzinfo=UTC)
    assert to_iso(dt) == "2026-06-15T12:30:45"


def test_to_iso_date():
    d = date(2026, 6, 15)
    assert to_iso(d) == "2026-06-15T00:00:00"
