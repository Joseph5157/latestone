"""Unit tests for services.monitoring_service - no database required."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from config.metrics import get_metric
from repositories.plant_monitoring_repository import RawReading
from services import monitoring_service as svc
from services.monitoring_service import (
    Freshness,
    MonitoringCondition,
    Period,
    Reading,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
DEVICE = "plant-01-t1-d1"


def _series(values: list[float], end: datetime = NOW) -> list[Reading]:
    """Build a 30-min-spaced ascending series ending at `end`."""
    return [
        Reading(timestamp=end - timedelta(minutes=30 * (len(values) - 1 - i)), value=v)
        for i, v in enumerate(values)
    ]


class TestEvaluateFreshness:
    def test_no_timestamp_is_no_data(self):
        assert svc.evaluate_freshness(None, NOW) is Freshness.NO_DATA

    def test_recent_reading_is_fresh(self):
        assert svc.evaluate_freshness(NOW - timedelta(minutes=20), NOW) is Freshness.FRESH

    def test_just_inside_threshold_is_fresh(self):
        assert svc.evaluate_freshness(NOW - timedelta(minutes=89), NOW) is Freshness.FRESH

    def test_beyond_three_intervals_is_stale(self):
        assert svc.evaluate_freshness(NOW - timedelta(minutes=91), NOW) is Freshness.STALE

    def test_far_past_is_stale_not_no_data(self):
        """Stale means late data; no_data means no reading ever."""
        assert svc.evaluate_freshness(NOW - timedelta(days=5), NOW) is Freshness.STALE


class TestComputeStatistics:
    def test_returns_min_max_average(self):
        assert svc._compute_statistics(_series([10.0, 20.0, 30.0])) == (10.0, 30.0, 20.0)

    def test_single_reading_returns_that_value(self):
        assert svc._compute_statistics(_series([7.5])) == (7.5, 7.5, 7.5)

    def test_empty_series_returns_all_none(self):
        assert svc._compute_statistics([]) == (None, None, None)


class TestPeriodDelta:
    """`_compute_delta` became `period_delta`, which returns a DeltaResult.

    The last assertion here is a deliberate reversal. The old test required a
    counter reset to surface as a negative number, on the reasoning that
    surfacing beats hiding. Both are true and neither is the right answer: a
    negative MWh figure reads as generation, so the reset is now surfaced as a
    *named* condition instead of as arithmetic that looks valid.
    """

    def test_returns_last_minus_first(self):
        result = svc.period_delta(_series([100.0, 110.0, 125.0]))
        assert result.value == pytest.approx(25.0)
        assert result.status is svc.DeltaStatus.OK

    def test_requires_at_least_two_readings(self):
        result = svc.period_delta(_series([100.0]))
        assert result.value is None
        assert result.status is svc.DeltaStatus.INSUFFICIENT_DATA

    def test_empty_series_returns_none(self):
        assert svc.period_delta([]).value is None

    def test_a_counter_reset_is_named_not_rendered_as_a_negative(self):
        result = svc.period_delta(_series([500.0, 10.0]))
        assert result.status is svc.DeltaStatus.DISCONTINUITY
        assert result.value is None


class TestPeriodStart:
    def test_24h(self):
        assert svc.period_start(Period.LAST_24H, NOW) == NOW - timedelta(hours=24)

    def test_7d(self):
        assert svc.period_start(Period.LAST_7D, NOW) == NOW - timedelta(days=7)

    def test_30d(self):
        assert svc.period_start(Period.LAST_30D, NOW) == NOW - timedelta(days=30)

    def test_custom_returns_none(self):
        assert svc.period_start(Period.CUSTOM, NOW) is None


class TestGetMetricView:
    @pytest.fixture(autouse=True)
    def _stub_repo(self, monkeypatch):
        self.latest: RawReading | None = RawReading(DEVICE, "temperature", NOW, 31.4)
        self.range_rows: list[RawReading] = [
            RawReading(DEVICE, "temperature", r.timestamp, r.value)
            for r in _series([30.0, 31.0, 32.0])
        ]
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo, "get_latest_reading", lambda device_id, metric: self.latest
        )
        monkeypatch.setattr(
            svc.repo,
            "get_readings_in_range",
            lambda device_id, metric, start, end: self.range_rows,
        )

    def test_returns_none_for_unknown_metric(self):
        assert svc.get_metric_view(DEVICE, "not-a-metric", Period.LAST_24H) is None

    def test_statistics_metric_populates_min_max_average(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert (view.minimum, view.maximum, view.average) == (30.0, 32.0, 31.0)

    def test_statistics_metric_leaves_period_change_none(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.period_change is None

    def test_current_is_latest_available_not_period_last(self):
        """Current must ignore the period; series ends at 32.0 but latest is 31.4."""
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.current == pytest.approx(31.4)

    def test_condition_is_always_unknown(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.condition is MonitoringCondition.UNKNOWN

    def test_delta_metric_populates_period_change_only(self, monkeypatch):
        self.latest = RawReading(DEVICE, "energy", NOW, 8142.0)
        self.range_rows = [
            RawReading(DEVICE, "energy", r.timestamp, r.value)
            for r in _series([8000.0, 8070.0, 8142.0])
        ]
        view = svc.get_metric_view(DEVICE, "energy", Period.LAST_24H)
        assert view.period_change == pytest.approx(142.0)
        assert (view.minimum, view.maximum, view.average) == (None, None, None)

    def test_delta_metric_with_single_reading_has_no_period_change(self):
        self.latest = RawReading(DEVICE, "energy", NOW, 8142.0)
        self.range_rows = [RawReading(DEVICE, "energy", NOW, 8142.0)]
        view = svc.get_metric_view(DEVICE, "energy", Period.LAST_24H)
        assert view.period_change is None

    def test_no_reading_ever_yields_empty_view(self):
        self.latest = None
        self.range_rows = []
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.has_data is False
        assert view.current is None
        assert view.last_updated is None
        assert view.series == []
        assert (view.minimum, view.maximum, view.average, view.period_change) == (
            None, None, None, None,
        )
        assert view.freshness is Freshness.NO_DATA

    def test_empty_period_keeps_current_and_last_updated(self):
        """Latest exists but the selected range holds no points."""
        self.range_rows = []
        view = svc.get_metric_view(DEVICE, "temperature", Period.LAST_24H)
        assert view.has_data is True
        assert view.current == pytest.approx(31.4)
        assert view.last_updated == NOW
        assert view.series == []
        assert (view.minimum, view.maximum, view.average) == (None, None, None)

    def test_custom_period_uses_explicit_bounds(self, monkeypatch):
        captured: dict = {}

        def _capture(device_id, metric, start, end):
            captured["start"], captured["end"] = start, end
            return self.range_rows

        monkeypatch.setattr(svc.repo, "get_readings_in_range", _capture)
        start = NOW - timedelta(days=3)
        end = NOW - timedelta(days=1)
        svc.get_metric_view(DEVICE, "temperature", Period.CUSTOM, start, end)
        assert (captured["start"], captured["end"]) == (start, end)

    def test_custom_period_without_bounds_returns_empty_series(self):
        view = svc.get_metric_view(DEVICE, "temperature", Period.CUSTOM, None, None)
        assert view.series == []


class TestGetDeviceSnapshot:
    def test_returns_one_snapshot_per_metric_in_display_order(self, monkeypatch):
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: {
                "temperature": RawReading(DEVICE, "temperature", NOW, 31.4)
            },
        )
        snapshots = svc.get_device_snapshot(DEVICE)
        assert len(snapshots) == 8
        assert [s.metric.display_order for s in snapshots] == list(range(1, 9))

    def test_metric_without_reading_is_no_data(self, monkeypatch):
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: {
                "temperature": RawReading(DEVICE, "temperature", NOW, 31.4)
            },
        )
        snapshots = {s.metric.key: s for s in svc.get_device_snapshot(DEVICE)}
        assert snapshots["temperature"].freshness is Freshness.FRESH
        assert snapshots["voltage"].freshness is Freshness.NO_DATA
        assert snapshots["voltage"].current is None

    def test_issues_exactly_one_repository_call(self, monkeypatch):
        calls = []
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: calls.append(device_id) or {},
        )
        svc.get_device_snapshot(DEVICE)
        assert len(calls) == 1


class TestGetDeviceFullView:
    @pytest.fixture(autouse=True)
    def _stub_repo(self, monkeypatch):
        self.range_calls: list[tuple] = []
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        monkeypatch.setattr(
            svc.repo,
            "get_latest_readings_for_device",
            lambda device_id, metrics=None: {
                # temperature is 2h behind the newest metric on this device
                "temperature": RawReading(DEVICE, "temperature", NOW - timedelta(hours=2), 31.4),
                "voltage": RawReading(DEVICE, "voltage", NOW, 11.02),
            },
        )

        def _batched(device_id, metrics, start, end):
            self.range_calls.append((tuple(metrics), start, end))
            return {m: [] for m in metrics}

        monkeypatch.setattr(svc.repo, "get_readings_for_device_in_range", _batched)

    def test_issues_exactly_one_batched_range_call(self):
        svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert len(self.range_calls) == 1

    def test_uses_one_common_window_anchored_to_now(self):
        svc.get_device_full_view(DEVICE, Period.LAST_24H)
        _, start, end = self.range_calls[0]
        assert end == NOW
        assert start == NOW - timedelta(hours=24)

    def test_each_metric_keeps_its_own_last_updated(self):
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert views["temperature"].last_updated == NOW - timedelta(hours=2)
        assert views["voltage"].last_updated == NOW

    def test_freshness_evaluated_per_metric_independently(self):
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert views["temperature"].freshness is Freshness.STALE
        assert views["voltage"].freshness is Freshness.FRESH

    def test_returns_a_view_for_every_metric(self):
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert len(views) == 8

    def test_custom_range_uses_explicit_bounds_not_anchor(self):
        start = NOW - timedelta(days=3)
        end = NOW - timedelta(days=1)
        svc.get_device_full_view(DEVICE, Period.CUSTOM, start, end)
        _, used_start, used_end = self.range_calls[0]
        assert (used_start, used_end) == (start, end)

    def test_device_with_no_readings_at_all(self, monkeypatch):
        monkeypatch.setattr(
            svc.repo, "get_latest_readings_for_device", lambda device_id, metrics=None: {}
        )
        views = svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert len(views) == 8
        assert all(v.has_data is False for v in views.values())
        assert all(v.freshness is Freshness.NO_DATA for v in views.values())
