"""
Migration tests — 011_temperature_threshold_config (THRESH-CONFIG-1).

Covers the singleton constraint (id=1 only), the FK to users, the NOT NULL
warning/critical columns, and a genuine downgrade-then-reupgrade round trip.
All tests run Alembic in a SUBPROCESS against a temporary schema so the real
seeded development database is never modified — same pattern as
tests/test_migration_forwarding_auto_disable.py.
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

TEST_SCHEMA = f"pm_thresh_config_{uuid.uuid4().hex[:8]}"


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


def _seed_user() -> None:
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
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr
    _seed_user()
    yield
    _drop_test_schema()


class TestTemperatureThresholdConfig:
    def setup_method(self):
        # Each test starts with an empty config table — the module-scoped
        # schema fixture is shared across tests in this class, and the
        # singleton constraint under test means leftover state from one
        # test would change what the next test is actually exercising.
        with session_scope() as session:
            session.execute(
                text(f"DELETE FROM {TEST_SCHEMA}.temperature_threshold_config")
            )

    def test_singleton_row_accepted(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                    "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                    "VALUES (1, 60.0, 75.0, :uid)"
                ),
                {"uid": admin_a},
            )

    def test_non_singleton_id_rejected_by_check_constraint(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                        "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                        "VALUES (2, 60.0, 75.0, :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_second_row_at_id_one_rejected_by_primary_key(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                    "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                    "VALUES (1, 60.0, 75.0, :uid)"
                ),
                {"uid": admin_a},
            )
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                        "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                        "VALUES (1, 61.0, 76.0, :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_missing_warning_rejected(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                        "(id, critical_temperature_c, configured_by_user_id) "
                        "VALUES (1, 75.0, :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_missing_critical_rejected(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                        "(id, warning_temperature_c, configured_by_user_id) "
                        "VALUES (1, 60.0, :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_unknown_user_rejected(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                        "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                        "VALUES (1, 60.0, 75.0, 999999)"
                    )
                )

    def test_database_rejects_warning_greater_than_critical(self):
        """Correctness fix: `warning_temperature_c < critical_temperature_c`
        IS a database CHECK (`ck_temperature_threshold_config_warning_lt_critical`)
        — the schema protects this relational invariant for any caller,
        not only the service. A service-side check on raw floats cannot be
        trusted to still hold once both values round to this column's
        fixed NUMERIC(12,3) scale, so the schema verifies it directly
        against what is actually persisted."""
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                        "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                        "VALUES (1, 90.0, 10.0, :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_database_rejects_warning_equal_to_critical(self):
        admin_a = _user_id("admin_a")
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                        "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                        "VALUES (1, 50.0, 50.0, :uid)"
                    ),
                    {"uid": admin_a},
                )

    def test_database_accepts_warning_below_critical(self):
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                    "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                    "VALUES (1, 10.0, 90.0, :uid)"
                ),
                {"uid": admin_a},
            )

    def test_excess_precision_is_rounded_by_the_database_not_rejected(self):
        """The DB's own rounding for a raw direct write is intentionally
        NOT the enforcement point for excess precision (that is the
        SERVICE's job, tested in test_temperature_threshold.py, where it
        REJECTS rather than rounds) — this only confirms what a bypassing
        direct write actually gets, so that fact stays documented rather
        than assumed."""
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                    "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                    "VALUES (1, 20.00049, 30.0, :uid)"
                ),
                {"uid": admin_a},
            )
            stored = session.execute(
                text(
                    f"SELECT warning_temperature_c FROM {TEST_SCHEMA}.temperature_threshold_config "
                    "WHERE id = 1"
                )
            ).scalar_one()
        assert str(stored) == "20.000"

    def test_row_can_be_replaced_after_delete(self):
        # The application layer upserts/deletes id=1 rather than ever
        # inserting a second row (repositories.plant_monitoring_repository.
        # set_/clear_temperature_threshold_config) — this just confirms the
        # schema itself permits that lifecycle.
        admin_a = _user_id("admin_a")
        with session_scope() as session:
            session.execute(
                text(
                    f"DELETE FROM {TEST_SCHEMA}.temperature_threshold_config WHERE id = 1"
                )
            )
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.temperature_threshold_config "
                    "(id, warning_temperature_c, critical_temperature_c, configured_by_user_id) "
                    "VALUES (1, 55.0, 70.0, :uid)"
                ),
                {"uid": admin_a},
            )


class TestUpgradeDowngradeUpgrade:
    def test_upgrade_downgrade_upgrade_round_trips(self):
        """011's table survives a downgrade-then-reupgrade without residue,
        same shape as test_migration_rtl_command_lifecycle.py's equivalent
        check."""
        down = _run_alembic("downgrade", "010_forwarding_auto_disable")
        assert down.returncode == 0, down.stderr

        with session_scope() as session:
            tables = set(
                session.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = :schema"
                    ),
                    {"schema": TEST_SCHEMA},
                ).scalars().all()
            )
        assert "temperature_threshold_config" not in tables

        up = _run_alembic("upgrade", "head")
        assert up.returncode == 0, up.stderr

        with session_scope() as session:
            columns = set(
                session.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = :schema AND table_name = 'temperature_threshold_config'"
                    ),
                    {"schema": TEST_SCHEMA},
                ).scalars().all()
            )
        assert {
            "id", "warning_temperature_c", "critical_temperature_c",
            "configured_by_user_id", "configured_at",
        } <= columns
        # No re-seed needed: the downgrade/upgrade cycle never touched
        # `users` (only this migration's own table), and this class runs
        # last in file order, so admin_a from the module fixture is still
        # exactly one row — re-inserting it would violate its own username
        # UNIQUE constraint.
