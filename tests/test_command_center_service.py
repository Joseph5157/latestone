"""Tests for the Command Center service facade (ADR-008).

Pure logic - monkeypatches the two approved read paths (get_fleet_health,
list_recent_device_events) rather than touching the database, matching the
house convention in tests/test_monitoring_service.py
(`monkeypatch.setattr(svc, "some_dependency", stub)`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from services import command_center_service as svc
from services.device_scope import EMPTY, UNRESTRICTED, DeviceScope
from services.monitoring_service import (
    FleetHealth,
    Freshness,
    FreshnessRollup,
    fleet_health_from_rows,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
RECENT = NOW - timedelta(minutes=5)


def _row(device_id, metric, reading_ts, *, plant_id="p1", transformer_id="t1"):
    """One (device, metric) latest-reading row, matching LatestReadingRow's
    shape (repositories/plant_monitoring_repository.py:479)."""
    return SimpleNamespace(
        plant_id=plant_id,
        transformer_id=transformer_id,
        device_id=device_id,
        metric=metric,
        reading_ts=reading_ts,
    )


def _snapshot_from_rows(monkeypatch, rows, *, scope=UNRESTRICTED):
    """Compose a snapshot over REAL freshness aggregation.

    Deliberately not a hand-built FleetHealth: these tests are about the
    semantics the aggregation produces, so stubbing its output would test
    the fixture instead of the pipeline.
    """
    monkeypatch.setattr(
        svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(rows, NOW)
    )
    monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
    return svc.get_command_center_snapshot(scope=scope)

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


class TestSituationSummaryValues:
    """Phase 5: the facade decides, components render (ACTIVE_GATE.md)."""

    def test_freshness_composition_is_presentation_ready(self, monkeypatch):
        rows = [
            _row("d1", "temperature", RECENT),          # fresh
            _row("d2", "temperature", NOW - timedelta(days=2)),   # stale
            _row("d3", "temperature", None),            # no data
        ]
        snap = _snapshot_from_rows(monkeypatch, rows)

        assert snap.monitored_device_count == 3
        assert snap.fresh_rtls == 1
        assert snap.stale_rtls == 1
        assert snap.no_data_rtls == 1

    def test_attention_is_stale_plus_no_data_only(self, monkeypatch):
        """ADR-002. Never mixed with event occurrences."""
        rows = [
            _row("d1", "temperature", RECENT),
            _row("d2", "temperature", NOW - timedelta(days=2)),
            _row("d3", "temperature", None),
        ]
        snap = _snapshot_from_rows(monkeypatch, rows)

        assert snap.attention_rtls == 2
        assert snap.attention_percent == pytest.approx(66.7, abs=0.05)

    def test_inventory_counts_come_from_the_monitoring_population(self, monkeypatch):
        rows = [
            _row("d1", "temperature", RECENT, plant_id="p1", transformer_id="t1"),
            _row("d2", "temperature", RECENT, plant_id="p1", transformer_id="t2"),
            _row("d3", "temperature", RECENT, plant_id="p2", transformer_id="t3"),
        ]
        snap = _snapshot_from_rows(monkeypatch, rows)

        assert snap.plant_count == 2
        assert snap.transformer_count == 3
        assert snap.monitored_device_count == 3

    def test_no_data_affected_plants_counts_plants_not_devices(self, monkeypatch):
        """Two No Data RTLs in one plant is one affected Plant, not two."""
        rows = [
            _row("d1", "temperature", None, plant_id="p1", transformer_id="t1"),
            _row("d2", "temperature", None, plant_id="p1", transformer_id="t2"),
            _row("d3", "temperature", RECENT, plant_id="p2", transformer_id="t3"),
        ]
        snap = _snapshot_from_rows(monkeypatch, rows)

        assert snap.no_data_rtls == 2
        assert snap.no_data_affected_plants == 1


class TestPartiallyReportingDeviceRegression:
    """THE regression case this gate exists to protect (ADR-002).

    A device whose other metrics are fresh is still NO_DATA when any one
    monitored metric has never reported - and its device_last_updated stays
    present, describing a DIFFERENT metric. Reading that timestamp as
    "recently reported, therefore fine" is the exact error corrected during
    CC-1 planning.
    """

    ROWS = [
        _row("rtl-a", "temperature", RECENT),
        _row("rtl-a", "voltage", RECENT),
        _row("rtl-a", "current", None),      # never reported
    ]

    def test_device_freshness_is_no_data(self, monkeypatch):
        snap = _snapshot_from_rows(monkeypatch, self.ROWS)
        assert snap.fleet_health.devices["rtl-a"].state is Freshness.NO_DATA

    def test_device_last_updated_is_still_present(self, monkeypatch):
        """It describes the fresh metrics, not the missing one - which is
        precisely why it must never be used to infer overall health."""
        snap = _snapshot_from_rows(monkeypatch, self.ROWS)
        assert snap.fleet_health.device_last_updated["rtl-a"] == RECENT

    def test_communication_count_includes_it(self, monkeypatch):
        snap = _snapshot_from_rows(monkeypatch, self.ROWS)
        assert snap.no_data_rtls == 1

    def test_needs_attention_includes_it(self, monkeypatch):
        snap = _snapshot_from_rows(monkeypatch, self.ROWS)
        assert snap.attention_rtls == 1

    def test_it_is_not_counted_fresh(self, monkeypatch):
        snap = _snapshot_from_rows(monkeypatch, self.ROWS)
        assert snap.fresh_rtls == 0


class TestDegenerateScopes:
    def test_empty_fleet_has_no_zero_division(self, monkeypatch):
        snap = _snapshot_from_rows(monkeypatch, [], scope=EMPTY)

        assert snap.monitored_device_count == 0
        assert snap.attention_rtls == 0
        assert snap.attention_percent == 0.0
        assert snap.no_data_percent == 0.0
        assert snap.has_monitored_devices is False

    def test_a_populated_fleet_reports_having_devices(self, monkeypatch):
        snap = _snapshot_from_rows(monkeypatch, [_row("d1", "temperature", RECENT)])
        assert snap.has_monitored_devices is True


class TestPopulationBoundary:
    def test_the_facade_never_reads_the_managed_rtl_population(self):
        """Inventory shows Monitoring Devices (active devices under active
        transformers), never Managed RTLs (administratively active
        regardless of transformer status) - the split
        services/admin_overview_service.py:15-20 states. Importing that
        service here is how the two populations would silently merge."""
        source = (
            __import__("pathlib").Path(svc.__file__).read_text(encoding="utf-8")
        )
        assert "admin_overview" not in source
