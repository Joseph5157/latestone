"""`list_programming_requests_since` — fleet-scoped recent requests (CC-NEW-1).

Read-only against the dev schema; never writes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from repositories import plant_monitoring_repository as repo

pytestmark = pytest.mark.db


def test_rows_are_inside_the_window_newest_first():
    since = datetime.now(timezone.utc) - timedelta(days=3650)
    rows = repo.list_programming_requests_since(since=since, allowed_device_ids=None, limit=50)
    stamps = [r.requested_at for r in rows]
    assert all(s >= since for s in stamps)
    assert stamps == sorted(stamps, reverse=True)
    assert len(rows) <= 50


def test_future_window_is_empty():
    since = datetime.now(timezone.utc) + timedelta(days=1)
    assert repo.list_programming_requests_since(since=since, allowed_device_ids=None) == []


def test_empty_scope_matches_nothing():
    since = datetime.now(timezone.utc) - timedelta(days=3650)
    assert repo.list_programming_requests_since(since=since, allowed_device_ids=frozenset()) == []
