"""Freshness policy comes from configuration, never hard-coded."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.settings import (
    DEFAULT_FRESHNESS_STALE_AFTER_MINUTES,
    MonitoringSettings,
    freshness_stale_after_minutes_from_environment,
    monitoring,
    resolve_freshness_stale_after_minutes,
)
from services.monitoring_service import Freshness, evaluate_freshness

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


class TestPolicyDefaults:
    def test_default_is_twenty_four_hours(self):
        assert DEFAULT_FRESHNESS_STALE_AFTER_MINUTES == 1440
        assert resolve_freshness_stale_after_minutes(None, None, None) == 1440
        assert monitoring.stale_after_minutes == 1440

    def test_direct_setting_is_used_without_interval_math(self):
        assert resolve_freshness_stale_after_minutes("720", None, None) == 720

    def test_direct_setting_wins_and_legacy_pair_is_explicitly_ignored(self):
        assert resolve_freshness_stale_after_minutes("1440", "30", "3") == 1440

    def test_legacy_pair_does_not_restore_ninety_minutes(self):
        assert resolve_freshness_stale_after_minutes(None, "30", "3") == 1440

    def test_invalid_or_non_positive_direct_value_falls_back_safely(self):
        assert resolve_freshness_stale_after_minutes("bad", None, None) == 1440
        assert resolve_freshness_stale_after_minutes("0", None, None) == 1440

    def test_environment_uses_direct_setting_over_legacy_pair(self, monkeypatch):
        monkeypatch.setenv("FRESHNESS_STALE_AFTER_MINUTES", "720")
        monkeypatch.setenv("EXPECTED_INTERVAL_MINUTES", "30")
        monkeypatch.setenv("STALE_AFTER_INTERVALS", "3")
        assert freshness_stale_after_minutes_from_environment() == 720

    def test_environment_ignores_legacy_pair_when_direct_setting_is_absent(self, monkeypatch):
        monkeypatch.delenv("FRESHNESS_STALE_AFTER_MINUTES", raising=False)
        monkeypatch.setenv("EXPECTED_INTERVAL_MINUTES", "30")
        monkeypatch.setenv("STALE_AFTER_INTERVALS", "3")
        assert freshness_stale_after_minutes_from_environment() == 1440


class TestPolicyIsHonoured:
    def test_threshold_boundary_follows_configuration(self, monkeypatch):
        """Changing config must change behaviour - proving it is not hard-coded."""
        import services.freshness_threshold_service as threshold_svc

        class _Stub:
            stale_after_minutes = 10

        monkeypatch.setattr(threshold_svc, "monitoring", _Stub())
        assert evaluate_freshness(NOW - timedelta(minutes=5), NOW) is Freshness.FRESH
        assert evaluate_freshness(NOW - timedelta(minutes=15), NOW) is Freshness.STALE

    def test_administrator_override_wins_over_environment_default(self, monkeypatch):
        """FRESHNESS-CONFIG-1: a configured value replaces the 24h default."""
        import services.freshness_threshold_service as threshold_svc

        monkeypatch.setattr(threshold_svc, "_read_override_minutes", lambda: 60)
        assert evaluate_freshness(NOW - timedelta(minutes=59), NOW) is Freshness.FRESH
        assert evaluate_freshness(NOW - timedelta(minutes=61), NOW) is Freshness.STALE
        # Under the 24h default the same reading would still be Fresh.
        assert evaluate_freshness(NOW - timedelta(hours=2), NOW) is Freshness.STALE

    def test_monitoring_settings_exposes_no_expected_interval_model(self):
        assert "expected_interval_minutes" not in MonitoringSettings.__dataclass_fields__
        assert "stale_after_intervals" not in MonitoringSettings.__dataclass_fields__


class TestRefreshInterval:
    def test_interval_is_configurable_and_positive(self):
        assert monitoring.refresh_interval_seconds > 0

    def test_explicit_constructor_value_is_honoured(self):
        assert MonitoringSettings(refresh_interval_seconds=300).refresh_interval_seconds == 300
