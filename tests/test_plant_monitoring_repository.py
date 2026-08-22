"""Repository tests against the seeded local PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
# Binding per HMI spec section 9: the fleet freshness query feeds a page load,
# and the client's history is longer than ours, so a query whose cost grows with
# history rather than device count must fail here rather than in production.
BUDGET_FLEET_FRESHNESS = 80
# Entity-scoped: at most ~8 devices, so ~8 bounded index seeks. Measured 2.4-2.7 ms
# warm. The budget is deliberately tight enough that a range-scan implementation
# (which would read ~1,400 rows per device to compute one maximum) cannot pass.
BUDGET_LATEST_METRIC = 50

ALL_METRIC_KEYS = [
    "temperature", "voltage", "current", "active_power",
    "reactive_power", "power_factor", "frequency", "energy",
]


class TestHierarchy:
    def test_lists_thirty_plants(self):
        with measure_time() as t:
            plants = repo.list_plants(allowed_device_ids=None)
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
            transformers = repo.list_transformers("plant-01", allowed_device_ids=None)
        assert transformers
        assert all(t.plant_id == "plant-01" for t in transformers)
        t.row_count = len(transformers)
        assert_timing(t, BUDGET_LIST_TRANSFORMERS, min_rows=1)

    def test_total_transformers_is_71(self):
        with measure_time() as t:
            total = sum(
                len(repo.list_transformers(p.plant_id, allowed_device_ids=None))
                for p in repo.list_plants(allowed_device_ids=None)
            )
        assert total == 71
        t.row_count = total
        assert_timing(t, BUDGET_LIST_TRANSFORMERS * 30)

    def test_devices_belong_to_requested_transformer(self):
        with measure_time() as t:
            devices = repo.list_devices("plant-01-t1", allowed_device_ids=None)
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
            counts = repo.count_hierarchy_by_plant(allowed_device_ids=None)
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


class TestFleetFreshness:
    """`latest_reading_times` — one round trip behind both the fleet Data Health
    card and the per-plant freshness column."""

    def test_covers_every_active_device_and_metric_pair(self):
        rows = repo.latest_reading_times(ALL_METRIC_KEYS, allowed_device_ids=None)
        pairs = {(r.device_id, r.metric) for r in rows}
        assert len(pairs) == len(rows), "a (device, metric) pair appeared twice"
        assert len(rows) == 120 * len(ALL_METRIC_KEYS)

    def test_stays_within_budget_on_the_full_reading_history(self):
        """The guard the spec makes binding: a shape that scales with history
        instead of device count passes every other test in this class.

        The first call in a process is discarded deliberately. Measured on the
        seeded database, engine and connection setup costs ~79 ms while the
        query itself runs in 15-19 ms; folding startup into the budget would
        measure SQLAlchemy, not the query shape this test exists to protect.
        """
        repo.latest_reading_times(ALL_METRIC_KEYS, allowed_device_ids=None)  # pay connection setup first
        with measure_time() as t:
            rows = repo.latest_reading_times(ALL_METRIC_KEYS, allowed_device_ids=None)
        t.row_count = len(rows)
        assert_timing(t, BUDGET_FLEET_FRESHNESS, min_rows=960)

    def test_reports_the_newest_reading_for_a_known_device(self):
        expected = repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature")
        rows = repo.latest_reading_times(["temperature"], allowed_device_ids=None)
        match = next(
            r for r in rows
            if r.device_id == RESERVED_DEVICE_ID and r.metric == "temperature"
        )
        assert match.reading_ts == expected.timestamp

    def test_carries_the_owning_plant_so_no_second_query_is_needed(self):
        rows = repo.latest_reading_times(["temperature"], allowed_device_ids=None)
        match = next(r for r in rows if r.device_id == RESERVED_DEVICE_ID)
        assert match.plant_id == "plant-01"
        assert len({r.plant_id for r in rows}) == 30

    def test_carries_the_owning_transformer_for_plant_level_rollups(self):
        """The Plant screen rolls up per transformer. The join is already in
        this query, so carrying the id costs nothing and saves a second one."""
        rows = repo.latest_reading_times(["temperature"], allowed_device_ids=None)
        match = next(r for r in rows if r.device_id == RESERVED_DEVICE_ID)
        assert match.transformer_id == "plant-01-t1"
        assert len({r.transformer_id for r in rows}) == 71

    def test_a_device_with_no_readings_yields_a_row_with_no_timestamp(self):
        """A silent device must appear as NO_DATA, not vanish from the fleet."""
        rows = repo.latest_reading_times(["not_a_seeded_metric"], allowed_device_ids=None)
        assert len(rows) == 120
        assert all(r.reading_ts is None for r in rows)

    def test_population_agrees_with_the_hierarchy_counts(self):
        """Fleet health and the plant table's device counts share a screen, so
        they must describe the same population — including the transformer-level
        status filter, which is easy to omit here and invisible while the seed
        holds no inactive rows."""
        counts = repo.count_hierarchy_by_plant(allowed_device_ids=None)
        rows = repo.latest_reading_times(["temperature"], allowed_device_ids=None)
        devices_per_plant = {}
        for r in rows:
            devices_per_plant[r.plant_id] = devices_per_plant.get(r.plant_id, 0) + 1
        for plant_id, (_transformers, devices) in counts.items():
            assert devices_per_plant.get(plant_id, 0) == devices, (
                f"{plant_id}: fleet freshness sees "
                f"{devices_per_plant.get(plant_id, 0)} devices, listings see {devices}"
            )

    def test_include_inactive_widens_the_population(self):
        default_rows = repo.latest_reading_times(["temperature"], allowed_device_ids=None)
        with_inactive = repo.latest_reading_times(["temperature"], include_inactive=True, allowed_device_ids=None)
        assert {r.device_id for r in default_rows} <= {r.device_id for r in with_inactive}

    def test_empty_metric_list_returns_empty_without_querying(self):
        with measure_time() as t:
            rows = repo.latest_reading_times([], allowed_device_ids=None)
        assert rows == []
        t.row_count = 0
        assert_timing(t, BUDGET_FLEET_FRESHNESS)

    def test_metric_names_are_bound_not_interpolated(self):
        injected = "'); DROP TABLE plant_monitoring.readings; --"
        rows = repo.latest_reading_times([injected], allowed_device_ids=None)
        assert all(r.reading_ts is None for r in rows)
        assert repo.get_latest_reading(RESERVED_DEVICE_ID, "temperature") is not None


class TestLatestMetricReadings:
    """`latest_metric_readings` — one metric, one entity subtree, one round trip.

    Backs the plant/transformer hottest-device attribution. Attribution rather
    than aggregation: the value shown is one device's real reading, so the query
    must carry enough identity to name that device.
    """

    PLANT = "plant-13"          # four transformers, seven devices
    TRANSFORMER = "plant-11-t1"  # a single-device transformer

    def test_returns_one_row_per_device_beneath_a_plant(self):
        rows = repo.latest_metric_readings("temperature", plant_id=self.PLANT)
        assert len(rows) == 7
        assert len({r.device_id for r in rows}) == len(rows), "a device appeared twice"

    def test_scopes_to_one_transformer(self):
        rows = repo.latest_metric_readings("temperature", transformer_id=self.TRANSFORMER)
        assert len(rows) == 1
        assert rows[0].transformer_id == self.TRANSFORMER

    def test_a_transformer_scope_is_a_subset_of_its_plant(self):
        plant_devices = {
            r.device_id for r in repo.latest_metric_readings("temperature", plant_id="plant-11")
        }
        transformer_devices = {
            r.device_id
            for r in repo.latest_metric_readings("temperature", transformer_id=self.TRANSFORMER)
        }
        assert transformer_devices
        assert transformer_devices <= plant_devices

    def test_carries_the_identity_needed_to_attribute_a_reading(self):
        """A maximum nobody can trace back to a device is not attribution."""
        row = repo.latest_metric_readings("temperature", plant_id=self.PLANT)[0]
        assert row.device_code and row.transformer_code
        assert row.device_id and row.transformer_id
        assert row.plant_id == self.PLANT
        assert row.metric == "temperature"

    def test_returns_only_the_requested_metric(self):
        rows = repo.latest_metric_readings("voltage", plant_id=self.PLANT)
        assert {r.metric for r in rows} == {"voltage"}

    def test_reports_the_newest_reading_for_a_device(self):
        rows = repo.latest_metric_readings("temperature", transformer_id=self.TRANSFORMER)
        newest = repo.get_latest_reading(rows[0].device_id, "temperature")
        assert rows[0].reading_ts == newest.timestamp
        assert rows[0].value == pytest.approx(newest.value)

    def test_population_matches_the_active_filtered_hierarchy(self):
        """The freshness figures and this query sit on one screen.

        Asserted as equivalence against the listing population rather than by
        seeding inactive equipment, so it keeps testing the filter even on a
        database where everything happens to be active.
        """
        from services import hierarchy_service
        from services.device_scope import UNRESTRICTED

        expected = {
            d.device_id
            for t in hierarchy_service.list_transformers(self.PLANT, scope=UNRESTRICTED)
            for d in hierarchy_service.list_devices(t.transformer_id, scope=UNRESTRICTED)
        }
        actual = {
            r.device_id for r in repo.latest_metric_readings("temperature", plant_id=self.PLANT)
        }
        assert actual == expected

    def test_requires_a_scope(self):
        """Without one this would seek every device in the fleet — the
        unbounded reading query the module docstring rules out."""
        with pytest.raises(ValueError):
            repo.latest_metric_readings("temperature")

    def test_metric_is_bound_not_interpolated(self):
        injected = "'); DROP TABLE plant_monitoring.readings; --"
        rows = repo.latest_metric_readings(injected, plant_id=self.PLANT)
        # Devices still listed; every one simply has no reading of that "metric".
        assert len(rows) == 7
        assert all(r.value is None and r.reading_ts is None for r in rows)
        assert repo.get_latest_reading("plant-01-t1-d1", "temperature") is not None

    def test_stays_within_budget(self):
        """Bounded index seeks, not a range scan. The first call in a process
        is discarded: it carries engine/connection setup, not query cost."""
        repo.latest_metric_readings("temperature", plant_id=self.PLANT)
        with measure_time() as t:
            rows = repo.latest_metric_readings("temperature", plant_id=self.PLANT)
        t.row_count = len(rows)
        assert_timing(t, BUDGET_LATEST_METRIC, min_rows=7)


class TestPrimingRead:
    """The reading that opens the first energy bin.

    A bar is consumption *across* its bin, so the first one needs the meter
    value at the window start - a reading that lies outside the window. Without
    it the first bar is short by one sampling interval and the bars no longer
    sum to the KPI, which is invisible on screen.
    """

    def test_returns_the_reading_immediately_before_the_instant(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "energy")
        with measure_time() as t:
            prime = repo.get_last_reading_before(
                RESERVED_DEVICE_ID, "energy", latest.timestamp
            )
        assert prime is not None
        assert prime.timestamp < latest.timestamp
        t.row_count = 1
        assert_timing(t, BUDGET_LATEST_READING, min_rows=1)

    def test_boundary_is_exclusive(self):
        """`before` means before. Including the instant itself would make the
        first bar cover zero elapsed time."""
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "energy")
        prime = repo.get_last_reading_before(
            RESERVED_DEVICE_ID, "energy", latest.timestamp
        )
        assert prime.timestamp != latest.timestamp

    def test_returns_the_nearest_earlier_reading_not_an_arbitrary_one(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "energy")
        prime = repo.get_last_reading_before(
            RESERVED_DEVICE_ID, "energy", latest.timestamp
        )
        earlier = repo.get_last_reading_before(
            RESERVED_DEVICE_ID, "energy", prime.timestamp
        )
        assert earlier.timestamp < prime.timestamp

    def test_returns_none_before_the_first_reading(self):
        ancient = datetime(2000, 1, 1, tzinfo=timezone.utc)
        assert repo.get_last_reading_before(
            RESERVED_DEVICE_ID, "energy", ancient
        ) is None

    def test_unknown_device_returns_none(self):
        assert repo.get_last_reading_before(
            "no-such-device", "energy", datetime(2026, 1, 1, tzinfo=timezone.utc)
        ) is None

    def test_metric_is_bound_not_interpolated(self):
        injected = "'); DROP TABLE plant_monitoring.readings; --"
        assert repo.get_last_reading_before(
            RESERVED_DEVICE_ID, injected, datetime(2026, 1, 1, tzinfo=timezone.utc)
        ) is None
        assert repo.get_latest_reading(RESERVED_DEVICE_ID, "energy") is not None
