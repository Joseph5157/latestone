"""Unit tests for the isolated, read-only RTL temperature repository."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pymssql
import pytest

from repositories.rtl_temperature_repository import (
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
)


@pytest.mark.rtl_db
def test_local_rtl_reader_returns_raw_latest_and_bounded_history():
    """Read real source facts only; the test performs no database writes."""
    repository = RTLTemperatureRepository()
    latest = repository.get_latest_temperature(29743)

    assert latest is not None
    assert latest.device_uid == 29743
    assert latest.reading_time is not None
    start = latest.reading_time - timedelta(days=1)
    readings = repository.get_temperature_range(29743, start, latest.reading_time)

    assert readings
    assert all(reading.device_uid == 29743 for reading in readings)
    assert all(reading.reading_time is not None for reading in readings)
    assert [reading.reading_time for reading in readings] == sorted(
        reading.reading_time for reading in readings
    )


def _repository(*, one=None, many=None, execute_error=None):
    cursor = Mock()
    cursor.fetchone.return_value = one
    cursor.fetchall.return_value = many or []
    if execute_error is not None:
        cursor.execute.side_effect = execute_error
    connection = Mock()
    connection.cursor.return_value = cursor
    return RTLTemperatureRepository(lambda: connection), cursor, connection


def test_latest_temperature_uses_parameterized_uid_and_returns_raw_row():
    row = (29017, datetime(2026, 9, 17, 8, 29), Decimal("37.50"))
    repository, cursor, connection = _repository(one=row)

    result = repository.get_latest_temperature(29017)

    assert result is not None
    assert result.device_uid == 29017
    assert result.reading_time == row[1]
    assert result.temperature == Decimal("37.50")
    sql, (uid,) = cursor.execute.call_args.args
    assert "device_uid = %s" in sql
    assert uid == 29017
    assert "29017" not in sql
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


def test_latest_temperature_returns_none_for_unknown_or_no_reading_uid():
    repository, cursor, _ = _repository(one=None)

    assert repository.get_latest_temperature(999999) is None
    assert "reading_timestamp IS NOT NULL" in cursor.execute.call_args.args[0]


def test_range_returns_deterministically_ordered_raw_rows_without_deduplication():
    start = datetime(2026, 9, 17, 7, 0)
    end = datetime(2026, 9, 17, 8, 0)
    rows = [
        (29017, start, Decimal("30.00")),
        (29017, start, Decimal("30.00")),
        (29017, end, Decimal("31.00")),
    ]
    repository, cursor, _ = _repository(many=rows)

    result = repository.get_temperature_range(29017, start, end)

    assert len(result) == 3
    assert [r.reading_time for r in result] == [start, start, end]
    assert [r.temperature for r in result] == [Decimal("30.00"), Decimal("30.00"), Decimal("31.00")]
    sql, (uid, actual_start, actual_end) = cursor.execute.call_args.args
    assert "device_uid = %s" in sql and "reading_timestamp >= %s" in sql
    assert "ORDER BY reading_timestamp ASC, temperature ASC" in sql
    assert (uid, actual_start, actual_end) == (29017, start, end)


def test_range_returns_empty_list_when_no_readings_match():
    repository, _, _ = _repository(many=[])

    assert repository.get_temperature_range(999999, datetime(2026, 1, 1), datetime(2026, 1, 2)) == []


def test_range_rejects_invalid_time_order_before_opening_connection():
    factory = Mock()
    repository = RTLTemperatureRepository(factory)

    with pytest.raises(ValueError, match="start_time"):
        repository.get_temperature_range(29017, datetime(2026, 1, 2), datetime(2026, 1, 1))

    factory.assert_not_called()


def test_database_error_is_safe_and_connection_is_closed():
    repository, cursor, connection = _repository(execute_error=pymssql.Error("network unavailable"))

    with pytest.raises(RTLTemperatureRepositoryError, match="unavailable"):
        repository.get_latest_temperature(29017)

    cursor.close.assert_called_once()
    connection.close.assert_called_once()
