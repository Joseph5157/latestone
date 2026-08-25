"""EVT-CONSUME-1I database-backed tests — scoped event reads and end-to-end
notification derivation against the isolated schema (tests/conftest.py).
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
from services.notification_service import current_notifications

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

PLANT = "con-p1"
T1 = "con-p1-t1"
D1 = "con-p1-t1-d1"   # code 29301
D2 = "con-p1-t1-d2"   # code 29302


def _wipe() -> None:
    with session_scope() as session:
        for table in (
            "audit_log", "device_events", "rtl_active_state",
            "rtl_programming_requests", "message_forwarding",
            "user_device_assignments", "readings",
            "devices", "transformers", "plants", "users",
        ):
            session.execute(text(f"DELETE FROM {repo._SCHEMA}.{table}"))


def _seed() -> None:
    with session_scope() as session:
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.plants "
                "(plant_id, name, country, latitude, longitude) "
                f"VALUES ('{PLANT}', 'Consume Plant', 'Testland', 0, 0)"
            )
        )
        session.execute(
            text(
                f"INSERT INTO {repo._SCHEMA}.transformers "
                f"(transformer_id, plant_id, transformer_code) "
                f"VALUES ('{T1}', '{PLANT}', 't1')"
            )
        )
        for device_id, code in ((D1, "29301"), (D2, "29302")):
            session.execute(
                text(
                    f"INSERT INTO {repo._SCHEMA}.devices "
                    "(device_id, transformer_id, device_code) "
                    f"VALUES ('{device_id}', '{T1}', '{code}')"
                )
            )


def _event(event_type, device_id=None, *, uid=None, ts=None,
           battery_voltage=None, temperature=None) -> int:
    return repo.insert_device_event(
        event_type=event_type,
        event_ts=ts or NOW,
        device_id=device_id,
        reported_uid=uid,
        battery_voltage=battery_voltage,
        temperature=temperature,
        source="test",
    )


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestListRecentDeviceEvents:
    def setup_method(self):
        _wipe()
        _seed()

    def test_filters_by_type_and_time(self):
        _event(EVENT_TYPE_BATTERY_LOW, D1)
        _event(EVENT_TYPE_STARTUP, D2)
        old = NOW - timedelta(days=31)
        _event(EVENT_TYPE_POWER_DOWN, D2, ts=old)

        rows = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_STARTUP],
            since=NOW - timedelta(days=30),
        )

        assert {(r.event_type, r.device_id) for r in rows} == {
            (EVENT_TYPE_BATTERY_LOW, D1),
            (EVENT_TYPE_STARTUP, D2),
        }

    def test_orders_by_event_ts_desc_with_event_id_tiebreak(self):
        """INGEST-D4 tiebreak reused at the read API (EVT-D9)."""
        first = _event(EVENT_TYPE_CHECK_IN, D1, ts=NOW - timedelta(hours=2))
        same_ts_a = _event(EVENT_TYPE_BATTERY_LOW, D1, ts=NOW)
        same_ts_b = _event(EVENT_TYPE_POWER_DOWN, D1, ts=NOW)

        rows = repo.list_recent_device_events(
            event_types=[
                EVENT_TYPE_CHECK_IN, EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_POWER_DOWN,
            ],
            since=NOW - timedelta(days=30),
        )

        assert [r.event_id for r in rows] == [same_ts_b, same_ts_a, first]

    def test_empty_scope_matches_nothing_but_none_is_unrestricted(self):
        """The None-vs-empty distinction is load-bearing (device_scope)."""
        _event(EVENT_TYPE_BATTERY_LOW, D1)

        unrestricted = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_BATTERY_LOW],
            since=NOW - timedelta(days=1),
            allowed_device_ids=None,
        )
        empty = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_BATTERY_LOW],
            since=NOW - timedelta(days=1),
            allowed_device_ids=frozenset(),
        )
        scoped = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_BATTERY_LOW],
            since=NOW - timedelta(days=1),
            allowed_device_ids=frozenset({D2}),   # wrong device on purpose
        )

        assert len(unrestricted) == 1
        assert empty == []
        assert scoped == []

    def test_scope_filters_at_sql_level_per_device(self):
        _event(EVENT_TYPE_SENSOR_ERROR, D1)
        _event(EVENT_TYPE_SENSOR_ERROR, D2)

        rows = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_SENSOR_ERROR],
            since=NOW - timedelta(days=1),
            allowed_device_ids=frozenset({D2}),
        )

        assert [r.device_id for r in rows] == [D2]

    def test_unattributed_rows_hidden_unless_explicitly_requested(self):
        """invalid_uid quarantines have no device: admin-only surface
        (EVT-D5) expressed as include_unattributed at the read API."""
        _event(EVENT_TYPE_INVALID_UID, uid="99999")
        _event(EVENT_TYPE_BATTERY_LOW, D1)

        default = repo.list_recent_device_events(
            event_types=sem_types(), since=NOW - timedelta(days=1),
            allowed_device_ids=None,
        )
        with_unattributed = repo.list_recent_device_events(
            event_types=sem_types(), since=NOW - timedelta(days=1),
            allowed_device_ids=None, include_unattributed=True,
        )

        assert {r.event_type for r in default} == {EVENT_TYPE_BATTERY_LOW}
        assert {r.event_type for r in with_unattributed} == {
            EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_INVALID_UID,
        }

    def test_limit_bounds_the_result_set(self):
        for i in range(5):
            _event(EVENT_TYPE_CHECK_IN, D1, ts=NOW - timedelta(hours=i))

        rows = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_CHECK_IN],
            since=NOW - timedelta(days=1),
            limit=3,
        )

        assert len(rows) == 3

    def test_payload_scalars_round_trip_as_display_values(self):
        _event(EVENT_TYPE_BATTERY_LOW, D1, battery_voltage=3.52,
               temperature=85.25)
        row = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_BATTERY_LOW], since=NOW - timedelta(days=1),
        )[0]
        assert row.battery_voltage == 3.52
        assert row.temperature == 85.25


def sem_types():
    from services.event_semantics import mapped_event_types

    return list(mapped_event_types())


@pytest.mark.db
@pytest.mark.usefixtures("isolated_schema")
class TestCurrentNotificationsComposition:
    def setup_method(self):
        _wipe()
        _seed()

    def test_composes_br008_and_event_backed_rows(self):
        result = current_notifications(
            reading_rows=[],                       # no readings → no BR008 rows
            scope=DeviceScope(device_ids=None),
            now=NOW,
        )
        # Nothing persisted yet: only the empty BR008 contribution.
        assert result == []

        _event(EVENT_TYPE_BATTERY_LOW, D1, battery_voltage=3.40)
        _event(EVENT_TYPE_STARTUP, D2)

        result = current_notifications(
            reading_rows=[],
            scope=DeviceScope(device_ids=None),
            now=NOW + timedelta(minutes=5),
        )
        keys = {r.key for r in result}
        assert keys == {f"battery_alarm:{D1}", f"startup_checkin:{D2}"}

    def test_technician_scope_hides_other_devices_events(self):
        _event(EVENT_TYPE_POWER_DOWN, D1)
        _event(EVENT_TYPE_POWER_DOWN, D2)

        result = current_notifications(
            reading_rows=[],
            scope=DeviceScope(device_ids=frozenset({D1})),
            now=NOW + timedelta(minutes=1),
        )

        assert [r.key for r in result] == [f"power_down:{D1}"]

    def test_admin_sees_unregistered_uids_technicians_do_not(self):
        _event(EVENT_TYPE_INVALID_UID, uid="99999")

        admin_view = current_notifications(
            reading_rows=[],
            scope=DeviceScope(device_ids=None),
            include_unregistered=True,
            now=NOW + timedelta(minutes=1),
        )
        tech_view = current_notifications(
            reading_rows=[],
            scope=DeviceScope(device_ids=frozenset()),   # even with devices, no UID rows
            include_unregistered=False,
            now=NOW + timedelta(minutes=1),
        )

        assert [r.key for r in admin_view] == ["unregistered_uid:99999"]
        assert admin_view[0].entity_type == "Unregistered UID"
        assert admin_view[0].href == ""
        assert tech_view == []

    def test_duplicate_events_collapse_with_count(self):
        """EVT-D8: append-only storage (INGEST-D3), collapsed presentation."""
        for i in range(4):
            _event(EVENT_TYPE_BATTERY_LOW, D1, battery_voltage=3.5 - i / 100,
                   ts=NOW - timedelta(hours=i))

        result = current_notifications(
            reading_rows=[],
            scope=DeviceScope(device_ids=None),
            now=NOW + timedelta(minutes=1),
        )

        assert len(result) == 1
        row = result[0]
        assert "4 event(s)" in row.detail
        assert row.occurred_at == NOW                 # latest occurrence shown

    def test_old_events_do_not_expire_from_the_notification_center(self):
        """Review correction: no notification retention/expiry exists. A
        relevant event older than REP-01's 30-day report horizon still
        renders — the 30-day rule belongs to the report only."""
        _event(EVENT_TYPE_BATTERY_LOW, D1, ts=NOW - timedelta(days=45))

        result = current_notifications(
            reading_rows=[],
            scope=DeviceScope(device_ids=None),
        )

        assert [r.key for r in result] == [f"battery_alarm:{D1}"]
        assert result[0].occurred_at == NOW - timedelta(days=45)

    def test_repo_since_remains_available_for_callers_that_need_it(self):
        """The optional technical bound still works when a caller (e.g. the
        future alarm-report query) asks for one."""
        _event(EVENT_TYPE_BATTERY_LOW, D1, ts=NOW - timedelta(days=45))
        _event(EVENT_TYPE_BATTERY_LOW, D2, ts=NOW - timedelta(days=1))

        bounded = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_BATTERY_LOW],
            since=NOW - timedelta(days=30),
        )
        unbounded = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_BATTERY_LOW]
        )

        assert {r.device_id for r in bounded} == {D2}
        assert {r.device_id for r in unbounded} == {D1, D2}

    def test_query_limit_is_a_technical_bound_not_semantics(self):
        """EVT-D8 correction: the limit bounds the QUERY; collapsed rows
        still render from whatever history the query returned."""
        for i in range(6):
            _event(EVENT_TYPE_CHECK_IN, D1, ts=NOW - timedelta(hours=i))

        events = repo.list_recent_device_events(
            event_types=[EVENT_TYPE_CHECK_IN], limit=3
        )
        assert len(events) == 3

        from services.event_semantics import build_event_notifications

        rows = build_event_notifications(events)
        assert len(rows) == 1
        assert "3 event(s)" in rows[0].detail     # count reflects queried set
