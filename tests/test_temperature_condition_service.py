"""TEMP-CONDITION-1: temperature condition against Administrator limits (ADR-023).

Pure — `classify`/`hottest` take values; `device_temperatures` is exercised
with its three reads monkeypatched, so nothing here opens a connection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from services import temperature_condition_service as svc
from services.device_scope import DeviceScope
from services.temperature_condition_service import (
    CONDITION_LABELS,
    DeviceTemperature,
    TemperatureCondition as C,
    TemperatureLimits,
    classify,
    hottest,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
FRESH = NOW - timedelta(minutes=10)
STALE_AFTER = timedelta(minutes=60)
LIMITS = TemperatureLimits(warning_c=Decimal("36"), critical_c=Decimal("40"))


def _c(value, ts=FRESH, limits=LIMITS):
    return classify(value, ts, now=NOW, limits=limits, stale_after=STALE_AFTER)


class TestClassify:
    @pytest.mark.parametrize(
        "value, expected",
        [(20.0, C.NORMAL), (35.999, C.NORMAL), (36.0, C.WARNING), (39.9, C.WARNING),
         (40.0, C.CRITICAL), (55.0, C.CRITICAL)],
    )
    def test_bands_are_inclusive_at_each_limit(self, value, expected):
        assert _c(value) is expected

    def test_no_limits_is_never_normal(self):
        assert _c(20.0, limits=None) is C.LIMITS_NOT_SET

    def test_missing_reading_is_no_recent_data(self):
        assert _c(None, ts=None) is C.NO_RECENT_DATA

    def test_stale_reading_is_no_recent_data_even_if_hot(self):
        assert _c(50.0, ts=NOW - timedelta(minutes=61)) is C.NO_RECENT_DATA

    def test_exactly_at_the_stale_threshold_is_still_recent(self):
        # Same strict `>` as monitoring_service.evaluate_freshness.
        assert _c(20.0, ts=NOW - STALE_AFTER) is C.NORMAL

    def test_stale_wins_over_limits_not_set(self):
        assert _c(20.0, ts=NOW - timedelta(days=2), limits=None) is C.NO_RECENT_DATA

    def test_float_noise_does_not_cross_a_limit(self):
        # Compared as Decimal(str(value)): 36.0 is exactly at the limit, and
        # a value just below it stays below it.
        assert _c(36.0) is C.WARNING and _c(35.99999999999999) is C.NORMAL

    def test_every_condition_has_a_label(self):
        assert set(CONDITION_LABELS) == set(C)


def _t(device_id, value, condition):
    return DeviceTemperature(
        plant_id="p", transformer_id="t", transformer_code="T1",
        device_id=device_id, device_code=device_id, value=value,
        reading_ts=FRESH, condition=condition,
    )


class TestHottest:
    def test_highest_first_and_capped(self):
        temps = [_t("a", 30.0, C.NORMAL), _t("b", 41.0, C.CRITICAL),
                 _t("c", 37.0, C.WARNING)]
        assert [t.device_id for t in hottest(temps, 2)] == ["b", "c"]

    def test_excludes_no_recent_data_and_missing_values(self):
        temps = [_t("a", 60.0, C.NO_RECENT_DATA), _t("b", None, C.NO_RECENT_DATA),
                 _t("c", 25.0, C.LIMITS_NOT_SET)]
        assert [t.device_id for t in hottest(temps, 5)] == ["c"]

    def test_ties_are_stable_by_device(self):
        temps = [_t("b", 30.0, C.NORMAL), _t("a", 30.0, C.NORMAL)]
        assert [t.device_id for t in hottest(temps, 5)] == ["a", "b"]


class _Row:
    def __init__(self, device_id, value, ts):
        self.plant_id, self.transformer_id, self.transformer_code = "p", "t", "T1"
        self.device_id = self.device_code = device_id
        self.value, self.reading_ts = value, ts


class TestDeviceTemperatures:
    def _patch(self, monkeypatch, rows, limits):
        seen = {}

        def fake_read(metric, **kw):
            seen.update(metric=metric, **kw)
            return rows

        monkeypatch.setattr(svc.repo, "latest_metric_readings", fake_read)
        monkeypatch.setattr(svc, "current_limits", lambda: limits)
        monkeypatch.setattr(svc, "effective_stale_after_minutes", lambda: 60)
        return seen

    def test_reads_fleet_temperature_in_the_callers_scope(self, monkeypatch):
        seen = self._patch(monkeypatch, [], LIMITS)
        scope = DeviceScope(device_ids=frozenset({"a"}))
        svc.device_temperatures(scope, now=NOW)
        assert seen == {"metric": "temperature", "fleet": True,
                        "allowed_device_ids": frozenset({"a"})}

    def test_classifies_every_row(self, monkeypatch):
        rows = [_Row("a", 41.0, FRESH), _Row("b", 20.0, FRESH), _Row("c", None, None)]
        self._patch(monkeypatch, rows, LIMITS)
        result = svc.device_temperatures(DeviceScope(device_ids=None), now=NOW)
        assert [(t.device_id, t.condition) for t in result] == [
            ("a", C.CRITICAL), ("b", C.NORMAL), ("c", C.NO_RECENT_DATA)]


class TestCurrentLimits:
    def test_none_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(svc, "get_current_threshold_config", lambda: None)
        assert svc.current_limits() is None

    def test_carries_the_stored_decimals(self, monkeypatch):
        class _State:
            warning_c, critical_c = Decimal("36.500"), Decimal("40.000")
        monkeypatch.setattr(svc, "get_current_threshold_config", lambda: _State())
        assert svc.current_limits() == TemperatureLimits(Decimal("36.500"), Decimal("40.000"))
