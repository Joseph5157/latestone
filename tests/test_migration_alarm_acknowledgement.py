"""Schema contract for the internal device-event acknowledgement fields."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from db.engine import session_scope


pytestmark = [pytest.mark.db, pytest.mark.usefixtures("isolated_schema")]


@pytest.fixture(scope="module", autouse=True)
def _schema(isolated_schema: str):
    with session_scope() as session:
        session.execute(text(f"INSERT INTO {isolated_schema}.users (username, full_name, role) VALUES ('ack', 'Ack', 'administrator')"))
        session.execute(text(f"INSERT INTO {isolated_schema}.plants (plant_id, name, country, latitude, longitude) VALUES ('p1', 'Plant', 'Test', 0, 0)"))
        session.execute(text(f"INSERT INTO {isolated_schema}.transformers (transformer_id, plant_id, transformer_code) VALUES ('t1', 'p1', 't1')"))
        session.execute(text(f"INSERT INTO {isolated_schema}.devices (device_id, transformer_id, device_code) VALUES ('d1', 't1', 'd1')"))


def test_upgrade_passes_table_name_before_check_condition(monkeypatch):
    """Pin Alembic's ``create_check_constraint`` positional contract.

    The migration itself is also exercised through ``isolated_schema`` below,
    but this direct operation assertion makes an accidental reversal precise.
    """
    migration_path = Path(__file__).parents[1] / "alembic" / "versions" / "013_alarm_acknowledgement.py"
    spec = importlib.util.spec_from_file_location("migration_013_alarm_acknowledgement", migration_path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    calls = []
    monkeypatch.setattr(migration.op, "add_column", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "create_foreign_key", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    migration.upgrade()

    assert calls == [(
        (
            "ck_device_events_acknowledgement_pair",
            "device_events",
            "(acknowledged_at IS NULL) = (acknowledged_by_user_id IS NULL)",
        ),
        {"schema": migration.SCHEMA},
    )]


def test_acknowledgement_fields_default_to_null(isolated_schema: str):
    with session_scope() as session:
        row = session.execute(text(f"INSERT INTO {isolated_schema}.device_events (device_id, event_type, event_ts) VALUES ('d1', 'battery_low', now()) RETURNING acknowledged_at, acknowledged_by_user_id")).one()
    assert row == (None, None)


def test_acknowledgement_pair_must_be_complete(isolated_schema: str):
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.execute(text(f"INSERT INTO {isolated_schema}.device_events (device_id, event_type, event_ts, acknowledged_at) VALUES ('d1', 'battery_low', now(), now())"))


def test_acknowledgement_actor_is_a_real_user(isolated_schema: str):
    with pytest.raises(IntegrityError):
        with session_scope() as session:
            session.execute(text(f"INSERT INTO {isolated_schema}.device_events (device_id, event_type, event_ts, acknowledged_at, acknowledged_by_user_id) VALUES ('d1', 'battery_low', now(), now(), 999999)"))
