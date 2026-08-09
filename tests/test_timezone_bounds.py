"""Custom range bounds must be timezone-aware before they reach the database.

Regression tests for audit finding NEW-04.

`_parse_picker_date()` returned naive datetimes and the custom branch of
`_resolve_window()` passed them through untouched, so they were compared against
`readings.reading_ts TIMESTAMPTZ`. PostgreSQL resolves a timezone-less timestamp
using the session's `TimeZone`, so the local Docker database happened to behave
while a client session in another timezone would silently shift the selected day.

**Assumption, stated because the client has not specified one:** UTC is the
canonical form throughout. That is what `_now()` already returns and what `_align_tz()`
already attaches, so this makes the picker consistent with the rest of the app
rather than introducing a new policy. If the client later wants plant-local time,
that is a display concern layered on top, not a change to storage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from callbacks.device import _parse_picker_date
from repositories.plant_monitoring_repository import RawReading
from services import monitoring_service as svc
from services.monitoring_service import Period

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
DEVICE = "plant-01-t1-d1"


class TestPickerDatesAreAware:
    def test_start_is_utc_aware(self):
        parsed = _parse_picker_date("2026-08-03")
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)

    def test_end_is_utc_aware(self):
        parsed = _parse_picker_date("2026-08-06", is_end=True)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)

    def test_end_still_covers_the_whole_day(self):
        """The NEW-1 fix must survive the timezone change."""
        end = _parse_picker_date("2026-08-06", is_end=True)
        assert (end.hour, end.minute) == (23, 59)
        assert end > datetime(2026, 8, 6, 23, 30, tzinfo=timezone.utc)

    def test_empty_is_still_none(self):
        assert _parse_picker_date(None) is None
        assert _parse_picker_date("") is None

    def test_an_already_aware_value_is_left_alone(self):
        value = "2026-08-06T12:00:00+00:00"
        assert _parse_picker_date(value) == datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


class TestWindowBoundsReachTheRepositoryAware:
    @pytest.fixture
    def captured(self, monkeypatch):
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_reading",
            lambda device_id, metric: RawReading(
                device_id=DEVICE, metric=metric, timestamp=NOW, value=1.0
            ),
        )
        seen: dict = {}

        def _capture(device_id, metric, start, end):
            seen["start"], seen["end"] = start, end
            return []

        monkeypatch.setattr(svc.repo, "get_readings_in_range", _capture)
        return seen

    def test_naive_custom_bounds_are_made_aware(self, captured):
        """The regression: these used to arrive naive at a TIMESTAMPTZ column."""
        svc.get_metric_view(
            DEVICE, "temperature", Period.CUSTOM,
            datetime(2026, 8, 3, 0, 0), datetime(2026, 8, 6, 23, 59),
        )
        assert captured["start"].tzinfo is not None
        assert captured["end"].tzinfo is not None

    def test_naive_bounds_keep_their_wall_clock_reading(self, captured):
        """Attaching UTC must not shift the instant the operator picked."""
        svc.get_metric_view(
            DEVICE, "temperature", Period.CUSTOM,
            datetime(2026, 8, 3, 0, 0), datetime(2026, 8, 6, 23, 59),
        )
        assert captured["start"] == datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
        assert captured["end"] == datetime(2026, 8, 6, 23, 59, tzinfo=timezone.utc)

    def test_already_aware_bounds_are_preserved(self, captured):
        start = datetime(2026, 8, 3, tzinfo=timezone.utc)
        end = datetime(2026, 8, 6, tzinfo=timezone.utc)
        svc.get_metric_view(DEVICE, "temperature", Period.CUSTOM, start, end)
        assert (captured["start"], captured["end"]) == (start, end)

    def test_relative_windows_are_aware_too(self, captured):
        svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert captured["start"].tzinfo is not None
        assert captured["end"].tzinfo is not None


class TestTimestampsAreLabelled:
    def test_readings_table_marks_its_timezone(self):
        from callbacks.device import TIMESTAMP_COLUMN_NAME

        assert "UTC" in TIMESTAMP_COLUMN_NAME

    def test_device_context_marks_its_timezone(self):
        from pages import device_dashboard

        from tests.dash_tree import find_by_class, text_of

        bar = find_by_class(device_dashboard.layout(), "equipment-context")[0]
        assert "UTC" in text_of(bar)
