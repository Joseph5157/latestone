"""Unit tests for db.live_simulator's scope-validation logic.

Pure functions, no database required. The run() loop itself is thin
orchestration (I/O, time.sleep) and isn't unit tested, matching how
db/seed_plant_monitoring.py's seed() orchestration isn't either.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from db.live_simulator import (
    HOT_SPOT_DEVICE_COUNT,
    TEMPERATURE_CRITICAL_SCENARIO,
    TEMPERATURE_WARNING_SCENARIO,
    ConfigurationError,
    plan_temperature_scenarios,
    resolve_device_scope,
    resolve_metric_scope,
    scenario_temperature,
)
from services.temperature_condition_service import (
    TemperatureCondition,
    TemperatureLimits,
    classify,
)

KNOWN_DEVICES = {"plant-01-t1-d1", "plant-01-t1-d2", "plant-02-t1-d1"}


class TestResolveDeviceScope:
    def test_empty_configuration_means_every_known_device(self):
        assert resolve_device_scope((), KNOWN_DEVICES) == sorted(KNOWN_DEVICES)

    def test_configured_subset_is_returned_as_given(self):
        result = resolve_device_scope(("plant-02-t1-d1", "plant-01-t1-d1"), KNOWN_DEVICES)
        assert result == ["plant-02-t1-d1", "plant-01-t1-d1"]

    def test_unknown_device_id_raises_configuration_error(self):
        with pytest.raises(ConfigurationError):
            resolve_device_scope(("plant-99-t1-d1",), KNOWN_DEVICES)

    def test_error_message_names_the_unknown_id(self):
        with pytest.raises(ConfigurationError, match="plant-99-t1-d1"):
            resolve_device_scope(("plant-99-t1-d1",), KNOWN_DEVICES)


class TestResolveMetricScope:
    KNOWN_METRICS = ("temperature", "voltage", "energy")

    def test_empty_configuration_means_every_metric(self):
        assert resolve_metric_scope((), self.KNOWN_METRICS) == list(self.KNOWN_METRICS)

    def test_configured_subset_is_returned_as_given(self):
        result = resolve_metric_scope(("energy", "temperature"), self.KNOWN_METRICS)
        assert result == ["energy", "temperature"]

    def test_unknown_metric_raises_configuration_error(self):
        with pytest.raises(ConfigurationError):
            resolve_metric_scope(("not_a_metric",), self.KNOWN_METRICS)

    def test_error_message_names_the_unknown_metric(self):
        with pytest.raises(ConfigurationError, match="not_a_metric"):
            resolve_metric_scope(("not_a_metric",), self.KNOWN_METRICS)


class TestSilencedFeedsInSimulator:
    def test_empty_when_no_capture_file(self, monkeypatch, tmp_path):
        from db import live_simulator
        monkeypatch.setattr(live_simulator, "CAPTURE_PATH", tmp_path / "absent.json")
        assert live_simulator.active_silenced_feeds() == frozenset()

    def test_demo_feeds_when_capture_file_exists(self, monkeypatch, tmp_path):
        from db import live_simulator
        capture = tmp_path / "capture.json"
        capture.write_text("[]")
        monkeypatch.setattr(live_simulator, "CAPTURE_PATH", capture)
        assert ("plant-03-t1-d1", "temperature") in live_simulator.active_silenced_feeds()

    def test_is_silenced(self):
        from db import live_simulator
        silenced = frozenset({("d1", "voltage")})
        assert live_simulator.is_silenced("d1", "voltage", silenced)
        assert not live_simulator.is_silenced("d1", "temperature", silenced)


def _fleet(plant_count: int, devices_per_plant: int = 4) -> dict[str, str]:
    """device_id -> plant_id for a synthetic fleet shaped like the real one."""
    return {
        f"plant-{plant:02d}-t1-d{device}": f"plant-{plant:02d}"
        for plant in range(1, plant_count + 1)
        for device in range(1, devices_per_plant + 1)
    }


def _plan(fleet: dict[str, str], warning: int = 7, critical: int = 3) -> dict[str, str]:
    return plan_temperature_scenarios(
        sorted(fleet), fleet, warning_count=warning, critical_count=critical
    )


def _condition_of(value, warning_c: Decimal, critical_c: Decimal):
    """Classify through the real service, not through arithmetic in the test."""
    now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    return classify(
        value,
        now,
        now=now,
        limits=TemperatureLimits(warning_c=warning_c, critical_c=critical_c),
        stale_after=timedelta(minutes=60),
    )


class TestPlanTemperatureScenarios:
    def test_the_first_plant_in_scope_carries_a_cluster_of_problem_rtls(self):
        fleet = _fleet(30)
        per_plant = Counter(fleet[device_id] for device_id in _plan(fleet))
        assert per_plant["plant-01"] == HOT_SPOT_DEVICE_COUNT

    def test_no_other_plant_is_as_bad_as_the_hot_spot(self):
        fleet = _fleet(30)
        per_plant = Counter(fleet[device_id] for device_id in _plan(fleet))
        assert max(per_plant.values()) == HOT_SPOT_DEVICE_COUNT

    def test_problem_rtls_outside_the_hot_spot_sit_on_distinct_plants(self):
        fleet = _fleet(30)
        scattered = [
            fleet[device_id]
            for device_id in _plan(fleet)
            if fleet[device_id] != "plant-01"
        ]
        assert len(scattered) == len(set(scattered))

    def test_the_scatter_reaches_the_far_end_of_the_fleet(self):
        """A stride, not the first N plants: the map must not bunch at the top."""
        fleet = _fleet(30)
        plants = {fleet[device_id] for device_id in _plan(fleet)}
        assert max(plants) > "plant-20"

    def test_requested_counts_are_honoured_exactly(self):
        fleet = _fleet(30)
        assert Counter(_plan(fleet).values()) == {
            TEMPERATURE_WARNING_SCENARIO: 7,
            TEMPERATURE_CRITICAL_SCENARIO: 3,
        }

    def test_critical_rtls_land_on_separate_plants(self):
        fleet = _fleet(30)
        plan = _plan(fleet)
        critical_plants = {
            fleet[device_id]
            for device_id, scenario in plan.items()
            if scenario == TEMPERATURE_CRITICAL_SCENARIO
        }
        assert len(critical_plants) == 3

    def test_the_plan_is_stable_across_calls(self):
        fleet = _fleet(30)
        assert _plan(fleet) == _plan(fleet)

    def test_input_ordering_does_not_change_the_plan(self):
        fleet = _fleet(30)
        reversed_scope = plan_temperature_scenarios(
            sorted(fleet, reverse=True), fleet, warning_count=7, critical_count=3
        )
        assert _plan(fleet) == reversed_scope

    def test_a_fleet_smaller_than_the_quotas_assigns_what_it_has(self):
        fleet = _fleet(1, devices_per_plant=2)
        plan = _plan(fleet)
        assert len(plan) == 2
        assert set(plan.values()) == {
            TEMPERATURE_WARNING_SCENARIO,
            TEMPERATURE_CRITICAL_SCENARIO,
        }

    def test_a_single_device_fleet_still_shows_a_problem(self):
        fleet = _fleet(1, devices_per_plant=1)
        assert len(_plan(fleet)) == 1

    def test_zero_counts_leave_every_rtl_nominal(self):
        fleet = _fleet(30)
        assert _plan(fleet, warning=0, critical=0) == {}

    def test_a_device_with_no_known_plant_is_never_assigned(self):
        fleet = _fleet(2)
        plan = plan_temperature_scenarios(
            sorted(fleet) + ["orphan-device"], fleet, warning_count=7, critical_count=3
        )
        assert "orphan-device" not in plan


class TestScenarioTemperature:
    LIMITS = {"warning_c": Decimal("40"), "critical_c": Decimal("55")}

    def test_a_warning_rtl_really_classifies_as_warning(self):
        value = scenario_temperature(
            "plant-03-t1-d1",
            {"plant-03-t1-d1": TEMPERATURE_WARNING_SCENARIO},
            **self.LIMITS,
        )
        assert _condition_of(value, **self.LIMITS) is TemperatureCondition.WARNING

    def test_a_critical_rtl_really_classifies_as_critical(self):
        value = scenario_temperature(
            "plant-03-t1-d1",
            {"plant-03-t1-d1": TEMPERATURE_CRITICAL_SCENARIO},
            **self.LIMITS,
        )
        assert _condition_of(value, **self.LIMITS) is TemperatureCondition.CRITICAL

    def test_every_planned_rtl_classifies_as_planned_even_on_a_narrow_band(self):
        """Values are a fraction of the administrator's own band, so a half-degree
        gap between the limits must still land each RTL on the right side."""
        limits = {"warning_c": Decimal("70.5"), "critical_c": Decimal("71.0")}
        fleet = _fleet(30)
        plan = _plan(fleet)
        expected = {
            TEMPERATURE_WARNING_SCENARIO: TemperatureCondition.WARNING,
            TEMPERATURE_CRITICAL_SCENARIO: TemperatureCondition.CRITICAL,
        }
        for device_id, scenario in plan.items():
            value = scenario_temperature(device_id, plan, **limits)
            assert _condition_of(value, **limits) is expected[scenario]

    def test_warning_rtls_do_not_all_report_the_same_temperature(self):
        """Identical readings would make the hottest-RTL panel look fabricated."""
        fleet = _fleet(30)
        plan = _plan(fleet)
        values = {
            scenario_temperature(device_id, plan, **self.LIMITS)
            for device_id, scenario in plan.items()
            if scenario == TEMPERATURE_WARNING_SCENARIO
        }
        assert len(values) > 1

    def test_critical_rtls_do_not_all_report_the_same_temperature(self):
        fleet = _fleet(30)
        plan = _plan(fleet)
        values = {
            scenario_temperature(device_id, plan, **self.LIMITS)
            for device_id, scenario in plan.items()
            if scenario == TEMPERATURE_CRITICAL_SCENARIO
        }
        assert len(values) > 1

    def test_a_device_keeps_its_temperature_across_ticks(self):
        plan = {"plant-03-t1-d1": TEMPERATURE_WARNING_SCENARIO}
        first = scenario_temperature("plant-03-t1-d1", plan, **self.LIMITS)
        second = scenario_temperature("plant-03-t1-d1", plan, **self.LIMITS)
        assert first == second

    def test_no_stored_limits_means_no_override(self):
        assert scenario_temperature(
            "d1",
            {"d1": TEMPERATURE_WARNING_SCENARIO},
            warning_c=None,
            critical_c=None,
        ) is None

    def test_devices_outside_the_plan_are_unchanged(self):
        assert scenario_temperature(
            "d3",
            {"d1": TEMPERATURE_WARNING_SCENARIO, "d2": TEMPERATURE_CRITICAL_SCENARIO},
            **self.LIMITS,
        ) is None

    def test_a_collapsed_limit_band_is_left_alone(self):
        """set_threshold_config forbids warning >= critical, but the simulator
        must not invent a value it cannot place on the correct side."""
        assert scenario_temperature(
            "d1",
            {"d1": TEMPERATURE_WARNING_SCENARIO},
            warning_c=Decimal("50"),
            critical_c=Decimal("50"),
        ) is None

    def test_an_unknown_scenario_is_a_programming_error(self):
        with pytest.raises(ValueError):
            scenario_temperature("d1", {"d1": "melting"}, **self.LIMITS)


class TestParseArgs:
    def test_no_arguments_means_run_forever(self):
        from db import live_simulator
        assert live_simulator.parse_args([]).backfill_events_days is None

    def test_backfill_days(self):
        from db import live_simulator
        args = live_simulator.parse_args(["--backfill-events-days", "7"])
        assert args.backfill_events_days == 7.0


class TestBackfillEvents:
    NOW = __import__("datetime").datetime(2026, 9, 19, tzinfo=__import__("datetime").timezone.utc)

    def _with_rate(self, monkeypatch, rate):
        import dataclasses
        from db import live_simulator
        monkeypatch.setattr(
            live_simulator, "live_sim",
            dataclasses.replace(live_simulator.live_sim, events_per_day=rate),
        )
        return live_simulator

    def test_plans_the_whole_window_and_emits(self, monkeypatch):
        import random
        live_simulator = self._with_rate(monkeypatch, 12.0)
        emitted = []
        monkeypatch.setattr(live_simulator, "_device_transformers",
                            lambda: {"d1": "t1", "d2": "t1"})
        monkeypatch.setattr(live_simulator, "emit_planned",
                            lambda planned, transformer_of: emitted.extend(planned) or len(planned))
        assert live_simulator.backfill_events(7, self.NOW, random.Random(1)) == 84
        assert len(emitted) == 84
        assert {e.device_id for e in emitted} <= {"d1", "d2"}

    def test_does_nothing_when_events_are_off(self, monkeypatch):
        import random
        live_simulator = self._with_rate(monkeypatch, 0.0)
        monkeypatch.setattr(live_simulator, "_device_transformers", lambda: 1 / 0)
        assert live_simulator.backfill_events(7, self.NOW, random.Random(1)) == 0
