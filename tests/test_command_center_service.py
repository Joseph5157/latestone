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


def _plant(plant_id, name):
    """A PlantRecord-shaped label source (hierarchy_service.list_plants)."""
    return SimpleNamespace(plant_id=plant_id, name=name)


def _snapshot_from_rows(monkeypatch, rows, *, scope=UNRESTRICTED, plants=None):
    """Compose a snapshot over REAL freshness aggregation.

    Deliberately not a hand-built FleetHealth: these tests are about the
    semantics the aggregation produces, so stubbing its output would test
    the fixture instead of the pipeline.
    """
    monkeypatch.setattr(
        svc, "get_fleet_health", lambda now, *, scope: fleet_health_from_rows(rows, NOW)
    )
    monkeypatch.setattr(svc, "list_recent_device_events", lambda **kwargs: [])
    monkeypatch.setattr(svc, "list_plants", lambda *, scope: list(plants or []))
    # Phase 8: with no explicit selection the facade falls back to the
    # worst affected plant, which reaches the transformer label lookup.
    monkeypatch.setattr(svc, "list_transformers", lambda plant_id, *, scope: [])
    # Phase 10: the priority ranking labels the attention population
    # through the same batched lookup (ADR-008/ADR-009).
    monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])
    return svc.get_command_center_snapshot(scope=scope)

def _stub_event(event_id, *, device_id="plant-01-t1-d1", event_type="power_down"):
    """A DeviceEventRecord-shaped stub (repositories/...:DeviceEventRecord)."""
    return SimpleNamespace(
        event_id=event_id,
        device_id=device_id,
        transformer_id="plant-01-t1",
        reported_uid=None,
        event_type=event_type,
        severity=None,
        event_ts=NOW,
        temperature=None,
        battery_voltage=None,
        message=None,
        source="test",
        created_at=NOW,
    )


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

#: The same fleet, but with the hierarchy populated so a plant is actually
#: selectable. `_FAKE_FLEET_HEALTH` has no plants, which makes the Phase 8
#: fallback resolve to None and quietly skips the transformer lookup - fine
#: for the tests that use it, useless for asserting the read-path budget.
_SELECTABLE_FLEET_HEALTH = FleetHealth(
    devices=_FAKE_FLEET_HEALTH.devices,
    transformers={
        "plant-01-t1": FreshnessRollup(
            state=Freshness.STALE,
            counts={Freshness.FRESH: 1, Freshness.STALE: 1},
            total=2,
        )
    },
    plants={
        "plant-01": FreshnessRollup(
            state=Freshness.STALE,
            counts={Freshness.FRESH: 1, Freshness.STALE: 1},
            total=2,
        )
    },
    counts={Freshness.FRESH: 1, Freshness.STALE: 1},
    _transformer_plant={"plant-01-t1": "plant-01"},
    plant_last_updated={},
)


class TestGetCommandCenterSnapshot:
    def test_calls_each_read_path_exactly_once(self, monkeypatch):
        """Mirrors get_fleet_health's own call discipline (its docstring:
        'call it once per render... calling it per component would issue N
        queries'). The facade must not be the place that discipline breaks.

        The dict is exhaustive on purpose: it encodes ADR-008's closed set
        of read entry points, so adding a fourth fails here and forces the
        ADR amendment rather than slipping in at a call site.
        """
        calls = {
            "fleet_health": 0, "events": 0, "plants": 0,
            "transformers": 0, "device_paths": 0,
        }

        def _fake_fleet_health(now, *, scope):
            calls["fleet_health"] += 1
            return _SELECTABLE_FLEET_HEALTH

        def _fake_events(**kwargs):
            calls["events"] += 1
            return [_stub_event(1, device_id="plant-01-t1-d2")]

        def _fake_plants(*, scope):
            calls["plants"] += 1
            return []

        def _fake_transformers(plant_id, *, scope):
            calls["transformers"] += 1
            return []

        def _fake_device_paths(device_ids, *, scope):
            calls["device_paths"] += 1
            return []

        monkeypatch.setattr(svc, "get_fleet_health", _fake_fleet_health)
        monkeypatch.setattr(svc, "list_recent_device_events", _fake_events)
        monkeypatch.setattr(svc, "list_plants", _fake_plants)
        monkeypatch.setattr(svc, "list_transformers", _fake_transformers)
        monkeypatch.setattr(svc, "list_device_paths", _fake_device_paths)

        svc.get_command_center_snapshot(scope=UNRESTRICTED)

        assert calls == {
            "fleet_health": 1, "events": 1, "plants": 1,
            "transformers": 1, "device_paths": 1,
        }

    def test_snapshot_carries_the_fleet_health_and_events_through(self, monkeypatch):
        monkeypatch.setattr(svc, "get_fleet_health", lambda now, *, scope: _FAKE_FLEET_HEALTH)
        monkeypatch.setattr(
            svc, "list_recent_device_events", lambda **kwargs: [_stub_event(7)]
        )
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])

        snapshot = svc.get_command_center_snapshot(scope=UNRESTRICTED)

        assert snapshot.fleet_health is _FAKE_FLEET_HEALTH
        assert [e.event_id for e in snapshot.recent_events] == [7]
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
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])

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
        monkeypatch.setattr(svc, "list_plants", lambda *, scope: [])
        monkeypatch.setattr(svc, "list_device_paths", lambda ids, *, scope: [])

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


