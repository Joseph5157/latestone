"""Unit tests for services.monitoring_service - no database required."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from config.metrics import get_metric, ordered_metrics
from repositories.plant_monitoring_repository import (
    DeviceMetricReading,
    LatestReadingRow,
    RawReading,
)
from services import monitoring_service as svc
from services.monitoring_service import (
    DeltaStatus,
    Freshness,
    MetricView,
    MonitoringCondition,
    Period,
    Reading,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
FRESH_TS = NOW - timedelta(minutes=10)
STALE_TS = NOW - timedelta(days=2)
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

    def test_23h_59m_59s_is_fresh(self):
        assert svc.evaluate_freshness(
            NOW - timedelta(hours=23, minutes=59, seconds=59), NOW
        ) is Freshness.FRESH

    def test_exactly_24h_is_fresh(self):
        assert svc.evaluate_freshness(NOW - timedelta(hours=24), NOW) is Freshness.FRESH

    def test_beyond_24h_is_stale(self):
        assert svc.evaluate_freshness(
            NOW - timedelta(hours=24, seconds=1), NOW
        ) is Freshness.STALE

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
                # temperature is 25h behind the newest metric on this device
                "temperature": RawReading(DEVICE, "temperature", NOW - timedelta(hours=25), 31.4),
                "voltage": RawReading(DEVICE, "voltage", NOW, 11.02),
            },
        )

        def _batched(device_id, metrics, start, end):
            self.range_calls.append((tuple(metrics), start, end))
            return {m: [] for m in metrics}

        monkeypatch.setattr(svc.repo, "get_readings_for_device_in_range", _batched)

        # The priming read for cumulative meters. Without this stub these tests
        # reach the real database despite being marked "not db": they passed
        # only where a correctly seeded database happened to be listening, and
        # failed the moment they ran against a checkout pointing elsewhere.
        self.prime_calls: list[tuple] = []

        def _prime(device_id, metric, ts):
            self.prime_calls.append((device_id, metric, ts))
            return None

        monkeypatch.setattr(svc.repo, "get_last_reading_before", _prime)

    def test_the_priming_read_is_only_issued_for_cumulative_meters(self):
        """Seven of the eight metrics have no meter to prime, and a query per
        metric would undo the point of batching."""
        svc.get_device_full_view(DEVICE, Period.LAST_24H)
        assert [m for _d, m, _t in self.prime_calls] == ["energy"]

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
        assert views["temperature"].last_updated == NOW - timedelta(hours=25)
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


class TestMetricViewKpiProperties:
    """Phase 4: kpi_card.py used to call `series_context`/`reading_age`
    itself; it now reads `view.min_at`/`max_at`/`sample_count`/`age`. These
    properties must reproduce exactly what those functions already produced
    — same inputs, same output, just relocated onto the view model so
    `series_context`/`reading_age` stay the one authoritative calculation."""

    def _view(self, series, last_updated=None):
        return MetricView(
            metric=get_metric("temperature"), current=None, minimum=None,
            maximum=None, average=None, period_change=None,
            period_change_status=DeltaStatus.OK, series=series,
            last_updated=last_updated, freshness=Freshness.FRESH,
            condition=MonitoringCondition.UNKNOWN, has_data=bool(series),
        )

    def test_min_at_max_at_and_sample_count_match_series_context(self):
        series = _series([5.0, 9.0, 3.0])
        view = self._view(series)
        expected = svc.series_context(series)
        assert view.min_at == expected["min_at"]
        assert view.max_at == expected["max_at"]
        assert view.sample_count == expected["count"]

    def test_empty_series_gives_no_extremes_and_zero_count(self):
        view = self._view([])
        assert view.min_at is None
        assert view.max_at is None
        assert view.sample_count == 0

    def test_age_matches_reading_age_at_the_same_instant(self, monkeypatch):
        monkeypatch.setattr(svc, "_now", lambda: NOW)
        view = self._view(_series([1.0]), last_updated=NOW - timedelta(hours=2))
        assert view.age == timedelta(hours=2)

    def test_age_is_none_without_a_reading(self):
        view = self._view([], last_updated=None)
        assert view.age is None


class TestMetricHealthFromRows:
    """Per-metric reporting/freshness beneath one Plant or Transformer.

    Not a value aggregate — this answers "how many devices are we hearing
    from for this metric", built on the same evaluate_freshness /
    aggregate_freshness chain the fleet rollup already uses. Phase 5,
    Objective A.
    """

    def _row(self, plant, transformer, device, metric, ts):
        return LatestReadingRow(plant, transformer, device, metric, ts)

    def test_all_devices_fresh_reports_fresh(self):
        rows = [
            self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS),
            self._row("p1", "p1-t1", "d2", "temperature", FRESH_TS),
        ]
        result = {h.metric.key: h for h in svc.metric_health_from_rows(rows, plant_id="p1", now=NOW)}
        temp = result["temperature"]
        assert temp.freshness is Freshness.FRESH
        assert (temp.fresh_count, temp.stale_count, temp.no_data_count) == (2, 0, 0)
        assert temp.total_devices == 2
        assert temp.reporting_count == 2

    def test_mixed_fresh_and_stale_reports_stale(self):
        rows = [
            self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS),
            self._row("p1", "p1-t1", "d2", "temperature", STALE_TS),
        ]
        result = {h.metric.key: h for h in svc.metric_health_from_rows(rows, plant_id="p1", now=NOW)}
        assert result["temperature"].freshness is Freshness.STALE

    def test_any_no_data_wins_over_fresh_and_stale(self):
        rows = [
            self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS),
            self._row("p1", "p1-t1", "d2", "temperature", STALE_TS),
            self._row("p1", "p1-t1", "d3", "temperature", None),
        ]
        result = {h.metric.key: h for h in svc.metric_health_from_rows(rows, plant_id="p1", now=NOW)}
        temp = result["temperature"]
        assert temp.freshness is Freshness.NO_DATA
        assert (temp.fresh_count, temp.stale_count, temp.no_data_count) == (1, 1, 1)

    def test_metric_with_no_rows_at_all_is_still_reported(self):
        """The registry drives the output, not the rows present."""
        rows = [self._row("p1", "p1-t1", "d1", "voltage", FRESH_TS)]
        result = {h.metric.key: h for h in svc.metric_health_from_rows(rows, plant_id="p1", now=NOW)}
        temp = result["temperature"]
        assert temp.freshness is Freshness.NO_DATA
        assert temp.total_devices == 0

    def test_one_missing_device_among_reporting_peers_is_no_data(self):
        rows = [
            self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS),
            self._row("p1", "p1-t1", "d2", "temperature", FRESH_TS),
            self._row("p1", "p1-t1", "d3", "temperature", None),
        ]
        result = {h.metric.key: h for h in svc.metric_health_from_rows(rows, plant_id="p1", now=NOW)}
        temp = result["temperature"]
        assert temp.total_devices == 3
        assert temp.no_data_count == 1
        assert temp.freshness is Freshness.NO_DATA

    def test_zero_device_scope_follows_existing_empty_semantics(self):
        """An unmatched plant_id must not invent a new status: NO_DATA is
        exactly what aggregate_freshness([]) already returns for an empty
        population."""
        rows = [self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS)]
        result = svc.metric_health_from_rows(rows, plant_id="unknown-plant", now=NOW)
        assert all(h.freshness is Freshness.NO_DATA for h in result)
        assert all(h.total_devices == 0 for h in result)

    def test_all_eight_configured_metrics_are_returned(self):
        result = svc.metric_health_from_rows([], plant_id="p1", now=NOW)
        assert len(result) == 8

    def test_registry_order_is_preserved(self):
        result = svc.metric_health_from_rows([], plant_id="p1", now=NOW)
        assert [h.metric.key for h in result] == [m.key for m in ordered_metrics()]

    def test_plant_scope_excludes_other_plants(self):
        rows = [
            self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS),
            self._row("p2", "p2-t1", "d2", "temperature", FRESH_TS),
        ]
        result = {h.metric.key: h for h in svc.metric_health_from_rows(rows, plant_id="p1", now=NOW)}
        assert result["temperature"].total_devices == 1

    def test_transformer_scope_excludes_other_transformers(self):
        rows = [
            self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS),
            self._row("p1", "p1-t2", "d2", "temperature", FRESH_TS),
        ]
        result = {
            h.metric.key: h
            for h in svc.metric_health_from_rows(rows, transformer_id="p1-t1", now=NOW)
        }
        assert result["temperature"].total_devices == 1

    def test_transformer_scope_wins_when_both_are_given(self):
        """Matches repositories.latest_metric_readings's existing precedence."""
        rows = [
            self._row("p1", "p1-t1", "d1", "temperature", FRESH_TS),
            self._row("p1", "p1-t2", "d2", "temperature", FRESH_TS),
        ]
        result = {
            h.metric.key: h
            for h in svc.metric_health_from_rows(
                rows, plant_id="p1", transformer_id="p1-t1", now=NOW
            )
        }
        assert result["temperature"].total_devices == 1

    def test_one_injected_timestamp_is_used_for_every_metric(self, monkeypatch):
        """Proves the reference instant is resolved once, not once per metric
        - _now() must be called at most once even across all 8 metrics."""
        calls: list[int] = []
        monkeypatch.setattr(svc, "_now", lambda: calls.append(1) or NOW)
        rows = [self._row("p1", "p1-t1", "d1", m.key, FRESH_TS) for m in ordered_metrics()]
        svc.metric_health_from_rows(rows, plant_id="p1")
        assert len(calls) == 1

    def test_requires_a_scope(self):
        with pytest.raises(ValueError):
            svc.metric_health_from_rows([], now=NOW)


