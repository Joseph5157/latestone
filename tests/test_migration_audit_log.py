"""
Migration tests — 007_audit_log (DB-1).

Covers the JSONB round-trip for old_values/new_values, the nullable user_id
FK (for future system-initiated actions), and the untyped entity_id (no FK,
by design — see the migration docstring).

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

TEST_SCHEMA = f"pm_db1_audit_{uuid.uuid4().hex[:8]}"


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


def _seed_users() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.users (username, full_name, role) "
                "VALUES ('admin_a', 'Admin A', 'administrator')"
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
    _seed_users()
    yield
    _drop_test_schema()


class TestAuditLogJsonbRoundTrip:
    def test_old_and_new_values_round_trip(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.audit_log "
                    "(user_id, operation, entity_type, entity_id, old_values, new_values) "
                    "VALUES (:uid, 'assign_technician', 'assignment', 'p1-t1-d1', "
                    "'{\"status\": \"unassigned\"}'::jsonb, "
                    "'{\"status\": \"assigned\", \"technician\": \"tech_a\"}'::jsonb)"
                ),
                {"uid": admin_a},
            )
        with session_scope() as session:
            old_values, new_values = session.execute(
                text(
                    f"SELECT old_values, new_values FROM {TEST_SCHEMA}.audit_log "
                    "WHERE entity_id = 'p1-t1-d1'"
                )
            ).one()
        assert old_values == {"status": "unassigned"}
        assert new_values == {"status": "assigned", "technician": "tech_a"}

    def test_null_old_values_allowed_for_creation_events(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.audit_log "
                    "(user_id, operation, entity_type, entity_id, new_values) "
                    "VALUES (:uid, 'register_device', 'device', 'p1-t1-d2', "
                    "'{\"device_code\": \"d2\"}'::jsonb)"
                ),
                {"uid": admin_a},
            )
        with session_scope() as session:
            old_values = session.execute(
                text(f"SELECT old_values FROM {TEST_SCHEMA}.audit_log WHERE entity_id = 'p1-t1-d2'")
            ).scalar_one()
        assert old_values is None


class TestAuditLogUserIdNullable:
    def test_system_initiated_action_without_user_succeeds(self):
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.audit_log (operation, entity_type, entity_id) "
                    "VALUES ('disable_message_forwarding', 'message_forwarding', '1')"
                )
            )
        with session_scope() as session:
            user_id = session.execute(
                text(
                    f"SELECT user_id FROM {TEST_SCHEMA}.audit_log "
                    "WHERE operation = 'disable_message_forwarding'"
                )
            ).scalar_one()
        assert user_id is None

    def test_unknown_user_rejected(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.audit_log (user_id, operation, entity_type, entity_id) "
                        "VALUES (999999, 'user_update', 'user', '999999')"
                    )
                )


class TestAuditLogEntityIdIsUntyped:
    def test_arbitrary_entity_type_and_id_accepted(self):
        """entity_id has no FK by design — audited entities have heterogeneous key types."""
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.audit_log (user_id, operation, entity_type, entity_id) "
                    "VALUES (:uid, 'role_change', 'user', :eid)"
                ),
                {"uid": admin_a, "eid": str(admin_a)},
            )
