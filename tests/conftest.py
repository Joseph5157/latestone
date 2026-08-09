"""Shared pytest configuration.

Repository tests need the seeded local PostgreSQL. They are marked `db` so
the pure-logic suite can run without Docker:
    python -m pytest -m "not db"
"""
from __future__ import annotations

import pytest

from db.engine import check_connection


_DB_AVAILABLE: bool | None = None


def pytest_configure(config):
    config.addinivalue_line("markers", "db: requires a seeded local PostgreSQL")


@pytest.fixture(autouse=True)
def _skip_db_tests_without_database(request):
    """Skip db-marked tests when PostgreSQL is not reachable.

    The connection check runs once per session, not once per test - it opens
    a real connection and there are dozens of db-marked tests.
    """
    global _DB_AVAILABLE
    if not request.node.get_closest_marker("db"):
        return
    if _DB_AVAILABLE is None:
        _DB_AVAILABLE = check_connection()
    if not _DB_AVAILABLE:
        pytest.skip("local PostgreSQL not available")
