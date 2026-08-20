"""
Migration tests — 004_user_device_assignments (DB-1).

The load-bearing behavior under test is the partial unique index:
    CREATE UNIQUE INDEX ux_user_device_assignments_active_device
        ON user_device_assignments (device_id) WHERE ended_at IS NULL

A second INSERT with ended_at IS NULL for the same device_id must raise
IntegrityError; closing the first assignment (setting ended_at) and then
inserting a new active row for the same device must succeed.

All tests run Alembic in a SUBPROCESS against a temporary schema so the real
seeded development database is never modified.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from db.engine import session_scope

pytestmark = pytest.mark.db

TEST_SCHEMA = f"pm_db1_assign_{uuid.uuid4().hex[:8]}"


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PLANT_MONITORING_SCHEMA"] = TEST_SCHEMA
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )


def _drop_test_schema() -> None:
    with session_scope() as session:
        session.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))


def _seed_hierarchy_and_users() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.plants (plant_id, name, country, latitude, longitude) "
                "VALUES ('p1', 'Test Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.transformers (transformer_id, plant_id, transformer_code) "
                "VALUES ('p1-t1', 'p1', 't1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.devices (device_id, transformer_id, device_code) "
                "VALUES ('p1-t1-d1', 'p1-t1', 'd1')"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.users (username, full_name, role) VALUES "
                "('tech_a', 'Technician A', 'technician'), "
                "('tech_b', 'Technician B', 'technician'), "
                "('admin_a', 'Admin A', 'administrator')"
            )
        )


def _user_id(username: str) -> int:
    with session_scope() as session:
        return session.execute(
            text(f"SELECT user_id FROM {TEST_SCHEMA}.users WHERE username = :u"),
            {"u": username},
        ).scalar_one()


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    _drop_test_schema()
    _run_alembic("upgrade", "head")
    _seed_hierarchy_and_users()
    yield
    _drop_test_schema()


class TestActiveAssignmentUniqueness:
    def test_first_active_assignment_succeeds(self):
        tech_a = _user_id("tech_a")
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.user_device_assignments "
                    "(device_id, user_id, assigned_by) VALUES ('p1-t1-d1', :uid, :aid)"
                ),
                {"uid": tech_a, "aid": admin_a},
            )

    def test_second_active_assignment_for_same_device_fails(self):
        tech_b = _user_id("tech_b")
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.user_device_assignments "
                        "(device_id, user_id, assigned_by) VALUES ('p1-t1-d1', :uid, :aid)"
                    ),
                    {"uid": tech_b, "aid": admin_a},
                )

    def test_reassignment_after_closing_first_succeeds(self):
        tech_b = _user_id("tech_b")
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.user_device_assignments "
                    "SET ended_at = now() WHERE device_id = 'p1-t1-d1' AND ended_at IS NULL"
                )
            )
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.user_device_assignments "
                    "(device_id, user_id, assigned_by) VALUES ('p1-t1-d1', :uid, :aid)"
                ),
                {"uid": tech_b, "aid": admin_a},
            )
        with session_scope() as session:
            history = session.execute(
                text(
                    f"SELECT user_id, ended_at IS NULL FROM {TEST_SCHEMA}.user_device_assignments "
                    "WHERE device_id = 'p1-t1-d1' ORDER BY assignment_id"
                )
            ).all()
        assert len(history) == 2
        assert history[0][1] is False  # first assignment closed
        assert history[1][1] is True   # second assignment active
        assert history[1][0] == tech_b


class TestAssignmentConstraints:
    def test_ended_before_assigned_rejected(self):
        tech_a = _user_id("tech_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.user_device_assignments "
                        "(device_id, user_id, assigned_at, ended_at) "
                        "VALUES ('p1-t1-d1', :uid, now(), now() - interval '1 day')"
                    ),
                    {"uid": tech_a},
                )

    def test_unknown_device_rejected(self):
        tech_a = _user_id("tech_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.user_device_assignments "
                        "(device_id, user_id) VALUES ('does-not-exist', :uid)"
                    ),
                    {"uid": tech_a},
                )
