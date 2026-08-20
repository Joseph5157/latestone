"""
Migration tests — 002_device_metadata (DB-1).

Verifies the additive devices metadata columns without touching the
original four columns (device_id, transformer_id, device_code, status).

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

from db.engine import session_scope

pytestmark = pytest.mark.db

TEST_SCHEMA = f"pm_db1_devmeta_{uuid.uuid4().hex[:8]}"


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


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    _drop_test_schema()
    yield
    _drop_test_schema()


def _column_names(table: str) -> set[str]:
    with session_scope() as session:
        rows = session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table"
            ),
            {"schema": TEST_SCHEMA, "table": table},
        ).scalars().all()
    return set(rows)


def _is_nullable(table: str, column: str) -> bool:
    with session_scope() as session:
        value = session.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :table AND column_name = :column"
            ),
            {"schema": TEST_SCHEMA, "table": table, "column": column},
        ).scalar_one()
    return value == "YES"


class TestDeviceMetadataUpgrade:
    def test_original_device_columns_preserved(self):
        result = _run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr
        columns = _column_names("devices")
        assert {"device_id", "transformer_id", "device_code", "status"} <= columns

    def test_new_metadata_columns_present(self):
        columns = _column_names("devices")
        assert {
            "msisdn", "hardware_version", "firmware_version",
            "installed_at", "created_at", "updated_at",
        } <= columns

    def test_optional_metadata_columns_are_nullable(self):
        for column in ("msisdn", "hardware_version", "firmware_version", "installed_at"):
            assert _is_nullable("devices", column), f"{column} should be nullable"

    def test_lifecycle_timestamps_are_not_nullable(self):
        for column in ("created_at", "updated_at"):
            assert not _is_nullable("devices", column), f"{column} should be NOT NULL"

    def test_existing_seeded_style_row_gets_default_timestamps(self):
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.plants "
                    "(plant_id, name, country, latitude, longitude) "
                    "VALUES ('p1', 'Test Plant', 'Testland', 0, 0)"
                )
            )
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.transformers "
                    "(transformer_id, plant_id, transformer_code) "
                    "VALUES ('p1-t1', 'p1', 't1')"
                )
            )
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.devices "
                    "(device_id, transformer_id, device_code) "
                    "VALUES ('p1-t1-d1', 'p1-t1', 'd1')"
                )
            )
            row = session.execute(
                text(
                    f"SELECT msisdn, created_at, updated_at FROM {TEST_SCHEMA}.devices "
                    "WHERE device_id = 'p1-t1-d1'"
                )
            ).one()
        assert row[0] is None
        assert row[1] is not None
        assert row[2] is not None


class TestDeviceMetadataDowngrade:
    def test_downgrade_removes_only_new_columns(self):
        result = _run_alembic("downgrade", "001_baseline")
        assert result.returncode == 0, result.stderr
        columns = _column_names("devices")
        assert columns == {"device_id", "transformer_id", "device_code", "status"}

    def test_reupgrade_restores_new_columns(self):
        result = _run_alembic("upgrade", "head")
        assert result.returncode == 0, result.stderr
        columns = _column_names("devices")
        assert {
            "msisdn", "hardware_version", "firmware_version",
            "installed_at", "created_at", "updated_at",
        } <= columns
