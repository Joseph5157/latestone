"""Narrow, read-only boundary for the final client RTL SQL Server database.

This module intentionally does not import ``db.engine``, SQLAlchemy, Alembic,
or the PostgreSQL repository. It accepts a raw RTL UID and exposes only the
temperature reads supported by the audited ``dbo.master_temperature`` plus
factual UID/mapping directories. No method executes DDL or data modification SQL.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
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


@dataclass(frozen=True)
class RTLLatestTemperature:
    """The latest raw reading state for one UID from a set-based latest read.

    ``tied_latest_row_count`` is how many source rows share the UID's latest
    timestamp; ``tied_source_temperatures`` holds their distinct values in
    ascending order (ordering only, not a preference).

    * One row, or several rows with the same value: ``temperature`` is that
      common source value and ``has_latest_ambiguity`` is False. Identical
      rows are counted, not cleaned or deduplicated.
    * Several distinct values: the source conflicts about the latest value.
      ``temperature`` is None and ``has_latest_ambiguity`` is True; no value
      is chosen. Which value is correct is an unresolved client decision.
    """

    device_uid: int
    reading_time: datetime | None
    temperature: Decimal | None
    tied_latest_row_count: int = 1
    tied_source_temperatures: tuple[Decimal, ...] = ()

    @property
    def tied_distinct_temperature_count(self) -> int:
        return len(self.tied_source_temperatures)

    @property
    def has_latest_ambiguity(self) -> bool:
        return self.tied_distinct_temperature_count > 1


# Practical query-size limit: one VALUES constructor takes at most 1000 rows in
# SQL Server, and drivers cap parameters (2100 for native RPC). One parameter
# is bound per UID, so larger requests are split into sequential batches of
# this size on one connection. 400 UIDs (all telemetry UIDs) is a single query.
LATEST_BATCH_SIZE = 500
_SQL_INT_MIN, _SQL_INT_MAX = -(2**31), 2**31 - 1

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

_LATEST_BATCH_SQL = """
WITH requested(device_uid) AS (
    SELECT v.device_uid FROM (VALUES {values}) AS v(device_uid)
),
latest(device_uid, latest_timestamp) AS (
    SELECT t.device_uid, MAX(t.reading_timestamp)
    FROM dbo.master_temperature AS t
    JOIN requested AS r ON r.device_uid = t.device_uid
    WHERE t.reading_timestamp IS NOT NULL
    GROUP BY t.device_uid
)
SELECT t.device_uid, t.reading_timestamp, t.temperature
FROM dbo.master_temperature AS t
JOIN latest AS l
  ON l.device_uid = t.device_uid AND l.latest_timestamp = t.reading_timestamp
ORDER BY t.device_uid ASC, t.temperature DESC
"""

_TELEMETRY_UIDS_SQL = """
SELECT DISTINCT device_uid
FROM dbo.master_temperature
WHERE device_uid IS NOT NULL
ORDER BY device_uid ASC
"""

_TELEMETRY_UIDS_BATCH_SQL = """
SELECT DISTINCT t.device_uid
FROM dbo.master_temperature AS t
JOIN (SELECT v.device_uid FROM (VALUES {values}) AS v(device_uid)) AS r
  ON r.device_uid = t.device_uid
