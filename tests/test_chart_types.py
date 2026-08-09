"""Chart type comes from config, never from a metric key."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components.metric_chart import CHART_HEIGHT, build_delta_figure
from config.metrics import Aggregation, get_metric, ordered_metrics
from services.monitoring_service import ConsumptionBar, DeltaResult, DeltaStatus

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _bar(i, value, status=DeltaStatus.OK):
    return ConsumptionBar(
        T0 + timedelta(hours=i), T0 + timedelta(hours=i + 1),
        DeltaResult(value, status),
    )


class TestChartMatrix:
    def test_energy_is_the_only_bar_chart(self):
        bars = [m.key for m in ordered_metrics() if m.chart_type == "bar"]
        assert bars == ["energy"]

    def test_every_other_metric_is_a_line(self):
        for metric in ordered_metrics():
            if metric.key != "energy":
                assert metric.chart_type == "line"

    def test_energy_is_a_bar_because_it_is_a_delta_metric(self):
        """The chart type follows the aggregation, not a hand-picked list."""
        energy = get_metric("energy")
        assert energy.aggregation is Aggregation.DELTA
        assert energy.chart_type == "bar"

    def test_no_statistics_metric_is_a_bar(self):
        for metric in ordered_metrics():
            if metric.aggregation is Aggregation.STATISTICS:
                assert metric.chart_type != "bar"


class TestDeltaFigure:
    def test_draws_one_bar_per_known_bin(self):
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 5.0), _bar(1, 7.0)])
        bar_traces = [t for t in fig.data if t.type == "bar"]
        assert len(bar_traces) == 1
        assert list(bar_traces[0].y) == [5.0, 7.0]

    def test_a_discontinuous_bin_draws_no_bar(self):
        fig = build_delta_figure(
            get_metric("energy"),
            [_bar(0, 5.0), _bar(1, None, DeltaStatus.DISCONTINUITY)],
        )
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert bar_trace.y[1] is None

    def test_a_discontinuity_is_marked_neutrally_not_as_a_warning(self):
        """Data quality, not an electrical alarm."""
        fig = build_delta_figure(
            get_metric("energy"), [_bar(0, None, DeltaStatus.DISCONTINUITY)],
        )
        markers = [t for t in fig.data if t.type == "scatter"]
        assert markers, "a discontinuity must be visible, not merely absent"
        colour = str(markers[0].marker.color).lower()
        assert colour not in ("red", "#ef4444", "#dc2626", "orange", "#f59e0b")

    def test_an_unknown_bin_is_never_drawn_as_zero(self):
        fig = build_delta_figure(
            get_metric("energy"),
            [_bar(0, None, DeltaStatus.INSUFFICIENT_DATA)],
        )
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert bar_trace.y[0] is None

    def test_title_states_the_bin_width(self):
        fig = build_delta_figure(
            get_metric("energy"), [_bar(0, 5.0)],
            period_label="Last 24 hours", bin_label="30 min bars",
        )
        assert "30 min bars" in fig.layout.title.text

    def test_empty_bars_render_an_explanatory_annotation(self):
        fig = build_delta_figure(get_metric("energy"), [])
        assert fig.layout.annotations
        assert "No data" in fig.layout.annotations[0].text

    def test_height_matches_the_frozen_line_chart(self):
        """Switching metric must not change the page's vertical geometry."""
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 1.0)])
        assert fig.layout.height == CHART_HEIGHT

    def test_hover_states_utc(self):
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 5.0)])
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert "UTC" in bar_trace.hovertemplate
