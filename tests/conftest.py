"""Shared pytest configuration.

Repository tests need the seeded local PostgreSQL. They are marked `db` so
the pure-logic suite can run without Docker:
    python -m pytest -m "not db"
"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
import uuid

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

from db.engine import check_connection, session_scope

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


class UnexpectedDatabaseAccess(RuntimeError):
    """Raised inside an unmarked test that tried to reach PostgreSQL."""


def _application_frames() -> str:
    """The project's own frames from the current stack, innermost last.

    SQLAlchemy and pytest frames are the bulk of the stack and say nothing
    about which application call went to the database, so they are dropped —
    as are this file's own frames, which are always the innermost ones and
    only ever point back at the guard itself.
    """
    frames = [
        f
        for f in traceback.extract_stack()
        if f.filename.startswith(_PROJECT_ROOT)
        and "site-packages" not in f.filename
        and os.path.abspath(f.filename) != os.path.abspath(__file__)
    ]
    return "".join(traceback.format_list(frames)) or "  <no application frames>\n"


@pytest.fixture(autouse=True)
def _no_database_outside_db_marked_tests(request):
    """Fail any test *without* the `db` marker that opens a connection.

    `python -m pytest -m "not db"` is documented as the pure-logic suite, and
    a test that quietly reaches the database breaks that promise in a way
    that is invisible on a developer machine: it passes here, against the
    running local PostgreSQL, and only fails on a clean checkout or in CI.
    That is exactly how an unmocked `hierarchy_service.list_all_devices` call
    survived review in tests/test_fleet_condition.py.

    Listens on the `Engine` *class*, so it covers every engine including any
    created later, and fires on pooled reuse as well as on new connections —
    watching psycopg2 alone would miss a connection a db-marked test had
    already left in the pool during a full-suite run.

    The raise stops the query, but application code that catches broad
    exceptions (`callbacks.listings.listing_outputs`, for one) can swallow
    it, so the attempt is also recorded and failed at teardown where nothing
    can intercept it.

    Not reachable across a process boundary: a test that shells out (the
    `alembic upgrade head` subprocess in `isolated_schema`, say) is
    unaffected by this fixture, which is fine — those are db-marked.
    """
    if request.node.get_closest_marker("db"):
        yield
        return

    attempts: list[str] = []

    def _refuse(_connection) -> None:
        attempts.append(_application_frames())
        raise UnexpectedDatabaseAccess(
            f"{request.node.nodeid} is not marked `db` but opened a database "
            f"connection. Mock the service/repository call, or mark the test "
            f"`@pytest.mark.db`."
        )

    event.listen(Engine, "engine_connect", _refuse)
    try:
        yield
    finally:
        event.remove(Engine, "engine_connect", _refuse)

    if attempts:
        pytest.fail(
            f"{request.node.nodeid} is not marked `db` but opened "
            f"{len(attempts)} database connection(s). Mock the service or "
            f"repository call, or mark the test `@pytest.mark.db`.\n\n"
            f"Application frames of the first attempt:\n{attempts[0]}",
            pytrace=False,
        )


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
