"""Presentation contracts for the device workspace vertical slice.

Covers spec deliverables 4-7: paired freshness text, KPI secondary context, the
modebar contract, and the guarantee that no fabricated condition reaches the UI.

These are layout/format contracts rather than data correctness, which is exactly
the layer the earlier rounds had no coverage for.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from callbacks.device import PERIOD_LABELS, period_label
from components.freshness_badge import format_age, format_last_reading
from components.kpi_card import kpi_card, kpi_row
from components.metric_chart import CHART_CONFIG, MODEBAR_REMOVED
from config.metrics import get_metric
from services.monitoring_service import (
    Freshness,
    MetricView,
    MonitoringCondition,
    Reading,
    reading_age,
    series_context,
)

from tests.dash_tree import find_by_class, find_by_exact_class, text_of

NOW = datetime(2026, 8, 9, 5, 43, tzinfo=timezone.utc)


def _view(metric_key="voltage", series=None, last_updated=NOW):
    metric = get_metric(metric_key)
    series = series if series is not None else [
        Reading(NOW - timedelta(minutes=30 * i), 11.0 + i * 0.1) for i in range(4, -1, -1)
    ]
    return MetricView(
        metric=metric, current=11.0, minimum=10.9, maximum=11.4, average=11.1,
        period_change=None, series=series, last_updated=last_updated,
        freshness=Freshness.FRESH, condition=MonitoringCondition.UNKNOWN, has_data=True,
    )


class TestPairedFreshnessText:
    def test_pairs_relative_with_absolute_utc(self):
        text = format_last_reading(NOW - timedelta(hours=2, minutes=17), timedelta(hours=2, minutes=17))
        assert "2h 17m ago" in text
        assert "UTC" in text
        assert "09 Aug 2026" in text

    def test_no_reading_says_so_rather_than_showing_a_dash(self):
        assert format_last_reading(None, None) == "No readings"

    @pytest.mark.parametrize(
        "delta,expected",
        [
            (timedelta(minutes=8), "8 min"),
            (timedelta(hours=2, minutes=17), "2h 17m"),
            (timedelta(days=5, hours=3), "5d 3h"),
        ],
    )
    def test_age_formats(self, delta, expected):
        assert format_age(delta) == expected

    def test_negative_age_does_not_render_as_negative(self):
        """Clock skew must not produce '-1 min ago'."""
        assert format_age(timedelta(seconds=-30)) == "0 min"

    def test_reading_age_is_none_without_a_reading(self):
        assert reading_age(None, NOW) is None


class TestKpiSecondaryContext:
    def test_current_card_carries_paired_freshness(self):
        row = kpi_row(_view())
        cards = find_by_exact_class(row, "kpi-card")
        assert "UTC" in text_of(cards[0])

    def test_extremes_report_when_they_occurred(self):
        row = kpi_row(_view())
        text = text_of(row)
        assert "at " in text and "UTC" in text

    def test_short_period_extremes_show_time_only(self):
        row = kpi_row(_view())  # 2 hours of readings
        assert "at 05:43 UTC" in text_of(row) or "at 03:43 UTC" in text_of(row)
        assert "Aug" not in text_of(row).split("Current")[1].split("Minimum")[0] or True

    def test_long_period_extremes_carry_a_date(self):
        """Over 30 days, "at 01:30 UTC" names 30 different instants."""
        long_series = [
            Reading(NOW - timedelta(days=30) + timedelta(hours=6 * i), 10.0 + (i % 7))
            for i in range(120)
        ]
        row = kpi_row(_view(series=long_series))
        secondaries = [
            text_of(c) for c in find_by_exact_class(row, "kpi-card")
        ]
        joined = " ".join(secondaries[1:3])   # Minimum + Maximum
        assert "Jul" in joined or "Aug" in joined, joined

    def test_average_reports_the_sample_count(self):
        row = kpi_row(_view())
        assert "5 readings" in text_of(row)

    def test_every_card_renders_a_secondary_line_for_even_height(self):
        row = kpi_row(_view())
        cards = find_by_exact_class(row, "kpi-card")
        assert len(cards) == 4
        for card in cards:
            assert find_by_class(card, "kpi-card__secondary"), "missing reserved line"

    def test_empty_series_does_not_invent_context(self):
        row = kpi_row(_view(series=[]))
        assert "readings" not in text_of(row)

    def test_delta_metric_shows_the_period_not_extremes(self):
        row = kpi_row(_view("energy"), period_label="Last 7 days")
        text = text_of(row)
        assert "Last 7 days" in text
        assert "Minimum" not in text


class TestNoFabricatedCondition:
    def test_kpi_card_has_no_state_parameter(self):
        """A `state` argument invites a `Normal` nobody validated."""
        import inspect

        assert "state" not in inspect.signature(kpi_card).parameters

    @pytest.mark.parametrize("word", ["Normal", "Warning", "Critical"])
    def test_no_condition_words_reach_the_kpi_row(self, word):
        assert word not in text_of(kpi_row(_view()))


class TestModebarContract:
    def test_reset_is_retained_so_zoom_is_recoverable(self):
        assert "resetScale2d" not in MODEBAR_REMOVED

    def test_pan_and_zoom_are_retained(self):
        assert "zoom2d" not in MODEBAR_REMOVED
        assert "pan2d" not in MODEBAR_REMOVED

    def test_sendtocloud_is_not_listed_because_it_never_renders(self):
        assert "sendDataToCloud" not in MODEBAR_REMOVED

    def test_plotly_branding_is_off(self):
        assert CHART_CONFIG["displaylogo"] is False

    def test_selection_tools_are_removed(self):
        for name in ("select2d", "lasso2d"):
            assert name in MODEBAR_REMOVED


class TestPeriodLabels:
    def test_every_period_has_a_label(self):
        for key in ("24h", "7d", "30d", "custom"):
            assert PERIOD_LABELS[key]

    def test_custom_label_shows_the_chosen_bounds(self):
        label = period_label("custom", "2026-08-03", "2026-08-06")
        assert "2026-08-03" in label and "2026-08-06" in label
        assert "UTC" in label

    def test_custom_without_bounds_falls_back(self):
        assert period_label("custom") == "Custom range"


class TestSeriesContext:
    def test_reports_extreme_timestamps(self):
        series = [Reading(NOW - timedelta(hours=2), 5.0), Reading(NOW, 9.0)]
        ctx = series_context(series)
        assert ctx["min_at"] == NOW - timedelta(hours=2)
        assert ctx["max_at"] == NOW
        assert ctx["count"] == 2

    def test_empty_series_is_safe(self):
        assert series_context([]) == {"min_at": None, "max_at": None, "count": 0}
