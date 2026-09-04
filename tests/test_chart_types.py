"""Chart type comes from config, never from a metric key."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from components.chart_presentation import MalformedBarGeometry, bar_geometry, bar_geometries
from components.metric_chart import CHART_HEIGHT, build_delta_figure, build_metric_figure
from config.metrics import Aggregation, get_metric, ordered_metrics
from services.monitoring_service import ConsumptionBar, DeltaResult, DeltaStatus, Reading

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


# ---------------------------------------------------------------------------
# ENERGY-SPARK-2 — a Bar trace given fewer than two positions has no gap to
# infer a width from. Plotly's own auto-width/auto-range then collapses the
# whole axis to a near-zero window around the lone bar, forcing sub-
# millisecond tick labels (overlapping, unreadable) while the bar's real,
# far-larger footprint renders outside that window as a solid block. Proven
# by rendering the actual figure in the exact Plotly.js build (2.35.2) Dash
# serves, against the real `bin_consumption`/`quick_trend_bars` output for a
# reconstructed "seed aged out of the lookback window, only a live-only
# trickle remains" series — the real ROLE-BROWSER-1 trigger. An explicit
# `width` (each bar's own true duration) removes Plotly's need to infer
# anything, at any bar count.
# ---------------------------------------------------------------------------


class TestSingleBarWidthGuard:
    def test_a_single_bar_carries_an_explicit_width(self):
        """ENERGY2-01. Fails against the original HEAD: `width` was never
        passed to `go.Bar`, so `bar_trace.width` was always None regardless
        of bar count."""
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 5.0)])
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert bar_trace.width is not None

    def test_the_width_equals_the_bars_own_true_duration(self):
        """ENERGY2-03. Not a fallback constant — the bar's actual covered
        interval, in milliseconds (Plotly's date-axis width unit)."""
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 5.0)])
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert list(bar_trace.width) == [3600 * 1000]  # _bar spans 1 hour

    def test_multiple_bars_each_carry_their_own_width(self):
        """ENERGY2-06. The normal, grid-aligned multi-bar case: unaffected
        in every respect except that width is now populated too."""
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 5.0), _bar(1, 7.0)])
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert list(bar_trace.width) == [3600 * 1000, 3600 * 1000]
        assert list(bar_trace.y) == [5.0, 7.0]

    def test_width_does_not_alter_the_plotted_values(self):
        """ENERGY2-05. The fix is presentation-only — values, and therefore
        the energy totals they sum to, are untouched. `x` is now each bar's
        midpoint (ENERGY-SPARK-2R), not its start."""
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 5.0), _bar(1, 7.0)])
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert list(bar_trace.y) == [5.0, 7.0]
        assert list(bar_trace.x) == [
            T0 + timedelta(minutes=30), T0 + timedelta(hours=1, minutes=30),
        ]

    def test_empty_bars_still_render_only_the_annotation(self):
        """No bars, no width array to build — must not raise."""
        fig = build_delta_figure(get_metric("energy"), [])
        assert not any(t.type == "bar" for t in fig.data)

    def test_a_short_irregular_bar_gets_its_own_short_width(self):
        """A bin narrower than the nominal grid step (the aged-out-seed
        scenario in miniature) must be sized to what it actually covers,
        not to the nominal bin width."""
        short_bar = ConsumptionBar(
            T0, T0 + timedelta(seconds=10), DeltaResult(0.01, DeltaStatus.OK),
        )
        fig = build_delta_figure(get_metric("energy"), [short_bar])
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert list(bar_trace.width) == [10 * 1000]


# ---------------------------------------------------------------------------
# ENERGY-SPARK-2R — Codex review of ENERGY-SPARK-2 found two live blockers:
#
# (1) Plotly centres a Bar mark ON `x` and extends `width` equally in both
#     directions; it does not treat `x` as a left edge. ENERGY-SPARK-2 passed
#     `x=bar.start`, which is only correct when every bar shares one width.
#     Unequal-width neighbours (e.g. a 5-minute bin beside a 55-minute one)
#     each land shifted half their own width to the right of where they
#     should start, so the wide bar's centred mark overlaps the next bar.
# (2) `bar_widths_ms` (now `bar_geometry`) had no floor: a zero-duration or
#     reversed bin silently produced a zero/negative Plotly width instead of
#     being rejected as the malformed geometry it is.
#
# `bar_geometry`/`bar_geometries` (components/chart_presentation.py) fix
# both: `x` is each bar's own midpoint so it renders exactly `[start, end]`
# at any width, and `end <= start` raises `MalformedBarGeometry` rather than
# producing a valid-looking bar over an interval that was never measured.
# ---------------------------------------------------------------------------


