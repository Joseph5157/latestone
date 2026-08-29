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
from services.monitoring_service import FleetHealth, Freshness, get_fleet_health

#: Technical pilot-safety bound, matching NOTIFICATION_QUERY_LIMIT's own
#: rationale (services/event_semantics.py) - not product semantics.
RECENT_EVENTS_LIMIT = 500


@dataclass(frozen=True)
class CommandCenterSnapshot:
    """One presentation-ready Command Center render.

    Every figure below is decided HERE, not in a component: the Situation
    Summary cards render numbers and never inspect `FleetHealth` themselves.
    That keeps exactly one freshness interpretation in Command Center - the
    same reason services/device_scope.py and services/authorization.py each
    insist on being the single answer to their own question.
    """

    fleet_health: FleetHealth
    recent_events: list[DeviceEventRecord]

    #: The monitored RTL population - active devices under active
    #: transformers. Backs the header's scope indicator (ADR-004), Fleet
    #: Health's total, every percentage denominator here, AND Inventory's
    #: "RTL Devices". Deliberately ONE field rather than a separate
    #: inventory count: the user froze Inventory's subtitle as "Monitored
    #: assets in your current access scope", so a second field could only
    #: ever drift from the population that phrase promises.
    monitored_device_count: int

    #: Freshness composition, device-level, worst-of across each device's
    #: metrics (ADR-002).
    fresh_rtls: int
    stale_rtls: int
    no_data_rtls: int

    #: ADR-002: Requires Attention is Stale + No Data and nothing else.
    #: Never mixed with event occurrences - events answer "did something
    #: happen", freshness answers "is the data current now".
    attention_rtls: int
    attention_percent: float
    no_data_percent: float

    #: Inventory - the same monitoring population, one level up.
    plant_count: int
    transformer_count: int

    #: Plants holding at least one No Data RTL. Counts PLANTS, not devices:
    #: two blind RTLs in one plant is one affected location.
    no_data_affected_plants: int

    @property
    def has_monitored_devices(self) -> bool:
        """Whether any RTL is in scope at all.

        Components ask this instead of testing a count against zero, so an
        empty scope renders a real empty state rather than "0.0% of 0",
        which reads as a measured healthy result when it is the absence of
        any measurement.
        """
        return self.monitored_device_count > 0


def _percent(part: int, whole: int) -> float:
    """Share of the monitored population; 0.0 when nothing is monitored.

    The zero case is never rendered as a percentage - `has_monitored_devices`
    gates that - but returning 0.0 rather than raising keeps the snapshot
    total: a caller assembling one is never handed an exception because a
    technician has no assignments yet.
    """
    return (100 * part / whole) if whole else 0.0


def _plants_with_no_data(fleet_health: FleetHealth) -> int:
    """Plants holding at least one NO_DATA device.

    Reads the rollups `get_fleet_health` already built (via the public
    `device_counts_for_plant`) - not a second traversal of readings and not
    a second freshness calculation.
    """
    return sum(
        1
        for plant_id in fleet_health.plants
        if fleet_health.device_counts_for_plant(plant_id).get(Freshness.NO_DATA, 0)
    )


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

    counts = fleet_health.counts
    monitored = fleet_health.device_count
    stale = counts.get(Freshness.STALE, 0)
    no_data = counts.get(Freshness.NO_DATA, 0)
    attention = stale + no_data

    return CommandCenterSnapshot(
        fleet_health=fleet_health,
        recent_events=events,
        monitored_device_count=monitored,
        fresh_rtls=counts.get(Freshness.FRESH, 0),
        stale_rtls=stale,
        no_data_rtls=no_data,
        attention_rtls=attention,
        attention_percent=_percent(attention, monitored),
        no_data_percent=_percent(no_data, monitored),
        plant_count=fleet_health.plant_count,
        transformer_count=len(fleet_health.transformers),
        no_data_affected_plants=_plants_with_no_data(fleet_health),
    )
