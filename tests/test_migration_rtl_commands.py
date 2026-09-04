"""
Migration tests — 008_rtl_commands (RTL-IF-1).

Covers the unique constraint on request_id (one command per request), FK
integrity against rtl_programming_requests and devices, the default state
of QUEUED, and the deliberate absence of a CHECK on command_type/state
(open vocabulary, unlike rtl_programming_requests.status).

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

TEST_SCHEMA = f"pm_db1_commands_{uuid.uuid4().hex[:8]}"


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


def _insert_request() -> int:
    admin_a = _user_id("admin_a")
    with session_scope() as session:
        return session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.rtl_programming_requests "
                "(device_id, transformer_id, requested_by, master_msisdn, request_method) "
                "VALUES ('p1-t1-d1', 'p1-t1', :uid, '1234567890', 'dashboard') "
                "RETURNING request_id"
            ),
            {"uid": admin_a},
        ).scalar_one()


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    _drop_test_schema()
    _run_alembic("upgrade", "head")
    _seed_hierarchy_and_users()
    yield
    _drop_test_schema()


class TestRequestIsUnique:
    def test_first_command_for_a_request_succeeds(self):
        request_id = _insert_request()
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                    "(request_id, device_id, command_type) "
                    "VALUES (:rid, 'p1-t1-d1', 'PROGRAM_RTL')"
                ),
                {"rid": request_id},
            )

    def test_second_command_for_the_same_request_is_rejected(self):
        request_id = _insert_request()
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                    "(request_id, device_id, command_type) "
                    "VALUES (:rid, 'p1-t1-d1', 'PROGRAM_RTL')"
                ),
                {"rid": request_id},
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                        "(request_id, device_id, command_type) "
                        "VALUES (:rid, 'p1-t1-d1', 'PROGRAM_RTL')"
                    ),
                    {"rid": request_id},
                )


class TestRtlCommandsForeignKeys:
    def test_unknown_request_rejected(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                        "(request_id, device_id, command_type) "
                        "VALUES (999999, 'p1-t1-d1', 'PROGRAM_RTL')"
                    )
                )

    def test_unknown_device_rejected(self):
        request_id = _insert_request()
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                        "(request_id, device_id, command_type) "
                        "VALUES (:rid, 'does-not-exist', 'PROGRAM_RTL')"
                    ),
                    {"rid": request_id},
                )


class TestDefaultState:
    def test_default_state_is_queued(self):
        request_id = _insert_request()
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                    "(request_id, device_id, command_type) "
                    "VALUES (:rid, 'p1-t1-d1', 'PROGRAM_RTL')"
                ),
                {"rid": request_id},
            )
            state = session.execute(
                text(
                    f"SELECT state FROM {TEST_SCHEMA}.rtl_commands "
                    "WHERE request_id = :rid"
                ),
                {"rid": request_id},
            ).scalar_one()
        assert state == "QUEUED"


class TestCommandTypeAndStateAreOpenVocabulary:
    """No CHECK constraint, unlike rtl_programming_requests.status — a
    future transport tranche must not need a migration to add a state."""

    def test_arbitrary_command_type_and_state_accepted(self):
        request_id = _insert_request()
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                    "(request_id, device_id, command_type, state) "
                    "VALUES (:rid, 'p1-t1-d1', 'SOME_FUTURE_COMMAND_TYPE', "
                    "'SOME_FUTURE_STATE')"
                ),
                {"rid": request_id},
            )
            row = session.execute(
                text(
                    f"SELECT command_type, state FROM {TEST_SCHEMA}.rtl_commands "
                    "WHERE request_id = :rid"
                ),
                {"rid": request_id},
            ).one()
        assert row == ("SOME_FUTURE_COMMAND_TYPE", "SOME_FUTURE_STATE")


class TestNoCascade:
    def test_command_foreign_keys_are_no_action(self):
        with session_scope() as session:
            rules = session.execute(
                text(
                    "SELECT rc.delete_rule "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.referential_constraints rc "
                    "  ON tc.constraint_name = rc.constraint_name "
                    "WHERE tc.constraint_type = 'FOREIGN KEY' "
                    "  AND tc.table_schema = :schema "
                    "  AND tc.table_name = 'rtl_commands'"
                ),
                {"schema": TEST_SCHEMA},
            ).scalars().all()
        assert set(rules) == {"NO ACTION"}
