"""
Migration tests — 009_rtl_command_lifecycle (RTL-IF-2).

Covers the four ordering/consistency CHECK constraints added to
rtl_commands: sent_at >= created_at, acknowledged_at >= sent_at (and
requires sent_at), completed_at >= sent_at (and requires sent_at), and
failure_code requiring completed_at. state/command_type still carry no
CHECK (unchanged from migration 008/ADR-017) — that vocabulary is enforced
by services/rtl_command_service.py, not the database, so this file does not
test it.

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

TEST_SCHEMA = f"pm_db1_cmdlifecycle_{uuid.uuid4().hex[:8]}"


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


def _insert_command(request_id: int) -> int:
    with session_scope() as session:
        return session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.rtl_commands "
                "(request_id, device_id, command_type) "
                "VALUES (:rid, 'p1-t1-d1', 'PROGRAM_RTL') "
                "RETURNING command_id"
            ),
            {"rid": request_id},
        ).scalar_one()


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    _drop_test_schema()
    _run_alembic("upgrade", "head")
    _seed_hierarchy_and_users()
    yield
    _drop_test_schema()


def _new_command() -> int:
    return _insert_command(_insert_request())


class TestNewColumnsDefaultToNull:
    def test_lifecycle_columns_default_to_null(self):
        command_id = _new_command()
        with session_scope() as session:
            row = session.execute(
                text(
                    f"SELECT sent_at, acknowledged_at, completed_at, "
                    f"failure_code, failure_detail FROM {TEST_SCHEMA}.rtl_commands "
                    "WHERE command_id = :cid"
                ),
                {"cid": command_id},
            ).one()
        assert row == (None, None, None, None, None)


class TestSentAfterCreated:
    def test_sent_at_at_or_after_created_at_accepted(self):
        command_id = _new_command()
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'SENT', "
                    "sent_at = created_at WHERE command_id = :cid"
                ),
                {"cid": command_id},
            )

    def test_sent_at_before_created_at_rejected(self):
        command_id = _new_command()
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'SENT', "
                        "sent_at = created_at - interval '1 minute' "
                        "WHERE command_id = :cid"
                    ),
                    {"cid": command_id},
                )


class TestAcknowledgedAfterSent:
    def test_acknowledged_at_without_sent_at_rejected(self):
        command_id = _new_command()
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'ACKNOWLEDGED', "
                        "acknowledged_at = now() WHERE command_id = :cid"
                    ),
                    {"cid": command_id},
                )

    def test_acknowledged_at_before_sent_at_rejected(self):
        command_id = _new_command()
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'SENT', "
                    "sent_at = now() WHERE command_id = :cid"
                ),
                {"cid": command_id},
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'ACKNOWLEDGED', "
                        "acknowledged_at = sent_at - interval '1 minute' "
                        "WHERE command_id = :cid"
                    ),
                    {"cid": command_id},
                )

    def test_acknowledged_at_at_or_after_sent_at_accepted(self):
        command_id = _new_command()
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'SENT', "
                    "sent_at = now() WHERE command_id = :cid"
                ),
                {"cid": command_id},
            )
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'ACKNOWLEDGED', "
                    "acknowledged_at = sent_at WHERE command_id = :cid"
                ),
                {"cid": command_id},
            )


class TestCompletedAfterSent:
    def test_completed_at_without_sent_at_rejected(self):
        command_id = _new_command()
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'SUCCEEDED', "
                        "completed_at = now() WHERE command_id = :cid"
                    ),
                    {"cid": command_id},
                )

    def test_completed_at_before_sent_at_rejected(self):
        command_id = _new_command()
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'SENT', "
                    "sent_at = now() WHERE command_id = :cid"
                ),
                {"cid": command_id},
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'FAILED', "
                        "completed_at = sent_at - interval '1 minute' "
                        "WHERE command_id = :cid"
                    ),
                    {"cid": command_id},
                )


class TestFailureRequiresCompletion:
    def test_failure_code_without_completed_at_rejected(self):
        command_id = _new_command()
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'FAILED', "
                        "failure_code = 'SIMULATED_FAILURE' WHERE command_id = :cid"
                    ),
                    {"cid": command_id},
                )

    def test_failure_code_with_completed_at_accepted(self):
        command_id = _new_command()
        with session_scope() as session:
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'SENT', "
                    "sent_at = now() WHERE command_id = :cid"
                ),
                {"cid": command_id},
            )
            session.execute(
                text(
                    f"UPDATE {TEST_SCHEMA}.rtl_commands SET state = 'FAILED', "
                    "completed_at = now(), failure_code = 'SIMULATED_FAILURE', "
                    "failure_detail = 'Simulated transport failure.' "
                    "WHERE command_id = :cid"
                ),
                {"cid": command_id},
            )


class TestUpgradeDowngradeUpgrade:
    def test_upgrade_downgrade_upgrade_round_trips(self):
        """009's columns/constraints survive a downgrade-then-reupgrade
        without residue — the same check test_migration_foundation.py's
        idempotency test performs for a plain re-upgrade, extended to a
        genuine down/up cycle for this migration specifically."""
        down = _run_alembic("downgrade", "008_rtl_commands")
        assert down.returncode == 0, down.stderr

        with session_scope() as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :schema AND table_name = 'rtl_commands'"
                    ),
                    {"schema": TEST_SCHEMA},
                ).scalars().all()
            )
        assert "sent_at" not in columns
        assert "failure_detail" not in columns

        up = _run_alembic("upgrade", "head")
        assert up.returncode == 0, up.stderr

        with session_scope() as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :schema AND table_name = 'rtl_commands'"
                    ),
                    {"schema": TEST_SCHEMA},
                ).scalars().all()
            )
        assert {
            "sent_at", "acknowledged_at", "completed_at",
            "failure_code", "failure_detail",
        } <= columns

        # Re-seed: the downgrade/upgrade cycle above did not touch data in
        # other tables, but this class runs last in file order deliberately
        # so no later test in this module depends on rows created before it.
