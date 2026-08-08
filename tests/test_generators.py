"""Unit tests for db.generators - pure functions, no database required."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.generators import (
    DAYS_OF_HISTORY,
    INTERVAL_MINUTES,
    build_timestamps,
    generate_device_series,
)

ANCHOR = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
EXPECTED_METRICS = {
    "temperature", "voltage", "current", "active_power",
    "reactive_power", "power_factor", "frequency", "energy",
}


class TestBuildTimestamps:
    def test_produces_1441_timestamps(self):
        assert len(build_timestamps(ANCHOR)) == 1441

    def test_spacing_is_30_minutes(self):
        ts = build_timestamps(ANCHOR)
        assert ts[1] - ts[0] == timedelta(minutes=INTERVAL_MINUTES)

    def test_spans_30_days_ending_at_anchor(self):
        ts = build_timestamps(ANCHOR)
        assert ts[-1] == ANCHOR
        assert ts[0] == ANCHOR - timedelta(days=DAYS_OF_HISTORY)


class TestGenerateDeviceSeries:
    def test_returns_all_eight_metrics(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert set(series) == EXPECTED_METRICS

    def test_every_series_matches_timestamp_count(self):
        ts = build_timestamps(ANCHOR)
        series = generate_device_series("plant-01-t1-d1", 30.8, ts)
        for key, values in series.items():
            assert len(values) == len(ts), key

    def test_energy_is_monotonically_increasing(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        energy = series["energy"]
        assert all(b >= a for a, b in zip(energy, energy[1:]))

    def test_energy_strictly_grows_over_the_window(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert series["energy"][-1] > series["energy"][0]

    def test_non_energy_metrics_fluctuate(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        for key in EXPECTED_METRICS - {"energy"}:
            assert len(set(series[key])) > 10, key

    def test_power_factor_within_zero_to_one(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert all(0.0 < v <= 1.0 for v in series["power_factor"])

    def test_frequency_near_nominal(self):
        series = generate_device_series("plant-01-t1-d1", 30.8, build_timestamps(ANCHOR))
        assert all(49.0 < v < 51.0 for v in series["frequency"])

    def test_deterministic_for_same_device(self):
        ts = build_timestamps(ANCHOR)
        assert generate_device_series("plant-01-t1-d1", 30.8, ts) == generate_device_series(
            "plant-01-t1-d1", 30.8, ts
        )

    def test_different_devices_produce_different_series(self):
        ts = build_timestamps(ANCHOR)
        a = generate_device_series("plant-01-t1-d1", 30.8, ts)
        b = generate_device_series("plant-02-t1-d1", 30.8, ts)
        assert a["temperature"] != b["temperature"]

    def test_latitude_influences_temperature_baseline(self):
        ts = build_timestamps(ANCHOR)
        equator = generate_device_series("plant-09-t1-d1", 1.0, ts)["temperature"]
        polar = generate_device_series("plant-09-t1-d1", 65.0, ts)["temperature"]
        assert sum(equator) / len(equator) > sum(polar) / len(polar)
