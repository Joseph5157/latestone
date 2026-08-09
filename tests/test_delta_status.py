"""Cumulative meter arithmetic. A decrease is never consumption.

The seeded data is monotonic by construction, so every discontinuity here is
synthesised. That is deliberate: this path will never be exercised by our data
and would otherwise ship untested.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.monitoring_service import (
    DeltaResult, DeltaStatus, Reading, period_delta,
)

T0 = datetime(2026, 8, 9, 0, 0, tzinfo=timezone.utc)


def _series(*values):
    return [Reading(T0 + timedelta(minutes=30 * i), v) for i, v in enumerate(values)]


class TestPeriodDelta:
    def test_monotonic_series_is_last_minus_first(self):
        result = period_delta(_series(100.0, 110.0, 125.0))
        assert result == DeltaResult(25.0, DeltaStatus.OK)

    def test_priming_reading_extends_coverage_backwards(self):
        prime = Reading(T0 - timedelta(minutes=30), 90.0)
        result = period_delta(_series(100.0, 110.0), prime=prime)
        assert result.value == 20.0
        assert result.status is DeltaStatus.OK

    def test_a_decrease_is_a_discontinuity_not_a_negative_number(self):
        """A meter reset must never print as negative consumption."""
        result = period_delta(_series(100.0, 110.0, 5.0, 12.0))
        assert result.status is DeltaStatus.DISCONTINUITY
        assert result.value is None

    def test_single_reading_is_insufficient_data(self):
        result = period_delta(_series(100.0))
        assert result.status is DeltaStatus.INSUFFICIENT_DATA
        assert result.value is None

    def test_empty_series_is_insufficient_data(self):
        assert period_delta([]).status is DeltaStatus.INSUFFICIENT_DATA

    def test_insufficient_data_is_distinguishable_from_discontinuity(self):
        """Today both collapse to None, which hides which one happened."""
        assert (
            period_delta(_series(100.0)).status
            is not period_delta(_series(100.0, 50.0)).status
        )

    def test_flat_meter_reports_zero_not_unknown(self):
        result = period_delta(_series(100.0, 100.0))
        assert result == DeltaResult(0.0, DeltaStatus.OK)

    def test_no_correction_rule_is_applied(self):
        """No abs(), no assumed rollover width, no summing positive segments —
        the register width and reset semantics are unknown."""
        result = period_delta(_series(100.0, 5.0))
        assert result.value is None

    def test_is_known_only_when_ok(self):
        assert period_delta(_series(1.0, 2.0)).is_known
        assert not period_delta(_series(2.0, 1.0)).is_known