class TestBarGeometry:
    def test_single_ten_second_bar_midpoint_and_width(self):
        """Scenario 1: midpoint correct, width = 10,000 ms."""
        bar = ConsumptionBar(T0, T0 + timedelta(seconds=10), DeltaResult(0.01, DeltaStatus.OK))
        geometry = bar_geometry(bar)
        assert geometry.x == T0 + timedelta(seconds=5)
        assert geometry.width_ms == 10_000

    def test_normal_thirty_minute_bar_midpoint_and_width(self):
        """Scenario 2: midpoint correct, width = 1,800,000 ms."""
        bar = ConsumptionBar(T0, T0 + timedelta(minutes=30), DeltaResult(5.0, DeltaStatus.OK))
        geometry = bar_geometry(bar)
        assert geometry.x == T0 + timedelta(minutes=15)
        assert geometry.width_ms == 1_800_000

    @staticmethod
    def _interval(geometry):
        half = timedelta(milliseconds=geometry.width_ms / 2)
        return geometry.x - half, geometry.x + half

    def test_unequal_adjacent_bars_render_without_overlap(self):
        """Scenario 3: a 5-minute bar beside a 55-minute one — each spans
        exactly its own start/end, and the two do not overlap."""
        first = ConsumptionBar(T0, T0 + timedelta(minutes=5), DeltaResult(1.0, DeltaStatus.OK))
        second = ConsumptionBar(
            T0 + timedelta(minutes=5), T0 + timedelta(hours=1),
            DeltaResult(2.0, DeltaStatus.OK),
        )
        first_geometry, second_geometry = bar_geometries([first, second])

        first_start, first_end = self._interval(first_geometry)
        second_start, second_end = self._interval(second_geometry)

        assert (first_start, first_end) == (first.start, first.end)
        assert (second_start, second_end) == (second.start, second.end)
        assert first_end <= second_start

    def test_multiple_normal_bars_are_contiguous_and_non_overlapping(self):
        """Scenario 4: equal-width bars, unaffected by the fix."""
        bars = [_bar(i, float(i)) for i in range(4)]
        intervals = [self._interval(g) for g in bar_geometries(bars)]

        for bar, (start, end) in zip(bars, intervals):
            assert (start, end) == (bar.start, bar.end)
        for (_, end), (next_start, _) in zip(intervals, intervals[1:]):
            assert end == next_start

    def test_zero_duration_bar_is_rejected(self):
        """Scenario 5: end == start."""
        bar = ConsumptionBar(T0, T0, DeltaResult(0.0, DeltaStatus.OK))
        with pytest.raises(MalformedBarGeometry):
            bar_geometry(bar)

    def test_reversed_bar_is_rejected(self):
        """Scenario 6: end before start."""
        bar = ConsumptionBar(T0 + timedelta(minutes=1), T0, DeltaResult(0.0, DeltaStatus.OK))
        with pytest.raises(MalformedBarGeometry):
            bar_geometry(bar)

    def test_energy_y_values_are_unaffected_by_geometry(self):
        """Scenario 7: geometry is x/width only — the plotted values (and the
        totals they sum to) are untouched."""
        bars = [_bar(0, 5.0), _bar(1, 7.0)]
        fig = build_delta_figure(get_metric("energy"), bars)
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert list(bar_trace.y) == [5.0, 7.0]

    def test_non_energy_metrics_do_not_use_bar_geometry(self):
        """Scenario 8: a line metric's trace still plots reading timestamps
        directly — the geometry fix lives entirely in the bar/delta path."""
        readings = [Reading(T0, 10.0), Reading(T0 + timedelta(minutes=30), 12.0)]
        fig = build_metric_figure(get_metric("voltage"), readings)
        trace = next(t for t in fig.data if t.type == "scatter")
        assert list(trace.x) == [T0, T0 + timedelta(minutes=30)]
        assert list(trace.y) == [10.0, 12.0]
