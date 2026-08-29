"""Command Center service - the one facade assembling a presentation-ready
snapshot for /command-center (ADR-008).

Calls `get_fleet_health()` and `list_recent_device_events()` exactly once
each per render, mirroring `get_fleet_health`'s own call discipline: resolve
once, pass the result down, never call this per-component. Owns no query of
its own - AGENTS.md rule 1 (no raw SQL in UI/page/component code) extends
here too: everything below is composition over what those two functions
already return, never a new SELECT.

Phase 3+4 (foundation and shell): only the fields the empty shell needs are
populated. Panel content (Phase 5 onward, docs/context/CC1_ROADMAP.md)
extends `CommandCenterSnapshot`, it does not replace this module's shape.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from repositories.plant_monitoring_repository import (
    DeviceEventRecord,
    list_recent_device_events,
)
from services import event_semantics
from services.device_scope import DeviceScope
from services.monitoring_service import FleetHealth, get_fleet_health

#: Technical pilot-safety bound, matching NOTIFICATION_QUERY_LIMIT's own
#: rationale (services/event_semantics.py) - not product semantics.
RECENT_EVENTS_LIMIT = 500


@dataclass(frozen=True)
class CommandCenterSnapshot:
    """One presentation-ready Command Center render."""

    fleet_health: FleetHealth
    recent_events: list[DeviceEventRecord]
    #: The header's read-only scope indicator (ADR-004: "Current access ·
    #: N monitored RTLs"). Equal to fleet_health.device_count - kept as its
    #: own field so callers never have to know FleetHealth's shape just to
    #: render the one number the shell needs first.
    monitored_device_count: int


def get_command_center_snapshot(
    *,
    scope: DeviceScope,
    now: datetime | None = None,
    event_limit: int = RECENT_EVENTS_LIMIT,
) -> CommandCenterSnapshot:
    """Assemble one Command Center snapshot. Call once per render."""
    fleet_health = get_fleet_health(now, scope=scope)
    events = list_recent_device_events(
        event_types=event_semantics.mapped_event_types(),
        allowed_device_ids=scope.device_ids,
        limit=event_limit,
    )
    return CommandCenterSnapshot(
        fleet_health=fleet_health,
        recent_events=events,
        monitored_device_count=fleet_health.device_count,
    )
