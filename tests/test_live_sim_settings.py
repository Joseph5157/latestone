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
