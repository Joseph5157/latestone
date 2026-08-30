"""Recent Operational Events — the façade's event projection (CC-1 Phase 9).

Persisted events only, through the one approved read path (ADR-008). These
tests are about what an event row MEANS, so they exercise the real
projection over stub event records rather than asserting on a hand-built
snapshot.

The distinction under test throughout:

    a recent Power Down EVENT   ≠   an RTL currently in Critical STATE

The first is a thing that happened and is displayed here. The second has no
closure contract (ADR-001) and stays `Unavailable` on the Phase 6 card.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_INVALID_UID,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)
from services import command_center_service as svc
from services.device_scope import UNRESTRICTED, DeviceScope
from services.monitoring_service import (
    FleetHealth,
    Freshness,
    FreshnessRollup,
    fleet_health_from_rows,
)

NOW = datetime(2026, 8, 29, 14, 30, tzinfo=timezone.utc)


def _event(
    event_id=1,
    *,
    event_type=EVENT_TYPE_POWER_DOWN,
    device_id="d1",
    transformer_id="t1",
    reported_uid=None,
    minutes_ago=0,
    battery_voltage=None,
    temperature=None,
):
    """A DeviceEventRecord-shaped stub (repositories/...:DeviceEventRecord)."""
    return SimpleNamespace(
        event_id=event_id,
        device_id=device_id,
        transformer_id=transformer_id,
        reported_uid=reported_uid,
        event_type=event_type,
        severity=None,
        event_ts=NOW - timedelta(minutes=minutes_ago),
        temperature=temperature,
        battery_voltage=battery_voltage,
        message=None,
        source="test",
        created_at=NOW,
    )


def _path(device_id, code, plant_name, transformer_code):
    """A DevicePath-shaped label row (hierarchy_service.list_device_paths)."""
    return SimpleNamespace(
        plant_id="p1",
        plant_name=plant_name,
        transformer_id="t1",
        transformer_code=transformer_code,
        device_id=device_id,
        device_code=code,
        device_status="active",
    )


_EMPTY_HEALTH = FleetHealth(
    devices={"d1": FreshnessRollup(state=Freshness.FRESH, counts={Freshness.FRESH: 1}, total=1)},
    transformers={},
    plants={},
    counts={Freshness.FRESH: 1},
    _transformer_plant={},
    plant_last_updated={},
)


def _snapshot(monkeypatch, events, *, paths=(), scope=UNRESTRICTED, **kwargs):
    monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
    monkeypatch.setattr(svc, "list_recent_device_events", lambda **kw: list(events))
    monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
    monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
    monkeypatch.setattr(
        svc, "list_device_paths", lambda device_ids, *, scope: list(paths)
    )
    return svc.get_command_center_snapshot(scope=scope, now=NOW, **kwargs)


def _only(snapshot):
    assert len(snapshot.recent_events) == 1
    return snapshot.recent_events[0]


class TestOrdering:
    def test_events_are_newest_first(self, monkeypatch):
        """Time is the operator's chronology. A severity-first order would
        move an old Power Down above a newer Startup and quietly turn a log
        into a priority queue — which is the alarm-management system this
        panel is explicitly not."""
        snap = _snapshot(
            monkeypatch,
            [
                _event(1, minutes_ago=0, event_type=EVENT_TYPE_STARTUP),
                _event(2, minutes_ago=30, event_type=EVENT_TYPE_POWER_DOWN),
                _event(3, minutes_ago=90, event_type=EVENT_TYPE_BATTERY_LOW),
            ],
        )
        assert [e.event_id for e in snap.recent_events] == [1, 2, 3]

    def test_the_repository_order_is_preserved_not_recomputed(self, monkeypatch):
        """`list_recent_device_events` already orders `event_ts DESC,
        event_id DESC` (INGEST-D4 tiebreak). Re-sorting here would be a
        second ordering rule, free to disagree with the query's."""
        newest_first = [
            _event(9, minutes_ago=1),
            _event(4, minutes_ago=1),
            _event(7, minutes_ago=5),
        ]
        snap = _snapshot(monkeypatch, newest_first)
        assert [e.event_id for e in snap.recent_events] == [9, 4, 7]


