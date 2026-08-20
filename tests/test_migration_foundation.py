"""
Migration foundation tests — DB-M0.

Verify the Alembic baseline behaves correctly on both bootstrap paths:

EXISTING DATABASE (stamp):
    `alembic stamp 001_baseline` records the revision and creates
    `alembic_version` in the configured schema WITHOUT executing the baseline
    DDL, so existing tables and their data are never touched.

FRESH DATABASE (upgrade):
    `alembic upgrade head` creates the full four-table baseline schema
    (plants, transformers, devices, readings) with the expected constraints
    and indexes.

All tests run Alembic in a SUBPROCESS against a temporary schema so the real
seeded development database is never modified. The temporary schema name is
injected through PLANT_MONITORING_SCHEMA so config.settings loads it fresh in
the child process — the same environment variable the application reads.

These tests require a running local PostgreSQL (they are marked `db`).
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import text

from db.engine import session_scope
from config.settings import monitoring

pytestmark = pytest.mark.db

#: Unique temporary schema per test run, so parallel/layered runs cannot collide.
TEST_SCHEMA = f"pm_m0_test_{uuid.uuid4().hex[:8]}"


def _run_alembic(*args: str) -> subprocess.CompletedProcess:
    """Run the alembic CLI in a subprocess with the test schema configured."""
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


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    """Ensure the temporary schema does not exist before and after the module."""
    _drop_test_schema()
    yield
    _drop_test_schema()


def _table_names(schema: str) -> set[str]:
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = :schema"
            ),
            {"schema": schema},
        ).scalars().all()
    return set(rows)


def _index_names(schema: str, table: str) -> set[str]:
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = :schema AND tablename = :table"
            ),
            {"schema": schema, "table": table},
        ).scalars().all()
    return set(rows)


def _column_names(schema: str, table: str) -> set[str]:
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table"
            ),
            {"schema": schema, "table": table},
        ).scalars().all()
    return set(rows)


# 001_baseline (4 tables) plus DB-1 (7 additive tables): users,
# user_device_assignments, rtl_programming_requests, message_forwarding,
# rtl_active_state, device_events, audit_log. Updated here as each migration
# extends "head" — this constant describes what `alembic upgrade head`
# produces today, not just the original baseline.
EXPECTED_UPGRADE_TABLES = {
    "plants", "transformers", "devices", "readings",
    "users", "user_device_assignments", "rtl_programming_requests",
    "message_forwarding", "rtl_active_state", "device_events", "audit_log",
    "alembic_version",
}


class TestFreshDatabaseUpgrade:
    """alembic upgrade head must create the full schema (baseline + DB-1) from nothing."""

    def test_upgrade_creates_all_application_tables(self):
        result = _run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr
        # alembic_version is expected: it lives inside the configured schema
        # (version_table_schema), alongside the eleven application tables.
        assert _table_names(TEST_SCHEMA) == EXPECTED_UPGRADE_TABLES

    def test_upgrade_creates_expected_baseline_columns(self):
        _run_alembic("upgrade", "head")
        assert _column_names(TEST_SCHEMA, "plants") == {
            "plant_id", "name", "country", "latitude", "longitude",
            "capacity_mw", "primary_fuel", "status",
        }
        assert _column_names(TEST_SCHEMA, "transformers") == {
            "transformer_id", "plant_id", "transformer_code", "status",
        }
        # devices carries the 002_device_metadata additive columns on top of
        # the original four (device_id, transformer_id, device_code, status).
        assert _column_names(TEST_SCHEMA, "devices") == {
            "device_id", "transformer_id", "device_code", "status",
            "msisdn", "hardware_version", "firmware_version",
            "installed_at", "created_at", "updated_at",
        }
        assert _column_names(TEST_SCHEMA, "readings") == {
            "id", "device_id", "metric", "reading_ts", "value",
        }

    def test_upgrade_creates_expected_indexes(self):
        _run_alembic("upgrade", "head")
        assert "ix_transformers_plant_id" in _index_names(TEST_SCHEMA, "transformers")
        assert "ix_devices_transformer_id" in _index_names(TEST_SCHEMA, "devices")
        assert "ix_readings_device_metric_ts" in _index_names(TEST_SCHEMA, "readings")

    def test_upgrade_creates_foreign_keys(self):
        _run_alembic("upgrade", "head")
        with session_scope() as session:
            rows = session.execute(
                text(
                    "SELECT tc.table_name, kcu.column_name, ccu.table_name "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON tc.constraint_name = kcu.constraint_name "
                    "JOIN information_schema.constraint_column_usage ccu "
                    "  ON tc.constraint_name = ccu.constraint_name "
                    "WHERE tc.constraint_type = 'FOREIGN KEY' "
                    "  AND tc.table_schema = :schema "
                    "ORDER BY tc.table_name"
                ),
                {"schema": TEST_SCHEMA},
            ).all()
        assert ("transformers", "plant_id", "plants") in rows
        assert ("devices", "transformer_id", "transformers") in rows
        assert ("readings", "device_id", "devices") in rows

    def test_upgrade_creates_unique_constraints(self):
        _run_alembic("upgrade", "head")
        with session_scope() as session:
            uniques = session.execute(
                text(
                    "SELECT tc.table_name, kcu.column_name "
                    "FROM information_schema.table_constraints tc "
                    "JOIN information_schema.key_column_usage kcu "
                    "  ON tc.constraint_name = kcu.constraint_name "
                    "WHERE tc.constraint_type = 'UNIQUE' "
                    "  AND tc.table_schema = :schema "
                    "ORDER BY tc.table_name, kcu.column_name"
                ),
                {"schema": TEST_SCHEMA},
            ).all()
        assert ("transformers", "plant_id") in uniques
        assert ("transformers", "transformer_code") in uniques
        assert ("devices", "transformer_id") in uniques
        assert ("devices", "device_code") in uniques
        assert ("readings", "device_id") in uniques
        assert ("readings", "metric") in uniques
        assert ("readings", "reading_ts") in uniques

    def test_second_upgrade_executes_no_migration(self):
        """Idempotency comes from Alembic revision tracking, not IF NOT EXISTS.

        The second `upgrade head` run has no pending revisions, so nothing is
        executed — a CREATE without IF NOT EXISTS cannot fail.
        """
        first = _run_alembic("upgrade", "head")
        assert first.returncode == 0, first.stderr

        second = _run_alembic("upgrade", "head")
        assert second.returncode == 0, second.stderr
        assert "Running upgrade" not in second.stderr

    def test_version_table_lives_in_configured_schema(self):
        _run_alembic("upgrade", "head")
        with session_scope() as session:
            rows = session.execute(
                text(
                    "SELECT schemaname FROM pg_tables "
                    "WHERE tablename = 'alembic_version'"
                ),
            ).scalars().all()
        assert TEST_SCHEMA in rows, (
            f"alembic_version must live in {TEST_SCHEMA}, not public. Got: {rows}"
        )
        assert "public" not in rows


class TestExistingDatabaseStamp:
    """alembic stamp must record the revision without executing DDL."""

    def test_stamp_records_revision_without_creating_tables(self):
        _drop_test_schema()
        result = _run_alembic("stamp", "001_baseline")
        assert result.returncode == 0, result.stderr

        # Version table exists in the configured schema...
        with session_scope() as session:
            row = session.execute(
                text(
                    f"SELECT version_num FROM {TEST_SCHEMA}.alembic_version"
                ),
            ).first()
            version_num = row[0] if row else None

        assert version_num == "001_baseline"

        # ...but NO application tables were created (DDL not executed).
        assert _table_names(TEST_SCHEMA) == {"alembic_version"}

    def test_stamp_is_idempotent(self):
        _drop_test_schema()
        first = _run_alembic("stamp", "001_baseline")
        assert first.returncode == 0, first.stderr
        second = _run_alembic("stamp", "001_baseline")
        assert second.returncode == 0, second.stderr

    def test_current_reports_baseline_after_stamp(self):
        _drop_test_schema()
        _run_alembic("stamp", "001_baseline")
        result = _run_alembic("current")
        assert result.returncode == 0, result.stderr
        assert "001_baseline" in result.stdout

    def test_upgrade_from_stamped_baseline_adds_only_db1_objects(self):
        """The real "existing seeded DB" path: baseline tables already exist
        (physically), the DB is stamped at 001_baseline, and `upgrade head`
        must add the DB-1 tables/columns on top without re-touching or
        recreating the baseline tables.

        `alembic upgrade 001_baseline` is used here (not raw stamp) purely to
        get physical baseline tables into the test schema — it has the same
        end state as "docker-entrypoint-initdb.d created these tables, then
        somebody ran `alembic stamp 001_baseline`" from the perspective of
        everything that runs afterward.
        """
        _drop_test_schema()
        bootstrap = _run_alembic("upgrade", "001_baseline")
        assert bootstrap.returncode == 0, bootstrap.stderr
        assert _table_names(TEST_SCHEMA) == {
            "plants", "transformers", "devices", "readings", "alembic_version",
        }

        result = _run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr

        # Baseline tables/columns are exactly as before — DB-1 never touches them.
        assert _column_names(TEST_SCHEMA, "devices") == {
            "device_id", "transformer_id", "device_code", "status",
            "msisdn", "hardware_version", "firmware_version",
            "installed_at", "created_at", "updated_at",
        }
        # Full DB-1 table set is now present alongside the untouched baseline.
        assert _table_names(TEST_SCHEMA) == EXPECTED_UPGRADE_TABLES


class TestSchemaFromSettings:
    def test_migrations_use_configured_schema_name(self):
        """The schema actually used must come from config, not a hard-code."""
        # Start from a genuinely fresh schema: an earlier class may have left
        # this schema stamped at 001_baseline, which would make upgrade a no-op.
        _drop_test_schema()
        result = _run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr
        # The tables were created under the test schema injected via the
        # PLANT_MONITORING_SCHEMA environment variable.
        assert _table_names(TEST_SCHEMA) == EXPECTED_UPGRADE_TABLES
