"""Energy bin selection — duration aware, never finer than the source data."""
from __future__ import annotations

from datetime import timedelta

import pytest

from config.metrics import SOURCE_RESOLUTION_MINUTES
from services.monitoring_service import TARGET_BARS, choose_bin


class TestChooseBin:
    @pytest.mark.parametrize("span,expected", [
        (timedelta(hours=24), timedelta(minutes=30)),
        (timedelta(days=7), timedelta(hours=6)),
        (timedelta(days=30), timedelta(days=1)),
        (timedelta(days=3), timedelta(hours=2)),
        (timedelta(days=90), timedelta(days=7)),
    ])
    def test_span_selects_its_rung(self, span, expected):
        assert choose_bin(span) == expected

    def test_never_finer_than_the_source_resolution(self):
        """A 5-minute bin would draw mostly-empty bars implying measurement we
        do not have."""
        floor = timedelta(minutes=SOURCE_RESOLUTION_MINUTES)
        for hours in (1, 2, 6, 12, 24):
            assert choose_bin(timedelta(hours=hours)) >= floor

    def test_bar_count_stays_within_target(self):
        for days in (1, 2, 3, 7, 14, 30, 60):
            span = timedelta(days=days)
            assert span / choose_bin(span) <= TARGET_BARS + 1

    def test_duration_aware_not_period_named(self):
        """Two custom ranges of different length must not share a bin."""
        assert choose_bin(timedelta(days=3)) != choose_bin(timedelta(days=90))

    def test_absurdly_long_span_uses_the_coarsest_rung(self):
        assert choose_bin(timedelta(days=3650)) == timedelta(days=7)