class TestSeverityPresentation:
    def test_power_down_takes_the_critical_presentation(self, monkeypatch):
        row = _only(_snapshot(monkeypatch, [_event(event_type=EVENT_TYPE_POWER_DOWN)]))
        assert row.tone == "critical"
        assert row.tone_label == "Critical"
        assert row.display_label == "Power Down"

    def test_battery_low_takes_the_warning_presentation(self, monkeypatch):
        row = _only(_snapshot(monkeypatch, [_event(event_type=EVENT_TYPE_BATTERY_LOW)]))
        assert row.tone == "warning"
        assert row.tone_label == "Warning"
        assert row.display_label == "Battery Low"

    @pytest.mark.parametrize(
        "event_type",
        [EVENT_TYPE_STARTUP, EVENT_TYPE_CHECK_IN, EVENT_TYPE_SENSOR_ERROR],
    )
    def test_other_types_stay_neutral(self, monkeypatch, event_type):
        """Owning a Critical style is not a reason to spend it. Only the two
        conditions the DEVICE classifies get a severity presentation."""
        row = _only(_snapshot(monkeypatch, [_event(event_type=event_type)]))
        assert row.tone == svc.TONE_EVENT
        assert row.tone_label == "Event"

    def test_invalid_uid_is_not_a_severity(self, monkeypatch):
        row = _only(
            _snapshot(
                monkeypatch,
                [_event(event_type=EVENT_TYPE_INVALID_UID, device_id=None,
                        reported_uid="29841")],
            )
        )
        assert row.tone == svc.TONE_EVENT

    def test_tone_is_derived_from_the_phase_6_condition_table(self, monkeypatch):
        """Not a second copy of it. Phase 6's ELECTRICAL_CONDITIONS is the
        single Command Center statement of `power_down → Critical`; if this
        panel restated the mapping the two surfaces could disagree about the
        same event type. Re-pointing that table must re-point these rows.
        """
        monkeypatch.setattr(
            svc,
            "ELECTRICAL_CONDITIONS",
            (
                svc.ElectricalCondition(
                    severity_key="warning",
                    severity_label="Warning",
                    event_type=EVENT_TYPE_POWER_DOWN,
                    condition_label="Power Down",
                    current_count=None,
                    definition="< 3.61 V",
                ),
            ),
        )
        row = _only(_snapshot(monkeypatch, [_event(event_type=EVENT_TYPE_POWER_DOWN)]))
        assert row.tone == "warning"

    def test_labels_come_from_the_shared_semantics_layer(self, monkeypatch):
        """EVT-D1: Command Center does not spell out an event type's name."""
        from services import event_semantics

        for event_type in (EVENT_TYPE_STARTUP, EVENT_TYPE_SENSOR_ERROR):
            row = _only(_snapshot(monkeypatch, [_event(event_type=event_type)]))
            assert row.display_label == event_semantics.display_label_for(event_type)


class TestVoltageIsNeverClassificationInput:
    def test_a_healthy_voltage_does_not_downgrade_a_battery_low_event(
        self, monkeypatch
    ):
        """EVT-D4: the event arrives ALREADY classified. 4.2 V is above both
        device thresholds, and the row must still read Warning — the device
        said so, and Command Center does not second-guess it."""
        row = _only(
            _snapshot(
                monkeypatch,
                [_event(event_type=EVENT_TYPE_BATTERY_LOW, battery_voltage=4.2)],
            )
        )
        assert row.tone == "warning"

    def test_a_low_voltage_does_not_promote_a_startup_event(self, monkeypatch):
        """The mirror case, and the one that would actually be tempting:
        3.10 V is below both thresholds, and a startup event stays neutral."""
        row = _only(
            _snapshot(
                monkeypatch,
                [_event(event_type=EVENT_TYPE_STARTUP, battery_voltage=3.10)],
            )
        )
        assert row.tone == svc.TONE_EVENT

    def test_voltage_is_carried_as_display_detail_only(self, monkeypatch):
        row = _only(
            _snapshot(
                monkeypatch,
                [_event(event_type=EVENT_TYPE_BATTERY_LOW, battery_voltage=3.58)],
            )
        )
        assert row.detail == "Battery voltage · 3.58 V"

    def test_absent_voltage_produces_no_detail_rather_than_a_zero(
        self, monkeypatch
    ):
        row = _only(_snapshot(monkeypatch, [_event(event_type=EVENT_TYPE_STARTUP)]))
        assert row.detail is None


