"""Event semantics — the single mapping from persisted event facts to
consumer-facing meaning (EVT-D1).

Layering:

    config/events.py            canonical event NAMES
    config/notifications.py     notification category LABELS (spec-frozen)
    services/event_semantics.py THIS MODULE — the binding between them

Notification Center, report projections and any future delivery code read
the mappings below; none of them may contain its own ``"battery_low"``-
style interpretation (EVT-D1), a numeric threshold (EVT-D4 — an incoming
``battery_low`` row is already a classified fact; ``battery_voltage`` is
display payload only), or forwarding-recipient logic (EVT-D7 deferred:
this module records WHICH types are forwarding-relevant and nothing more).

High-temperature and vibration_event deliberately have NO entry: their
domain rules are client-clarification items, so they are structurally
absent rather than disabled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_INVALID_UID,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)
from config.notifications import get_category
from routes import device_href
from services.notification_service import NotificationRow

#: Notification categories used by the mapping. Keys must match
#: config.notifications.CATEGORIES exactly (asserted by tests).
CATEGORY_BATTERY_ALARM = "battery_alarm"
CATEGORY_POWER_DOWN = "power_down"
CATEGORY_SENSOR_ERROR = "sensor_error"
CATEGORY_STARTUP_CHECKIN = "startup_checkin"

#: How far back the REP-01 alarm projection looks. This is the client-
#: confirmed "RTL Alarms (30 Days)" report horizon and belongs ONLY to
#: that report surface (EVT-D6). It is NOT a notification-retention rule:
#: the Notification Center applies no time window at all — an event-backed
#: notification never expires merely because REP-01 is a 30-day report.
ALARM_REPORT_WINDOW = timedelta(days=30)

#: Technical pilot-safety bound on Notification Center event queries:
#: pure implementation capacity, NOT product semantics. Not named as
#: retention, not derived from any report horizon, and it can never be
#: represented as "notifications expire". The semantic rule stays: latest
#: persisted relevant event per (device, category), count/detail derived
#: from the queried history.
NOTIFICATION_QUERY_LIMIT = 500

#: Display label for quarantined unregistered UIDs (EVT-D5). Not a
#: config.notifications category: that list is spec-frozen and this
#: surface is a development-scope default pending a client answer.
UNREGISTERED_NOTIFICATION_TYPE = "Unregistered UID"


@dataclass(frozen=True)
class EventSemantics:
    """What one persisted event type means to consumers."""

    #: config.notifications key for Notification Center rows; None means
    #: the type has no notification surface.
    notification_category_key: str | None
    #: Whether rows of this type belong in the REP-01 alarm projection.
    is_reportable_alarm: bool
    #: EVT-D7: classification ONLY. Who receives a forwarded startup /
    #: check-in is deferred to the forwarding-delivery planning slice.
    forwarding_relevant: bool
    #: The event TYPE's human name, in the EVENT's own vocabulary — not the
    #: notification category's. ``battery_low`` is "Battery Low" here and
    #: "Battery Alarm" as a category (config/notifications.py); both are
    #: right for their own surface, and flattening them would misname one.
    #: Defaulted so an unmapped type stays inert; every mapped type supplies
    #: one and a test enforces that.
    display_label: str | None = None


_SEMANTICS: dict[str, EventSemantics] = {
    EVENT_TYPE_BATTERY_LOW: EventSemantics(
        notification_category_key=CATEGORY_BATTERY_ALARM,
        is_reportable_alarm=True,
        forwarding_relevant=False,
        display_label="Battery Low",
    ),
    EVENT_TYPE_POWER_DOWN: EventSemantics(
        notification_category_key=CATEGORY_POWER_DOWN,
        is_reportable_alarm=True,
        forwarding_relevant=False,
        display_label="Power Down",
    ),
    EVENT_TYPE_SENSOR_ERROR: EventSemantics(
        notification_category_key=CATEGORY_SENSOR_ERROR,
        is_reportable_alarm=True,
        forwarding_relevant=False,
        display_label="Sensor Error",
    ),
    EVENT_TYPE_STARTUP: EventSemantics(
        notification_category_key=CATEGORY_STARTUP_CHECKIN,
        is_reportable_alarm=False,
        forwarding_relevant=True,
        display_label="Startup",
    ),
    EVENT_TYPE_CHECK_IN: EventSemantics(
        notification_category_key=CATEGORY_STARTUP_CHECKIN,
        is_reportable_alarm=False,
        forwarding_relevant=True,
        display_label="Check-In",
    ),
    # Quarantine surface only (EVT-D5); never an alarm, never forwarded.
    EVENT_TYPE_INVALID_UID: EventSemantics(
        notification_category_key=None,
        is_reportable_alarm=False,
        forwarding_relevant=False,
        display_label="Invalid UID",
    ),
}

_DEFAULT_SEMANTICS = EventSemantics(
    notification_category_key=None,
    is_reportable_alarm=False,
    forwarding_relevant=False,
)


def semantics_for(event_type: str) -> EventSemantics:
    """The frozen meaning of one event type; unknown types are inert.

    Open-vocabulary persistence (INGEST-D7) means unknown names can be
    stored at any time; they simply have no consumer behaviour yet.
    """
    return _SEMANTICS.get(event_type, _DEFAULT_SEMANTICS)


def display_label_for(event_type: str) -> str:
    """The event type's human name.

    Falls back to the RAW TYPE for an unmapped name rather than hiding the
    row or inventing a label: open-vocabulary persistence (INGEST-D7) means
    an unknown type can be stored at any time, and an operator is better
    served by ``some_future_type`` than by a blank cell or a guess.
    """
    return semantics_for(event_type).display_label or event_type


def mapped_event_types() -> tuple[str, ...]:
    """Every type with ANY consumer mapping — the repository query's
    ``event_types`` argument."""
    return tuple(_SEMANTICS.keys())


def notification_backed_event_types() -> tuple[str, ...]:
    """Types that surface as Notification Center rows."""
    return tuple(
        event_type
        for event_type, semantics in _SEMANTICS.items()
        if semantics.notification_category_key is not None
    )


def _category_label(category_key: str) -> str:
    category = get_category(category_key)
    if category is None:  # pragma: no cover - guarded by tests
        raise ValueError(f"Unknown notification category {category_key!r}")
    return category.label


def alarm_label_for_event_type(event_type: str) -> str:
    """The report-facing alarm label for one event type (R3-D5).

    Single-sourced through the same semantics → category mapping as
    notifications, so report code never spells out "Battery Alarm" etc.
    itself. Raises for non-alarm types — callers must have filtered via
    ``is_reportable_alarm`` first.
    """
    semantics = semantics_for(event_type)
    if (
        not semantics.is_reportable_alarm
        or semantics.notification_category_key is None
    ):
        raise ValueError(f"{event_type!r} is not a reportable alarm type.")
    return _category_label(semantics.notification_category_key)


def reportable_alarm_event_types() -> tuple[str, ...]:
    """Exactly the types the REP-01 alarm report includes (R3-D1)."""
    return tuple(
        event_type
        for event_type, semantics in _SEMANTICS.items()
        if semantics.is_reportable_alarm
    )


def build_event_notifications(
    events,
    *,
    include_unregistered: bool = False,
) -> list[NotificationRow]:
    """Derive Notification Center rows from persisted events.

    Semantic rule (EVT-D8, corrected per review): the latest persisted
    relevant event per (device, category), keyed ``{category}:{device_id}``
    with the count of queried events in the detail — NO time window, no
    expiry/retention/acknowledgement/suppression rule. An event-backed
    notification never disappears merely because REP-01 is a 30-day
    report. Unregistered UIDs have no device, so their stable key uses the
    normalized reported_uid instead — unknown UIDs are never collapsed
    into one global row.
    """

    @dataclass
    class _Bucket:
        label: str
        entity_id: str
        entity_label: str
        href: str
        notification_type: str
        latest: object
        count: int = 0
        battery_voltage: float | None = None

    buckets: dict[str, _Bucket] = {}
    for event in events:
        if event.device_id is None:
            # Quarantined unregistered UID (EVT-D5): admin-only visibility
            # is decided by the CALLER via include_unregistered; this
            # function only renders what it is given.
            if event.reported_uid is None or not include_unregistered:
                continue
            key = f"unregistered_uid:{event.reported_uid}"
            bucket = _Bucket(
                label=UNREGISTERED_NOTIFICATION_TYPE,
                entity_id=event.reported_uid,
                entity_label=event.reported_uid,
                href="",                      # no device page to link
                notification_type=UNREGISTERED_NOTIFICATION_TYPE,
                latest=event,
            )
            entity_type = "Unregistered UID"
        else:
            semantics = semantics_for(event.event_type)
            category_key = semantics.notification_category_key
            if category_key is None:
                continue          # inert type: persisted, never rendered
            key = f"{category_key}:{event.device_id}"
            bucket = _Bucket(
                label=_category_label(category_key),
                entity_id=event.device_id,
                entity_label=event.device_id,
                href=device_href(event.device_id),
                notification_type=_category_label(category_key),
                latest=event,
            )
            entity_type = "Device"

        existing = buckets.get(key)
        if existing is None:
            buckets[key] = bucket
        else:
            bucket = existing
        bucket.count += 1
        if event.event_ts > bucket.latest.event_ts:
            bucket.latest = event
        if event.battery_voltage is not None:
            bucket.battery_voltage = event.battery_voltage

    rows: list[NotificationRow] = []
    for key in sorted(buckets):
        b = buckets[key]
        latest_ts = b.latest.event_ts
        detail = (
            f"{b.count} event(s); "
            f"latest {latest_ts.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        if b.battery_voltage is not None:
            detail += f"; battery {b.battery_voltage:.2f} V"
        rows.append(
            NotificationRow(
                key=key,
                entity_id=b.entity_id,
                entity_label=b.entity_label,
                entity_type=(
                    "Device"
                    if b.latest.device_id is not None
                    else "Unregistered UID"
                ),
                notification_type=b.notification_type,
                detail=detail,
                occurred_at=latest_ts,
                href=b.href,
            )
        )
    return rows


@dataclass(frozen=True)
class AlarmEventProjection:
    """Typed REP-01 domain contract (EVT-D6) — facts only, no UI wiring.

    One projection per reportable alarm EVENT (reports are records; the
    collapsing in build_event_notifications is presentation-only). The
    client's OU/Zone/Sector/CNC/Feeder taxonomy has no confirmed mapping
    yet, so those fields stay None per REPORT-2 precedent (R2-D2).
    ``alarm_at`` is the source occurrence time (EVT-D9).
    """

    ou: None = field(default=None, init=False)
    zone: None = field(default=None, init=False)
    sector: None = field(default=None, init=False)
    cnc: None = field(default=None, init=False)
    feeder_name: None = field(default=None, init=False)

    transformer_id: str
    uid: str | None
    alarm_label: str
    alarm_at: datetime
    temperature: float | None
    battery_voltage: float | None
    firmware_version: str | None
    event_id: int


def alarm_event_projections(
    events, device_metadata=None, *, now: datetime | None = None
) -> list[AlarmEventProjection]:
    """Project persisted alarm events onto the REP-01 column contract.

    Bounded by ALARM_REPORT_WINDOW — the client-confirmed "RTL Alarms
    (30 Days)" horizon. That window belongs to THIS report surface only;
    the Notification Center applies no time bound whatsoever.

    ``device_metadata`` optionally maps device_id → object exposing
    ``device_code`` / ``firmware_version`` (e.g. repo DeviceRecord); events
    without resolvable metadata still project, with uid/firmware None —
    an exporter added later can distinguish "unmapped" honestly.
    """
    reference = now or datetime.now(timezone.utc)
    cutoff = reference - ALARM_REPORT_WINDOW
    metadata = device_metadata or {}
    projections: list[AlarmEventProjection] = []
    for event in sorted(events, key=lambda e: (e.event_ts, e.event_id)):
        if event.event_ts < cutoff:
            continue      # outside the REP-01 30-day report horizon
        semantics = semantics_for(event.event_type)
        if not semantics.is_reportable_alarm:
            continue
        if event.device_id is None:
            continue      # alarms belong to registered devices only
        record = metadata.get(event.device_id)
        projections.append(
            AlarmEventProjection(
                transformer_id=event.transformer_id or "",
                uid=getattr(record, "device_code", None),
                alarm_label=_category_label(semantics.notification_category_key),
                alarm_at=event.event_ts,
                temperature=event.temperature,
                battery_voltage=event.battery_voltage,
                firmware_version=getattr(record, "firmware_version", None),
                event_id=event.event_id,
            )
        )
    return projections


__all__ = [
    "ALARM_REPORT_WINDOW",
    "AlarmEventProjection",
    "EventSemantics",
    "NOTIFICATION_QUERY_LIMIT",
    "UNREGISTERED_NOTIFICATION_TYPE",
    "alarm_event_projections",
    "alarm_label_for_event_type",
    "build_event_notifications",
    "display_label_for",
    "mapped_event_types",
    "notification_backed_event_types",
    "reportable_alarm_event_types",
    "semantics_for",
]
