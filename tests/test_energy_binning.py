"""Energy bin selection and bar arithmetic.

Bins are duration aware and never finer than the source data. A bar is
consumption *across* its bin, computed from the meter value at each boundary —
not from the extremes of the readings inside it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config.metrics import SOURCE_RESOLUTION_MINUTES, get_metric
from services.monitoring_service import (
    DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading, TARGET_BARS,
    bin_consumption, choose_bin, period_delta, quick_trend_bars,
)

DAY = datetime(2026, 8, 9, 0, 0, tzinfo=timezone.utc)


class TestChooseBin:
    @pytest.mark.parametrize("span,expected", [
        (timedelta(hours=24), timedelta(minutes=30)),
        (timedelta(days=7), timedelta(hours=6)),
        (timedelta(days=30), timedelta(days=1)),
        (timedelta(days=3), timedelta(hours=2)),
        (timedelta(days=90), timedelta(days=7)),
    ])
    def test_span_selects_its_rung(self, span, expected):
        assert choose_bin(span) == expected

    def test_never_finer_than_the_source_resolution(self):
        """A 5-minute bin would draw mostly-empty bars implying measurement we
        do not have."""
        floor = timedelta(minutes=SOURCE_RESOLUTION_MINUTES)
        for hours in (1, 2, 6, 12, 24):
            assert choose_bin(timedelta(hours=hours)) >= floor

    def test_bar_count_stays_within_target(self):
        for days in (1, 2, 3, 7, 14, 30, 60):
            span = timedelta(days=days)
            assert span / choose_bin(span) <= TARGET_BARS + 1

    def test_duration_aware_not_period_named(self):
        """Two custom ranges of different length must not share a bin."""
        assert choose_bin(timedelta(days=3)) != choose_bin(timedelta(days=90))

    def test_absurdly_long_span_uses_the_coarsest_rung(self):
        assert choose_bin(timedelta(days=3650)) == timedelta(days=7)


def _meter(start_value, step, count, first_ts=DAY, cadence_minutes=30):
    """A clean monotonic meter at the source cadence."""
    return [
        Reading(first_ts + timedelta(minutes=cadence_minutes * i), start_value + step * i)
        for i in range(count)
    ]


class TestBarArithmetic:
    def test_24h_of_30min_samples_yields_48_non_zero_bars(self):
        """THE regression test for the boundary-value definition.

        A bar is consumption *across* its bin. Computing it as last − first of
        the readings *inside* the bin gives 48 zero-height bars here, because
        each 30-minute bin holds exactly one reading. Nothing else in the suite
        would notice, and the chart would look entirely plausible.
        """
        end = DAY + timedelta(hours=24)
        series = _meter(1000.0, 2.0, 48, first_ts=DAY + timedelta(minutes=30))
        prime = Reading(DAY, 998.0)
        bars = bin_consumption(series, timedelta(minutes=30), DAY, end, prime=prime)
        assert len(bars) == 48
        assert all(b.result.status is DeltaStatus.OK for b in bars)
        assert all(b.result.value == 2.0 for b in bars)

    def test_bars_sum_exactly_to_the_period_delta(self):
        """The load-bearing invariant: the chart and the KPI are one number."""
        end = DAY + timedelta(hours=24)
        series = _meter(1000.0, 2.0, 48, first_ts=DAY + timedelta(minutes=30))
        prime = Reading(DAY, 998.0)
        bars = bin_consumption(series, timedelta(hours=6), DAY, end, prime=prime)
        total = sum(b.result.value for b in bars)
        assert total == pytest.approx(period_delta(series, prime=prime).value)

    def test_sums_to_period_delta_without_a_priming_reading(self):
        end = DAY + timedelta(hours=24)
        series = _meter(1000.0, 2.0, 48, first_ts=DAY)
        bars = bin_consumption(series, timedelta(hours=6), DAY, end)
        known = [b.result.value for b in bars if b.result.is_known]
        assert sum(known) == pytest.approx(period_delta(series).value)

    def test_bins_align_to_utc_boundaries_not_to_the_first_sample(self):
        start = DAY + timedelta(minutes=17)
        end = start + timedelta(hours=4)
        series = _meter(500.0, 1.0, 10, first_ts=start)
        bars = bin_consumption(series, timedelta(hours=1), start, end)
        assert bars[1].start == DAY + timedelta(hours=1)

    def test_a_bin_containing_a_decrease_is_indeterminate(self):
        end = DAY + timedelta(hours=2)
        series = [
            Reading(DAY + timedelta(minutes=30), 100.0),
            Reading(DAY + timedelta(minutes=60), 110.0),
            Reading(DAY + timedelta(minutes=90), 4.0),
            Reading(DAY + timedelta(minutes=120), 9.0),
        ]
        bars = bin_consumption(series, timedelta(hours=1), DAY, end)
        assert any(b.result.status is DeltaStatus.DISCONTINUITY for b in bars)
        assert all(
            b.result.value is None or b.result.value >= 0 for b in bars
        ), "no bar may render as negative consumption"

    def test_a_bin_with_no_closing_reading_is_insufficient_not_zero(self):
        """Carrying the previous value forward would assert zero consumption,
        which we did not measure."""
        end = DAY + timedelta(hours=3)
        series = [Reading(DAY + timedelta(minutes=30), 100.0)]
        prime = Reading(DAY, 99.0)
        bars = bin_consumption(series, timedelta(hours=1), DAY, end, prime=prime)
        assert bars[0].result.is_known
        assert bars[-1].result.status is DeltaStatus.INSUFFICIENT_DATA

    def test_a_bin_with_no_opening_value_is_insufficient(self):
        """Before the meter's first reading we know nothing, not zero."""
        end = DAY + timedelta(hours=2)
        series = [Reading(DAY + timedelta(minutes=90), 100.0)]
        bars = bin_consumption(series, timedelta(hours=1), DAY, end)
        assert bars[0].result.status is DeltaStatus.INSUFFICIENT_DATA

    def test_empty_series_yields_bars_that_are_all_unknown(self):
        end = DAY + timedelta(hours=3)
        bars = bin_consumption([], timedelta(hours=1), DAY, end)
        assert bars
        assert all(not b.result.is_known for b in bars)

    def test_bars_cover_the_window_contiguously(self):
        end = DAY + timedelta(hours=4)
        bars = bin_consumption([], timedelta(hours=1), DAY, end)
        assert bars[0].start == DAY
        assert bars[-1].end == end
        for earlier, later in zip(bars, bars[1:]):
            assert earlier.end == later.start