class TestAssetResolution:
    def test_a_resolved_device_gets_its_code_and_path_and_a_link(
        self, monkeypatch
    ):
        snap = _snapshot(
            monkeypatch,
            [_event(device_id="plant-01-t1-d1")],
            paths=[_path("plant-01-t1-d1", "29017", "Kariba North", "aa12")],
        )
        row = _only(snap)
        assert row.asset_label == "29017"
        assert row.context_label == "Kariba North / aa12"
        assert row.asset_href == "/devices/plant-01-t1-d1"

    def test_an_unresolved_device_keeps_its_id_and_loses_its_link(
        self, monkeypatch
    ):
        """ADR-008: the persisted event is the authority that something
        happened, so the row survives a label miss. Offering "Open asset"
        would be a claim the lookup just failed to support."""
        snap = _snapshot(monkeypatch, [_event(device_id="ghost")], paths=[])
        row = _only(snap)
        assert row.asset_label == "ghost"
        assert row.context_label is None
        assert row.asset_href is None

    def test_an_unregistered_uid_has_no_asset_page(self, monkeypatch):
        """EVT-D5: the UID matched no registered device, so there is no
        /devices/... page for it. A disabled-looking link would still be
        claiming the asset exists."""
        snap = _snapshot(
            monkeypatch,
            [
                _event(
                    event_type=EVENT_TYPE_INVALID_UID,
                    device_id=None,
                    transformer_id=None,
                    reported_uid="29841",
                )
            ],
        )
        row = _only(snap)
        assert row.asset_href is None
        assert row.asset_label == "UID 29841"
        assert row.context_label == "Unregistered UID"

    def test_the_path_lookup_is_one_batched_call_for_the_visible_rows(
        self, monkeypatch
    ):
        """ADR-008 Phase 9: once per render over the visible ids, never per
        row. This is the discipline the batched read exists to make possible.
        """
        calls = []

        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(
            svc,
            "list_recent_device_events",
            lambda **kw: [_event(i, device_id=f"d{i}") for i in range(1, 6)],
        )

        def _paths(device_ids, *, scope):
            calls.append(list(device_ids))
            return []

        monkeypatch.setattr(svc, "list_device_paths", _paths)
        svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)

        assert len(calls) == 1
        assert sorted(calls[0]) == ["d1", "d2", "d3", "d4", "d5"]

    def test_no_path_lookup_is_issued_when_nothing_needs_labelling(
        self, monkeypatch
    ):
        calls = []
        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kw: [])
        monkeypatch.setattr(
            svc, "list_device_paths", lambda ids, *, scope: calls.append(ids) or []
        )

        svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)

        assert calls == []


class TestRowBudget:
    def test_the_panel_asks_for_only_the_rows_it_shows(self, monkeypatch):
        """The repository already orders newest-first, so LIMIT N *is* the
        newest N. Fetching 500 to render 10 would make the query, and the
        label lookup behind it, 50x larger than the panel."""
        captured = {}

        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
        monkeypatch.setattr(
            svc, "list_recent_device_events", lambda **kw: captured.update(kw) or []
        )

        svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)

        assert captured["limit"] == svc.RECENT_EVENT_ROWS
        assert 8 <= svc.RECENT_EVENT_ROWS <= 12

    def test_a_caller_cannot_ask_past_the_pilot_safety_ceiling(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
        monkeypatch.setattr(
            svc, "list_recent_device_events", lambda **kw: captured.update(kw) or []
        )

        svc.get_command_center_snapshot(
            scope=UNRESTRICTED, now=NOW, event_limit=10_000
        )

        assert captured["limit"] == svc.RECENT_EVENTS_LIMIT


class TestUnregisteredVisibility:
    def test_unattributed_rows_are_excluded_by_default(self, monkeypatch):
        """EVT-D5: an unregistered UID belongs to no device set, so scope
        alone cannot decide who may see it. The default is the safe one."""
        captured = {}
        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
        monkeypatch.setattr(
            svc, "list_recent_device_events", lambda **kw: captured.update(kw) or []
        )

        svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)
        assert captured["include_unattributed"] is False

    def test_an_administrator_snapshot_requests_them(self, monkeypatch):
        captured = {}
        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
        monkeypatch.setattr(
            svc, "list_recent_device_events", lambda **kw: captured.update(kw) or []
        )

        svc.get_command_center_snapshot(
            scope=UNRESTRICTED, now=NOW, include_unregistered=True
        )
        assert captured["include_unattributed"] is True


class TestFailureBoundary:
    def _snapshot_with_failing_events(self, monkeypatch, rows):
        def _boom(**kwargs):
            raise RuntimeError("events table unavailable")

        monkeypatch.setattr(
            svc,
            "get_fleet_health",
            lambda now, *, scope: fleet_health_from_rows(rows, NOW),
        )
        monkeypatch.setattr(svc, "list_recent_device_events", _boom)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
        return svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)

    def test_an_event_read_failure_does_not_fail_the_whole_snapshot(
        self, monkeypatch
    ):
        """The events read answers 'what happened recently'; everything else
        answers 'what is the state of the fleet'. Blanking the second
        because the first failed removes far more truth than the failure
        cost (ADR-008)."""
        rows = [
            SimpleNamespace(
                plant_id="p1", transformer_id="t1", device_id="d1",
                metric="temperature", reading_ts=NOW - timedelta(minutes=5),
            )
        ]
        snap = self._snapshot_with_failing_events(monkeypatch, rows)
        assert snap.monitored_device_count == 1
        assert snap.fresh_rtls == 1

    def test_a_failed_read_is_distinguishable_from_no_events(self, monkeypatch):
        """Never flattened into an empty list: 'nothing happened' and 'we
        could not look' are different facts, the same distinction ADR-001
        draws between Unavailable and 0."""
        snap = self._snapshot_with_failing_events(monkeypatch, [])
        assert snap.recent_events == ()
        assert snap.recent_events_failed is True

    def test_a_genuinely_empty_read_is_not_marked_failed(self, monkeypatch):
        snap = _snapshot(monkeypatch, [])
        assert snap.recent_events == ()
        assert snap.recent_events_failed is False

    def test_a_fleet_health_failure_still_fails_the_snapshot(self, monkeypatch):
        """The boundary is one-directional. Freshness IS the page; there is
        no honest partial render without it."""
        def _boom(now, *, scope):
            raise RuntimeError("readings unavailable")

        monkeypatch.setattr(svc, "get_fleet_health", _boom)
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kw: [])
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])

        with pytest.raises(RuntimeError):
            svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)


