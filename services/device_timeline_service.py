"""One RTL's alarm history and reading gaps for the Device page (ADR-027).

The Command Center answers "what needs attention across the fleet"; this
answers "what happened to this RTL, and when", beside its own chart.

- Alarms are read through the one consumer read API
  (`list_recent_device_events`, EVT-D2), scoped to the single RTL. Kinds and
  labels come from `attention_service`, so the Device page and the Command
  Center name an alarm the same way.
- A reading gap is judged against the RTL's OWN rhythm in the shown window
  (median spacing), never a fixed cadence: the application does not know
  any RTL's reporting cadence (config/settings.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Iterable

from repositories import plant_monitoring_repository as repo
from services.attention_service import ALARM_EVENT_TYPES, KIND_LABELS, ProblemKind, event_kind
from services.auth_service import current_identity
from services.authorization import may_access_route
from services.device_scope import DeviceScope, scope_for

#: A gap is shaded when it is longer than this many times the RTL's median
#: reading spacing in the window (ADR-027).
GAP_FACTOR = 4

#: Fewer readings than this give no trustworthy "usual spacing".
_MIN_READINGS_FOR_GAPS = 3

#: Alarm history follows the roles that may already see alarms elsewhere
#: (Notifications, Command Center): Administrator and Technician (ADR-027).
ALARM_ROUTE = "notifications"

#: Technical capacity bound for one RTL's window, not product semantics.
_ALARM_READ_LIMIT = 500


@dataclass(frozen=True)
class DeviceAlarm:
    event_id: int
    kind: ProblemKind
    at: datetime
    acknowledged_at: datetime | None

    @property
    def label(self) -> str:
        return KIND_LABELS[self.kind]

    @property
    def is_open(self) -> bool:
        return self.acknowledged_at is None

    @property
    def acknowledged_after(self) -> timedelta | None:
        return None if self.acknowledged_at is None else self.acknowledged_at - self.at


@dataclass(frozen=True)
class ReadingGap:
    start: datetime
    end: datetime

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


def device_alarms(
    scope: DeviceScope, device_id: str, start: datetime | None, end: datetime | None
) -> tuple[DeviceAlarm, ...]:
    """This RTL's alarms in [start, end], newest first. Empty outside `scope`."""
    if not scope.allows(device_id):
        return ()
    events = repo.list_recent_device_events(
        event_types=ALARM_EVENT_TYPES,
        since=start,
        allowed_device_ids=frozenset({device_id}),
        include_unattributed=False,
        limit=_ALARM_READ_LIMIT,
    )
    return tuple(
        DeviceAlarm(e.event_id, event_kind(e.event_type), e.event_ts, e.acknowledged_at)
        for e in events
        if event_kind(e.event_type) is not None
        and e.device_id == device_id
        and (end is None or e.event_ts <= end)
    )


def reading_gaps(
    timestamps: Iterable[datetime], *, until: datetime | None = None
) -> tuple[ReadingGap, ...]:
    """Stretches with no readings, longer than GAP_FACTOR x the usual spacing.

    `until` (the window end) also catches the silence AFTER the last reading
    — for an RTL that has stopped reporting, the gap that matters most.
    """
    ts = sorted(timestamps)
    if len(ts) < _MIN_READINGS_FOR_GAPS:
        return ()
    steps = [b - a for a, b in zip(ts, ts[1:])]
    usual = median(steps)
    if usual <= timedelta(0):
        return ()
    limit = usual * GAP_FACTOR
    gaps = [ReadingGap(a, b) for a, b, step in zip(ts, ts[1:], steps) if step > limit]
    if until is not None and until - ts[-1] > limit:
        gaps.append(ReadingGap(ts[-1], until))
    return tuple(gaps)


def current_alarm_history(
    device_id: str, start: datetime | None, end: datetime | None
) -> tuple[DeviceAlarm, ...] | None:
    """The current user's view of this RTL's alarms; None when their role may
    not see alarms at all (General User), so the page shows no history."""
    identity = current_identity()
    if identity is None or not may_access_route(identity.role, ALARM_ROUTE):
        return None
    return device_alarms(scope_for(identity), device_id, start, end)
