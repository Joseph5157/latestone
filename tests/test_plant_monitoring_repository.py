"""Repository tests against the seeded local PostgreSQL."""
from __future__ import annotations

from datetime import timedelta

import pytest

from repositories import plant_monitoring_repository as repo

pytestmark = pytest.mark.db

RESERVED_DEVICE_ID = "plant-01-t1-d1"


class TestHierarchy:
    def test_lists_thirty_plants(self):
        assert len(repo.list_plants()) == 30

    def test_get_plant_returns_record(self):
        plant = repo.get_plant("plant-01")
        assert plant is not None and plant.plant_id == "plant-01"

    def test_get_plant_returns_none_for_unknown_id(self):
        assert repo.get_plant("does-not-exist") is None

    def test_transformers_belong_to_requested_plant(self):
        transformers = repo.list_transformers("plant-01")
        assert transformers
        assert all(t.plant_id == "plant-01" for t in transformers)

    def test_total_transformers_is_71(self):
        total = sum(len(repo.list_transformers(p.plant_id)) for p in repo.list_plants())
        assert total == 71

    def test_devices_belong_to_requested_transformer(self):
        devices = repo.list_devices("plant-01-t1")
        assert devices
        assert all(d.transformer_id == "plant-01-t1" for d in devices)

    def test_get_device_returns_none_for_unknown_id(self):
        assert repo.get_device("nope") is None

    def test_breadcrumb_resolves_full_path_in_one_call(self):
        path = repo.get_device_breadcrumb(RESERVED_DEVICE_ID)
        assert path is not None
        assert path.plant_id == "plant-01"
        assert path.transformer_code == "aa12"
        assert path.device_code == "29017"
        assert path.plant_name

    def test_breadcrumb_returns_none_for_unknown_device(self):
        assert repo.get_device_breadcrumb("nope") is None

    def test_hierarchy_counts_cover_all_plants(self):
        counts = repo.count_hierarchy_by_plant()
        assert len(counts) == 30
        assert sum(t for t, _ in counts.values()) == 71
        assert sum(d for _, d in counts.values()) == 120


class TestLatestReadings:
    def test_returns_latest_reading(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        assert latest is not None
        assert latest.metric == "temperature"
        assert latest.device_id == RESERVED_DEVICE_ID

    def test_returns_none_for_unknown_metric(self):
        assert repo.get_latest_reading(RESERVED_DEVICE_ID, "not-a-metric") is None

    def test_returns_none_for_unknown_device(self):
        assert repo.get_latest_reading("nope", "temperature") is None

    def test_batched_latest_returns_all_eight_metrics(self):
        latest = repo.get_latest_readings_for_device(RESERVED_DEVICE_ID)
        assert len(latest) == 8

    def test_batched_latest_matches_single_metric_query(self):
        batched = repo.get_latest_readings_for_device(RESERVED_DEVICE_ID)
        single = repo.get_latest_reading(RESERVED_DEVICE_ID, "voltage")
        assert batched["voltage"] == single

    def test_batched_latest_honours_metric_filter(self):
        latest = repo.get_latest_readings_for_device(
            RESERVED_DEVICE_ID, ["voltage", "energy"]
        )
        assert set(latest) == {"voltage", "energy"}

    def test_batched_latest_with_empty_metric_list_returns_empty(self):
        assert repo.get_latest_readings_for_device(RESERVED_DEVICE_ID, []) == {}


class TestRangeQueries:
    def test_returns_only_readings_inside_range(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        rows = repo.get_readings_in_range(RESERVED_DEVICE_ID, "temperature", start, latest.timestamp)
        assert rows
        assert all(start <= r.timestamp <= latest.timestamp for r in rows)

    def test_24h_window_returns_49_inclusive_samples(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        rows = repo.get_readings_in_range(RESERVED_DEVICE_ID, "temperature", start, latest.timestamp)
        assert len(rows) == 49  # 48 intervals, both endpoints inclusive

    def test_range_is_ordered_ascending(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        rows = repo.get_readings_in_range(
            RESERVED_DEVICE_ID, "temperature", latest.timestamp - timedelta(days=7), latest.timestamp
        )
        assert [r.timestamp for r in rows] == sorted(r.timestamp for r in rows)

    def test_range_outside_data_returns_empty(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        far_past = latest.timestamp - timedelta(days=400)
        rows = repo.get_readings_in_range(
            RESERVED_DEVICE_ID, "temperature", far_past, far_past + timedelta(days=1)
        )
        assert rows == []

    def test_batched_range_returns_requested_metrics(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, ["temperature", "voltage", "energy"], start, latest.timestamp
        )
        assert set(result) == {"temperature", "voltage", "energy"}
        assert all(len(v) == 49 for v in result.values())

    def test_batched_range_matches_single_metric_range(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "voltage")
        start = latest.timestamp - timedelta(hours=24)
        batched = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, ["voltage"], start, latest.timestamp
        )
        single = repo.get_readings_in_range(RESERVED_DEVICE_ID, "voltage", start, latest.timestamp)
        assert batched["voltage"] == single

    def test_batched_range_includes_key_for_metric_with_no_rows(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        far_past = latest.timestamp - timedelta(days=400)
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, ["temperature", "voltage"], far_past, far_past + timedelta(days=1)
        )
        assert result == {"temperature": [], "voltage": []}

    def test_batched_range_with_empty_metric_list_returns_empty(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID, [], latest.timestamp - timedelta(hours=1), latest.timestamp
        )
        assert result == {}

    def test_metric_names_are_bound_not_interpolated(self):
        """A SQL metacharacter in a metric name must be inert, not an error."""
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        result = repo.get_readings_for_device_in_range(
            RESERVED_DEVICE_ID,
            ["temperature", "'); DROP TABLE plant_monitoring.readings; --"],
            latest.timestamp - timedelta(hours=1),
            latest.timestamp,
        )
        assert result["'); DROP TABLE plant_monitoring.readings; --"] == []
        assert repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature") is not None
