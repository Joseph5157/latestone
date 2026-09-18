"""Migration tests — 015_freshness_threshold_config (FRESHNESS-CONFIG-1).

Alembic runs in a subprocess against a temporary schema, so the real
development database is never modified (same pattern as
tests/test_migration_temperature_threshold_config.py).
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

TEST_SCHEMA = f"pm_fresh_config_{uuid.uuid4().hex[:8]}"


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PLANT_MONITORING_SCHEMA"] = TEST_SCHEMA
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=os.getcwd(), env=env, capture_output=True, text=True,
    )


def _drop_test_schema() -> None:
    with session_scope() as session:
        session.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))


def _tables() -> set[str]:
    with session_scope() as session:
        return set(
            session.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema"
                ),
                {"schema": TEST_SCHEMA},
            ).scalars().all()
        )


def _insert(row_id: int, minutes: int, user_id: int) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.freshness_threshold_config "
                "(id, stale_after_minutes, configured_by_user_id) "
                "VALUES (:id, :minutes, :user_id)"
            ),
            {"id": row_id, "minutes": minutes, "user_id": user_id},
        )


@pytest.fixture(scope="module", autouse=True)
def _schema():
    _drop_test_schema()
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {TEST_SCHEMA}.users (username, full_name, role) "
                "VALUES ('admin_f', 'Admin F', 'administrator')"
            )
        )
    yield
    _drop_test_schema()


@pytest.fixture
def admin_id():
    with session_scope() as session:
        session.execute(text(f"DELETE FROM {TEST_SCHEMA}.freshness_threshold_config"))
        return session.execute(
            text(f"SELECT user_id FROM {TEST_SCHEMA}.users WHERE username = 'admin_f'")
        ).scalar_one()


class TestFreshnessThresholdConfigTable:
    def test_table_exists_at_head(self):
        assert "freshness_threshold_config" in _tables()

    def test_singleton_only_id_one(self, admin_id):
        _insert(1, 720, admin_id)
        with pytest.raises(IntegrityError):
            _insert(2, 720, admin_id)

    @pytest.mark.parametrize("minutes", [5, 1440, 525600])
    def test_in_range_values_accepted(self, admin_id, minutes):
        _insert(1, minutes, admin_id)

    @pytest.mark.parametrize("minutes", [0, 4, -1, 525601])
    def test_out_of_range_values_rejected(self, admin_id, minutes):
        with pytest.raises(IntegrityError):
            _insert(1, minutes, admin_id)

    def test_actor_must_be_a_real_user(self, admin_id):
        with pytest.raises(IntegrityError):
            _insert(1, 720, admin_id + 999_999)


class TestUpgradeDowngradeUpgrade:
    def test_round_trips_without_residue(self):
        down = _run_alembic("downgrade", "014_alarm_ack_fk_no_action")
        assert down.returncode == 0, down.stderr
        assert "freshness_threshold_config" not in _tables()

        up = _run_alembic("upgrade", "head")
        assert up.returncode == 0, up.stderr
        assert "freshness_threshold_config" in _tables()
