"""Narrow, read-only boundary for the final client RTL SQL Server database.

This module intentionally does not import ``db.engine``, SQLAlchemy, Alembic,
or the PostgreSQL repository. It accepts a raw RTL UID and exposes only the
two temperature reads supported by the audited ``dbo.master_temperature``.
No method executes DDL or data modification SQL.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

import pymssql

from config.settings import rtl_database


class RTLTemperatureRepositoryError(RuntimeError):
    """Safe application-facing failure for an unavailable RTL read source."""


class _Cursor(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...]) -> None: ...
    def fetchone(self) -> object | None: ...
    def fetchall(self) -> list[object]: ...
    def close(self) -> None: ...


class _Connection(Protocol):
    def cursor(self) -> _Cursor: ...
    def close(self) -> None: ...


ConnectionFactory = Callable[[], _Connection]


@dataclass(frozen=True)
class RTLTemperatureReading:
    """A raw temperature fact from ``dbo.master_temperature``.

    ``reading_time`` is deliberately a naive ``datetime | None`` because the
    audited SQL Server ``datetime2(7)`` column has no timezone offset. Range
    reads exclude null timestamps because a null cannot satisfy a time range;
    latest reads exclude them because a latest instant cannot be determined.
    No value filtering, timezone conversion, deduplication, UID mapping, or
    hierarchy mapping occurs here.
    """

    device_uid: int
    reading_time: datetime | None
    temperature: Decimal


@dataclass(frozen=True)
class RTLRegisteredDevice:
    """A registered RTL UID from ``dbo.device_list``.

    The source table also carries a cellular contact field. It is deliberately
    outside this read model: it is not required to identify a registered RTL
    and should not travel into application/UI data accidentally.
    """

    device_uid: int


@dataclass(frozen=True)
class RTLTransformerMapping:
    """An observed UID-to-transformer-code row from ``dbo.trfr_list``.

    This preserves a source fact only. It does not claim that the mapping is
    complete, authoritative, or a canonical application hierarchy.
    """

    device_uid: int
    transformer_code: str


_LATEST_SQL = """
SELECT TOP (1) device_uid, reading_timestamp, temperature
FROM dbo.master_temperature
WHERE device_uid = %s
  AND reading_timestamp IS NOT NULL
ORDER BY reading_timestamp DESC, temperature DESC
"""

_RANGE_SQL = """
SELECT device_uid, reading_timestamp, temperature
FROM dbo.master_temperature
WHERE device_uid = %s
  AND reading_timestamp >= %s
  AND reading_timestamp <= %s
ORDER BY reading_timestamp ASC, temperature ASC
"""

_REGISTERED_DEVICES_SQL = """
SELECT device_uid
FROM dbo.device_list
ORDER BY device_uid ASC
"""

_TRANSFORMER_MAPPINGS_SQL = """
SELECT device_uid, trfr
FROM dbo.trfr_list
ORDER BY device_uid ASC, trfr ASC, id ASC
"""


def _connect_read_only() -> _Connection:
    """Open an autocommit connection used exclusively for SELECT statements."""
    rtl_database.require_complete()
    return pymssql.connect(
        server=rtl_database.host,
        port=rtl_database.port,
        user=rtl_database.user,
        password=rtl_database.password,
        database=rtl_database.name,
        login_timeout=5,
        timeout=30,
        autocommit=True,
    )


def _as_reading(row: object) -> RTLTemperatureReading:
    """Turn the three selected columns into the deliberately small contract."""
    device_uid, reading_time, temperature = row  # pymssql rows support unpacking
    return RTLTemperatureReading(
        device_uid=int(device_uid),
        reading_time=reading_time,
        temperature=temperature,
    )


class RTLTemperatureRepository:
    """Parameterized, SELECT-only reader for real RTL temperature facts.

    Ordering is deterministic for all observable contract fields: latest is
    newest time then highest temperature; ranges are ascending time then
    temperature. Exact duplicate rows remain represented individually in
    ranges. When equal rows have all three contract fields equal, their order
    is immaterial because the records are indistinguishable by this contract.
    """

    def __init__(self, connection_factory: ConnectionFactory = _connect_read_only):
        self._connection_factory = connection_factory

    def get_latest_temperature(self, device_uid: int) -> RTLTemperatureReading | None:
        """Return the latest timestamped raw temperature for one UID, if any."""
        return self._fetch_one(_LATEST_SQL, (device_uid,))

    def get_registered_devices(self) -> list[RTLRegisteredDevice]:
        """Return the source registered-UID directory in deterministic order."""
        return self._fetch_registered_devices(_REGISTERED_DEVICES_SQL, ())

    def get_transformer_mappings(self) -> list[RTLTransformerMapping]:
        """Return observed source UID-to-transformer-code rows, not an authority claim."""
        return self._fetch_transformer_mappings(_TRANSFORMER_MAPPINGS_SQL, ())

    def get_temperature_range(
        self,
        device_uid: int,
        start_time: datetime,
        end_time: datetime,
    ) -> list[RTLTemperatureReading]:
        """Return raw, timestamped readings in the inclusive requested range."""
        if start_time > end_time:
            raise ValueError("start_time must be less than or equal to end_time")
        return self._fetch_all(_RANGE_SQL, (device_uid, start_time, end_time))

    def _fetch_one(
        self, sql: str, parameters: tuple[object, ...]
    ) -> RTLTemperatureReading | None:
        connection: _Connection | None = None
        cursor: _Cursor | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(sql, parameters)
            row = cursor.fetchone()
            return _as_reading(row) if row is not None else None
        except pymssql.Error as exc:
            raise RTLTemperatureRepositoryError("RTL temperature source is unavailable") from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _fetch_all(
        self, sql: str, parameters: tuple[object, ...]
    ) -> list[RTLTemperatureReading]:
        connection: _Connection | None = None
        cursor: _Cursor | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(sql, parameters)
            rows = cursor.fetchall()
            return [_as_reading(row) for row in rows]
        except pymssql.Error as exc:
            raise RTLTemperatureRepositoryError("RTL temperature source is unavailable") from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _fetch_registered_devices(
        self, sql: str, parameters: tuple[object, ...]
    ) -> list[RTLRegisteredDevice]:
        connection: _Connection | None = None
        cursor: _Cursor | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(sql, parameters)
            return [RTLRegisteredDevice(device_uid=int(device_uid)) for (device_uid,) in cursor.fetchall()]
        except pymssql.Error as exc:
            raise RTLTemperatureRepositoryError("RTL temperature source is unavailable") from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def _fetch_transformer_mappings(
        self, sql: str, parameters: tuple[object, ...]
    ) -> list[RTLTransformerMapping]:
        connection: _Connection | None = None
        cursor: _Cursor | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(sql, parameters)
            return [
                RTLTransformerMapping(device_uid=int(device_uid), transformer_code=str(transformer_code))
                for device_uid, transformer_code in cursor.fetchall()
            ]
        except pymssql.Error as exc:
            raise RTLTemperatureRepositoryError("RTL temperature source is unavailable") from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()
