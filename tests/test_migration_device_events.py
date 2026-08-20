"""
Migration tests — 006_device_events (DB-1).

Covers the attribution CHECK (device_id / transformer_id / reported_uid),
the deliberate absence of a CHECK on event_type (open vocabulary), and the
invalid_uid case that reported_uid exists specifically to support.

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

TEST_SCHEMA = f"pm_db1_events_{uuid.uuid4().hex[:8]}"


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


def _seed_hierarchy() -> None:
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


@pytest.fixture(scope="module", autouse=True)
def _clean_test_schema():
    _drop_test_schema()
    _run_alembic("upgrade", "head")
    _seed_hierarchy()
    yield
    _drop_test_schema()


class TestAttributionCheck:
    def test_known_device_event_succeeds(self):
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.device_events (device_id, event_type, event_ts) "
                    "VALUES ('p1-t1-d1', 'startup', now())"
                )
            )

    def test_transformer_scoped_event_succeeds(self):
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.device_events (transformer_id, event_type, event_ts) "
                    "VALUES ('p1-t1', 'comms_alarm', now())"
                )
            )

    def test_invalid_uid_event_with_only_reported_uid_succeeds(self):
        """The scenario reported_uid exists for: a UID that matches no registered device."""
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.device_events (reported_uid, event_type, event_ts) "
                    "VALUES ('29999', 'invalid_uid', now())"
                )
            )
        with session_scope() as session:
            row = session.execute(
                text(
                    f"SELECT device_id, transformer_id, reported_uid FROM {TEST_SCHEMA}.device_events "
                    "WHERE reported_uid = '29999'"
                )
            ).one()
        assert row == (None, None, "29999")

    def test_event_with_no_attribution_at_all_fails(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.device_events (event_type, event_ts) "
                        "VALUES ('startup', now())"
                    )
                )


class TestEventTypeIsOpenVocabulary:
    def test_documented_event_types_accepted(self):
        documented = [
            "startup", "check_in", "sensor_error", "battery_low", "power_down",
            "comms_alarm", "high_temperature", "vibration_event", "invalid_uid",
        ]
        with session_scope() as session:
            for event_type in documented:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.device_events (device_id, event_type, event_ts) "
                        "VALUES ('p1-t1-d1', :et, now())"
                    ),
                    {"et": event_type},
                )

    def test_arbitrary_future_event_type_succeeds(self):
        """event_type has no CHECK: a legitimate new type must not require a migration."""
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {TEST_SCHEMA}.device_events (device_id, event_type, event_ts) "
                    "VALUES ('p1-t1-d1', 'firmware_update_completed', now())"
                )
            )
        with session_scope() as session:
            count = session.execute(
                text(
                    f"SELECT COUNT(*) FROM {TEST_SCHEMA}.device_events "
                    "WHERE event_type = 'firmware_update_completed'"
                )
            ).scalar_one()
        assert count == 1


class TestDeviceEventsForeignKeys:
    def test_unknown_device_rejected(self):
        with pytest.raises(IntegrityError):
            with session_scope() as session:
                session.execute(
                    text(
                        f"INSERT INTO {TEST_SCHEMA}.device_events (device_id, event_type, event_ts) "
                        "VALUES ('does-not-exist', 'startup', now())"
                    )
                )
