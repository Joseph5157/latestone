"""Unit tests for db.generators - pure functions, no database required."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.generators import (
    DAYS_OF_HISTORY,
    INTERVAL_MINUTES,
    REGISTRATION_HISTORY_DAYS,
    build_timestamps,
    generate_device_series,
    registration_timestamp,
)
from db.hierarchy import build_hierarchy

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


class TestRegistrationTimestamp:
    """Synthetic administrative registration dates for seeded devices.

    Guards the defect these replaced: before this existed the seed never set
    `devices.created_at`, so every row took migration 002's `now()` default and
    the whole fleet shared one registration instant.
    """

    def test_deterministic_for_same_device(self):
        assert registration_timestamp("plant-01-t1-d1", ANCHOR) == registration_timestamp(
            "plant-01-t1-d1", ANCHOR
        )

    def test_different_devices_register_at_different_times(self):
        a = registration_timestamp("plant-01-t1-d1", ANCHOR)
        b = registration_timestamp("plant-02-t1-d1", ANCHOR)
        assert a != b

    def test_never_later_than_the_anchor(self):
        assert registration_timestamp("plant-01-t1-d1", ANCHOR) <= ANCHOR

    def test_within_the_documented_history_window(self):
        earliest = ANCHOR - timedelta(days=REGISTRATION_HISTORY_DAYS)
        assert registration_timestamp("plant-01-t1-d1", ANCHOR) >= earliest

    def test_preserves_anchor_timezone(self):
        assert registration_timestamp("plant-01-t1-d1", ANCHOR).tzinfo is not None

    def test_offset_is_anchor_independent(self):
        """Shifting the anchor shifts every registration by the same delta.

        The offset comes from `device_id` alone, so which devices fall inside a
        recency window is a fixed property of the hierarchy rather than a
        function of when the seed happened to run. That is what makes the
        Recently Registered figure reproducible across reseeds.
        """
        shift = timedelta(days=10)
        first = registration_timestamp("plant-03-t2-d1", ANCHOR)
        second = registration_timestamp("plant-03-t2-d1", ANCHOR + shift)
        assert second - first == shift


class TestRegistrationSpreadAcrossTheFleet:
    """The property the card depends on, checked over the real 120 devices."""

    def _timestamps(self):
        plant_ids = [f"plant-{i:02d}" for i in range(1, 31)]
        countries = {pid: "Country" for pid in plant_ids}
        _transformers, devices = build_hierarchy(plant_ids, countries)
        assert len(devices) == 120
        return [registration_timestamp(d.device_id, ANCHOR) for d in devices]

    def test_registrations_are_not_all_identical(self):
        assert len(set(self._timestamps())) > 1

    def test_history_spans_more_than_a_year(self):
        stamps = self._timestamps()
        assert max(stamps) - min(stamps) > timedelta(days=365)

    def test_no_device_registers_in_the_future(self):
        assert all(ts <= ANCHOR for ts in self._timestamps())

    def test_every_device_registers_within_the_window(self):
        earliest = ANCHOR - timedelta(days=REGISTRATION_HISTORY_DAYS)
        assert all(ts >= earliest for ts in self._timestamps())
