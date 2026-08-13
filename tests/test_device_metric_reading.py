"""Row conversion for `latest_metric_readings`.

Pure tests — the point is the NULL path, which the seeded database cannot
produce (every device there reports every metric) but a real one will the
moment a device is installed and not yet reporting.
"""
from __future__ import annotations

from datetime import datetime, timezone

from repositories.plant_monitoring_repository import (
    DeviceMetricReading,
    _to_device_metric_reading,
)

TS = datetime(2026, 8, 9, 16, 30, tzinfo=timezone.utc)


def _row(reading_ts, value):
    return ("plant-13", "plant-13-t1", "ta01", "plant-13-t1-d1", "29057",
            "temperature", reading_ts, value)


def test_converts_a_reported_reading():
    row = _to_device_metric_reading(_row(TS, 30.147))
    assert isinstance(row, DeviceMetricReading)
    assert row.value == 30.147
    assert row.reading_ts == TS
    assert row.device_code == "29057"
    assert row.transformer_code == "ta01"


def test_a_device_with_no_reading_survives_as_a_null_row():
    """The regression this converter exists for.

    `_to_reading` does an unguarded `float(row[3])`; reusing it here would
    raise TypeError on the NULLs a LEFT JOIN returns for a device that has
    never reported this metric. Dropping such a device instead would be worse
    still — the card would say "hottest of 6" while the plant has 7.
    """
    row = _to_device_metric_reading(_row(None, None))
    assert row.value is None
    assert row.reading_ts is None
    assert row.device_id == "plant-13-t1-d1", "identity must survive the gap"


def test_numeric_values_are_coerced_to_float():
    """PostgreSQL NUMERIC arrives as Decimal; arithmetic downstream assumes float."""
    from decimal import Decimal

    row = _to_device_metric_reading(_row(TS, Decimal("30.147")))
    assert isinstance(row.value, float)