class TestElectricalConditionModel:
    """Phase 6 - the Critical/Warning presentation contract (ADR-001).

    The facade decides the mapping; components render it. These assert the
    mapping is event-type based and that current state stays a deliberate
    None.
    """

    def _by_key(self, monkeypatch):
        snap = _snapshot_from_rows(monkeypatch, [_row("d1", "temperature", RECENT)])
        return {c.severity_key: c for c in snap.electrical_conditions}

    def test_power_down_is_the_critical_presentation(self, monkeypatch):
        critical = self._by_key(monkeypatch)["critical"]
        assert critical.event_type == "power_down"
        assert critical.severity_label == "Critical"
        assert critical.condition_label == "Power Down"

    def test_battery_low_is_the_warning_presentation(self, monkeypatch):
        warning = self._by_key(monkeypatch)["warning"]
        assert warning.event_type == "battery_low"
        assert warning.severity_label == "Warning"
        assert warning.condition_label == "Battery Low"

    def test_current_critical_state_is_unavailable(self, monkeypatch):
        """Not zero. Events record that something OCCURRED; without a
        resolve/clear contract an old event cannot establish that an RTL is
        still in that state now (ADR-001)."""
        assert self._by_key(monkeypatch)["critical"].current_count is None

    def test_current_warning_state_is_unavailable(self, monkeypatch):
        assert self._by_key(monkeypatch)["warning"].current_count is None

    def test_definitions_carry_the_device_thresholds_as_text(self, monkeypatch):
        conditions = self._by_key(monkeypatch)
        assert "< 3.61 V" in conditions["critical"].definition
        assert "< 3.75 V" in conditions["warning"].definition

    def test_only_the_two_classified_conditions_are_presented(self, monkeypatch):
        """High temperature and vibration are structurally absent from
        services/event_semantics.py because their domain rules are open
        client-clarification items. Having a Critical *category* must not
        become a reason to invent membership in it."""
        conditions = self._by_key(monkeypatch)
        assert set(conditions) == {"critical", "warning"}
        event_types = {c.event_type for c in conditions.values()}
        assert "high_temperature" not in event_types
        assert "vibration_event" not in event_types

    def test_definition_figures_match_the_spec_frozen_source(self):
        """Binds the legend to config/notifications.py rather than retyping
        it. That module's descriptions cite BR002/BR011 and are the source
        for both numbers; if the spec text changes, this fails loudly
        instead of Command Center silently showing a stale figure."""
        from config.notifications import get_category

        assert "3.61" in get_category("power_down").description
        assert "3.75" in get_category("battery_alarm").description
        assert "3.61" in svc.CRITICAL_DEFINITION
        assert "3.75" in svc.WARNING_DEFINITION


