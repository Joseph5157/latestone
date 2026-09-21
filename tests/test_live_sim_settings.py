"""Unit tests for config.settings' LIVE_SIM_* env-var parsing helpers.

Pure functions, no database required.
"""
from __future__ import annotations

from config.settings import _get_float, _parse_csv_list


class TestGetFloat:
    def test_returns_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_FLOAT_VAR", raising=False)
        assert _get_float("TEST_FLOAT_VAR", 10.0) == 10.0

    def test_parses_a_valid_float(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT_VAR", "1800")
        assert _get_float("TEST_FLOAT_VAR", 10.0) == 1800.0

    def test_falls_back_to_default_on_invalid_value(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT_VAR", "not-a-number")
        assert _get_float("TEST_FLOAT_VAR", 10.0) == 10.0

    def test_empty_string_uses_default(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT_VAR", "")
        assert _get_float("TEST_FLOAT_VAR", 10.0) == 10.0


class TestParseCsvList:
    def test_returns_empty_tuple_when_unset(self, monkeypatch):
        monkeypatch.delenv("TEST_CSV_VAR", raising=False)
        assert _parse_csv_list("TEST_CSV_VAR") == ()

    def test_splits_on_commas(self, monkeypatch):
        monkeypatch.setenv("TEST_CSV_VAR", "a,b,c")
        assert _parse_csv_list("TEST_CSV_VAR") == ("a", "b", "c")

    def test_trims_whitespace_and_drops_empty_entries(self, monkeypatch):
        monkeypatch.setenv("TEST_CSV_VAR", " a , , b ,")
        assert _parse_csv_list("TEST_CSV_VAR") == ("a", "b")


class TestEventsPerDaySetting:
    def test_defaults_to_zero_so_events_are_off(self, monkeypatch):
        monkeypatch.delenv("LIVE_SIM_EVENTS_PER_DAY", raising=False)
        from config.settings import LiveSimSettings
        assert LiveSimSettings().events_per_day == 0.0

    def test_reads_the_environment(self, monkeypatch):
        monkeypatch.setenv("LIVE_SIM_EVENTS_PER_DAY", "12")
        from config.settings import LiveSimSettings
        assert LiveSimSettings().events_per_day == 12.0


class TestTemperatureScenariosSetting:
    def test_defaults_on_for_dashboard_showcase_states(self, monkeypatch):
        monkeypatch.delenv("LIVE_SIM_TEMPERATURE_SCENARIOS", raising=False)
        from config.settings import LiveSimSettings
        assert LiveSimSettings().temperature_scenarios is True

    def test_can_be_disabled_for_nominal_only_simulation(self, monkeypatch):
        monkeypatch.setenv("LIVE_SIM_TEMPERATURE_SCENARIOS", "false")
        from config.settings import LiveSimSettings
        assert LiveSimSettings().temperature_scenarios is False


class TestScenarioCountSettings:
    def test_defaults_populate_the_fleet_map_without_swamping_it(self, monkeypatch):
        monkeypatch.delenv("LIVE_SIM_WARNING_RTLS", raising=False)
        monkeypatch.delenv("LIVE_SIM_CRITICAL_RTLS", raising=False)
        from config.settings import LiveSimSettings
        settings = LiveSimSettings()
        assert (settings.warning_rtls, settings.critical_rtls) == (7, 3)

    def test_counts_are_configurable_without_a_code_change(self, monkeypatch):
        monkeypatch.setenv("LIVE_SIM_WARNING_RTLS", "12")
        monkeypatch.setenv("LIVE_SIM_CRITICAL_RTLS", "5")
        from config.settings import LiveSimSettings
        settings = LiveSimSettings()
        assert (settings.warning_rtls, settings.critical_rtls) == (12, 5)
