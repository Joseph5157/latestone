"""Shared pytest configuration.

Repository tests need the seeded local PostgreSQL. They are marked `db` so
the pure-logic suite can run without Docker:
    python -m pytest -m "not db"
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text

from db.engine import check_connection, session_scope


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


@pytest.fixture(scope="module")
def isolated_schema():
    """A fresh, empty schema — the full DB-1/DB-2 table set via `alembic
    upgrade head` — isolated from the real `plant_monitoring` schema.

    For any test that writes to a persistent table (currently: users, via
    services/prototype_users.py). `python -m pytest` must never change rows
    in the developer's normal plant_monitoring.* tables, so tests that
    create/update/delete persistent rows run against a disposable schema
    instead: same mechanism tests/test_migration_*.py already use to
    provision a schema (`alembic upgrade head` in a subprocess against a
    unique `pm_test_<uuid>` name), extended here to functional/CRUD tests
    rather than just DDL-shape assertions.

    Module-scoped rather than function-scoped: one schema (and one
    `alembic upgrade head` subprocess, the slow part) per test file, not per
    test. Every test in a module that opts in via
    ``pytestmark = pytest.mark.usefixtures("isolated_schema")`` shares it;
    `clear_all_users()` and friends inside that module therefore only ever
    touch this schema, never the real one.

    Redirection works by monkeypatching
    `repositories.plant_monitoring_repository`'s module-level `_SCHEMA`
    constant — every repository function reads that name as a bare global at
    call time, so this is sufficient to redirect all of them without
    touching `config.settings` (which only the *next* Python process, e.g. a
    subprocess spawned by a test, needs to see via the
    `PLANT_MONITORING_SCHEMA` env var instead).
    """
    from repositories import plant_monitoring_repository as repo

    schema = f"pm_test_{uuid.uuid4().hex[:8]}"
    env = dict(os.environ)
    env["PLANT_MONITORING_SCHEMA"] = schema
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Failed to provision isolated test schema {schema}: {result.stderr}"
    )

    mp = pytest.MonkeyPatch()
    mp.setattr(repo, "_SCHEMA", schema)

    yield schema

    mp.undo()
    with session_scope() as session:
        session.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
