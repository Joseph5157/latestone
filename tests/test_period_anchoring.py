"""Relative periods must be anchored to wall-clock now, not to the last sample.

Regression tests for audit finding NEW-03.

`24h / 7d / 30d` were windowed off the newest reading's timestamp. A device that
stopped reporting five days ago therefore answered "Last 24h" with the 24 hours
preceding that five-day-old reading: a fully populated chart and a complete set
of KPIs, under a label the operator reads as "the last 24 hours". The freshness
badge said stale, but nothing else did.

`current` / `last_updated` are a separate concept and must stay tied to the
latest available reading regardless of the selected period — REQUIREMENTS.md
defines them that way.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from repositories.plant_monitoring_repository import RawReading
from services import monitoring_service as svc
from services.monitoring_service import Freshness, Period

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
DEVICE = "plant-01-t1-d1"
STALE_BY = timedelta(days=5)


def _raw(metric: str, timestamp: datetime, value: float) -> RawReading:
    return RawReading(device_id=DEVICE, metric=metric, timestamp=timestamp, value=value)


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(svc, "_now", lambda: NOW)


@pytest.fixture
def stale_device(monkeypatch, clock):
    """A device whose newest reading is five days old."""
    last_ts = NOW - STALE_BY
    monkeypatch.setattr(
        svc.repo,
        "get_latest_reading",
        lambda device_id, metric: _raw(metric, last_ts, 31.4),
    )

    captured: dict = {}

    def _capture_range(device_id, metric, start, end):
        captured["start"], captured["end"] = start, end
        return []

    monkeypatch.setattr(svc.repo, "get_readings_in_range", _capture_range)
    return captured


class TestRelativePeriodsUseWallClock:
    @pytest.mark.parametrize(
        "period,expected_span",
        [
            (Period.LAST_24H, timedelta(hours=24)),
            (Period.LAST_7D, timedelta(days=7)),
            (Period.LAST_30D, timedelta(days=30)),
        ],
    )
    def test_window_ends_at_now_for_a_stale_device(self, stale_device, period, expected_span):
        svc.get_metric_view(DEVICE, "temperature", period)
        assert stale_device["end"] == NOW
        assert stale_device["start"] == NOW - expected_span

    def test_stale_device_does_not_backfill_the_window(self, stale_device):
        """The regression: the query must not slide back to the old reading."""
        svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert stale_device["start"] > NOW - STALE_BY, (
            "24h window reached back past a five-day-old reading"
        )

    def test_stale_device_reports_an_empty_last_24h(self, stale_device):
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.series == []
        assert (view.minimum, view.maximum, view.average) == (None, None, None)


class TestCurrentStaysPeriodIndependent:
    def test_current_and_last_updated_still_come_from_the_latest_reading(self, stale_device):
        """Fixing the window must not blank out Current."""
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.current == pytest.approx(31.4)
        assert view.last_updated == NOW - STALE_BY
        assert view.has_data is True
        assert view.freshness is Freshness.STALE


class TestCustomRangeIsUnaffected:
    def test_custom_bounds_are_still_passed_through_verbatim(self, stale_device):
        start = NOW - timedelta(days=3)
        end = NOW - timedelta(days=1)
        svc.get_metric_view(DEVICE, "temperature", Period.CUSTOM, start, end)
        assert (stale_device["start"], stale_device["end"]) == (start, end)


class TestFullViewAnchoring:
    @pytest.fixture
    def stale_full_view(self, monkeypatch, clock):
        last_ts = NOW - STALE_BY
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: {
                "temperature": _raw("temperature", last_ts, 31.4),
                "voltage": _raw("voltage", last_ts, 400.0),
            },
        )
        captured: dict = {}

        def _batched(device_id, metrics, start, end):
            captured["start"], captured["end"] = start, end
            return {m: [] for m in metrics}

        monkeypatch.setattr(svc.repo, "get_readings_for_device_in_range", _batched)
        # Cumulative metrics also ask for the reading that opens the window.
        # Unstubbed, this test reaches the real database despite being marked
        # "not db".
        monkeypatch.setattr(
            svc.repo, "get_last_reading_before", lambda device_id, metric, ts: None
        )
        return captured

    def test_common_window_ends_at_now(self, stale_full_view):
        svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert stale_full_view["end"] == NOW
        assert stale_full_view["start"] == NOW - timedelta(hours=24)