def _view(metric_key, series):
    return MetricView(
        metric=get_metric(metric_key), current=None, minimum=None, maximum=None,
        average=None, period_change=None, period_change_status=DeltaStatus.OK,
        series=series, last_updated=None, freshness=Freshness.FRESH,
        condition=MonitoringCondition.UNKNOWN, has_data=bool(series),
    )


class TestQuickTrendBars:
    """`quick_trend_bars` relocates trend_grid's own binning call into the
    service layer (Phase 3 boundary fix) without changing the algorithm:
    same `choose_bin`/`bin_consumption`, same series-span basis, no `prime`."""

    def test_non_delta_metric_never_gets_bars(self):
        series = _meter(10.0, 1.0, 4)
        assert quick_trend_bars(_view("temperature", series)) == []

    def test_empty_series_yields_no_bars(self):
        assert quick_trend_bars(_view("energy", [])) == []

    def test_delta_metric_reproduces_calling_bin_consumption_directly(self):
        """Same output as the pre-move call site: binned over the series'
        own first/last timestamp, no `prime`."""
        series = _meter(1000.0, 2.0, 8, first_ts=DAY)
        start, end = series[0].timestamp, series[-1].timestamp
        expected = bin_consumption(series, choose_bin(end - start), start, end)

        assert quick_trend_bars(_view("energy", series)) == expected

    def test_uses_the_series_own_span_not_a_wider_window(self):
        """Unlike the primary chart's bars (window_start/window_end/prime,
        see callbacks.device), a Quick Trend cell has no KPI beside it and
        bins only over what its own series actually covers."""
        series = _meter(1000.0, 2.0, 4, first_ts=DAY + timedelta(hours=2))
        bars = quick_trend_bars(_view("energy", series))
        assert bars[0].start == series[0].timestamp
        assert bars[-1].end == series[-1].timestamp
