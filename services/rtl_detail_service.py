"""One registered client RTL, as facts (RTL-UID-DETAIL-01).

The detail counterpart to ``rtl_fleet_service``. Composes, from the read-only
client RTL SQL Server only:

* registration — a ``dbo.device_list`` row is what makes this page exist;
* latest temperature and its source timestamp from ``dbo.master_temperature``,
  via ``rtl_source_facts_service.get_device_facts`` so the ambiguity rule is
  inherited rather than re-implemented;
* the current network context (transformer, hierarchy, source disagreement)
  from ``rtl_network_service`` - ADR-031's rule, consumed and never re-derived
  here (RTL-NETWORK-USE-01);
* a bounded temperature history window for one UID.

**Registration is the gate.** A numeric UID in a URL is not enough: 81
telemetry UIDs and 88 historical-only UIDs are absent from ``device_list``, and
absence is not retirement (knowledge base sections 4-6). An unregistered UID
yields ``NOT_REGISTERED`` and *no source facts at all* — the registration check
runs first, so a probe never reaches a temperature read.

Deliberately absent, and not an oversight: Online/Offline, Active/Inactive,
Healthy, any lifecycle or communication state, ``device_status.last_status``,
``comms_alarm``, ``vw_installed_rtls``, the seven electrical metrics, every
PostgreSQL path, and any fallback when the source is unavailable. Temperature
is the only confirmed continuous telemetry in this database.

Timestamps stay naive source-clock values (SAST, ADR-029) and are never
converted — including the history window bounds, which is why the window is
anchored to the RTL's own last reading rather than to wall-clock now (ADR-030).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from config.settings import RTLDatabaseConfigurationError
from repositories.rtl_temperature_repository import (
    RTLTemperatureReading,
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
)
from services import rtl_network_service as network
from services import rtl_source_facts_service as facts
from services.rtl_fleet_service import (
    HierarchyContext,
    HierarchyState,
    TemperatureState,
)

logger = logging.getLogger(__name__)

_SOURCE_UID_MIN, _SOURCE_UID_MAX = 1, 2_147_483_647


class DetailStatus(str, Enum):
    DATA = "data"
    NOT_REGISTERED = "not_registered"  # no device_list row; nothing is exposed
    UNAVAILABLE = "unavailable"  # source unreachable; deliberately NOT "missing"


class HistoryStatus(str, Enum):
    DATA = "data"
    NO_DATA = "no_data"  # the window is real and genuinely contains no readings
    NOT_REGISTERED = "not_registered"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class HistoryWindow:
    """A selectable history span. ``key`` is what a URL or control carries."""

    key: str
    label: str
    span: timedelta


#: The three established windows. No fourth is invented here, and there is no
#: "all time": an unbounded read of ``master_temperature`` (2.4M rows, no index
#: we may add) is exactly the full-table fetch the gate forbids.
HISTORY_WINDOWS: tuple[HistoryWindow, ...] = (
    HistoryWindow("24h", "24 hours", timedelta(hours=24)),
    HistoryWindow("7d", "7 days", timedelta(days=7)),
    HistoryWindow("30d", "30 days", timedelta(days=30)),
)

DEFAULT_WINDOW_KEY = "24h"

_WINDOWS_BY_KEY = {w.key: w for w in HISTORY_WINDOWS}


def window_for(key: str | None) -> HistoryWindow | None:
    """The window this key names, or None. An unknown key is never guessed."""
    return _WINDOWS_BY_KEY.get(key) if isinstance(key, str) else None


@dataclass(frozen=True)
class RTLDetail:
    """One registered client RTL. Field names carry no state it cannot prove.

    There is no ``status``, ``online``, ``active`` or ``healthy`` field, and
    none of the seven unsupported metrics — not because they are hidden, but
    because this database contains no source for them.
    """

    device_uid: int
    temperature_state: TemperatureState
    temperature: Decimal | None  # None unless state is VALUE
    ambiguous_values: tuple[Decimal, ...]  # preserved source values when AMBIGUOUS
    last_reported: datetime | None  # latest master_temperature time, naive SAST
    transformer_codes: tuple[str, ...]  # raw trfr_list values; empty when unmapped
    hierarchy_state: HierarchyState
    hierarchy: HierarchyContext | None
    #: Supporting sources whose latest transformer code differs from the
    #: current mapping (ADR-031). Informational: the mapping stays the display.
    disagreements: tuple[network.SourceDisagreement, ...] = ()
    provenance: facts.FactSource = facts.FactSource.CLIENT_RTL_SQLSERVER

    @property
    def has_transformer_mapping(self) -> bool:
        return bool(self.transformer_codes)


@dataclass(frozen=True)
class RTLDetailResult:
    status: DetailStatus
    device_uid: int | None = None
    rtl: RTLDetail | None = None  # None unless status is DATA


@dataclass(frozen=True)
class RTLHistory:
    status: HistoryStatus
    device_uid: int | None = None
    window_key: str | None = None
    window_label: str | None = None
    window_start: datetime | None = None  # naive source clock
    window_end: datetime | None = None  # naive source clock; the last reading
    readings: tuple[RTLTemperatureReading, ...] = ()
    provenance: facts.FactSource = facts.FactSource.CLIENT_RTL_SQLSERVER


def _is_source_uid(value: object) -> bool:
    """A plain in-range integer. `True` is not 1 here."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and _SOURCE_UID_MIN <= value <= _SOURCE_UID_MAX
    )