ORDER BY t.device_uid ASC
"""


def normalise_device_uids(device_uids: Iterable[int]) -> list[int]:
    """Validate and return unique UIDs in ascending order (deterministic)."""
    unique: set[int] = set()
    for uid in device_uids:
        if isinstance(uid, bool) or not isinstance(uid, int):
            raise ValueError("device UIDs must be integers")
        if not _SQL_INT_MIN <= uid <= _SQL_INT_MAX:
            raise ValueError("device UID is outside the SQL Server int range")
        unique.add(uid)
    return sorted(unique)


def _batches(uids: list[int]) -> list[list[int]]:
    return [uids[i : i + LATEST_BATCH_SIZE] for i in range(0, len(uids), LATEST_BATCH_SIZE)]


def _values_clause(batch: list[int]) -> str:
    """Placeholders only; UID values are always bound parameters."""
    return ",".join("(%s)" for _ in batch)


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

    def get_registered_device_uids(self) -> list[int]:
        """UIDs with a ``device_list`` row (source registration fact only)."""
        return [device.device_uid for device in self.get_registered_devices()]

    def get_mapped_device_uids(self) -> list[int]:
        """Distinct UIDs with at least one ``trfr_list`` row."""
        return sorted({mapping.device_uid for mapping in self.get_transformer_mappings()})

    def get_telemetry_device_uids(
        self, device_uids: Iterable[int] | None = None
    ) -> list[int]:
        """UIDs with any ``master_temperature`` row, optionally within a request.

        Unrestricted, this is a full heap scan of the source (no index exists
        and none may be added). Prefer passing the UID population of interest.
        """
        if device_uids is None:
            return self._read(lambda cur: self._distinct_uids(cur, _TELEMETRY_UIDS_SQL, ()))
        uids = normalise_device_uids(device_uids)
        if not uids:
            return []

        def run(cursor: _Cursor) -> list[int]:
            found: list[int] = []
            for batch in _batches(uids):
                sql = _TELEMETRY_UIDS_BATCH_SQL.format(values=_values_clause(batch))
                found.extend(self._distinct_uids(cursor, sql, tuple(batch)))
            return sorted(found)

        return self._read(run)

    def get_latest_temperatures(
        self, device_uids: Iterable[int]
    ) -> dict[int, RTLLatestTemperature]:
        """Set-based latest raw reading per requested UID.

        Returns only UIDs that have a timestamped reading; an unknown UID, or
        one with no timestamped reading, is simply absent (no synthetic row).
        Empty input returns ``{}`` without opening a connection. Duplicate
        input UIDs are collapsed. Requests larger than ``LATEST_BATCH_SIZE``
        are split into batches on one connection (one query per batch, never
        one per UID). No filtering, deduplication, timezone conversion, or
        value cleaning occurs; ties on the latest timestamp are reported via
        the ``RTLLatestTemperature.tied_*`` fields.
        """
        uids = normalise_device_uids(device_uids)
        if not uids:
            return {}

        def run(cursor: _Cursor) -> dict[int, RTLLatestTemperature]:
            grouped: dict[int, list[tuple[datetime | None, Decimal]]] = {}
            for batch in _batches(uids):
                sql = _LATEST_BATCH_SQL.format(values=_values_clause(batch))
                cursor.execute(sql, tuple(batch))
                for uid, reading_time, temperature in cursor.fetchall():
                    grouped.setdefault(int(uid), []).append((reading_time, temperature))
            result: dict[int, RTLLatestTemperature] = {}
            for uid in sorted(grouped):
                rows = grouped[uid]
                reading_time = rows[0][0]  # all rows share the latest timestamp
                distinct = tuple(sorted({row[1] for row in rows}))
                result[uid] = RTLLatestTemperature(
                    device_uid=uid,
                    reading_time=reading_time,
                    temperature=distinct[0] if len(distinct) == 1 else None,
                    tied_latest_row_count=len(rows),
                    tied_source_temperatures=distinct,
                )
            return result

        return self._read(run)

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

    @staticmethod
    def _distinct_uids(cursor: _Cursor, sql: str, parameters: tuple[object, ...]) -> list[int]:
        cursor.execute(sql, parameters)
        return [int(uid) for (uid,) in cursor.fetchall()]

    def _read(self, action: Callable[[_Cursor], object]):
        """Run one read on one connection; map driver errors to a safe error."""
        connection: _Connection | None = None
        cursor: _Cursor | None = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            return action(cursor)
        except pymssql.Error as exc:
            raise RTLTemperatureRepositoryError("RTL temperature source is unavailable") from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

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
