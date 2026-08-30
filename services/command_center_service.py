"""Command Center service - the one facade assembling a presentation-ready
snapshot for /command-center (ADR-008).

Calls each of ADR-008's approved read paths at most once per render,
mirroring `get_fleet_health`'s own call discipline: resolve once, pass the
result down, never call this per-component. Owns no query of its own -
AGENTS.md rule 1 (no raw SQL in UI/page/component code) extends here too:
everything below is composition over what those reads already return, never
a new SELECT.

Two boundaries this module holds and the components below it do not:

- FRESHNESS vs EVENTS. `attention_rtls` and every ranking come from
  `FleetHealth` alone (ADR-002); events never enter them. Events answer "did
  something happen", freshness answers "is the data current now", and mixing
  the two time semantics is the thing ADR-002 exists to forbid.
- OCCURRENCE vs STATE. A recent Power Down event is displayed; a count of
  RTLs *currently* in Critical is not derivable and stays `Unavailable`
  (ADR-001 - no closure contract exists).

Each phase extends `CommandCenterSnapshot`; none replaces this module's
shape (docs/context/CC1_ROADMAP.md).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from config.events import EVENT_TYPE_BATTERY_LOW, EVENT_TYPE_POWER_DOWN
from repositories.plant_monitoring_repository import list_recent_device_events
from routes import device_href
from services import event_semantics
from services.device_scope import DeviceScope
from services.hierarchy_service import (
    list_device_paths,
    list_plants,
    list_transformers,
)
from services.monitoring_service import FleetHealth, Freshness, get_fleet_health

logger = logging.getLogger(__name__)

#: Technical pilot-safety bound, matching NOTIFICATION_QUERY_LIMIT's own
#: rationale (services/event_semantics.py) - not product semantics. It is the
#: CEILING a caller cannot ask past, not the number Command Center wants.
RECENT_EVENTS_LIMIT = 500

#: How many event rows the panel shows, and therefore how many the query asks
#: for. The repository already orders `event_ts DESC, event_id DESC`, so
#: LIMIT N *is* the newest N - fetching 500 to render 10 would make the query,
#: and the label lookup behind it, fifty times larger than the panel. Ten is
#: enough to be operationally useful without turning a context strip into an
#: alarm list; the Notification Center stays the deeper destination.
RECENT_EVENT_ROWS = 10

#: The neutral presentation every event that is NOT one of the two
#: device-classified conditions takes. A word, not an absence: colour never
#: carries meaning alone, so a neutral marker still needs a label beside it.
TONE_EVENT = "event"
TONE_EVENT_LABEL = "Event"

#: An event attributed to a transformer but to no device and no reported UID
#: (INGEST-D2 rule 4). Named rather than left blank so the row reads as a
#: fact about attribution rather than as a field that failed to load.
UNATTRIBUTED_ASSET_LABEL = "Unattributed"

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
    #: The Stale / No Data split behind `affected_rtls`. "18 affected" alone
    #: does not tell an operator whether the plant stopped reporting or
    #: never started, and those need different responses.
    stale_rtls: int
    no_data_rtls: int
    total_monitored_rtls: int
    transformers: tuple[TransformerConcentration, ...]

    @property
    def has_monitored_rtls(self) -> bool:
        """Distinct from `affected_rtls == 0`. A plant with nothing to
        monitor and a plant whose RTLs are all healthy are different facts,
        and reporting the second when the first is true would invent a
        clean bill of health."""
        return self.total_monitored_rtls > 0


@dataclass(frozen=True)
class RecentEvent:
    """One persisted event, as the operator reads it.

    Presentation-ready by construction: the component renders these strings
    and never inspects `event_type` itself. Same rule the Situation Summary
    follows, for the same reason — two parts of one screen interpreting the
    same event vocabulary is how they come to disagree about what it means.

    An OCCURRENCE, never a state. A row here says "this happened at 14:02";
    it does not say the RTL is in that condition now, and nothing derived
    from these rows may claim otherwise (ADR-001 — no closure contract).
    """

    event_id: int
    occurred_at: datetime
    event_type: str
    #: The event's own name, from the shared semantics layer (EVT-D1).
    display_label: str
    #: CSS tone key — "critical" | "warning" | TONE_EVENT.
    tone: str
    tone_label: str
    #: What the event happened TO: a device code, "UID 29841", or a raw id
    #: when the label lookup could not resolve one.
    asset_label: str
    #: "Plant / Transformer", the unregistered-UID note, or None.
    context_label: str | None
    #: Secondary payload the event carried. Display only.
    detail: str | None
    #: The existing RTL route — present ONLY when the asset actually resolved.
    asset_href: str | None
    time_label: str
    time_title: str


def _tone_for(event_type: str) -> tuple[str, str]:
    """The severity presentation for one event type.

    Derived from ELECTRICAL_CONDITIONS at call time rather than copied into
    a second table: that tuple is Command Center's single statement of
    `power_down -> Critical`, and a second copy is how the Phase 6 card and
    these rows would eventually disagree about the same event type.

    Everything else is neutral. Owning a Critical style is not a reason to
    spend it on an event the device did not classify as one.
    """
    for condition in ELECTRICAL_CONDITIONS:
        if condition.event_type == event_type:
            return condition.severity_key, condition.severity_label
    return TONE_EVENT, TONE_EVENT_LABEL


def _event_detail(event) -> str | None:
    """Secondary payload, formatted for display and for nothing else.

    The voltage is what the DEVICE measured before it decided (EVT-D4). It
    is shown because an operator heading to the asset benefits from it; it
    is never compared, ranked or thresholded here, and a structural test
    (tests/test_command_center_service.py) fails the build if it ever is.
    """
    voltage = event.battery_voltage
    if voltage is None:
        return None
    return f"Battery voltage · {voltage:.2f} V"


def _time_labels(occurred_at: datetime, reference: datetime) -> tuple[str, str]:
    """A compact clock time, plus the unambiguous one for the row's title.

    Same-day events show the bare time; anything older carries its date. A
    three-day-old event rendered as "14:02" reads as this afternoon, which
    is the panel implying a recency it does not have.

    Times are UTC, as persisted (INGEST-D4). The panel names that once in
    its subtitle rather than suffixing every row.
    """
    title = occurred_at.strftime("%Y-%m-%d %H:%M UTC")
    if occurred_at.date() == reference.date():
        return occurred_at.strftime("%H:%M"), title
    return occurred_at.strftime("%d %b %H:%M"), title


def _recent_event(event, paths: dict, reference: datetime) -> RecentEvent:
    """Project one persisted event onto its row.

    Three attribution cases, kept apart because they are three different
    facts about what is KNOWN, not three renderings of one:

    - a resolved device: real labels, and a link to its existing RTL page
    - a device the label lookup missed: its id, and NO link — offering
      "Open asset" would claim an asset the lookup just failed to support
    - an unregistered UID (EVT-D5): no device exists, so no page does
    """
    if event.device_id is not None:
        path = paths.get(event.device_id)
        asset_label = path.device_code if path else event.device_id
        context_label = (
            f"{path.plant_name} / {path.transformer_code}" if path else None
        )
        asset_href = device_href(event.device_id) if path else None
    elif event.reported_uid is not None:
        asset_label = f"UID {event.reported_uid}"
        context_label = event_semantics.UNREGISTERED_NOTIFICATION_TYPE
        asset_href = None
    else:
        asset_label = event.transformer_id or UNATTRIBUTED_ASSET_LABEL
        context_label = None
        asset_href = None

    tone, tone_label = _tone_for(event.event_type)
    time_label, time_title = _time_labels(event.event_ts, reference)
    return RecentEvent(
        event_id=event.event_id,
        occurred_at=event.event_ts,
        event_type=event.event_type,
        display_label=event_semantics.display_label_for(event.event_type),
        tone=tone,
        tone_label=tone_label,
        asset_label=asset_label,
        context_label=context_label,
        detail=_event_detail(event),
        asset_href=asset_href,
        time_label=time_label,
        time_title=time_title,
    )


def _recent_events(
    events, reference: datetime, scope: DeviceScope
) -> tuple[RecentEvent, ...]:
    """The visible event rows, labelled in ONE batched lookup (ADR-008).

    Order is the repository's, untouched: it already sorts `event_ts DESC,
    event_id DESC` (INGEST-D4 tiebreak), and re-sorting here would be a
    second ordering rule free to disagree with the query's. Severity never
    enters it — a severity-first order would lift an old Power Down above a
    newer Startup and quietly turn a chronology into a priority queue, which
    is the alarm-management system this panel is explicitly not.
    """
    device_ids = [e.device_id for e in events if e.device_id is not None]
    paths = (
        {p.device_id: p for p in list_device_paths(device_ids, scope=scope)}
        if device_ids
        else {}
    )
    return tuple(_recent_event(event, paths, reference) for event in events)


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

    #: Presentation-ready event rows, newest first. Occurrences, never a
    #: current state — see RecentEvent.
    recent_events: tuple[RecentEvent, ...]

    #: Whether the event read FAILED, as opposed to returning nothing.
    #: Structurally distinct for the same reason `current_count is None` is
    #: distinct from `0`: "nothing happened" and "we could not look" are
    #: different facts, and the panel must be able to say which one it has.
    recent_events_failed: bool

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


def _resolve_selected_plant(
    fleet_health: FleetHealth,
    ranked_locations: tuple[AffectedLocation, ...],
    plant_id: str | None,
) -> str | None:
    """Which plant the panel shows.

    An explicit, still-valid selection wins. Anything else - nothing chosen
    yet, a hand-edited id, or a plant that has dropped out of the caller's
    scoped snapshot since the link was made - falls back to the WORST
    AFFECTED plant, so the panel opens on the thing most worth looking at
    rather than on a prompt.

    The fallback also future-proofs polling: a refresh that changes scope
    can invalidate a selection made a moment ago, and silently landing on
    the current worst plant is better than blanking the panel.

    Returns None only when nothing is affected at all - a calm fleet, which
    the panel states rather than treating as an error.
    """
    if plant_id and plant_id in fleet_health.plants:
        return plant_id
    for location in ranked_locations:
        if location.affected_rtls:
            return location.plant_id
    return None


def _selected_location(
    fleet_health: FleetHealth,
    plant_names: dict[str, str],
    plant_id: str | None,
    scope: DeviceScope,
) -> SelectedLocation | None:
    """Transformer concentration within one plant.

    Counts come from the rollups `get_fleet_health` already built; only the
    transformer CODES are fetched, and only for this one plant (ADR-008).
    """
    if plant_id is None:
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
    plant_stale = plant_counts.get(Freshness.STALE, 0)
    plant_no_data = plant_counts.get(Freshness.NO_DATA, 0)
    return SelectedLocation(
        plant_id=plant_id,
        plant_name=plant_names.get(plant_id, plant_id),
        affected_rtls=plant_stale + plant_no_data,
        stale_rtls=plant_stale,
        no_data_rtls=plant_no_data,
        total_monitored_rtls=sum(plant_counts.values()),
        transformers=ranked,
    )


def _read_recent_events(
    *,
    scope: DeviceScope,
    reference: datetime,
    event_limit: int,
    include_unregistered: bool,
) -> tuple[tuple[RecentEvent, ...], bool]:
    """The events read, behind its own failure boundary (ADR-008).

    Every other read in this façade answers "what is the state of the
    fleet". This one answers "what happened recently", which is CONTEXT
    around that state rather than the state itself — so an operator who
    cannot see the last ten events can still act on Needs Attention,
    Affected Locations and the transformer concentration. Blanking all of
    those because an event query failed would remove far more truth than the
    failure actually cost.

    The failure is never flattened into an empty list. It is returned as a
    flag beside an empty tuple, so the panel can state which of the two it
    has.

    The boundary is deliberately one-directional: a `get_fleet_health` or
    label failure still fails the whole snapshot, because those ARE the page.
    """
    try:
        events = list_recent_device_events(
            event_types=event_semantics.mapped_event_types(),
            allowed_device_ids=scope.device_ids,
            include_unattributed=include_unregistered,
            limit=min(event_limit, RECENT_EVENTS_LIMIT),
        )
        return _recent_events(events, reference, scope), False
    except Exception:
        logger.exception("Command Center could not read recent device events")
        return (), True


def get_command_center_snapshot(
    *,
    scope: DeviceScope,
    now: datetime | None = None,
    event_limit: int = RECENT_EVENT_ROWS,
    selected_plant_id: str | None = None,
    include_unregistered: bool = False,
) -> CommandCenterSnapshot:
    """Assemble one Command Center snapshot. Call once per render.

    `include_unregistered` is the EVT-D5 administrator gate, decided by the
    caller exactly as `callbacks/notifications.py` already decides it: an
    unregistered UID belongs to no device set, so scope alone cannot express
    who may see it. The default is the safe one.
    """
    fleet_health = get_fleet_health(now, scope=scope)
    recent_events, recent_events_failed = _read_recent_events(
        scope=scope,
        reference=now or datetime.now(timezone.utc),
        event_limit=event_limit,
        include_unregistered=include_unregistered,
    )
    # Labels only (ADR-008) - every Plant-level number and the ranking order
    # come from fleet_health above. Scoped like every other read so an
    # out-of-scope plant name can never surface (ADR-004).
    plant_names = {p.plant_id: p.name for p in list_plants(scope=scope)}

    ranked_locations = _affected_locations(fleet_health, plant_names)

    counts = fleet_health.counts
    monitored = fleet_health.device_count
    stale = counts.get(Freshness.STALE, 0)
    no_data = counts.get(Freshness.NO_DATA, 0)
    attention = stale + no_data

    return CommandCenterSnapshot(
        fleet_health=fleet_health,
        recent_events=recent_events,
        recent_events_failed=recent_events_failed,
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
        affected_locations=ranked_locations,
        selected_location=_selected_location(
            fleet_health,
            plant_names,
            _resolve_selected_plant(fleet_health, ranked_locations, selected_plant_id),
            scope,
        ),
    )