class TestEventsNeverTouchFreshnessTruth:
    ROWS = [
        SimpleNamespace(
            plant_id="p1", transformer_id="t1", device_id="d1",
            metric="temperature", reading_ts=NOW - timedelta(minutes=5),
        ),
        SimpleNamespace(
            plant_id="p1", transformer_id="t1", device_id="d2",
            metric="temperature", reading_ts=NOW - timedelta(days=3),
        ),
    ]

    def _with_events(self, monkeypatch, events):
        monkeypatch.setattr(
            svc,
            "get_fleet_health",
            lambda now, *, scope: fleet_health_from_rows(self.ROWS, NOW),
        )
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kw: events)
        monkeypatch.setattr(
            svc, "list_plants", lambda *, scope: [SimpleNamespace(plant_id="p1", name="P1")]
        )
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
        return svc.get_command_center_snapshot(scope=UNRESTRICTED, now=NOW)

    def test_needs_attention_is_unchanged_by_a_storm_of_events(self, monkeypatch):
        """ADR-002: Requires Attention is Stale + No Data and nothing else.
        Twenty Power Down events on a fresh RTL do not make it need
        attention — they are different time semantics."""
        quiet = self._with_events(monkeypatch, [])
        storm = self._with_events(
            monkeypatch,
            [_event(i, device_id="d1", event_type=EVENT_TYPE_POWER_DOWN)
             for i in range(20)],
        )
        assert storm.attention_rtls == quiet.attention_rtls == 1
        assert storm.stale_rtls == quiet.stale_rtls

    def test_the_plant_ranking_is_unchanged_by_events(self, monkeypatch):
        quiet = self._with_events(monkeypatch, [])
        storm = self._with_events(
            monkeypatch,
            [_event(i, device_id="d1") for i in range(20)],
        )
        assert [(r.plant_id, r.affected_rtls) for r in storm.affected_locations] == [
            (r.plant_id, r.affected_rtls) for r in quiet.affected_locations
        ]

    def test_current_critical_and_warning_state_stay_unavailable(self, monkeypatch):
        """The whole point of the distinction. Recent Power Down events on
        screen must not become a current Critical count on the Phase 6 card
        — no closure contract exists (ADR-001)."""
        snap = self._with_events(
            monkeypatch,
            [_event(i, event_type=EVENT_TYPE_POWER_DOWN) for i in range(5)],
        )
        assert all(c.current_count is None for c in snap.electrical_conditions)


class TestTimePresentation:
    def test_todays_events_show_a_bare_clock_time(self, monkeypatch):
        row = _only(_snapshot(monkeypatch, [_event(minutes_ago=28)]))
        assert row.time_label == "14:02"

    def test_older_events_carry_their_date(self, monkeypatch):
        """A three-day-old event rendered as "14:02" reads as this
        afternoon. The date is what stops the panel implying recency it
        does not have."""
        row = _only(_snapshot(monkeypatch, [_event(minutes_ago=60 * 24 * 3)]))
        assert row.time_label == "26 Aug 14:30"

    def test_the_full_timestamp_is_available_for_the_row_title(self, monkeypatch):
        row = _only(_snapshot(monkeypatch, [_event(minutes_ago=28)]))
        assert row.time_title == "2026-08-29 14:02 UTC"


class TestScopePassThrough:
    def test_the_path_lookup_is_scoped_like_every_other_read(self, monkeypatch):
        captured = {}
        scope = DeviceScope(device_ids=frozenset({"d1"}))

        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _EMPTY_HEALTH)
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
        monkeypatch.setattr(svc, "list_recent_device_events", lambda **kw: [_event()])

        def _paths(device_ids, *, scope):
            captured["scope"] = scope
            return []

        monkeypatch.setattr(svc, "list_device_paths", _paths)
        svc.get_command_center_snapshot(scope=scope, now=NOW)

        assert captured["scope"] is scope