class TestHottestTemperature:
    """Attribution, not aggregation: the value shown is one device's real
    reading, selected by comparing latest-available values only. Phase 5,
    Objective B.
    """

    def _reading(self, transformer_id, transformer_code, device_id, device_code, ts, value):
        return DeviceMetricReading(
            plant_id="p1", transformer_id=transformer_id, transformer_code=transformer_code,
            device_id=device_id, device_code=device_code, metric="temperature",
            reading_ts=ts, value=value,
        )

    def test_hottest_value_is_selected(self):
        readings = [
            self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 30.0),
            self._reading("p1-t1", "ta01", "d2", "29002", FRESH_TS, 37.5),
            self._reading("p1-t1", "ta01", "d3", "29003", FRESH_TS, 25.0),
        ]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.value == pytest.approx(37.5)
        assert result.device_id == "d2"

    def test_a_stale_hottest_reading_is_still_eligible(self):
        readings = [
            self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 30.0),
            self._reading("p1-t1", "ta01", "d2", "29002", STALE_TS, 40.0),
        ]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.value == pytest.approx(40.0)
        assert result.freshness is Freshness.STALE

    def test_a_hotter_stale_reading_beats_a_cooler_fresh_one(self):
        """The rule this feature exists for: freshness never substitutes for
        value when selecting the maximum."""
        readings = [
            self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 22.0),
            self._reading("p1-t1", "ta01", "d2", "29002", STALE_TS, 41.0),
        ]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.device_id == "d2"
        assert result.value == pytest.approx(41.0)

    def test_selected_reading_carries_its_own_freshness(self):
        readings = [self._reading("p1-t1", "ta01", "d1", "29001", STALE_TS, 40.0)]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.freshness is svc.evaluate_freshness(STALE_TS, NOW)

    def test_carries_device_identity(self):
        readings = [self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 40.0)]
        result = svc.hottest_temperature(readings, now=NOW)
        assert (result.device_id, result.device_code) == ("d1", "29001")

    def test_carries_transformer_identity(self):
        readings = [self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 40.0)]
        result = svc.hottest_temperature(readings, now=NOW)
        assert (result.transformer_id, result.transformer_code) == ("p1-t1", "ta01")

    def test_reporting_count_excludes_devices_with_no_value(self):
        readings = [
            self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 30.0),
            self._reading("p1-t1", "ta01", "d2", "29002", None, None),
        ]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.reporting_count == 1

    def test_total_devices_includes_devices_with_no_value(self):
        readings = [
            self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 30.0),
            self._reading("p1-t1", "ta01", "d2", "29002", None, None),
        ]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.total_devices == 2

    def test_no_active_device_has_a_reading_returns_an_explicit_no_data_result(self):
        readings = [
            self._reading("p1-t1", "ta01", "d1", "29001", None, None),
            self._reading("p1-t1", "ta01", "d2", "29002", None, None),
        ]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.has_data is False
        assert result.value is None
        assert result.device_id is None
        assert result.freshness is Freshness.NO_DATA
        assert result.total_devices == 2
        assert result.reporting_count == 0

    def test_tie_is_broken_by_transformer_code_then_device_code_not_input_order(self):
        a = self._reading("p1-t2", "ta02", "dA", "29010", FRESH_TS, 35.0)
        b = self._reading("p1-t1", "ta01", "dB", "29005", FRESH_TS, 35.0)
        winner_forward = svc.hottest_temperature([a, b], now=NOW)
        winner_reversed = svc.hottest_temperature([b, a], now=NOW)
        assert winner_forward.device_id == winner_reversed.device_id == "dB"

    def test_readings_are_used_as_given_with_no_extra_status_filtering(self):
        """DeviceMetricReading carries no status field: active-only filtering
        is entirely repositories.latest_metric_readings's job (include_inactive
        defaults False). This documents the boundary rather than re-testing
        the repository's own filter."""
        field_names = {f.name for f in dataclasses.fields(DeviceMetricReading)}
        assert "status" not in field_names
        readings = [self._reading("p1-t1", "ta01", "d1", "29001", FRESH_TS, 30.0)]
        result = svc.hottest_temperature(readings, now=NOW)
        assert result.total_devices == len(readings)
