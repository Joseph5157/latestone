"""The one RTL UID format rule (ADR-022), shared by registration and programming."""
from __future__ import annotations

import pytest

from services import rtl_programming_service, rtl_uid
from services.rtl_uid import UID_FORMAT_MESSAGE, UID_REQUIRED_MESSAGE, uid_format_error


class TestUidFormatError:
    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_blank_is_required(self, value):
        assert uid_format_error(value) == UID_REQUIRED_MESSAGE

    @pytest.mark.parametrize("value", ["29017", "10005", "00000", " 29017 "])
    def test_exactly_five_digits_passes(self, value):
        assert uid_format_error(value) is None

    @pytest.mark.parametrize("value", [
        "2901",        # too short
        "290171",      # too long
        "29a17",       # non-digit
        "AB-12",       # the old contract allowed this
        "29 17",       # inner space
        "２９０１７",   # full-width digits are not ASCII digits
    ])
    def test_anything_else_is_a_format_error(self, value):
        assert uid_format_error(value) == UID_FORMAT_MESSAGE

    def test_no_29_prefix_is_required(self):
        """The specification shows `29xxx` as an example, not a rule."""
        assert uid_format_error("40009") is None


class TestSingleSourceOfTheRule:
    def test_programming_uses_the_same_pattern_object(self):
        assert rtl_programming_service.UID_PATTERN is rtl_uid.UID_PATTERN
