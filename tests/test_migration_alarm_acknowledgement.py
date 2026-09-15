"""Schema contract for the internal device-event acknowledgement fields."""
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
TEST_SCHEMA = f"pm_alarm_ack_{uuid.uuid4().hex[:8]}"


def _run_alembic(*args: str) -> None:
    env = dict(os.environ)
    env["PLANT_MONITORING_SCHEMA"] = TEST_SCHEMA
    subprocess.run([sys.executable, "-m", "alembic", *args], cwd=os.getcwd(), env=env, check=True, capture_output=True, text=True)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    with session_scope() as session:
        session.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
    _run_alembic("upgrade", "head")
    with session_scope() as session:
        session.execute(text(f"INSERT INTO {TEST_SCHEMA}.users (username, full_name, role) VALUES ('ack', 'Ack', 'administrator')"))
        session.execute(text(f"INSERT INTO {TEST_SCHEMA}.plants (plant_id, name, country, latitude, longitude) VALUES ('p1', 'Plant', 'Test', 0, 0)"))
        session.execute(text(f"INSERT INTO {TEST_SCHEMA}.transformers (transformer_id, plant_id, transformer_code) VALUES ('t1', 'p1', 't1')"))
        session.execute(text(f"INSERT INTO {TEST_SCHEMA}.devices (device_id, transformer_id, device_code) VALUES ('d1', 't1', 'd1')"))
    yield
    with session_scope() as session:
        session.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))


def test_acknowledgement_fields_default_to_null():
    with session_scope() as session:
        row = session.execute(text(f"INSERT INTO {TEST_SCHEMA}.device_events (device_id, event_type, event_ts) VALUES ('d1', 'battery_low', now()) RETURNING acknowledged_at, acknowledged_by_user_id")).one()
    assert row == (None, None)


def test_acknowledgement_pair_must_be_complete():
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.execute(text(f"INSERT INTO {TEST_SCHEMA}.device_events (device_id, event_type, event_ts, acknowledged_at) VALUES ('d1', 'battery_low', now(), now())"))


def test_acknowledgement_actor_is_a_real_user():
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.execute(text(f"INSERT INTO {TEST_SCHEMA}.device_events (device_id, event_type, event_ts, acknowledged_at, acknowledged_by_user_id) VALUES ('d1', 'battery_low', now(), now(), 999999)"))
