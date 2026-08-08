"""Unit tests for services.temperature_service (no database required)."""
from __future__ import annotations

from datetime import datetime

import pytest

from repositories.temperature_repository import RawReading
from services.temperature_service import (
    Status,
    get_status,
    parse_reading,
)


class TestParseReading:
    def test_parses_valid_reading(self):
        raw = RawReading(timestamp_raw="26/08/01,00:00", temperature_raw="31.5")
        result = parse_reading(raw)
        assert result is not None
        assert result.timestamp == datetime(2026, 8, 1, 0, 0)
        assert result.temperature_c == pytest.approx(31.5)

    def test_returns_none_for_malformed_timestamp(self):
        raw = RawReading(timestamp_raw="not-a-date", temperature_raw="31.5")
        assert parse_reading(raw) is None

    def test_returns_none_for_malformed_temperature(self):
        raw = RawReading(timestamp_raw="26/08/01,00:00", temperature_raw="N/A")
        assert parse_reading(raw) is None

    def test_handles_whitespace(self):
        raw = RawReading(timestamp_raw=" 26/08/01,00:00 ", temperature_raw=" 31.5 ")
        result = parse_reading(raw)
        assert result is not None
        assert result.temperature_c == pytest.approx(31.5)


class TestGetStatus:
    def test_below_threshold_is_normal(self):
        assert get_status(30.0) == Status.NORMAL

    def test_above_threshold_is_warning(self):
        assert get_status(999.0) == Status.WARNING

    def test_none_is_no_data(self):
        assert get_status(None) == Status.NO_DATA
