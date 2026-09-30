"""Real Fleet Overview data: the registered client RTL directory, as facts.

SATURDAY-REAL-FLEET-01. Composes, from the read-only client RTL SQL Server
only, one row per RTL in ``dbo.device_list`` (the registered directory, 339
today - NOT "active", "online" or "operational"):

* latest temperature and its timestamp from ``dbo.master_temperature`` via
  ``rtl_source_facts_service.get_latest_temperatures`` (one set-based read;
  ambiguity semantics are inherited, never re-implemented here);
* raw ``dbo.trfr_list`` mapping (a candidate, not an approved authority);
* ``dbo.vw_transformer_org_hierarchy`` context where it exists.

Deliberately absent: Online/Offline or any freshness verdict, the legacy
``vw_installed_rtls`` view and ``device_status`` values, the seven electrical
metrics, PostgreSQL data, and any fallback when the source is unavailable.
Timestamps stay naive source-clock values (SAST, ADR-029) - never converted.
Counts are derived from the source rows, never hard-coded.

Authorization: raw client UIDs have no approved mapping to application
devices or technician assignments, so the real fleet is shown only to roles
whose device scope is unrestricted (``may_view_real_fleet``). Everyone else
gets an explicit "not available" state, never an empty-looking fleet.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from config.settings import RTLDatabaseConfigurationError
from repositories.rtl_temperature_repository import (
    RTLLatestTemperature,
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
    RTLTransformerHierarchy,
)
from services import rtl_source_facts_service as facts
from services.device_scope import DeviceScope

logger = logging.getLogger(__name__)


class TemperatureState(str, Enum):
    VALUE = "value"  # one (or several identical) values at the latest timestamp
    AMBIGUOUS = "ambiguous"  # conflicting values at the latest timestamp
    NO_DATA = "no_data"  # no timestamped reading in master_temperature


class HierarchyState(str, Enum):
    AVAILABLE = "available"  # mapped, and the hierarchy view has a path
    UNAVAILABLE = "unavailable"  # mapped, but no hierarchy path in the source
    NOT_MAPPED = "not_mapped"  # no trfr_list row


class FleetStatus(str, Enum):
    DATA = "data"
    UNAVAILABLE = "unavailable"  # source unreachable/unconfigured; nothing synthesised


@dataclass(frozen=True)
class HierarchyContext:
    operating_unit: str | None
    zone: str | None
    sector: str | None
    cnc: str | None
    feeder: str | None

    @property
    def is_empty(self) -> bool:
        return not any((self.zone, self.sector, self.cnc, self.feeder, self.operating_unit))


@dataclass(frozen=True)
class RTLFleetRow:
    device_uid: int
    temperature_state: TemperatureState
    temperature: Decimal | None  # None unless state is VALUE
    ambiguous_values: tuple[Decimal, ...]  # preserved source values when AMBIGUOUS
    last_reported: datetime | None  # latest master_temperature timestamp, naive SAST
    transformer_codes: tuple[str, ...]  # raw trfr_list values; empty when unmapped
    hierarchy_state: HierarchyState
    hierarchy: HierarchyContext | None

    @property
    def has_transformer_mapping(self) -> bool:
        return bool(self.transformer_codes)


@dataclass(frozen=True)
class FleetSummary:
    registered: int
    mapped: int
    with_temperature: int  # a timestamped latest reading exists (value or ambiguous)
    no_temperature: int
    ambiguous: int
    hierarchy_unavailable: int  # mapped, no hierarchy path

    @property
    def unmapped(self) -> int:
        return self.registered - self.mapped

    @property
    def hierarchy_resolved(self) -> int:
        """Mapped RTLs with a full hierarchy path (mapped states partition)."""
        return self.mapped - self.hierarchy_unavailable


@dataclass(frozen=True)
class RealFleet:
    status: FleetStatus
    rows: tuple[RTLFleetRow, ...] = ()
    summary: FleetSummary | None = None


def may_view_real_fleet(scope: DeviceScope | None) -> bool:
    """Only an unrestricted scope (Administrator, General User) sees the fleet.

    ``None``, a technician's assignment set and the EMPTY scope are refused:
    there is no approved raw-UID-to-assignment map, so nothing is widened.
    """
    return scope is not None and scope.is_unrestricted


def summarise(rows: tuple[RTLFleetRow, ...]) -> FleetSummary:
    return FleetSummary(
        registered=len(rows),
        mapped=sum(r.has_transformer_mapping for r in rows),
        with_temperature=sum(r.temperature_state is not TemperatureState.NO_DATA for r in rows),
        no_temperature=sum(r.temperature_state is TemperatureState.NO_DATA for r in rows),
        ambiguous=sum(r.temperature_state is TemperatureState.AMBIGUOUS for r in rows),
        hierarchy_unavailable=sum(r.hierarchy_state is HierarchyState.UNAVAILABLE for r in rows),
    )


def build_rows(
    registered: list[int],
    latest: dict[int, RTLLatestTemperature],
    mappings: dict[int, tuple[str, ...]],
    hierarchy: dict[int, HierarchyContext],
) -> tuple[RTLFleetRow, ...]:
    """Pure assembly, one row per registered UID in ascending UID order.

    Telemetry-only and historical-only UIDs never appear: only ``registered``
    is iterated. A mapped RTL whose hierarchy row is missing or entirely
    blank is UNAVAILABLE, not guessed.
    """
    rows = []
    for uid in sorted(registered):
        reading = latest.get(uid)
        if reading is None or reading.reading_time is None:
            state, value, tied, when = TemperatureState.NO_DATA, None, (), None
        elif reading.has_latest_ambiguity:
            state, value = TemperatureState.AMBIGUOUS, None
            tied, when = reading.tied_source_temperatures, reading.reading_time
        else:
            state, value, tied, when = TemperatureState.VALUE, reading.temperature, (), reading.reading_time

        codes = mappings.get(uid, ())
        context = hierarchy.get(uid)
        if not codes:
            h_state, context = HierarchyState.NOT_MAPPED, None
        elif context is None or context.is_empty:
            h_state, context = HierarchyState.UNAVAILABLE, None
        else:
            h_state = HierarchyState.AVAILABLE
        rows.append(RTLFleetRow(uid, state, value, tied, when, codes, h_state, context))
    return tuple(rows)


def get_real_fleet(repository: RTLTemperatureRepository | None = None) -> RealFleet:
    """The registered fleet, composed from a fixed number of set-based reads.

    Reads: registered directory, latest temperatures (batched, never per UID),
    transformer mappings, hierarchy view. Any source failure yields
    UNAVAILABLE with no rows.
    """
    repo = repository if repository is not None else RTLTemperatureRepository()
    try:
        registered = repo.get_registered_device_uids()
        latest_result = facts.get_latest_temperatures(registered, repo)
        if latest_result.status is facts.FactsStatus.UNAVAILABLE:
            return RealFleet(FleetStatus.UNAVAILABLE)
        mapping_rows = repo.get_transformer_mappings()
        hierarchy_rows = repo.get_transformer_hierarchy()
    except (RTLTemperatureRepositoryError, RTLDatabaseConfigurationError) as exc:
        # Operation and exception class only: never SQL, credentials or rows.
        logger.warning("Real fleet unavailable (%s)", type(exc).__name__)
        return RealFleet(FleetStatus.UNAVAILABLE)

    mappings: dict[int, list[str]] = {}
    for m in mapping_rows:
        mappings.setdefault(m.device_uid, []).append(m.transformer_code)
    hierarchy = _hierarchy_by_uid(hierarchy_rows, mappings)
    rows = build_rows(
        registered,
        latest_result.latest_by_uid,
        {uid: tuple(sorted(codes)) for uid, codes in mappings.items()},
        hierarchy,
    )
    return RealFleet(FleetStatus.DATA, rows, summarise(rows))


def _hierarchy_by_uid(
    rows: list[RTLTransformerHierarchy], mappings: dict[int, list[str]]
) -> dict[int, HierarchyContext]:
    """Hierarchy only where the view row names the same transformer as trfr_list.

    An exact code match, nothing fuzzy: a mismatch is treated as "no hierarchy".
    """
    by_uid: dict[int, HierarchyContext] = {}
    for row in rows:
        if row.transformer_code not in mappings.get(row.device_uid, ()):
            continue
        by_uid[row.device_uid] = HierarchyContext(
            row.operating_unit, row.zone, row.sector, row.cnc, row.feeder
        )
    return by_uid
