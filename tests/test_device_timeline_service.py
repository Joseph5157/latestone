"""ALARM-HISTORY-1 (ADR-027): one RTL's alarms and reading gaps for the Device
page. Pure logic + a monkeypatched repository — no database connection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

from services import device_timeline_service as svc
from services.attention_service import ProblemKind as K
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=7)


def _event(event_id, event_type, ts, acked_at=None, device_id="d1"):
    return NS(event_id=event_id, device_id=device_id, event_type=event_type,
              event_ts=ts, acknowledged_at=acked_at)


def _fake_repo(monkeypatch, events):
    seen = {}

    def list_recent_device_events(**kw):
        seen.update(kw)
        return list(events)

    monkeypatch.setattr(svc.repo, "list_recent_device_events", list_recent_device_events)
    return seen


class TestDeviceAlarms:
    def test_reads_only_this_rtl_alarm_types_from_the_window_start(self, monkeypatch):
        seen = _fake_repo(monkeypatch, [])
        svc.device_alarms(UNRESTRICTED, "d1", START, NOW)
        assert seen["allowed_device_ids"] == frozenset({"d1"})
        assert set(seen["event_types"]) == {"power_down", "battery_low", "sensor_error"}
        assert seen["since"] == START
        assert seen["include_unattributed"] is False

    def test_newest_first_with_kind_and_acknowledgement(self, monkeypatch):
        _fake_repo(monkeypatch, [
            _event(3, "sensor_error", NOW - timedelta(hours=2)),
            _event(2, "power_down", NOW - timedelta(days=2),
                   acked_at=NOW - timedelta(days=2) + timedelta(hours=6)),
            _event(1, "battery_low", NOW - timedelta(days=5)),
        ])
        alarms = svc.device_alarms(UNRESTRICTED, "d1", START, NOW)
        assert [a.kind for a in alarms] == [K.SENSOR_ERROR, K.POWER_DOWN, K.BATTERY_LOW]
        assert [a.is_open for a in alarms] == [True, False, True]
        assert alarms[1].acknowledged_after == timedelta(hours=6)
        assert alarms[0].label == "Sensor Error"

    def test_drops_alarms_after_a_custom_window_end(self, monkeypatch):
        end = NOW - timedelta(days=1)
        _fake_repo(monkeypatch, [
            _event(2, "power_down", NOW - timedelta(hours=1)),   # after `end`
            _event(1, "battery_low", NOW - timedelta(days=3)),
        ])
        assert [a.event_id for a in svc.device_alarms(UNRESTRICTED, "d1", START, end)] == [1]

    def test_ignores_non_alarm_event_types(self, monkeypatch):
        _fake_repo(monkeypatch, [_event(1, "startup", NOW - timedelta(hours=1))])
        assert svc.device_alarms(UNRESTRICTED, "d1", START, NOW) == ()

    def test_out_of_scope_rtl_reads_nothing(self, monkeypatch):
        seen = _fake_repo(monkeypatch, [_event(1, "power_down", NOW)])
        technician = DeviceScope(device_ids=frozenset({"d2"}))
        assert svc.device_alarms(technician, "d1", START, NOW) == ()
        assert svc.device_alarms(EMPTY, "d1", START, NOW) == ()
        assert seen == {}  # never queried


class TestReadingGaps:
    def _every(self, minutes, count, start=START):
        return [start + timedelta(minutes=minutes * i) for i in range(count)]

    def test_regular_readings_have_no_gaps(self):
        assert svc.reading_gaps(self._every(30, 48)) == ()

    def test_gap_longer_than_four_times_the_usual_spacing(self):
        before = self._every(30, 20)
        after = self._every(30, 20, start=before[-1] + timedelta(hours=5, minutes=30))
        gaps = svc.reading_gaps(before + after)
        assert gaps == (svc.ReadingGap(before[-1], after[0]),)
        assert gaps[0].duration == timedelta(hours=5, minutes=30)

    def test_threshold_follows_the_rtls_own_rhythm(self):
        # Hourly RTL: a 3 h gap is under 4 x 1 h, so it is not shaded ...
        hourly = self._every(60, 10)
        later = self._every(60, 10, start=hourly[-1] + timedelta(hours=3))
        assert svc.reading_gaps(hourly + later) == ()
        # ... while the same 3 h gap on a 30-minute RTL is.
        half = self._every(30, 10)
        later = self._every(30, 10, start=half[-1] + timedelta(hours=3))
        assert len(svc.reading_gaps(half + later)) == 1

    def test_unsorted_input_and_too_few_readings(self):
        assert svc.reading_gaps([NOW, START]) == ()
        ts = self._every(30, 10) + [START + timedelta(hours=12)]
        assert len(svc.reading_gaps(list(reversed(ts)))) == 1


class TestCurrentAlarmHistory:
    def _as(self, monkeypatch, role, scope=UNRESTRICTED):
        monkeypatch.setattr(svc, "current_identity", lambda: None if role is None else NS(role=role))
        monkeypatch.setattr(svc, "scope_for", lambda identity: scope)
        _fake_repo(monkeypatch, [_event(1, "power_down", NOW - timedelta(hours=1))])

    def test_administrator_and_technician_see_alarms(self, monkeypatch):
        self._as(monkeypatch, "administrator")
        assert len(svc.current_alarm_history("d1", START, NOW)) == 1
        self._as(monkeypatch, "technician", DeviceScope(device_ids=frozenset({"d1"})))
        assert len(svc.current_alarm_history("d1", START, NOW)) == 1

    def test_technician_outside_scope_gets_an_empty_history(self, monkeypatch):
        self._as(monkeypatch, "technician", DeviceScope(device_ids=frozenset({"d9"})))
        assert svc.current_alarm_history("d1", START, NOW) == ()

    def test_general_user_and_no_session_get_no_history(self, monkeypatch):
        self._as(monkeypatch, "general")
        assert svc.current_alarm_history("d1", START, NOW) is None
        self._as(monkeypatch, None)
        assert svc.current_alarm_history("d1", START, NOW) is None


class TestTrailingGap:
    def _every(self, minutes, count, start=START):
        return [start + timedelta(minutes=minutes * i) for i in range(count)]

    def test_silence_after_the_last_reading_up_to_the_window_end(self):
        ts = self._every(30, 20)
        until = ts[-1] + timedelta(days=1)
        assert svc.reading_gaps(ts, until=until) == (svc.ReadingGap(ts[-1], until),)

    def test_a_short_wait_for_the_next_reading_is_not_a_gap(self):
        ts = self._every(30, 20)
        assert svc.reading_gaps(ts, until=ts[-1] + timedelta(minutes=45)) == ()
