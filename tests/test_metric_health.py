"""Metric Health overview component — presentation only, no freshness math.

Data health only: these tests never assert a rendered temperature or
voltage value, only counts and freshness wording.
"""
from __future__ import annotations

import pathlib

from components.metric_health import metric_health_overview, metric_health_tile
from config.metrics import get_metric, ordered_metrics
from services.monitoring_service import Freshness, FreshnessRollup, MetricHealth
from tests.dash_tree import find_by_exact_class, text_of
from tests.test_component_architecture import (
    FORBIDDEN_SERVICE_SYMBOLS,
    _imported_symbols_from_services,
)

F, S, N = Freshness.FRESH, Freshness.STALE, Freshness.NO_DATA


def _health(key, state, counts, total):
    return MetricHealth(metric=get_metric(key), rollup=FreshnessRollup(state, counts, total))


class TestRendersSuppliedItems:
    def test_renders_one_tile_per_supplied_metric(self):
        items = [_health(m.key, F, {F: 3, S: 0, N: 0}, 3) for m in ordered_metrics()[:5]]
        grid = metric_health_overview(items)
        assert len(find_by_exact_class(grid, "metric-health-tile")) == 5

    def test_preserves_supplied_ordering_not_registry_order(self):
        """The service already returns registry order; the component must not
        re-sort — a deliberately out-of-order input proves that."""
        reversed_metrics = list(reversed(ordered_metrics()))
        items = [_health(m.key, F, {F: 1, S: 0, N: 0}, 1) for m in reversed_metrics]
        grid = metric_health_overview(items)
        labels = [text_of(t) for t in find_by_exact_class(grid, "metric-health-tile__label")]
        assert labels == [m.label for m in reversed_metrics]


class TestFreshnessStates:
    def test_renders_fresh(self):
        tile = metric_health_tile(_health("temperature", F, {F: 3, S: 0, N: 0}, 3))
        assert "Fresh" in text_of(tile)

    def test_renders_stale(self):
        tile = metric_health_tile(_health("temperature", S, {F: 2, S: 5, N: 0}, 7))
        assert "Stale" in text_of(tile)

    def test_renders_no_data(self):
        tile = metric_health_tile(_health("voltage", N, {F: 0, S: 0, N: 7}, 7))
        assert "No data" in text_of(tile)


class TestCountsAndCoverage:
    def test_mixed_state_shows_breakdown_and_coverage(self):
        tile = metric_health_tile(_health("temperature", S, {F: 2, S: 5, N: 0}, 7))
        text = text_of(tile)
        assert "5 stale" in text and "2 fresh" in text
        assert "7 of 7 devices reporting" in text

    def test_no_data_coverage_reads_zero_of_total(self):
        tile = metric_health_tile(_health("voltage", N, {F: 0, S: 0, N: 7}, 7))
        assert "0 of 7 devices reporting" in text_of(tile)

    def test_all_fresh_uses_the_all_devices_phrasing(self):
        tile = metric_health_tile(_health("temperature", F, {F: 7, S: 0, N: 0}, 7))
        assert "All 7 devices reporting" in text_of(tile)

    def test_single_state_population_omits_the_redundant_breakdown_line(self):
        """7 no-data devices would just repeat '0 of 7 devices reporting' as
        '7 no data' - the breakdown line is left empty rather than restating
        the coverage line in different words."""
        tile = metric_health_tile(_health("voltage", N, {F: 0, S: 0, N: 7}, 7))
        breakdown = find_by_exact_class(tile, "metric-health-tile__breakdown")[0]
        assert breakdown.children == ""


class TestZeroDeviceState:
    def test_zero_device_scope_is_intentional_not_a_crash(self):
        tile = metric_health_tile(_health("temperature", N, {F: 0, S: 0, N: 0}, 0))
        assert "No active devices" in text_of(tile)


class TestArchitectureBoundary:
    def test_component_does_not_import_forbidden_service_functions(self):
        path = pathlib.Path(__file__).resolve().parent.parent / "components" / "metric_health.py"
        hit = _imported_symbols_from_services(path) & FORBIDDEN_SERVICE_SYMBOLS
        assert not hit
