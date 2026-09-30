"""Historical Events (HISTORICAL-EVENTS-01).

Normalises the four verified client event logs into one factual record type.
These are *recorded events*, not alarm state: the legacy database has no
acknowledgement, resolution, escalation or severity, so this model has none,
and nothing here says an RTL currently has a problem.

Network context is the RTL's *current* mapping (ADR-031), taken from the
shared ``rtl_network_service`` snapshot - never reconstructed for the time of
the event. The transformer code the event row itself carries is kept apart as
``event_transformer_code``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum

from repositories.rtl_events_repository import RTLEventsRepository
from config.settings import RTLDatabaseConfigurationError
from repositories.rtl_temperature_repository import RTLTemperatureRepositoryError
from services import rtl_network_service as network
from repositories.rtl_temperature_repository import RTLTemperatureRepository
from services.rtl_network_service import CurrentNetworkRow, NetworkStatus, may_view_real_fleet
from services.rtl_scope import RtlScope, UNRESTRICTED

logger = logging.getLogger(__name__)

__all__ = ["EventType", "EventSource", "EventsStatus", "HistoricalEvent", "EventsPage",
           "get_events_page", "default_window", "parse_uid", "may_view_real_fleet",
           "PAGE_SIZE", "DEFAULT_WINDOW_DAYS"]

#: Default window: 30 calendar days ending on the newest recorded event. The
#: window is anchored on the data, not on today's date, because the source can
#: be a restored copy whose newest event is older than today.
DEFAULT_WINDOW_DAYS = 30
PAGE_SIZE = 50
_MAX_UID = 2_147_483_647


class EventType(str, Enum):
    HIGH_TEMPERATURE = "high_temperature"
    SENSOR_ERROR = "sensor_error"
    BATTERY_LOW = "battery_low"
    POWERDOWN = "powerdown"

    @property
    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    EventType.HIGH_TEMPERATURE: "High Temperature",
    EventType.SENSOR_ERROR: "Sensor Error",
    EventType.BATTERY_LOW: "Battery Low",
    EventType.POWERDOWN: "Powerdown",
}


class EventSource(str, Enum):
    """Internal provenance only; the UI shows the event label, not this."""

    ALARM_LOG = "alarm_log"
    SENSOR_ERROR_LOG = "sensor_error_log"
    STARTUP_MSG_LOG = "startup_msg_log"
    POWERDOWN_LOG = "powerdown_log"


SOURCE_BY_TYPE = {
    EventType.HIGH_TEMPERATURE: EventSource.ALARM_LOG,
    EventType.SENSOR_ERROR: EventSource.SENSOR_ERROR_LOG,
    EventType.BATTERY_LOW: EventSource.STARTUP_MSG_LOG,
    EventType.POWERDOWN: EventSource.POWERDOWN_LOG,
}
#: What the recorded number is: the source's own column, uninterpreted.
VALUE_KIND = {
    EventType.HIGH_TEMPERATURE: "temperature",
    EventType.SENSOR_ERROR: "recorded",
    EventType.BATTERY_LOW: "battery_voltage",
    EventType.POWERDOWN: "battery_voltage",
}


class EventsStatus(str, Enum):
    DATA = "data"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


@dataclass(frozen=True)
class HistoricalEvent:
    event_type: EventType
    device_uid: int
    recorded_at: datetime  # naive source clock (SAST)
    recorded_value: Decimal | None
    source: EventSource
    event_transformer_code: str | None  # as recorded on the event row
    registered: bool  # in the current device_list
    current: CurrentNetworkRow | None  # current network context; None if unregistered

    @property
    def value_kind(self) -> str:
        return VALUE_KIND[self.event_type]


@dataclass(frozen=True)
class EventsPage:
    status: EventsStatus
    start: date | None = None
    end: date | None = None
    counts: dict[EventType, int] | None = None
    total: int = 0  # events matching the type filter in the window
    page: int = 0
    events: tuple[HistoricalEvent, ...] = ()

    @property
    def page_count(self) -> int:
        return max(1, -(-self.total // PAGE_SIZE))


def default_window(latest: datetime | None) -> tuple[date, date] | None:
    """The default range, or None when the source holds no events."""
    if latest is None:
        return None
    end = latest.date()
    return end - timedelta(days=DEFAULT_WINDOW_DAYS - 1), end


def parse_uid(text) -> tuple[int | None, bool]:
    """(uid, ok). Blank means no filter; anything but a plain UID is not ok."""
    if text is None or str(text).strip() == "":
        return None, True
    t = str(text).strip()
    if not (t.isascii() and t.isdigit()) or int(t) > _MAX_UID:
        return None, False
    return int(t), True


def _parse_type(value) -> EventType | None:
    try:
        return EventType(value) if value else None
    except ValueError:
        raise ValueError("unknown event type") from None


def _registered_uids() -> set[int]:
    return set(RTLTemperatureRepository().get_registered_device_uids())


def _scope_uids(scope: RtlScope, registered_fetch) -> tuple[int, ...] | None:
    """The UID set the event reads are restricted to; None = unrestricted.

    A restricted (Technician) scope is intersected with the CURRENT registered
    directory, so events of a historical/unregistered UID are never shown to a
    Technician even if an assignment row somehow names it (ADR-032).
    """
    if scope.is_unrestricted:
        return None
    if not scope.permitted:
        return ()
    return tuple(scope.restrict(registered_fetch()))


def get_latest_event_time(
    repository: RTLEventsRepository | None = None, *, scope: RtlScope = UNRESTRICTED,
    registered_fetch=_registered_uids,
) -> datetime | None:
    repo = repository if repository is not None else RTLEventsRepository()
    try:
        return repo.get_latest_event_time(_scope_uids(scope, registered_fetch))
    except (RTLTemperatureRepositoryError, RTLDatabaseConfigurationError) as exc:
        logger.warning("Historical event window unavailable (%s)", type(exc).__name__)
        return None


def get_events_page(
    start: date, end: date, event_type=None, uid_text=None, page: int = 0, *,
    repository: RTLEventsRepository | None = None,
    network_fetch=network.get_current_network,
    scope: RtlScope = UNRESTRICTED,
    registered_fetch=_registered_uids,
) -> EventsPage:
    """One bounded, newest-first page of events for ``start..end`` inclusive.

    Reads: per-class counts and one page of rows (each one set-based query over
    the window), then - only if the page has rows - one current-network
    snapshot for registration and context. No per-event lookups.
    """
    uid, uid_ok = parse_uid(uid_text)
    try:
        chosen = _parse_type(event_type)
    except ValueError:
        return EventsPage(EventsStatus.INVALID)
    if not uid_ok or start is None or end is None or start > end:
        return EventsPage(EventsStatus.INVALID)
    repo = repository if repository is not None else RTLEventsRepository()
    lo, hi = datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)
    types = [chosen] if chosen else list(EventType)
    try:
        # Server-side scope: the UID set is part of every event query, so
        # out-of-scope rows are never read, counted or paged (ADR-032).
        scope_uids = _scope_uids(scope, registered_fetch)
        raw_counts = repo.count_events(lo, hi, uid, scope_uids)
        counts = {t: raw_counts.get(t.value, 0) for t in EventType}
        total = sum(counts[t] for t in types)
        page = min(max(0, int(page or 0)), max(0, -(-total // PAGE_SIZE) - 1))
        rows = (repo.get_events(lo, hi, [t.value for t in types], uid, PAGE_SIZE,
                                page * PAGE_SIZE, scope_uids) if total else [])
    except (RTLTemperatureRepositoryError, RTLDatabaseConfigurationError) as exc:
        logger.warning("Historical events unavailable (%s)", type(exc).__name__)
        return EventsPage(EventsStatus.UNAVAILABLE)

    by_uid: dict[int, CurrentNetworkRow] = {}
    if rows:
        current = network_fetch()
        if current.status is not NetworkStatus.DATA:
            return EventsPage(EventsStatus.UNAVAILABLE)
        by_uid = {r.device_uid: r for r in current.rows}
    events = tuple(
        HistoricalEvent(
            event_type=EventType(r.event_type), device_uid=r.device_uid,
            recorded_at=r.recorded_at, recorded_value=r.recorded_value,
            source=SOURCE_BY_TYPE[EventType(r.event_type)],
            event_transformer_code=r.transformer_code,
            registered=r.device_uid in by_uid, current=by_uid.get(r.device_uid),
        )
        for r in rows
    )
    return EventsPage(EventsStatus.DATA, start, end, counts, total, page, events)
