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

from config.events import EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_POWER_DOWN
from repositories.plant_monitoring_repository import (
    DeviceEventRecord,
    list_recent_device_events,
)
from services import event_semantics
from services.device_scope import DeviceScope
from services.hierarchy_service import list_plants, list_transformers
from services.monitoring_service import FleetHealth, Freshness, get_fleet_health

#: Technical pilot-safety bound, matching NOTIFICATION_QUERY_LIMIT's own
#: rationale (services/event_semantics.py) - not product semantics.
RECENT_EVENTS_LIMIT = 500

#: Device-definition legend copy (ADR-001). These figures describe what the
#: DEVICE already decided before emitting the event - they are never
#: evaluated here. Sourced from config/notifications.py, whose spec-frozen
#: category descriptions cite BR002/BR011 ("Battery voltage below 3.61 V,
#: device entering power-down mode", "below 3.75 V"); a test binds these
#: strings to that source so a spec change fails loudly rather than leaving
#: Command Center quietly showing a stale number.
CRITICAL_DEFINITION = "< 3.61 V"
WARNING_DEFINITION = "< 3.75 V"


@dataclass(frozen=True)
class ElectricalCondition:
    """One already-classified event type, as the operator sees it.

    `current_count is None` is a DELIBERATE DOMAIN RESULT, not an unfinished
    UI. Persisted events record that something occurred; there is no
    resolve/clear/closure contract (ADR-001), so no count of RTLs *currently*
    in this condition is derivable. Rendering 0 would assert the fleet is
    healthy on evidence that does not exist - which is why the type is
    `int | None` rather than `int` defaulting to zero.
    """

    #: CSS tone key - "critical" | "warning". Styles the category marker,
    #: never the unavailable value.
    severity_key: str
    severity_label: str
    #: Canonical name from config.events, not retyped.
    event_type: str
    condition_label: str
    current_count: int | None
    definition: str


#: The two conditions the device classifies and this card presents.
#:
#: high_temperature and vibration_event are deliberately absent, exactly as
#: they are absent from services/event_semantics.py: their domain rules are
#: open client-clarification items. Owning a "Critical" category is not a
#: reason to invent membership in it.
#:
#: `condition_label` names the DEVICE CONDITION, so Battery Low keeps the
#: event's own vocabulary. That differs on purpose from the Notification
#: Center, which labels the same event's category "Battery Alarm"
#: (config/notifications.py): a notification category and a device condition
#: are different things, and flattening them would misname one of the two.
ELECTRICAL_CONDITIONS: tuple[ElectricalCondition, ...] = (
    ElectricalCondition(
        severity_key="critical",
        severity_label="Critical",
        event_type=EVENT_TYPE_POWER_DOWN,
        condition_label="Power Down",
        current_count=None,
        definition=CRITICAL_DEFINITION,
    ),
    ElectricalCondition(
        severity_key="warning",
        severity_label="Warning",
        event_type=EVENT_TYPE_BATTERY_LOW,
        condition_label="Battery Low",
        current_count=None,
        definition=WARNING_DEFINITION,
    ),
)


@dataclass(frozen=True)
class AffectedLocation:
    """One Plant's freshness exception load (CC-1 Phase 7).

    Location = Plant (ADR-003). Every number here is derived from the
    `FleetHealth` already fetched; only `plant_name` comes from elsewhere,
    and only as a label (ADR-008).
    """

    plant_id: str
    #: Falls back to `plant_id` when the label lookup has no entry - the
    #: freshness snapshot is the authority on which plants are in scope, so
    #: a missing name must never remove a plant from the ranking.
    plant_name: str
    affected_rtls: int
    stale_rtls: int
    no_data_rtls: int
    total_monitored_rtls: int
    affected_percent: float


@dataclass(frozen=True)
class TransformerConcentration:
    """One transformer's share of a plant's freshness exceptions."""

    transformer_id: str
    #: Falls back to `transformer_id` when the label lookup has no entry,
    #: for the same reason plant_name does: FleetHealth is the authority on
    #: what exists in scope, and labelling must never shrink it.
    transformer_code: str
    affected_rtls: int
    stale_rtls: int
    no_data_rtls: int
    total_monitored_rtls: int


@dataclass(frozen=True)
class SelectedLocation:
    """The plant currently under investigation, and what is driving it.

    Present only when a visible plant is selected. An unknown or
    out-of-scope id yields None rather than an error or a message
    confirming that a plant the caller cannot see exists.
    """

    plant_id: str
    plant_name: str
    affected_rtls: int
    total_monitored_rtls: int
    transformers: tuple[TransformerConcentration, ...]


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

    #: The classified electrical conditions and their current-state
    #: availability. Constant in CC-1 (every current_count is None) but
    #: carried on the snapshot rather than imported by the component, so the
    #: day a closure contract exists this becomes a computed field and no
    #: component changes.
    electrical_conditions: tuple[ElectricalCondition, ...]

    #: Plants ranked by freshness exception load, worst first. Includes
    #: zero-affected plants: whether to show a calm plant is a presentation
    #: choice, and dropping it here would make "every plant is healthy"
    #: indistinguishable from "no plants in scope".
    affected_locations: tuple[AffectedLocation, ...]

    #: The plant named by `?plant=`, or None. Selection is a lens on one
    #: plant, never a filter on the fleet: every figure above is unchanged
    #: by it, and a test asserts that.
    selected_location: SelectedLocation | None

    @property
    def has_affected_locations(self) -> bool:
        """Whether any Plant carries a freshness exception at all."""
        return any(row.affected_rtls for row in self.affected_locations)

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