class TestNoThresholdLogicInCommandCenter:
    """EVT-D4 / ADR-001, enforced structurally rather than by review.

    An AST walk, not a text scan: `"< 3.61 V"` is a legitimate display
    string, so grepping for the number (or for `<`) cannot distinguish
    legend copy from a classification predicate. Comparing against the
    literal in a Compare node is exactly the forbidden thing, and nothing
    else is.
    """

    THRESHOLDS = {3.61, 3.75}

    def _command_center_sources(self):
        import pathlib

        root = pathlib.Path(svc.__file__).resolve().parents[1]
        return [
            root / "services" / "command_center_service.py",
            *sorted((root / "components" / "command_center").glob("*.py")),
            root / "callbacks" / "command_center.py",
            root / "pages" / "command_center.py",
        ]

    def test_no_source_compares_against_a_voltage_threshold(self):
        import ast

        offenders = []
        for path in self._command_center_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                operands = [node.left, *node.comparators]
                for operand in operands:
                    if (
                        isinstance(operand, ast.Constant)
                        and isinstance(operand.value, (int, float))
                        and operand.value in self.THRESHOLDS
                    ):
                        offenders.append(f"{path.name}:{node.lineno}")
        assert not offenders, (
            "Command Center must never classify from battery voltage - the "
            f"event arrives already classified (EVT-D4). Found: {offenders}"
        )

    def test_battery_voltage_is_never_ranked_or_thresholded(self):
        """battery_voltage is display payload, never a classification input
        (ADR-001, EVT-D4).

        Phase 6 enforced this as "Command Center never touches the field at
        all", which was true then and is not now: Phase 9's event rows show
        the voltage the device reported as secondary context, which the gate
        explicitly asks for. Widening the ban to keep the old test passing
        would have been the wrong trade - so the guard was narrowed to the
        rule it was always standing in for.

        Displaying it is allowed. ORDERING or EQUALITY-testing it is not:
        `event.battery_voltage < anything` is Command Center deciding a
        severity the device already decided, whatever number follows. That is
        strictly stronger than the threshold-literal guard above for this
        field, because it catches a hand-typed 3.6 that is in no constant.

        `is None` / `is not None` stay legal - presence is not magnitude, and
        the row has to know whether it has a payload to render.

        ALIASES COUNT. A first version of this guard matched only
        `event.battery_voltage` directly, and `voltage = event.battery_voltage;
        if voltage < 3.4` walked straight past it - the guard was checked
        against a deliberate violation and did not fire. Names bound from a
        payload attribute are therefore treated as the payload itself.
        """
        import ast

        ranking_ops = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
        payload_fields = {"battery_voltage", "temperature"}

        def _is_payload_attr(node) -> bool:
            return isinstance(node, ast.Attribute) and node.attr in payload_fields

        offenders = []
        for path in self._command_center_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))

            # Names bound from a payload attribute anywhere in the module.
            aliases = set(payload_fields)
            for node in ast.walk(tree):
                targets = []
                if isinstance(node, ast.Assign) and _is_payload_attr(node.value):
                    targets = node.targets
                elif (
                    isinstance(node, ast.AnnAssign)
                    and node.value is not None
                    and _is_payload_attr(node.value)
                ):
                    targets = [node.target]
                elif isinstance(node, ast.NamedExpr) and _is_payload_attr(node.value):
                    targets = [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        aliases.add(target.id)

            def _is_payload(node) -> bool:
                return _is_payload_attr(node) or (
                    isinstance(node, ast.Name) and node.id in aliases
                )

            for node in ast.walk(tree):
                if not isinstance(node, ast.Compare):
                    continue
                if not any(isinstance(op, ranking_ops) for op in node.ops):
                    continue
                if any(_is_payload(o) for o in (node.left, *node.comparators)):
                    offenders.append(f"{path.name}:{node.lineno}")
        assert not offenders, (
            "Command Center must never rank or threshold an event's own "
            "payload - the event arrives already classified (EVT-D4). "
            f"Found: {offenders}"
        )

    def test_the_severity_of_an_event_row_is_decided_by_its_type_alone(self):
        """The behavioural half of the guard above, and the one that would
        actually catch a regression: a structural test proves no comparison
        is written, this proves the payload cannot influence the outcome even
        through some indirect route."""
        from types import SimpleNamespace

        from config.events import EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_STARTUP

        def _event(event_type, voltage):
            return SimpleNamespace(
                event_id=1, device_id=None, transformer_id="t1",
                reported_uid=None, event_type=event_type, severity=None,
                event_ts=datetime(2026, 8, 29, 14, 0, tzinfo=timezone.utc),
                temperature=None, battery_voltage=voltage, message=None,
                source="t", created_at=NOW,
            )

        reference = datetime(2026, 8, 29, 14, 30, tzinfo=timezone.utc)
        # Well ABOVE both device thresholds, yet the device classified it.
        high = svc._recent_event(_event(EVENT_TYPE_BATTERY_LOW, 4.20), {}, reference)
        # Well BELOW both, and still only a startup.
        low = svc._recent_event(_event(EVENT_TYPE_STARTUP, 3.10), {}, reference)

        assert high.tone == "warning"
        assert low.tone == svc.TONE_EVENT
