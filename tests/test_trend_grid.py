"""Quick Trends — eight cells, fixed positions, no modebar."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components.trend_grid import TREND_CHART_CONFIG, trend_grid
from config.metrics import ordered_metrics
from services.monitoring_service import (
    DeltaResult, DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading,
)
from tests.dash_tree import find_by_class, find_by_exact_class, links, walk

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _views(with_data=True):
    out = {}
    for m in ordered_metrics():
        series = (
            [Reading(T0 + timedelta(minutes=30 * i), 10.0 + i) for i in range(4)]
            if with_data else []
        )
        out[m.key] = MetricView(
            metric=m, current=10.0, minimum=None, maximum=None, average=None,
            period_change=None, period_change_status=DeltaStatus.OK, series=series,
            last_updated=T0, freshness=Freshness.FRESH,
            condition=MonitoringCondition.UNKNOWN, has_data=with_data,
            change=DeltaResult(1.0, DeltaStatus.OK),
        )
    return out


def _figures(grid):
    return [n for n in walk(grid) if getattr(n, "figure", None) is not None]


class TestGridShape:
    def test_renders_one_cell_per_configured_metric(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        assert len(find_by_exact_class(grid, "trend-cell")) == len(ordered_metrics())

    def test_cells_follow_display_order_and_do_not_reflow(self):
        """Fixed positions are the point: cell location becomes muscle memory,
        so it must not depend on which metric is selected."""
        expected = [m.label for m in ordered_metrics()]
        for active in ("temperature", "energy", "power_factor"):
            grid = trend_grid(_views(), active, "dev-1")
            labels = [e.children for e in find_by_class(grid, "trend-cell__label")]
            assert labels == expected

    def test_no_modebar_anywhere(self):
        """Eight more toolbars would compete with the primary chart."""
        assert TREND_CHART_CONFIG["displayModeBar"] is False

    def test_every_cell_carries_a_figure(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        assert len(_figures(grid)) == len(ordered_metrics())


class TestSelection:
    def test_exactly_one_cell_is_selected(self):
        grid = trend_grid(_views(), "voltage", "dev-1")
        selected = [
            e for e in find_by_exact_class(grid, "trend-cell")
            if "trend-cell--selected" in e.className
        ]
        assert len(selected) == 1

    def test_selection_never_borrows_the_warning_or_freshness_classes(self):
        """"The one you are looking at" and "the one with a problem" are
        different statements and must not share styling."""
        grid = trend_grid(_views(), "voltage", "dev-1")
        selected = next(
            e for e in find_by_exact_class(grid, "trend-cell")
            if "trend-cell--selected" in e.className
        )
        assert "warning" not in selected.className
        assert "freshness" not in selected.className
        assert "stale" not in selected.className


class TestPromotion:
    def test_every_cell_links_to_its_metric_preserving_period(self):
        grid = trend_grid(_views(), "temperature", "dev-1", period="7d")
        hrefs = [href for _label, href in links(grid)]
        assert len(hrefs) == len(ordered_metrics())
        assert all("period=7d" in h for h in hrefs)
        assert any("metric=energy" in h for h in hrefs)

    def test_custom_bounds_survive_promotion(self):
        grid = trend_grid(
            _views(), "temperature", "dev-1",
            period="custom", custom_start="2026-08-01", custom_end="2026-08-03",
        )
        hrefs = [href for _label, href in links(grid)]
        assert all("start=2026-08-01" in h and "end=2026-08-03" in h for h in hrefs)

    def test_links_point_at_the_same_device(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        assert all("dev-1" in href for _label, href in links(grid))


class TestEmptyAndTypes:
    def test_empty_metric_keeps_full_cell_height(self):
        """A collapsed cell reads as a layout fault rather than absent data."""
        grid = trend_grid(_views(with_data=False), "temperature", "dev-1")
        assert all(g.figure.layout.height for g in _figures(grid))

    def test_empty_metric_says_so(self):
        grid = trend_grid(_views(with_data=False), "temperature", "dev-1")
        texts = [a.text for g in _figures(grid) for a in g.figure.layout.annotations]
        assert texts and all("No readings" in t for t in texts)

    def test_energy_cell_is_a_bar_chart(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        energy = _figures(grid)[-1]
        assert any(t.type == "bar" for t in energy.figure.data)

    def test_statistics_cells_are_line_charts(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        voltage = _figures(grid)[1]
        assert any(t.type == "scatter" for t in voltage.figure.data)

    def test_hover_states_utc(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        trace = _figures(grid)[0].figure.data[0]
        assert "UTC" in trace.hovertemplate
