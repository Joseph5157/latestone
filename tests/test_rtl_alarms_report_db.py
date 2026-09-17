"""REPORT-3 database-backed tests — RTL Alarms (30 Days) on the isolated
schema (tests/conftest.py).

Locks the refined R3-D6 semantics explicitly:
- an event with an explicit historical transformer_id keeps reporting that
  transformer even after devices.transformer_id is changed;
- an event whose transformer_id is NULL falls back to the device's CURRENT
  transformer.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_INVALID_UID,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope
from services.report_service import rtl_alarms_30d_rows

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

PLANT = "rep-p1"
T1 = "rep-p1-t1"
T2 = "rep-p1-t2"
D1 = "rep-p1-t1-d1"   # code 29501, currently under T1


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "device_events", "rtl_active_state",
            "rtl_programming_requests", "message_forwarding",
            "user_device_assignments", "readings",
            "devices", "transformers", "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed(with_second_transformer: bool = False) -> list[str]:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                f"VALUES ('{PLANT}', 'Report Plant', 'Testland', 0, 0)"
            )
        )
        transformers = [T1] + ([T2] if with_second_transformer else [])
        for i, transformer_id in enumerate(transformers, start=1):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.transformers "
                    "(transformer_id, plant_id, transformer_code) "
                    f"VALUES ('{transformer_id}', '{PLANT}', :code)"
                ),
                {"code": f"tc{i}"},
            )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.devices "
                "(device_id, transformer_id, device_code) "
                f"VALUES ('{D1}', '{T1}', '29501')"
            )
        )
        return transformers


def _move_device(device_id: str, new_transformer_id: str) -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"UPDATE {repo._SCHEMA}.devices "
                f"SET transformer_id = :t WHERE device_id = :d"
            ),
            {"t": new_transformer_id, "d": device_id},
        )


def _event(event_type, device_id=None, *, ts=None, transformer_id=None,
           temperature=None, battery_voltage=None, uid=None) -> int:
    return repo.insert_device_event(
        event_type=event_type,
        event_ts=ts or NOW - timedelta(hours=1),
        device_id=device_id,
        transformer_id=transformer_id,
        reported_uid=uid,
        temperature=temperature,
        battery_voltage=battery_voltage,
        source="test",
    )


def _rows(**kwargs):
    return rtl_alarms_30d_rows(device_scope=kwargs.pop("device_scope", DeviceScope(device_ids=None)), now=NOW, **kwargs)


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestAlarmInclusionAndHorizon:
    def setup_method(self):
        _wipe()
        _seed()

    def test_only_alarm_types_become_rows(self):
        """R3-D1: startup/check-in/invalid_uid never appear in REP-01."""
        _event(EVENT_TYPE_BATTERY_LOW, D1)
        _event(EVENT_TYPE_POWER_DOWN, D1)
        _event(EVENT_TYPE_SENSOR_ERROR, D1)
        _event(EVENT_TYPE_STARTUP, D1)
        _event(EVENT_TYPE_CHECK_IN, D1)
        _event(EVENT_TYPE_INVALID_UID, uid="99999")

        rows = _rows()

        # BR009 (FS-ALARM-1): power_down/sensor_error share the "Comms
        # Alarm" client-facing label; battery_low stays "Battery Alarm".
        assert {r.alarm_label for r in rows} == {"Battery Alarm", "Comms Alarm"}
        assert len(rows) == 3

    def test_thirty_day_horizon_boundary(self):
        """R3-D7: inside by a minute is in; outside by a minute is out."""
        inside = _event(
            EVENT_TYPE_BATTERY_LOW, D1,
            ts=NOW - timedelta(days=30) + timedelta(minutes=1),
        )
        outside = _event(
            EVENT_TYPE_BATTERY_LOW, D1,
            ts=NOW - timedelta(days=30) - timedelta(minutes=1),
        )

        rows = _rows()

        assert len(rows) == 1

    def test_zero_rows_is_a_legitimate_empty_report(self):
        assert _rows() == []

    def test_one_row_per_event_with_deterministic_newest_first_order(self):
        """R3-D3/D4: no collapsing; event_ts DESC with event_id tiebreak."""
        older = _event(EVENT_TYPE_BATTERY_LOW, D1,
                       ts=NOW - timedelta(days=2))
        tie_a = _event(EVENT_TYPE_POWER_DOWN, D1, ts=NOW)
        tie_b = _event(EVENT_TYPE_BATTERY_LOW, D1, ts=NOW)

        rows = _rows()

        assert len(rows) == 3
        assert all(rows[i].alarm_at >= rows[i + 1].alarm_at
                   for i in range(len(rows) - 1))
        # Same-timestamp pair resolves newest-id first:
        assert rows[0].alarm_at == rows[1].alarm_at


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestScopeIntersection:
    def setup_method(self):
        _wipe()
        _seed()
        self.other = "rep-p1-t1-d2"
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    "(device_id, transformer_id, device_code) "
                    f"VALUES ('{self.other}', '{T1}', '29502')"
                )
            )
        _event(EVENT_TYPE_POWER_DOWN, D1)
        _event(EVENT_TYPE_POWER_DOWN, self.other)

    def test_role_scope_narrows_rows_at_the_query(self):
        rows = _rows(device_scope=DeviceScope(device_ids=frozenset({D1})))
        assert len(rows) == 1

        empty = _rows(device_scope=DeviceScope(device_ids=frozenset()))
        assert empty == []

    def test_asset_scope_filters(self):
        rows = _rows(device_id=D1)
        assert len(rows) == 1


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestTransformerSnapshotRule:
    def setup_method(self):
        _wipe()

    def test_historical_snapshot_survives_a_later_device_move(self):
        """R3-D6 proof 1: the event's explicit transformer attribution is
        reported even after the device has moved to another transformer."""
        _seed(with_second_transformer=True)
        _event(EVENT_TYPE_BATTERY_LOW, D1, transformer_id=T2)

        # The device LATER moves from T1 to T2... then history must still win.
        _move_device(D1, T2)
        rows = _rows()
        assert rows[0].transformer == "tc2"

        # ...and if it moves somewhere entirely different instead:
        t3 = "rep-p1-t3"
        with session_scope() as session:
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.transformers "
                    "(transformer_id, plant_id, transformer_code) "
                    f"VALUES ('{t3}', '{PLANT}', 'tc3')"
                )
            )
        _move_device(D1, t3)
        rows = _rows()
        assert rows[0].transformer == "tc2"     # snapshot, not current

    def test_null_snapshot_falls_back_to_current_transformer(self):
        """R3-D6 proof 2: UID-resolved events carry no snapshot and use the
        device's present transformer as the explicit fallback."""
        _seed(with_second_transformer=True)
        _event(EVENT_TYPE_BATTERY_LOW, D1, transformer_id=None)

        rows = _rows()
        assert rows[0].transformer == "tc1"     # device's current (T1)

        # The fallback follows the CURRENT hierarchy when it changes:
        _move_device(D1, T2)
        rows = _rows()
        assert rows[0].transformer == "tc2"


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestPayloadRenderingInputs:
    def setup_method(self):
        _wipe()
        _seed()

    def test_payload_values_and_nulls_round_trip(self):
        _event(EVENT_TYPE_BATTERY_LOW, D1, battery_voltage=3.48,
               temperature=None)

        rows = _rows()

        row = rows[0]
        assert row.battery_voltage == 3.48      # renders as "3.48"
        assert row.temperature is None          # renders as "—"
        assert row.alarm_label == "Battery Alarm"
        assert row.uid == "29501"
        assert row.firmware_version is None
