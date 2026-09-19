"""CC-NEW-1: the new Command Center's facade. Pure builders + a monkeypatched
snapshot — no database connection."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace as NS

from services import attention_service as svc
from services.attention_service import ProblemKind as K
from services.device_scope import DeviceScope
from services.temperature_condition_service import (
    DeviceTemperature,
    TemperatureCondition as C,
    TemperatureLimits,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
LIMITS = TemperatureLimits(Decimal("36"), Decimal("40"))
PLANTS = {"p1": "Alpha", "p2": "Bravo"}


def _temp(device_id, value, condition, plant="p1", ts=NOW - timedelta(minutes=5)):
    return DeviceTemperature(
        plant_id=plant, transformer_id=f"{plant}-t1", transformer_code="T1",
        device_id=device_id, device_code=device_id.upper(), value=value,
        reading_ts=ts, condition=condition,
    )


def _event(event_id, device_id, event_type, ts, acked_at=None, voltage=None):
    return NS(event_id=event_id, device_id=device_id, event_type=event_type,
              event_ts=ts, acknowledged_at=acked_at, battery_voltage=voltage,
              temperature=None)


TEMPS = [
    _temp("d1", 41.0, C.CRITICAL),
    _temp("d2", 37.0, C.WARNING, plant="p2"),
    _temp("d3", 25.0, C.NORMAL),
    _temp("d4", None, C.NO_RECENT_DATA),
]
WHERE = svc.locations(TEMPS, PLANTS)


class TestTemperatureProblems:
    def test_only_warning_and_critical_become_problems(self):
        problems = svc.temperature_problems(TEMPS, LIMITS, WHERE)
        assert [(p.kind, p.device_id) for p in problems] == [
            (K.TEMP_CRITICAL, "d1"), (K.TEMP_WARNING, "d2")]

    def test_detail_names_value_and_limit(self):
        critical = svc.temperature_problems(TEMPS, LIMITS, WHERE)[0]
        assert critical.detail == "41.0 °C · limit 40 °C"
        assert critical.plant_name == "Alpha"


class TestFormatLimit:
    def test_plain_numbers(self):
        assert svc.format_limit(Decimal("40.000")) == "40"
        assert svc.format_limit(Decimal("36.500")) == "36.5"


class TestNoDataProblems:
    def test_maps_br008_rows(self):
        rows = [NS(entity_id="d4", occurred_at=NOW - timedelta(hours=30),
                   detail="Last reading …")]
        [p] = svc.no_data_problems(rows, WHERE)
        assert p.kind is K.NO_DATA_24H and p.device_id == "d4"
        assert p.since == NOW - timedelta(hours=30)


class TestEventProblems:
    def test_groups_unacknowledged_alarms_per_device_and_type(self):
        events = [
            _event(1, "d1", "battery_low", NOW - timedelta(hours=5), voltage=3.70),
            _event(2, "d1", "battery_low", NOW - timedelta(hours=2), voltage=3.66),
            _event(3, "d1", "battery_low", NOW - timedelta(hours=1), acked_at=NOW),
            _event(4, "d2", "power_down", NOW - timedelta(hours=3)),
            _event(5, None, "power_down", NOW - timedelta(hours=3)),
            _event(6, "d3", "startup", NOW - timedelta(hours=3)),
        ]
        problems = {(p.kind, p.device_id): p for p in svc.event_problems(events, WHERE)}
        assert set(problems) == {(K.BATTERY_LOW, "d1"), (K.POWER_DOWN, "d2")}
        battery = problems[(K.BATTERY_LOW, "d1")]
        assert battery.count == 2
        assert battery.event_ids == (1, 2)
        assert battery.since == NOW - timedelta(hours=5)

    def test_unknown_device_falls_back_to_its_id(self):
        [p] = svc.event_problems([_event(1, "zz", "sensor_error", NOW)], WHERE)
        assert p.device_code == "zz" and p.plant_name == ""


class TestRanking:
    def test_kind_order_then_oldest_first(self):
        mk = lambda kind, dev, hours: svc.Problem(
            kind=kind, device_id=dev, device_code=dev, plant_id="p1",
            plant_name="Alpha", transformer_code="T1",
            since=NOW - timedelta(hours=hours), detail="")
        ranked = svc.rank_problems([
            mk(K.SENSOR_ERROR, "a", 1), mk(K.BATTERY_LOW, "b", 1),
            mk(K.TEMP_WARNING, "c", 1), mk(K.NO_DATA_24H, "d", 1),
            mk(K.POWER_DOWN, "e", 1), mk(K.TEMP_CRITICAL, "f", 1),
            mk(K.POWER_DOWN, "g", 9),
        ])
        assert [p.device_id for p in ranked] == ["f", "g", "e", "d", "c", "b", "a"]

    def test_every_kind_has_a_label(self):
        assert all(svc.KIND_LABELS[k] for k in K)


class TestActivity:
    def test_switch_ons_requests_and_acknowledgements_in_24h(self):
        events = [
            _event(1, "d1", "startup", NOW - timedelta(hours=1)),
            _event(2, "d1", "startup", NOW - timedelta(hours=30)),
            _event(3, "d2", "power_down", NOW - timedelta(days=3),
                   acked_at=NOW - timedelta(hours=2)),
        ]
        requests = [NS(device_id="d3", requested_at=NOW - timedelta(hours=3))]
        items = svc.activity_items(events, requests, WHERE, now=NOW)
        assert [(i.label, i.device_id) for i in items] == [
            ("Switched on", "d1"),
            ("Acknowledged: Power Down", "d2"),
            ("Programming requested", "d3"),
        ]


class TestDailyAlarms:
    def test_seven_zero_filled_days_counting_alarm_types_only(self):
        events = [
            _event(1, "d1", "battery_low", NOW - timedelta(hours=1)),
            _event(2, "d1", "power_down", NOW - timedelta(days=1)),
            _event(3, "d1", "startup", NOW - timedelta(hours=1)),
            _event(4, "d1", "sensor_error", NOW - timedelta(days=10)),
        ]
        days = svc.daily_alarm_counts(events, now=NOW)
        assert [d.day for d in days] == [date(2026, 9, 13) + timedelta(days=i) for i in range(7)]
        assert [d.count for d in days] == [0, 0, 0, 0, 0, 1, 1]


class TestSnapshot:
    def test_assembles_one_snapshot(self, monkeypatch):
        seen = {}
        monkeypatch.setattr(svc, "device_temperatures", lambda scope, now: TEMPS)
        monkeypatch.setattr(svc, "current_limits", lambda: LIMITS)
        monkeypatch.setattr(svc, "latest_reading_rows", lambda scope: [])
        monkeypatch.setattr(svc, "build_no_data_notifications", lambda rows, now: [])
        monkeypatch.setattr(svc, "_plant_names", lambda scope: PLANTS)

        def events(**kw):
            seen["events"] = kw
            return [_event(1, "d2", "power_down", NOW - timedelta(hours=1))]

        monkeypatch.setattr(svc.repo, "list_recent_device_events", events)
        monkeypatch.setattr(svc.repo, "list_programming_requests_since", lambda **kw: [])
        scope = DeviceScope(device_ids=frozenset({"d1", "d2"}))
        snap = svc.get_attention_snapshot(scope, now=NOW)

        assert seen["events"]["allowed_device_ids"] == frozenset({"d1", "d2"})
        assert seen["events"]["include_unattributed"] is False
        assert (snap.total_rtls, snap.reporting_rtls) == (4, 3)
        assert [p.kind for p in snap.problems] == [K.TEMP_CRITICAL, K.POWER_DOWN, K.TEMP_WARNING]
        assert [t.device_id for t in snap.hottest] == ["d1", "d2", "d3"]
        assert snap.limits == LIMITS and snap.generated_at == NOW


class TestAcknowledgeProblem:
    USER = NS(user_id=7, role="administrator")
    SCOPE = DeviceScope(device_ids=None)

    def _patch(self, monkeypatch, events, refuse=False):
        calls = {"guard": [], "ack": []}

        def guard(user, action, *, device_id):
            calls["guard"].append((action, device_id))
            if refuse:
                raise svc.AuthorizationError("no")

        def ack(*, event_id, actor_user_id, scope):
            calls["ack"].append((event_id, actor_user_id))
            return NS(changed=True)

        monkeypatch.setattr(svc.repo, "list_recent_device_events", lambda **kw: events)
        monkeypatch.setattr(svc, "require_action", guard)
        monkeypatch.setattr(svc.alarm_acknowledgement_service, "acknowledge_alarm", ack)
        return calls

    def test_acknowledges_every_open_event_of_that_kind_on_that_rtl(self, monkeypatch):
        events = [
            _event(1, "d1", "battery_low", NOW - timedelta(hours=3)),
            _event(2, "d1", "battery_low", NOW - timedelta(hours=1)),
            _event(3, "d1", "battery_low", NOW, acked_at=NOW),
            _event(4, "d2", "battery_low", NOW),
        ]
        calls = self._patch(monkeypatch, events)
        n = svc.acknowledge_problem(self.USER, self.SCOPE, "d1", K.BATTERY_LOW)
        assert n == 2
        assert calls["ack"] == [(1, 7), (2, 7)]
        assert calls["guard"] == [("acknowledge_alarm", "d1")] * 2

    def test_refusal_propagates_and_acknowledges_nothing(self, monkeypatch):
        import pytest
        calls = self._patch(monkeypatch, [_event(1, "d1", "power_down", NOW)], refuse=True)
        with pytest.raises(svc.AuthorizationError):
            svc.acknowledge_problem(self.USER, self.SCOPE, "d1", K.POWER_DOWN)
        assert calls["ack"] == []

    def test_non_alarm_kinds_are_refused(self):
        import pytest
        with pytest.raises(ValueError):
            svc.acknowledge_problem(self.USER, self.SCOPE, "d1", K.NO_DATA_24H)

    def test_acknowledgeable_kinds(self):
        assert svc.ACKNOWLEDGEABLE_KINDS == {K.POWER_DOWN, K.BATTERY_LOW, K.SENSOR_ERROR}


def test_acknowledged_count_uses_the_24h_window_not_the_row_cap():
    from types import SimpleNamespace
    from datetime import datetime, timedelta, timezone
    from services import attention_service as svc
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    events = [SimpleNamespace(acknowledged_at=now - timedelta(hours=h)) for h in range(0, 30)]
    events.append(SimpleNamespace(acknowledged_at=None))
    assert svc.acknowledged_count(events, now=now) == 25  # 0..24 h inclusive
