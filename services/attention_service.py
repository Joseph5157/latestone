"""The redesigned Command Center's facade (CC-NEW-1).

Answers one question — "what needs my attention now?" — as ONE snapshot per
poll, so no two panels can disagree about the fleet (ADR-005, ADR-008).

Everything here is assembled from existing reads; nothing new is decided:

- temperature condition   -> temperature_condition_service (ADR-023)
- no data for over 24 h   -> notification_service.build_no_data_notifications (BR008)
- alarm / activity events -> repo.list_recent_device_events, labels from
                             event_semantics only (ADR-001)
- programming requests    -> repo.list_programming_requests_since

Problem ranking (redesign decision D5), most urgent first:

    Critical temperature > Power down > No data > 24 h > Warning temperature
    > Battery alarm > Sensor error

and within one kind, the oldest first. An alarm event stays a problem until
someone acknowledges it; events have no clear/resolve contract, so
acknowledgement is the only honest way off the list.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, Mapping

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)
from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope
from services.event_semantics import display_label_for
from services.hierarchy_service import list_plants
from services.monitoring_service import latest_reading_rows
from services.notification_service import build_no_data_notifications
from services.temperature_condition_service import (
    DeviceTemperature,
    TemperatureCondition,
    TemperatureLimits,
    current_limits,
    device_temperatures,
    hottest,
)

HOTTEST_COUNT = 5
ACTIVITY_WINDOW = timedelta(hours=24)
ACTIVITY_ROWS = 10
TREND_DAYS = 7
#: Newest events read per poll — one read serves problems, activity and the
#: trend. At the simulator's ~12/day this spans weeks; an unacknowledged alarm
#: older than the newest EVENT_READ_LIMIT events drops off the list.
EVENT_READ_LIMIT = 500


class ProblemKind(str, Enum):
    TEMP_CRITICAL = "temp_critical"
    POWER_DOWN = "power_down"
    NO_DATA_24H = "no_data_24h"
    TEMP_WARNING = "temp_warning"
    BATTERY_LOW = "battery_low"
    SENSOR_ERROR = "sensor_error"


#: Declaration order above IS the rank (D5).
KIND_RANK: dict[ProblemKind, int] = {kind: i for i, kind in enumerate(ProblemKind)}

KIND_LABELS: dict[ProblemKind, str] = {
    ProblemKind.TEMP_CRITICAL: "Critical temperature",
    ProblemKind.POWER_DOWN: display_label_for(EVENT_TYPE_POWER_DOWN),
    ProblemKind.NO_DATA_24H: "No data for over 24 hours",
    ProblemKind.TEMP_WARNING: "High temperature (warning)",
    ProblemKind.BATTERY_LOW: display_label_for(EVENT_TYPE_BATTERY_LOW),
    ProblemKind.SENSOR_ERROR: display_label_for(EVENT_TYPE_SENSOR_ERROR),
}

_EVENT_KIND: dict[str, ProblemKind] = {
    EVENT_TYPE_POWER_DOWN: ProblemKind.POWER_DOWN,
    EVENT_TYPE_BATTERY_LOW: ProblemKind.BATTERY_LOW,
    EVENT_TYPE_SENSOR_ERROR: ProblemKind.SENSOR_ERROR,
}
ALARM_EVENT_TYPES: tuple[str, ...] = tuple(_EVENT_KIND)
_READ_EVENT_TYPES = ALARM_EVENT_TYPES + (EVENT_TYPE_STARTUP, EVENT_TYPE_CHECK_IN)

_TEMP_KIND = {
    TemperatureCondition.CRITICAL: ProblemKind.TEMP_CRITICAL,
    TemperatureCondition.WARNING: ProblemKind.TEMP_WARNING,
}


@dataclass(frozen=True)
class Location:
    plant_id: str
    plant_name: str
    transformer_code: str
    device_code: str


@dataclass(frozen=True)
class Problem:
    kind: ProblemKind
    device_id: str
    device_code: str
    plant_id: str
    plant_name: str
    transformer_code: str
    since: datetime | None
    detail: str
    #: The unacknowledged events behind an alarm problem (Phase 4 acts on them).
    event_ids: tuple[int, ...] = ()
    count: int = 1

    @property
    def label(self) -> str:
        return KIND_LABELS[self.kind]


@dataclass(frozen=True)
class ActivityItem:
    at: datetime
    label: str
    device_id: str
    device_code: str
    plant_name: str


@dataclass(frozen=True)
class DailyAlarms:
    day: date
    count: int


@dataclass(frozen=True)
class AttentionSnapshot:
    total_rtls: int
    reporting_rtls: int
    problems: tuple[Problem, ...]
    hottest: tuple[DeviceTemperature, ...]
    activity: tuple[ActivityItem, ...]
    daily_alarms: tuple[DailyAlarms, ...]
    limits: TemperatureLimits | None
    generated_at: datetime
    temperatures: tuple[DeviceTemperature, ...] = field(default=(), repr=False)


def locations(
    temps: Iterable[DeviceTemperature], plant_names: Mapping[str, str]
) -> dict[str, Location]:
    """device_id -> where it is, from the in-scope temperature rows."""
    return {
        t.device_id: Location(
            plant_id=t.plant_id,
            plant_name=plant_names.get(t.plant_id, t.plant_id),
            transformer_code=t.transformer_code,
            device_code=t.device_code,
        )
        for t in temps
    }


def _where(device_id: str, where: Mapping[str, Location]) -> Location:
    return where.get(device_id) or Location("", "", "", device_id)


def _problem(kind, device_id, where, *, since, detail, event_ids=(), count=1) -> Problem:
    loc = _where(device_id, where)
    return Problem(
        kind=kind, device_id=device_id, device_code=loc.device_code,
        plant_id=loc.plant_id, plant_name=loc.plant_name,
        transformer_code=loc.transformer_code, since=since, detail=detail,
        event_ids=tuple(event_ids), count=count,
    )


def format_limit(value) -> str:
    """36.500 -> '36.5', 40.000 -> '40' (never '4E+1')."""
    return format(value.normalize(), "f")


def temperature_problems(
    temps: Iterable[DeviceTemperature],
    limits: TemperatureLimits | None,
    where: Mapping[str, Location],
) -> list[Problem]:
    problems = []
    for t in temps:
        kind = _TEMP_KIND.get(t.condition)
        if kind is None or limits is None:
            continue
        limit = limits.critical_c if kind is ProblemKind.TEMP_CRITICAL else limits.warning_c
        problems.append(_problem(
            kind, t.device_id, where, since=t.reading_ts,
            detail=f"{t.value:.1f} °C · limit {format_limit(limit)} °C",
        ))
    return problems


def no_data_problems(notification_rows, where: Mapping[str, Location]) -> list[Problem]:
    """BR008 rows (already filtered to > 24 h) as problems."""
    return [
        _problem(ProblemKind.NO_DATA_24H, row.entity_id, where,
                 since=row.occurred_at, detail=row.detail)
        for row in notification_rows
    ]


def event_problems(events, where: Mapping[str, Location]) -> list[Problem]:
    """Unacknowledged alarm events, one problem per (RTL, type)."""
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for e in events:
        if e.device_id is None or e.acknowledged_at is not None:
            continue
        if e.event_type in _EVENT_KIND:
            groups[(e.device_id, e.event_type)].append(e)
    problems = []
    for (device_id, event_type), group in groups.items():
        group.sort(key=lambda e: (e.event_ts, e.event_id))
        latest = group[-1]
        detail = f"{len(group)} unacknowledged" if len(group) > 1 else "Unacknowledged"
        if latest.battery_voltage is not None:
            detail += f" · last reported {latest.battery_voltage:.2f} V"
        problems.append(_problem(
            _EVENT_KIND[event_type], device_id, where, since=group[0].event_ts,
            detail=detail, event_ids=[e.event_id for e in group], count=len(group),
        ))
    return problems


_NEVER = datetime.max.replace(tzinfo=timezone.utc)


def rank_problems(problems: Iterable[Problem]) -> list[Problem]:
    return sorted(
        problems,
        key=lambda p: (KIND_RANK[p.kind], p.since or _NEVER, p.device_code),
    )


def activity_items(events, requests, where: Mapping[str, Location], *, now: datetime) -> list[ActivityItem]:
    """Switch-ons, acknowledgements and programming requests in the last 24 h."""
    since = now - ACTIVITY_WINDOW
    items: list[ActivityItem] = []

    def add(at, label, device_id):
        loc = _where(device_id, where)
        items.append(ActivityItem(at, label, device_id, loc.device_code, loc.plant_name))

    for e in events:
        if e.device_id is None:
            continue
        if e.event_type == EVENT_TYPE_STARTUP and e.event_ts >= since:
            add(e.event_ts, "Switched on", e.device_id)
        if e.acknowledged_at is not None and e.acknowledged_at >= since:
            add(e.acknowledged_at, f"Acknowledged: {display_label_for(e.event_type)}", e.device_id)
    for r in requests:
        if r.requested_at >= since:
            add(r.requested_at, "Programming requested", r.device_id)
    items.sort(key=lambda i: i.at, reverse=True)
    return items[:ACTIVITY_ROWS]


def daily_alarm_counts(events, *, now: datetime) -> list[DailyAlarms]:
    """Alarm events per UTC day for the last TREND_DAYS days, today last."""
    today = now.astimezone(timezone.utc).date()
    days = [today - timedelta(days=offset) for offset in range(TREND_DAYS - 1, -1, -1)]
    counts = {d: 0 for d in days}
    for e in events:
        if e.event_type in _EVENT_KIND:
            day = e.event_ts.astimezone(timezone.utc).date()
            if day in counts:
                counts[day] += 1
    return [DailyAlarms(d, counts[d]) for d in days]


def _plant_names(scope: DeviceScope) -> dict[str, str]:
    return {p.plant_id: p.name for p in list_plants(scope=scope)}


def get_attention_snapshot(
    scope: DeviceScope, *, now: datetime | None = None
) -> AttentionSnapshot:
    """One snapshot for one poll. Resolve `scope` once and pass it in (ADR-004)."""
    now = now or datetime.now(timezone.utc)
    temps = device_temperatures(scope, now=now)
    limits = current_limits()
    where = locations(temps, _plant_names(scope))
    events = repo.list_recent_device_events(
        event_types=_READ_EVENT_TYPES,
        allowed_device_ids=scope.device_ids,
        include_unattributed=False,
        limit=EVENT_READ_LIMIT,
    )
    requests = repo.list_programming_requests_since(
        since=now - ACTIVITY_WINDOW, allowed_device_ids=scope.device_ids
    )
    no_data_rows = build_no_data_notifications(latest_reading_rows(scope=scope), now)

    problems = rank_problems(
        temperature_problems(temps, limits, where)
        + no_data_problems(no_data_rows, where)
        + event_problems(events, where)
    )
    return AttentionSnapshot(
        total_rtls=len(temps),
        reporting_rtls=sum(
            t.condition is not TemperatureCondition.NO_RECENT_DATA for t in temps
        ),
        problems=tuple(problems),
        hottest=tuple(hottest(temps, HOTTEST_COUNT)),
        activity=tuple(activity_items(events, requests, where, now=now)),
        daily_alarms=tuple(daily_alarm_counts(events, now=now)),
        limits=limits,
        generated_at=now,
        temperatures=tuple(temps),
    )
