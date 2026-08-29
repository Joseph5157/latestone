"""Tests for the Command Center service facade (ADR-008).

Pure logic - monkeypatches the two approved read paths (get_fleet_health,
list_recent_device_events) rather than touching the database, matching the
house convention in tests/test_monitoring_service.py
(`monkeypatch.setattr(svc, "some_dependency", stub)`).
"""
from __future__ import annotations

from services import command_center_service as svc
from services.device_scope import UNRESTRICTED, DeviceScope
from services.monitoring_service import FleetHealth, Freshness, FreshnessRollup

_FAKE_FLEET_HEALTH = FleetHealth(
    devices={
        "plant-01-t1-d1": FreshnessRollup(
            state=Freshness.FRESH, counts={Freshness.FRESH: 8}, total=8
        ),
        "plant-01-t1-d2": FreshnessRollup(
            state=Freshness.STALE, counts={Freshness.FRESH: 6, Freshness.STALE: 2}, total=8
        ),
    },
    transformers={},
    plants={},
    counts={Freshness.FRESH: 1, Freshness.STALE: 1},
    _transformer_plant={},
    plant_last_updated={},
)


class TestGetCommandCenterSnapshot:
    def test_calls_each_read_path_exactly_once(self, monkeypatch):
        """Mirrors get_fleet_health's own call discipline (its docstring:
        'call it once per render... calling it per component would issue N
        queries'). The facade must not be the place that discipline breaks."""
        calls = {"fleet_health": 0, "events": 0}

        def _fake_fleet_health(now, *, scope):
            calls["fleet_health"] += 1
            return _FAKE_FLEET_HEALTH

        def _fake_events(**kwargs):
            calls["events"] += 1
            return []

        monkeypatch.setattr(svc, "get_fleet_health", _fake_fleet_health)
        monkeypatch.setattr(svc, "list_recent_device_events", _fake_events)

        svc.get_command_center_snapshot(scope=UNRESTRICTED)

        assert calls == {"fleet_health": 1, "events": 1}

    def test_snapshot_carries_the_fleet_health_and_events_through(self, monkeypatch):
        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _FAKE_FLEET_HEALTH)
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: ["event-1"])

        snapshot = svc.get_command_center_snapshot(scope=UNRESTRICTED)

        assert snapshot.fleet_health is _FAKE_FLEET_HEALTH
        assert snapshot.recent_events == ["event-1"]
        assert snapshot.monitored_device_count == 2

    def test_scope_device_ids_pass_through_to_the_event_read(self, monkeypatch):
        """DeviceScope.device_ids and list_recent_device_events's
        allowed_device_ids share the same None-means-unrestricted contract
        (device_scope.py's own docstring) - the facade must not translate
        between them, only pass the value through."""
        captured = {}
        scope = DeviceScope(device_ids=frozenset({"plant-01-t1-d1"}))

        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _FAKE_FLEET_HEALTH)

        def _fake_events(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(svc, "list_recent_device_events", _fake_events)

        svc.get_command_center_snapshot(scope=scope)

        assert captured["allowed_device_ids"] == frozenset({"plant-01-t1-d1"})

    def test_event_types_come_from_event_semantics_not_a_hand_written_list(self, monkeypatch):
        """ADR-008: a new event type mapped in event_semantics.py must be
        visible to Command Center without a second edit here."""
        captured = {}

        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _FAKE_FLEET_HEALTH)

        def _fake_events(**kwargs):
            captured.update(kwargs)
            return []

        monkeypatch.setattr(svc, "list_recent_device_events", _fake_events)

        svc.get_command_center_snapshot(scope=UNRESTRICTED)

        assert captured["event_types"] == svc.event_semantics.mapped_event_types()