def _affected_locations(
    fleet_health: FleetHealth, plant_names: dict[str, str]
) -> tuple[AffectedLocation, ...]:
    """Plants ranked by freshness exception load (ADR-002, ADR-003).

    Composed entirely from the rollups `get_fleet_health` already built.
    Ranking is deliberately NOT pushed into SQL: an ORDER BY over a fresh
    query would be a second definition of "affected", free to drift from
    the one Fleet Overview and the Situation Summary share.

    Order: affected count DESCENDING, then plant NAME ascending. The
    tie-break is on the displayed name rather than `plant_id` so the
    rendered list reads alphabetically where counts are equal - ordering by
    an id the operator cannot see would look arbitrary on screen.

    Name comparison is CASE-INSENSITIVE. A raw ASCII sort puts every
    all-caps name in its own block ahead of the mixed-case ones - real
    fleet data ranked "GRAVELINES" above "Grand Coulee", which reads as a
    bug to anyone scanning the list alphabetically. `plant_id` is the final
    key so two names differing only in case still order deterministically
    rather than falling back on dict iteration order.

    No event data participates. Events answer "did something happen";
    this answers "is the data current now".
    """
    rows = []
    for plant_id in fleet_health.plants:
        counts = fleet_health.device_counts_for_plant(plant_id)
        stale = counts.get(Freshness.STALE, 0)
        no_data = counts.get(Freshness.NO_DATA, 0)
        affected = stale + no_data
        total = sum(counts.values())
        rows.append(
            AffectedLocation(
                plant_id=plant_id,
                plant_name=plant_names.get(plant_id, plant_id),
                affected_rtls=affected,
                stale_rtls=stale,
                no_data_rtls=no_data,
                total_monitored_rtls=total,
                affected_percent=_percent(affected, total),
            )
        )
    return tuple(
        sorted(
            rows,
            key=lambda r: (-r.affected_rtls, r.plant_name.casefold(), r.plant_id),
        )
    )


def _selected_location(
    fleet_health: FleetHealth,
    plant_names: dict[str, str],
    plant_id: str | None,
    scope: DeviceScope,
) -> SelectedLocation | None:
    """Transformer concentration within one plant.

    Returns None for no selection, an unknown plant, or one outside scope -
    all three are "selects nothing", never an error. Distinguishing them in
    the UI would confirm that a plant the caller cannot see exists.

    Counts come from the rollups `get_fleet_health` already built; only the
    transformer CODES are fetched, and only for this one plant (ADR-008).
    """
    if not plant_id or plant_id not in fleet_health.plants:
        return None

    codes = {
        t.transformer_id: t.transformer_code
        for t in list_transformers(plant_id, scope=scope)
    }

    rows = []
    for transformer_id, rollup in fleet_health.transformers_for_plant(plant_id).items():
        stale = rollup.counts.get(Freshness.STALE, 0)
        no_data = rollup.counts.get(Freshness.NO_DATA, 0)
        rows.append(
            TransformerConcentration(
                transformer_id=transformer_id,
                transformer_code=codes.get(transformer_id, transformer_id),
                affected_rtls=stale + no_data,
                stale_rtls=stale,
                no_data_rtls=no_data,
                total_monitored_rtls=rollup.total,
            )
        )

    # Same rule as the plant ranking, one level down: worst first, then the
    # displayed code (case-insensitively, so an all-caps code does not sort
    # into its own block), then the id so ordering is fully determined.
    ranked = tuple(
        sorted(
            rows,
            key=lambda r: (
                -r.affected_rtls,
                r.transformer_code.casefold(),
                r.transformer_id,
            ),
        )
    )

    plant_counts = fleet_health.device_counts_for_plant(plant_id)
    return SelectedLocation(
        plant_id=plant_id,
        plant_name=plant_names.get(plant_id, plant_id),
        affected_rtls=(
            plant_counts.get(Freshness.STALE, 0)
            + plant_counts.get(Freshness.NO_DATA, 0)
        ),
        total_monitored_rtls=sum(plant_counts.values()),
        transformers=ranked,
    )


def get_command_center_snapshot(
    *,
    scope: DeviceScope,
    now: datetime | None = None,
    event_limit: int = RECENT_EVENTS_LIMIT,
    selected_plant_id: str | None = None,
) -> CommandCenterSnapshot:
    """Assemble one Command Center snapshot. Call once per render."""
    fleet_health = get_fleet_health(now, scope=scope)
    events = list_recent_device_events(
        event_types=event_semantics.mapped_event_types(),
        allowed_device_ids=scope.device_ids,
        limit=event_limit,
    )
    # Labels only (ADR-008) - every Plant-level number and the ranking order
    # come from fleet_health above. Scoped like every other read so an
    # out-of-scope plant name can never surface (ADR-004).
    plant_names = {p.plant_id: p.name for p in list_plants(scope=scope)}

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
        electrical_conditions=ELECTRICAL_CONDITIONS,
        affected_locations=_affected_locations(fleet_health, plant_names),
        selected_location=_selected_location(
            fleet_health, plant_names, selected_plant_id, scope
        ),
    )
