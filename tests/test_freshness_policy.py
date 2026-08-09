"""Freshness policy comes from configuration, never hard-coded."""
from __future__ import annotations

import importlib
from datetime import datetime, timedelta, timezone

from config.settings import monitoring
from services.monitoring_service import Freshness, evaluate_freshness

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


class TestPolicyDefaults:
    def test_expected_interval_is_thirty_minutes(self):
        assert monitoring.expected_interval_minutes == 30

    def test_stale_after_three_intervals(self):
        assert monitoring.stale_after_intervals == 3

    def test_derived_threshold_is_ninety_minutes(self):
        assert monitoring.stale_after_minutes == 90


class TestPolicyIsHonoured:
    def test_threshold_boundary_follows_configuration(self, monkeypatch):
        """Changing config must change behaviour - proving it is not hard-coded."""
        import services.monitoring_service as svc

        class _Stub:
            stale_after_minutes = 10

        monkeypatch.setattr(svc, "monitoring", _Stub())
        assert evaluate_freshness(NOW - timedelta(minutes=5), NOW) is Freshness.FRESH
        assert evaluate_freshness(NOW - timedelta(minutes=15), NOW) is Freshness.STALE


class TestRefreshInterval:
    def test_interval_is_configurable_and_positive(self):
        assert monitoring.refresh_interval_seconds > 0

    def test_interval_read_from_environment(self, monkeypatch):
        monkeypatch.setenv("UI_REFRESH_INTERVAL_SECONDS", "300")
        import config.settings as settings

        importlib.reload(settings)
        assert settings.monitoring.refresh_interval_seconds == 300
        monkeypatch.delenv("UI_REFRESH_INTERVAL_SECONDS")
        importlib.reload(settings)
