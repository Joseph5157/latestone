"""SELECT-only reader for the client's historical RTL event logs (HISTORICAL-EVENTS-01).

Four verified sources, one per event class (knowledge base section 17):

* High Temperature - ``dbo.alarm_log`` (``event_timestamp``, ``temperature``)
* Sensor Error     - ``dbo.sensor_error_log`` (``reading_timestamp``, ``temperature``)
* Battery Low      - ``dbo.startup_msg_log`` where ``status = 'Battery Low'``
* Powerdown        - ``dbo.powerdown_log`` (``event_timestamp``)

There is no unified alarm table and no acknowledgement or resolution column
in any of them, so none is modelled. Every statement is static SQL with bound
parameters, a bounded time range and a page limit: the corpus is never read
whole. The type filter only selects which fixed fragments are joined; no
caller text is ever placed in SQL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import pymssql

from repositories.rtl_temperature_repository import (
    ConnectionFactory,
    RTLTemperatureRepositoryError,
    _connect_read_only,
)

#: (type key, fixed SELECT). Value column is the source's own recorded number:
#: temperature for the first two, battery voltage for the last two.
_SOURCES: dict[str, str] = {
    "high_temperature": (
        "SELECT 'high_temperature' AS event_type, device_uid, trfr, "
        "event_timestamp AS recorded_at, temperature AS recorded_value "
        "FROM dbo.alarm_log WHERE event_timestamp >= %s AND event_timestamp < %s"
    ),
    "sensor_error": (
        "SELECT 'sensor_error' AS event_type, device_uid, trfr, "
        "reading_timestamp AS recorded_at, temperature AS recorded_value "
        "FROM dbo.sensor_error_log WHERE reading_timestamp >= %s AND reading_timestamp < %s"
    ),
    "battery_low": (
        "SELECT 'battery_low' AS event_type, device_uid, trfr, "
        "event_timestamp AS recorded_at, battery_voltage AS recorded_value "
        "FROM dbo.startup_msg_log WHERE status = 'Battery Low' "
        "AND event_timestamp >= %s AND event_timestamp < %s"
    ),
    "powerdown": (
        "SELECT 'powerdown' AS event_type, device_uid, trfr, "
        "event_timestamp AS recorded_at, battery_voltage AS recorded_value "
        "FROM dbo.powerdown_log WHERE event_timestamp >= %s AND event_timestamp < %s"
    ),
}
_UID_FILTER = " AND device_uid = %s"

_LATEST_SQL = (
    "SELECT MAX(t) FROM ("
    "SELECT MAX(event_timestamp) AS t FROM dbo.alarm_log "
    "UNION ALL SELECT MAX(reading_timestamp) FROM dbo.sensor_error_log "
    "UNION ALL SELECT MAX(event_timestamp) FROM dbo.startup_msg_log WHERE status = 'Battery Low' "
    "UNION ALL SELECT MAX(event_timestamp) FROM dbo.powerdown_log) AS m"
)


@dataclass(frozen=True)
class RTLEventRow:
    """One recorded event exactly as the source holds it."""

    event_type: str
    device_uid: int
    transformer_code: str | None  # ``trfr`` recorded with the event itself
    recorded_at: datetime  # naive source clock (SAST, ADR-029)
    recorded_value: Decimal | None


def _text_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _selected(types) -> list[str]:
    return [t for t in _SOURCES if t in set(types)]


def _union(types: list[str], with_uid: bool) -> str:
    suffix = _UID_FILTER if with_uid else ""
    return " UNION ALL ".join(_SOURCES[t] + suffix for t in types)


def _params(types: list[str], start: datetime, end: datetime, uid: int | None) -> tuple:
    one = (start, end) + ((uid,) if uid is not None else ())
    return one * len(types)


class RTLEventsRepository:
    def __init__(self, connection_factory: ConnectionFactory = _connect_read_only):
        self._connection_factory = connection_factory

    def _read(self, sql: str, parameters: tuple):
        connection = cursor = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(sql, parameters)
            return cursor.fetchall()
        except pymssql.Error as exc:
            raise RTLTemperatureRepositoryError("RTL event source is unavailable") from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def get_latest_event_time(self) -> datetime | None:
        """The newest recorded event time across the four sources."""
        rows = self._read(_LATEST_SQL, ())
        return rows[0][0] if rows and rows[0][0] is not None else None

    def count_events(self, start: datetime, end: datetime, uid: int | None = None) -> dict[str, int]:
        """Events per class in ``[start, end)``, optionally for one UID."""
        types = list(_SOURCES)
        sql = (f"SELECT event_type, COUNT_BIG(*) FROM ({_union(types, uid is not None)}) AS e "
               "GROUP BY event_type")
        counts = {t: 0 for t in types}
        for event_type, n in self._read(sql, _params(types, start, end, uid)):
            counts[str(event_type)] = int(n)
        return counts

    def get_events(self, start: datetime, end: datetime, types, uid: int | None,
                   limit: int, offset: int) -> list[RTLEventRow]:
        """One page of events, newest first; ties break by class then UID."""
        chosen = _selected(types)
        if not chosen:
            return []
        limit, offset = max(1, int(limit)), max(0, int(offset))
        sql = (f"SELECT event_type, device_uid, trfr, recorded_at, recorded_value "
               f"FROM ({_union(chosen, uid is not None)}) AS e "
               "ORDER BY recorded_at DESC, event_type, device_uid "
               "OFFSET %s ROWS FETCH NEXT %s ROWS ONLY")
        params = _params(chosen, start, end, uid) + (offset, limit)
        return [RTLEventRow(str(t), int(u), _text_or_none(code), when, value)
                for t, u, code, when, value in self._read(sql, params)]
