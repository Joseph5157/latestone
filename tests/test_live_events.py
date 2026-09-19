"""Pure tests for db.live_events — no database."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from db.live_events import EVENT_MIX, plan_events
from services.simulated_event_source import SUPPORTED_EVENT_TYPES

T0 = datetime(2026, 9, 19, tzinfo=timezone.utc)
DEVICES = [f"plant-01-t1-d{i}" for i in range(1, 6)]


def _plan(per_day, days=7.0, seed=1):
    return plan_events(random.Random(seed), DEVICES, T0 - timedelta(days=days), T0, per_day)


class TestPlanEvents:
    def test_zero_rate_plans_nothing(self):
        assert _plan(0) == []

    def test_whole_expected_count_is_exact(self):
        assert len(_plan(12, days=7)) == 84

    def test_timestamps_are_inside_window_and_sorted(self):
        events = _plan(12)
        stamps = [e.event_ts for e in events]
        assert stamps == sorted(stamps)
        assert all(T0 - timedelta(days=7) <= s < T0 for s in stamps)

    def test_only_supported_types_and_known_devices(self):
        events = _plan(50)
        assert {e.event_type for e in events} <= set(SUPPORTED_EVENT_TYPES)
        assert {e.device_id for e in events} <= set(DEVICES)

    def test_mix_only_names_supported_types(self):
        assert {t for t, _ in EVENT_MIX} <= set(SUPPORTED_EVENT_TYPES)

    def test_same_seed_same_plan(self):
        assert _plan(12, seed=7) == _plan(12, seed=7)

    def test_short_tick_plans_zero_or_one(self):
        counts = {
            len(plan_events(random.Random(s), DEVICES, T0 - timedelta(seconds=300), T0, 12))
            for s in range(200)
        }
        assert counts == {0, 1}

    def test_battery_payloads(self):
        for e in _plan(200):
            if e.event_type == "battery_low":
                assert 3.62 <= e.battery_voltage <= 3.74
            elif e.event_type == "power_down":
                assert 3.45 <= e.battery_voltage <= 3.60
            elif e.event_type == "sensor_error":
                assert e.temperature == 512.0
            else:
                assert e.battery_voltage is None and e.temperature is None

    def test_no_devices_plans_nothing(self):
        assert plan_events(random.Random(1), [], T0 - timedelta(days=1), T0, 12) == []