def _repo(repository: RTLTemperatureRepository | None) -> RTLTemperatureRepository:
    return repository if repository is not None else RTLTemperatureRepository()


def get_rtl_detail(
    device_uid: int, repository: RTLTemperatureRepository | None = None
) -> RTLDetailResult:
    """Facts for one registered client RTL UID, or an explicit refusal.

    Order matters: registration is resolved first and a UID absent from
    ``device_list`` returns immediately, so an unregistered UID never causes a
    temperature, mapping or hierarchy read. That is what stops this route being
    an existence oracle for the 81 telemetry-only and 88 historical-only UIDs.
    """
    if not _is_source_uid(device_uid):
        return RTLDetailResult(DetailStatus.NOT_REGISTERED)

    repo = _repo(repository)
    try:
        registered = set(repo.get_registered_device_uids())
        if device_uid not in registered:
            return RTLDetailResult(DetailStatus.NOT_REGISTERED, device_uid)

        latest = repo.get_latest_temperatures([device_uid]).get(device_uid)
        net_status, net_row = network.get_network_row(device_uid, repo)
        if net_row is None:
            if net_status is network.NetworkStatus.DATA:
                return RTLDetailResult(DetailStatus.NOT_REGISTERED, device_uid)
            return RTLDetailResult(DetailStatus.UNAVAILABLE, device_uid)
    except (RTLTemperatureRepositoryError, RTLDatabaseConfigurationError) as exc:
        # Operation and exception class only: never SQL, credentials or rows.
        logger.warning("RTL detail unavailable (%s)", type(exc).__name__)
        return RTLDetailResult(DetailStatus.UNAVAILABLE, device_uid)

    if latest is None or latest.reading_time is None:
        state, value, tied, when = TemperatureState.NO_DATA, None, (), None
    elif latest.has_latest_ambiguity:
        state, value = TemperatureState.AMBIGUOUS, None
        tied, when = latest.tied_source_temperatures, latest.reading_time
    else:
        state, value = TemperatureState.VALUE, latest.temperature
        tied, when = (), latest.reading_time

    return RTLDetailResult(
        DetailStatus.DATA,
        device_uid,
        RTLDetail(
            device_uid=device_uid,
            temperature_state=state,
            temperature=value,
            ambiguous_values=tied,
            last_reported=when,
            transformer_codes=net_row.mapping_codes,
            hierarchy_state=net_row.hierarchy_state,
            hierarchy=net_row.hierarchy,
            disagreements=net_row.disagreements,
        ),
    )


def get_temperature_history(
    device_uid: int,
    window_key: str | None = DEFAULT_WINDOW_KEY,
    repository: RTLTemperatureRepository | None = None,
) -> RTLHistory:
    """A bounded temperature history window for one registered RTL.

    ADR-030: the window ends at this RTL's own latest source reading, not at
    wall-clock now. Client telemetry stops well before the present and many
    registered RTLs last reported years ago, so a "last 24 hours" measured
    from today is empty for effectively the whole fleet — technically true and
    completely uninformative. Anchoring to the last reading keeps both window
    bounds as source-clock values, so the range needs no timezone conversion
    and the exact span is stated on screen.

    Re-checks registration for the same reason ``get_rtl_detail`` does: a
    callback must not become a second, unguarded way into the source.
    """
    window = window_for(window_key)
    if window is None or not _is_source_uid(device_uid):
        return RTLHistory(HistoryStatus.NO_DATA, window_key=window_key)

    repo = _repo(repository)
    try:
        if device_uid not in set(repo.get_registered_device_uids()):
            return RTLHistory(
                HistoryStatus.NOT_REGISTERED, device_uid, window.key, window.label
            )
        latest = repo.get_latest_temperatures([device_uid]).get(device_uid)
        if latest is None or latest.reading_time is None:
            # No anchor exists, so no window does either. Stated as no data
            # rather than silently showing an arbitrary range around today.
            return RTLHistory(HistoryStatus.NO_DATA, device_uid, window.key, window.label)
        end = latest.reading_time
        start = end - window.span
        readings = tuple(repo.get_temperature_range(device_uid, start, end))
    except (RTLTemperatureRepositoryError, RTLDatabaseConfigurationError) as exc:
        logger.warning("RTL history unavailable (%s)", type(exc).__name__)
        return RTLHistory(HistoryStatus.UNAVAILABLE, device_uid, window.key, window.label)

    return RTLHistory(
        HistoryStatus.DATA if readings else HistoryStatus.NO_DATA,
        device_uid,
        window.key,
        window.label,
        start,
        end,
        readings,
    )
