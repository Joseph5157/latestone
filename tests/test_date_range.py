"""Tests for the callback-layer date/URL wiring.

This layer had no coverage, which is why the end-date truncation bug and the
period-dropping snapshot links survived a green suite. The service tests pass
`datetime` objects straight in and never exercise the picker-string
conversion where the truncation happened.
"""
from __future__ import annotations

from datetime import datetime, timezone

from callbacks.device import _parse_picker_date
from components.metric_snapshot_strip import snapshot_tile
from config.metrics import get_metric
from routes import device_href, parse_custom_range, parse_query
from services.monitoring_service import (
    DeltaStatus, Freshness, MetricView, MonitoringCondition,
)


class TestParsePickerDate:
    # Bounds are UTC-aware since NEW-04; they are compared against a
    # TIMESTAMPTZ column, where a naive value is resolved using the database
    # session's timezone.
    def test_empty_is_none(self):
        assert _parse_picker_date(None) is None
        assert _parse_picker_date("") is None

    def test_start_date_is_midnight(self):
        assert _parse_picker_date("2026-08-03") == datetime(
            2026, 8, 3, 0, 0, tzinfo=timezone.utc
        )

    def test_end_date_covers_the_whole_day(self):
        """The regression: a date-only end must not truncate to midnight."""
        end = _parse_picker_date("2026-08-06", is_end=True)
        assert end.date() == datetime(2026, 8, 6).date()
        assert (end.hour, end.minute) == (23, 59)
        assert end > datetime(2026, 8, 6, 23, 30, tzinfo=timezone.utc)

    def test_end_with_explicit_time_is_left_alone(self):
        value = "2026-08-06T12:00:00"
        assert _parse_picker_date(value, is_end=True) == datetime(
            2026, 8, 6, 12, 0, tzinfo=timezone.utc
        )

    def test_a_full_day_of_half_hourly_readings_is_included(self):
        """30-min cadence: the last reading of the end day is 23:30."""
        end = _parse_picker_date("2026-08-06", is_end=True)
        assert datetime(2026, 8, 6, 23, 30, tzinfo=timezone.utc) <= end


class TestCustomRangeInUrl:
    def test_bounds_round_trip(self):
        href = device_href(
            "d1", metric_key="energy", period="custom",
            start="2026-08-03", end="2026-08-06",
        )
        _, _, query = href.partition("?")
        assert parse_custom_range(f"?{query}") == ("2026-08-03", "2026-08-06")

    def test_bounds_omitted_for_non_custom_periods(self):
        href = device_href("d1", period="7d", start="2026-08-03", end="2026-08-06")
        assert "start=" not in href and "end=" not in href

    def test_absent_bounds(self):
        assert parse_custom_range(None) == (None, None)
        assert parse_custom_range("?metric=energy") == (None, None)

    def test_unparseable_bounds_are_discarded_not_raised(self):
        assert parse_custom_range("?start=not-a-date&end=2026-08-06") == (None, "2026-08-06")


class TestSnapshotTileKeepsPeriod:
    def _tile_href(self, **kwargs):
        # The tile is fed MetricViews since the analytics phase: the strip reads
        # from the same fetch as the KPIs and charts, so it can also show the
        # period direction.
        view = MetricView(
            metric=get_metric("energy"), current=1.0, minimum=None, maximum=None,
            average=None, period_change=None, period_change_status=DeltaStatus.OK,
            series=[], last_updated=None, freshness=Freshness.FRESH,
            condition=MonitoringCondition.UNKNOWN, has_data=True,
        )
        return snapshot_tile(view, False, "d1", **kwargs).children[0].href

    def test_period_is_preserved(self):
        """The regression: switching metric must not snap back to 24h."""
        href = self._tile_href(period="30d")
        assert "period=30d" in href
        assert parse_query(href.partition("?")[2])[1] == "30d"

    def test_default_period_stays_omitted(self):
        assert "period=" not in self._tile_href(period="24h")

    def test_custom_bounds_are_carried(self):
        href = self._tile_href(
            period="custom", custom_start="2026-08-03", custom_end="2026-08-06"
        )
        assert "start=2026-08-03" in href and "end=2026-08-06" in href
