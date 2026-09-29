"""Application-facing RTL source facts, without business meaning.

This is a DATA ACCESS FOUNDATION over ``RTLTemperatureRepository``. It reports
what the client RTL SQL Server proves and nothing more:

* ``registered_in_device_list`` means only "a row exists in device_list".
* ``has_temperature_telemetry`` means only "a master_temperature row exists".
* ``has_transformer_mapping`` / ``transformer_mapping_values`` are raw
  ``trfr_list`` rows, not an authoritative transformer assignment.

It deliberately does not decide fleet membership, online/offline/active state,
timezone, or temperature validity. Every multi-device operation takes an
explicit UID population (or exposes one factual source population). It is NOT
an authorization layer: raw RTL UID availability never implies a user may view
that device, and no callback, route or component may hand it browser input.
Timestamps stay naive source-clock values.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from repositories.rtl_temperature_repository import (
    RTLLatestTemperature,
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
    normalise_device_uids,
)

logger = logging.getLogger(__name__)


class FactSource(str, Enum):
    """Where a fact came from (client RTL facts are always tagged as such)."""

    CLIENT_RTL_SQLSERVER = "client_rtl_sqlserver"


class FactsStatus(str, Enum):
    """Application-level outcome of an RTL facts request."""

    DATA = "data"  # available; every requested UID has a latest reading
    PARTIAL = "partial"  # available; some requested UIDs have no reading
    NO_DATA = "no_data"  # available; no requested UID has a reading (or none requested)
    UNAVAILABLE = "unavailable"  # RTL query/connection failed; nothing synthesised


@dataclass(frozen=True)
class RTLSourcePopulations:
    """The three factual source UID sets, separately, with no 'fleet' chosen."""

    registered: frozenset[int]
    telemetry: frozenset[int]
    mapped: frozenset[int]
    provenance: FactSource = FactSource.CLIENT_RTL_SQLSERVER


@dataclass(frozen=True)
class RTLSourcePopulationsResult:
    status: FactsStatus
    populations: RTLSourcePopulations | None = None
    provenance: FactSource = FactSource.CLIENT_RTL_SQLSERVER


@dataclass(frozen=True)
class RTLLatestTemperaturesResult:
    status: FactsStatus
    requested_uids: tuple[int, ...] = ()
    latest_by_uid: dict[int, RTLLatestTemperature] = field(default_factory=dict)
    uids_without_reading: tuple[int, ...] = ()
    provenance: FactSource = FactSource.CLIENT_RTL_SQLSERVER


@dataclass(frozen=True)
class RTLDeviceFacts:
    """Factual RTL record for one explicitly requested UID."""

    device_uid: int
    registered_in_device_list: bool
    has_temperature_telemetry: bool
    has_transformer_mapping: bool
    transformer_mapping_values: tuple[str, ...] = ()  # raw ``trfr`` values
    latest_temperature: RTLLatestTemperature | None = None  # source clock, unconverted
    provenance: FactSource = FactSource.CLIENT_RTL_SQLSERVER


@dataclass(frozen=True)
class RTLDeviceFactsResult:
    status: FactsStatus
    facts: tuple[RTLDeviceFacts, ...] = ()  # ascending UID; empty when unavailable
    provenance: FactSource = FactSource.CLIENT_RTL_SQLSERVER


def _repo(repository: RTLTemperatureRepository | None) -> RTLTemperatureRepository:
    return repository if repository is not None else RTLTemperatureRepository()


def _log_unavailable(operation: str, exc: Exception) -> None:
    # Only the operation and exception class: never SQL, credentials, or rows.
    logger.warning("RTL source facts unavailable during %s (%s)", operation, type(exc).__name__)


def _latest_status(requested: int, found: int) -> FactsStatus:
    if found == 0:
        return FactsStatus.NO_DATA
    return FactsStatus.DATA if found == requested else FactsStatus.PARTIAL


def get_source_populations(
    repository: RTLTemperatureRepository | None = None,
) -> RTLSourcePopulationsResult:
    """Return registered / telemetry / mapped UID sets as separate populations.

    The telemetry population is a full source heap scan; use ``get_device_facts``
    with an explicit population when only a subset is needed.
    """
    repo = _repo(repository)
    try:
        populations = RTLSourcePopulations(
            registered=frozenset(repo.get_registered_device_uids()),
            telemetry=frozenset(repo.get_telemetry_device_uids()),
            mapped=frozenset(repo.get_mapped_device_uids()),
        )
    except RTLTemperatureRepositoryError as exc:
        _log_unavailable("source populations", exc)
        return RTLSourcePopulationsResult(FactsStatus.UNAVAILABLE)
    return RTLSourcePopulationsResult(FactsStatus.DATA, populations)


def get_latest_temperatures(
    device_uids: Iterable[int],
    repository: RTLTemperatureRepository | None = None,
) -> RTLLatestTemperaturesResult:
    """Latest raw temperature per explicitly supplied UID (set-based)."""
    requested = tuple(normalise_device_uids(device_uids))
    if not requested:
        return RTLLatestTemperaturesResult(FactsStatus.NO_DATA)
    try:
        latest = _repo(repository).get_latest_temperatures(requested)
    except RTLTemperatureRepositoryError as exc:
        _log_unavailable("latest temperatures", exc)
        return RTLLatestTemperaturesResult(FactsStatus.UNAVAILABLE, requested)
    missing = tuple(uid for uid in requested if uid not in latest)
    return RTLLatestTemperaturesResult(
        _latest_status(len(requested), len(latest)), requested, latest, missing
    )


def get_device_facts(
    device_uids: Iterable[int],
    repository: RTLTemperatureRepository | None = None,
) -> RTLDeviceFactsResult:
    """Factual RTL records for an explicit UID population, in ascending UID order.

    A UID unknown to every source table still yields a record with all flags
    False: the caller supplied the population, this only reports what exists.
    """
    requested = tuple(normalise_device_uids(device_uids))
    if not requested:
        return RTLDeviceFactsResult(FactsStatus.NO_DATA)
    repo = _repo(repository)
    try:
        registered = set(repo.get_registered_device_uids())
        telemetry = set(repo.get_telemetry_device_uids(requested))
        mappings = repo.get_transformer_mappings()
        latest = repo.get_latest_temperatures(requested)
    except RTLTemperatureRepositoryError as exc:
        _log_unavailable("device facts", exc)
        return RTLDeviceFactsResult(FactsStatus.UNAVAILABLE)
    mapping_values: dict[int, list[str]] = {}
    for mapping in mappings:
        mapping_values.setdefault(mapping.device_uid, []).append(mapping.transformer_code)
    facts = tuple(
        RTLDeviceFacts(
            device_uid=uid,
            registered_in_device_list=uid in registered,
            has_temperature_telemetry=uid in telemetry,
            has_transformer_mapping=uid in mapping_values,
            transformer_mapping_values=tuple(sorted(mapping_values.get(uid, ()))),
            latest_temperature=latest.get(uid),
        )
        for uid in requested
    )
    return RTLDeviceFactsResult(_latest_status(len(requested), len(latest)), facts)
