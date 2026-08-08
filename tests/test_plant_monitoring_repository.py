"""Repository tests against the seeded local PostgreSQL."""
from __future__ import annotations

from datetime import timedelta

import pytest

from repositories import plant_monitoring_repository as repo
from tests.timing import TimingResult, assert_timing, measure_time

pytestmark = pytest.mark.db

RESERVED_DEVICE_ID = "plant-01-t1-d1"

# Performance budgets (ms) — generous for local Docker Postgres on CI runners
BUDGET_LIST_PLANTS = 50
BUDGET_GET_PLANT = 20
BUDGET_LIST_TRANSFORMERS = 30
BUDGET_GET_TRANSFORMER = 20
BUDGET_LIST_DEVICES = 30
BUDGET_GET_DEVICE = 20
BUDGET_BREADCRUMB = 30
BUDGET_HIERARCHY_COUNTS = 50
BUDGET_LATEST_READING = 50
BUDGET_BATCHED_LATEST = 80
BUDGET_RANGE_SINGLE = 100
BUDGET_BATCHED_RANGE = 150


class TestHierarchy:
    def test_lists_thirty_plants(self):
        with measure_time() as t:
            plants = repo.list_plants()
        assert len(plants) == 30
        t.row_count = len(plants)
        assert_timing(t, BUDGET_LIST_PLANTS, min_rows=30)

    def test_get_plant_returns_record(self):
        with measure_time() as t:
            plant = repo.get_plant("plant-01")
        assert plant is not None and plant.plant_id == "plant-01"
        t.row_count = 1 if plant else 0
        assert_timing(t, BUDGET_GET_PLANT, min_rows=1)

    def test_get_plant_returns_none_for_unknown_id(self):
        with measure_time() as t:
            plant = repo.get_plant("does-not-exist")
        assert plant is None
        t.row_count = 0
        assert_timing(t, BUDGET_GET_PLANT)

    def test_transformers_belong_to_requested_plant(self):
        with measure_time() as t:
            transformers = repo.list_transformers("plant-01")
        assert transformers
        assert all(t.plant_id == "plant-01" for t in transformers)
        t.row_count = len(transformers)
        assert_timing(t, BUDGET_LIST_TRANSFORMERS, min_rows=1)

    def test_total_transformers_is_71(self):
        with measure_time() as t:
            total = sum(len(repo.list_transformers(p.plant_id)) for p in repo.list_plants())
        assert total == 71
        t.row_count = total
        assert_timing(t, BUDGET_LIST_TRANSFORMERS * 30)

    def test_devices_belong_to_requested_transformer(self):
        with measure_time() as t:
            devices = repo.list_devices("plant-01-t1")
        assert devices
        assert all(d.transformer_id == "plant-01-t1" for d in devices)
        t.row_count = len(devices)
        assert_timing(t, BUDGET_LIST_DEVICES, min_rows=1)

    def test_get_device_returns_none_for_unknown_id(self):
        with measure_time() as t:
            device = repo.get_device("nope")
        assert device is None
        t.row_count = 0
        assert_timing(t, BUDGET_GET_DEVICE)

    def test_breadcrumb_resolves_full_path_in_one_call(self):
        with measure_time() as t:
            path = repo.get_device_breadcrumb(RESERVED_DEVICE_ID)
        assert path is not None
        assert path.plant_id == "plant-01"
        assert path.transformer_code == "aa12"
        assert path.device_code == "29017"
        assert path.plant_name
        t.row_count = 1 if path else 0
        assert_timing(t, BUDGET_BREADCRUMB, min_rows=1)

    def test_breadcrumb_returns_none_for_unknown_device(self):
        with measure_time() as t:
            path = repo.get_device_breadcrumb("nope")
        assert path is None
        t.row_count = 0
        assert_timing(t, BUDGET_BREADCRUMB)

    def test_hierarchy_counts_cover_all_plants(self):
        with measure_time() as t:
            counts = repo.count_hierarchy_by_plant()
        assert len(counts) == 30
        assert sum(t for t, _ in counts.values()) == 71
        assert sum(d for _, d in counts.values()) == 120
        t.row_count = len(counts)
        assert_timing(t, BUDGET_HIERARCHY_COUNTS, min_rows=30)


class TestLatestReadings:
    def test_returns_latest_reading(self):
        with measure_time() as t:
            latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        assert latest is not None
        assert latest.metric == "temperature"
        assert latest.device_id == RESERVED_DEVICE_ID
        t.row_count = 1 if latest else 0
        assert_timing(t, BUDGET_LATEST_READING, min_rows=1)

    def test_returns_none_for_unknown_metric(self):
        with measure_time() as t:
            result = repo.get_latest_reading(RESERVED_DEVICE_ID, "not-a-metric")
        assert result is None
        t.row_count = 0
        assert_timing(t, BUDGET_LATEST_READING)

    def test_returns_none_for_unknown_device(self):
        with measure_time() as t:
            result = repo.get_latest_reading("nope", "temperature")
        assert result is None
        t.row_count = 0
        assert_timing(t, BUDGET_LATEST_READING)

    def test_batched_latest_returns_all_eight_metrics(self):
        with measure_time() as t:
            latest = repo.get_latest_readings_for_device(RESERVED_DEVICE_ID)
        assert len(latest) == 8
        t.row_count = len(latest)
        assert_timing(t, BUDGET_BATCHED_LATEST, min_rows=8)

    def test_batched_latest_matches_single_metric_query(self):
        with measure_time() as t:
            batched = repo.get_latest_readings_for_device(RESERVED_DEVICE_ID)
            single = repo.get_latest_reading(RESERVED_DEVICE_ID, "voltage")
        assert batched["voltage"] == single
        t.row_count = len(batched)
        assert_timing(t, BUDGET_BATCHED_LATEST)

    def test_batched_latest_honours_metric_filter(self):
        with measure_time() as t:
            latest = repo.get_latest_readings_for_device(
                RESERVED_DEVICE_ID, ["voltage", "energy"]
            )
        assert set(latest) == {"voltage", "energy"}
        t.row_count = len(latest)
        assert_timing(t, BUDGET_BATCHED_LATEST, min_rows=2)

    def test_batched_latest_with_empty_metric_list_returns_empty(self):
        with measure_time() as t:
            result = repo.get_latest_readings_for_device(RESERVED_DEVICE_ID, [])
        assert result == {}
        t.row_count = 0
        assert_timing(t, BUDGET_BATCHED_LATEST)


