"""SELECT-only reader for the legacy Technician evidence (ADR-032).

Two client tables, read to bootstrap the application-owned assignment store
once and never to authorize anything at request time:

* ``dbo.persons`` joined to ``dbo.roles`` - the Technician identities. ONLY
  ``person_id`` and ``full_name`` are selected; the table also carries contact
  and credential columns that must never enter this application's read model.
* ``dbo.techmician_device_list`` - the legacy (name, UID) snapshot: transitional
  positive evidence, not an authoritative source (forensics: no timestamp, no
  actor, no history, no enforced references).

Every statement is static SQL with no caller-supplied text. This module never
writes: the client SQL Server stays READ_ONLY (ADR-029).
"""
from __future__ import annotations

from dataclasses import dataclass

import pymssql

from repositories.rtl_temperature_repository import (
    ConnectionFactory,
    RTLTemperatureRepositoryError,
    _connect_read_only,
)

_TECHNICIAN_PERSONS_SQL = (
    "SELECT p.person_id, p.full_name FROM dbo.persons p "
    "JOIN dbo.roles r ON r.role_id = p.role_id "
    "WHERE r.role_name = 'Technician' ORDER BY p.person_id"
)
_ALL_PERSON_NAMES_SQL = "SELECT person_id, full_name FROM dbo.persons ORDER BY person_id"
_LEGACY_SQL = "SELECT full_name, device_uid FROM dbo.techmician_device_list ORDER BY id"


@dataclass(frozen=True)
class ClientPerson:
    person_id: int
    full_name: str


@dataclass(frozen=True)
class LegacyAssignmentRow:
    """One row of the legacy snapshot, exactly as stored."""

    full_name: str
    device_uid: int


class RTLAssignmentSourceRepository:
    def __init__(self, connection_factory: ConnectionFactory = _connect_read_only):
        self._connection_factory = connection_factory

    def _read(self, sql: str) -> list:
        connection = cursor = None
        try:
            connection = self._connection_factory()
            cursor = connection.cursor()
            cursor.execute(sql, ())
            return cursor.fetchall()
        except pymssql.Error as exc:
            raise RTLTemperatureRepositoryError("RTL assignment source is unavailable") from exc
        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def get_technician_persons(self) -> list[ClientPerson]:
        return [ClientPerson(int(i), str(n)) for i, n in self._read(_TECHNICIAN_PERSONS_SQL)]

    def get_all_persons(self) -> list[ClientPerson]:
        """Every person (id and name only), to detect a name that is not a Technician."""
        return [ClientPerson(int(i), str(n)) for i, n in self._read(_ALL_PERSON_NAMES_SQL)]

    def get_legacy_assignments(self) -> list[LegacyAssignmentRow]:
        return [LegacyAssignmentRow(str(n), int(u)) for n, u in self._read(_LEGACY_SQL)]
