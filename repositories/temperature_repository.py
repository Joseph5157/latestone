"""
Temperature repository.

This is the ONLY module allowed to build physical table identifiers or run
SQL against trfr_temperature.*. Everything above this layer (services, UI)
must go through the functions defined here and must never see a physical
table name.

Identifier safety:
- transformer/device are validated against a strict allowlist pattern
  before ever being used to build a table name.
- Only known demo devices are permitted (registry below); this is not a
  general-purpose "any transformer/device" resolver.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text

from config.settings import database
from db.engine import session_scope

# Strict allowlist patterns for dynamic identifier components.
_TRANSFORMER_PATTERN = re.compile(r"^[a-z0-9]{2,10}$")
_DEVICE_PATTERN = re.compile(r"^[0-9]{3,10}$")

# Explicit registry of known demo devices. Production would replace this
# with a metadata table lookup (see PROJECT_CONTEXT.md / ARCHITECTURE.md).
_KNOWN_DEMO_DEVICES: set[tuple[str, str]] = {
    ("aa12", "29017"),
}


class InvalidIdentifierError(ValueError):
    """Raised when a transformer/device identifier fails validation."""


class UnknownDeviceError(ValueError):
    """Raised when a transformer/device pair is not in the demo registry."""


@dataclass(frozen=True)
class RawReading:
    timestamp_raw: str
    temperature_raw: str


def _validate_identifiers(transformer: str, device: str) -> tuple[str, str]:
    transformer = transformer.strip().lower()
    device = device.strip().lower()

    if not _TRANSFORMER_PATTERN.match(transformer):
        raise InvalidIdentifierError(f"Invalid transformer identifier: {transformer!r}")
    if not _DEVICE_PATTERN.match(device):
        raise InvalidIdentifierError(f"Invalid device identifier: {device!r}")
    if (transformer, device) not in _KNOWN_DEMO_DEVICES:
        raise UnknownDeviceError(
            f"Transformer/device pair not recognised in demo registry: "
            f"{transformer}/{device}"
        )
    return transformer, device


def _resolve_table(transformer: str, device: str) -> str:
    """Build the validated, quoted physical table reference.

    Only ever called with already-validated identifiers.
    """
    transformer, device = _validate_identifiers(transformer, device)
    table_name = f"{transformer}_{device}"
    schema = database.schema
    return f'{schema}."{table_name}"'


def get_readings_between(
    transformer: str, device: str, start: datetime, end: datetime
) -> list[RawReading]:
    """Return raw (unparsed) readings between two datetimes, oldest first.

    Parsing of the varchar timestamp/temperature fields happens in the
    service layer, not here - the repository's job is safe data access,
    not domain conversion.
    """
    table = _resolve_table(transformer, device)

    # NOTE: timestamp is stored as varchar (YY/MM/DD,HH:MM), so range
    # filtering happens in Python after fetch rather than in SQL, to avoid
    # relying on lexical string ordering matching chronological order
    # across year boundaries. For the demo's fixed format the two orders
    # coincide, but we keep filtering explicit and testable in Python.
    with session_scope() as session:
        rows = session.execute(
            text(f'SELECT "timestamp", temperature FROM {table} ORDER BY "timestamp" ASC')
        ).all()

    return [RawReading(timestamp_raw=r[0], temperature_raw=r[1]) for r in rows]


def get_all_readings(transformer: str, device: str) -> list[RawReading]:
    """Return every stored reading, oldest first."""
    table = _resolve_table(transformer, device)
    with session_scope() as session:
        rows = session.execute(
            text(f'SELECT "timestamp", temperature FROM {table} ORDER BY "timestamp" ASC')
        ).all()
    return [RawReading(timestamp_raw=r[0], temperature_raw=r[1]) for r in rows]


def get_recent_readings(transformer: str, device: str, limit: int = 50) -> list[RawReading]:
    """Return the most recent N readings, newest first."""
    table = _resolve_table(transformer, device)
    with session_scope() as session:
        rows = session.execute(
            text(
                f'SELECT "timestamp", temperature FROM {table} '
                f'ORDER BY "timestamp" DESC LIMIT :limit'
            ),
            {"limit": limit},
        ).all()
    return [RawReading(timestamp_raw=r[0], temperature_raw=r[1]) for r in rows]


def get_latest_reading(transformer: str, device: str) -> RawReading | None:
    table = _resolve_table(transformer, device)
    with session_scope() as session:
        row = session.execute(
            text(f'SELECT "timestamp", temperature FROM {table} ORDER BY "timestamp" DESC LIMIT 1')
        ).first()
    return RawReading(timestamp_raw=row[0], temperature_raw=row[1]) if row else None
