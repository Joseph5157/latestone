"""Unit tests for repository identifier validation (no database required)."""
from __future__ import annotations

import pytest

from repositories.temperature_repository import (
    InvalidIdentifierError,
    UnknownDeviceError,
    _resolve_table,
    _validate_identifiers,
)


class TestValidateIdentifiers:
    def test_accepts_known_demo_pair(self):
        transformer, device = _validate_identifiers("aa12", "29017")
        assert transformer == "aa12"
        assert device == "29017"

    def test_normalises_case_and_whitespace(self):
        transformer, device = _validate_identifiers(" AA12 ", " 29017 ")
        assert transformer == "aa12"
        assert device == "29017"

    def test_rejects_invalid_transformer_pattern(self):
        with pytest.raises(InvalidIdentifierError):
            _validate_identifiers("aa12; DROP TABLE x;--", "29017")

    def test_rejects_invalid_device_pattern(self):
        with pytest.raises(InvalidIdentifierError):
            _validate_identifiers("aa12", "not-a-number")

    def test_rejects_unknown_but_well_formed_pair(self):
        with pytest.raises(UnknownDeviceError):
            _validate_identifiers("zz99", "12345")


class TestResolveTable:
    def test_builds_expected_qualified_name(self):
        table = _resolve_table("aa12", "29017")
        assert table == 'trfr_temperature."aa12_29017"'

    def test_rejects_injection_attempt(self):
        with pytest.raises(InvalidIdentifierError):
            _resolve_table('aa12" ; DROP TABLE users; --', "29017")