class TestRangeQueries:
    def test_returns_only_readings_inside_range(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        with measure_time() as t:
            rows = repo.get_readings_in_range(RESERVED_DEVICE_ID, "temperature", start, latest.timestamp)
        assert rows
        assert all(start <= r.timestamp <= latest.timestamp for r in rows)
        t.row_count = len(rows)
        assert_timing(t, BUDGET_RANGE_SINGLE, min_rows=1)

    def test_24h_window_returns_49_inclusive_samples(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        with measure_time() as t:
            rows = repo.get_readings_in_range(RESERVED_DEVICE_ID, "temperature", start, latest.timestamp)
        assert len(rows) == 49  # 48 intervals, both endpoints inclusive
        t.row_count = len(rows)
        assert_timing(t, BUDGET_RANGE_SINGLE, min_rows=49)

    def test_range_is_ordered_ascending(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        with measure_time() as t:
            rows = repo.get_readings_in_range(
                RESERVED_DEVICE_ID, "temperature", latest.timestamp - timedelta(days=7), latest.timestamp
            )
        assert [r.timestamp for r in rows] == sorted(r.timestamp for r in rows)
        t.row_count = len(rows)
        assert_timing(t, BUDGET_RANGE_SINGLE)

    def test_range_outside_data_returns_empty(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        far_past = latest.timestamp - timedelta(days=400)
        with measure_time() as t:
            rows = repo.get_readings_in_range(
                RESERVED_DEVICE_ID, "temperature", far_past, far_past + timedelta(days=1)
            )
        assert rows == []
        t.row_count = 0
        assert_timing(t, BUDGET_RANGE_SINGLE)

    def test_batched_range_returns_requested_metrics(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        start = latest.timestamp - timedelta(hours=24)
        with measure_time() as t:
            result = repo.get_readings_for_device_in_range(
                RESERVED_DEVICE_ID, ["temperature", "voltage", "energy"], start, latest.timestamp
            )
        assert set(result) == {"temperature", "voltage", "energy"}
        assert all(len(v) == 49 for v in result.values())
        total_rows = sum(len(v) for v in result.values())
        t.row_count = total_rows
        assert_timing(t, BUDGET_BATCHED_RANGE, min_rows=49 * 3)

    def test_batched_range_matches_single_metric_range(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "voltage")
        start = latest.timestamp - timedelta(hours=24)
        with measure_time() as t:
            batched = repo.get_readings_for_device_in_range(
                RESERVED_DEVICE_ID, ["voltage"], start, latest.timestamp
            )
            single = repo.get_readings_in_range(RESERVED_DEVICE_ID, "voltage", start, latest.timestamp)
        assert batched["voltage"] == single
        t.row_count = len(batched.get("voltage", []))
        assert_timing(t, BUDGET_BATCHED_RANGE)

    def test_batched_range_includes_key_for_metric_with_no_rows(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        far_past = latest.timestamp - timedelta(days=400)
        with measure_time() as t:
            result = repo.get_readings_for_device_in_range(
                RESERVED_DEVICE_ID, ["temperature", "voltage"], far_past, far_past + timedelta(days=1)
            )
        assert result == {"temperature": [], "voltage": []}
        t.row_count = 0
        assert_timing(t, BUDGET_BATCHED_RANGE)

    def test_batched_range_with_empty_metric_list_returns_empty(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        with measure_time() as t:
            result = repo.get_readings_for_device_in_range(
                RESERVED_DEVICE_ID, [], latest.timestamp - timedelta(hours=1), latest.timestamp
            )
        assert result == {}
        t.row_count = 0
        assert_timing(t, BUDGET_BATCHED_RANGE)

    def test_metric_names_are_bound_not_interpolated(self):
        """A SQL metacharacter in a metric name must be inert, not an error."""
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        with measure_time() as t:
            result = repo.get_readings_for_device_in_range(
                RESERVED_DEVICE_ID,
                ["temperature", "'); DROP TABLE plant_monitoring.readings; --"],
                latest.timestamp - timedelta(hours=1),
                latest.timestamp,
            )
        assert result["'); DROP TABLE plant_monitoring.readings; --"] == []
        assert repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature") is not None
        total_rows = sum(len(v) for v in result.values())
        t.row_count = total_rows
        assert_timing(t, BUDGET_BATCHED_RANGE)
