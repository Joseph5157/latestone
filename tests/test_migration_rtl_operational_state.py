"""
Migration tests — 005_rtl_operational_state (DB-1).

Covers rtl_programming_requests (status CHECK, FK integrity),
message_forwarding (PK=FK on user_id), and rtl_active_state (PK=FK on
device_id, independent of devices.status).

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

TEST_SCHEMA = f"pm_db1_rtlops_{uuid.uuid4().hex[:8]}"


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
    _seed_hierarchy_and_users()
    yield
    _drop_test_schema()


class TestRtlProgrammingRequests:
    def test_valid_status_accepted(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.rtl_programming_requests "
                    "(device_id, transformer_id, requested_by, master_msisdn, request_method, status) "
                    "VALUES ('p1-t1-d1', 'p1-t1', :uid, '1234567890', 'sms', 'pending')"
                ),
                {"uid": admin_a},
            )

    def test_invalid_status_rejected(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.rtl_programming_requests "
                        "(device_id, transformer_id, requested_by, master_msisdn, request_method, status) "
                        "VALUES ('p1-t1-d1', 'p1-t1', :uid, '1234567890', 'sms', 'not_a_real_status')"
                    ),
                    {"uid": admin_a},
                )

    def test_default_status_is_pending(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.rtl_programming_requests "
                    "(device_id, transformer_id, requested_by, master_msisdn, request_method) "
                    "VALUES ('p1-t1-d1', 'p1-t1', :uid, '1234567890', 'sms')"
                ),
                {"uid": admin_a},
            )
            status = session.execute(
                text(
                    f"SELECT status FROM {TEST_SCHEMA}.rtl_programming_requests "
                    "WHERE master_msisdn = '1234567890' ORDER BY request_id DESC LIMIT 1"
                )
            ).scalar_one()
        assert status == "pending"

    def test_completed_before_requested_rejected(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.rtl_programming_requests "
                        "(device_id, transformer_id, requested_by, master_msisdn, request_method, "
                        "requested_at, completed_at, status) "
                        "VALUES ('p1-t1-d1', 'p1-t1', :uid, '1234567890', 'sms', "
                        "now(), now() - interval '1 day', 'successful')"
                    ),
                    {"uid": admin_a},
                )


class TestMessageForwarding:
    def test_user_id_is_pk_and_fk(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(f"INSERT INTO {TEST_SCHEMA}.message_forwarding (user_id, enabled) VALUES (:uid, true)"),
                {"uid": admin_a},
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(f"INSERT INTO {TEST_SCHEMA}.message_forwarding (user_id, enabled) VALUES (:uid, false)"),
                    {"uid": admin_a},
                )

    def test_unknown_user_rejected(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(f"INSERT INTO {TEST_SCHEMA}.message_forwarding (user_id) VALUES (999999)")
                )


class TestRtlActiveState:
    def test_device_id_is_pk_and_fk(self):
        with session_scope() as session:
            session.execute(
                text(f"INSERT INTO {TEST_SCHEMA}.rtl_active_state (device_id, is_active) VALUES ('p1-t1-d1', true)")
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(f"INSERT INTO {TEST_SCHEMA}.rtl_active_state (device_id) VALUES ('p1-t1-d1')")
                )

    def test_independent_of_device_administrative_status(self):
        # devices.status defaults to 'active'; rtl_active_state.is_active
        # is a completely separate concept and must not be coupled to it.
        with session_scope() as session:
            device_status, rtl_active = session.execute(
                text(
                    f"SELECT d.status, r.is_active FROM {TEST_SCHEMA}.devices d "
                    f"JOIN {TEST_SCHEMA}.rtl_active_state r ON r.device_id = d.device_id "
                    "WHERE d.device_id = 'p1-t1-d1'"
                )
            ).one()
        assert device_status == "active"
        assert rtl_active is True  # set in test_device_id_is_pk_and_fk above
