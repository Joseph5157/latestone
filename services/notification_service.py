"""
Notification service — builds notification rows from existing frontend data.

Owns the formal >24h no-data notification rule (BR008), which is deliberately
separate from the freshness STALE threshold. Current STALE logic must NOT be
renamed or treated as the formal >24h notification condition.

All functions are pure and testable without Dash, database, or identity system.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.notifications import CATEGORIES, derivable_categories
from routes import device_href

#: Formal business rule: RTL failed to send data for more than 24 hours (BR008).
#: This is NOT the same as the STALE threshold in config.settings.monitoring.
NO_DATA_NOTIFICATION_AFTER = timedelta(hours=24)


@dataclass(frozen=True)
class NotificationRow:
    """One notification row for the Notification Center table."""

    key: str
    entity_id: str
    entity_label: str
    entity_type: str
    notification_type: str
    detail: str
    occurred_at: datetime | None
    href: str
    # A notification may be derived from freshness or from a persisted event.
    # Only the latter can carry this internal acknowledgement lifecycle.
    event_id: int | None = None
    acknowledgement_state: str | None = None
    acknowledged_at: datetime | None = None


def _device_label(device_id: str, device_code: str | None = None) -> str:
    """Human-readable device label."""
    if device_code:
        return f"{device_code} ({device_id})"
    return device_id


def build_no_data_notifications(
    rows,
    now: datetime | None = None,
) -> list[NotificationRow]:
    """Build >24h no-data notification rows from latest-reading data.

    Uses the formal BR008 rule: active RTL has failed to send data for more
    than 24 hours. This is deliberately separate from the STALE threshold.

    Rules:
    - Only active devices are considered (already filtered by repository).
    - Last reading older than 24h → notification row.
    - Never-reported devices (reading_ts is None) are excluded unless we can
      establish they have been active for >24h. Since the current system has
      no activation/start timestamp, never-reported devices are labeled as
      current frontend NO_DATA, not formal BR008 notification.
    - One row per affected device (no duplicates at plant/transformer level).
    """
    reference = now or datetime.now(timezone.utc)

    # Group by device, find the worst (oldest) reading timestamp
    device_latest: dict[str, datetime | None] = {}
    device_plant: dict[str, str] = {}
    device_transformer: dict[str, str] = {}
    device_code: dict[str, str | None] = {}

    for row in rows:
        device_id = row.device_id
        device_plant[device_id] = row.plant_id
        device_transformer[device_id] = getattr(row, "transformer_id", "")
        if hasattr(row, "device_code"):
            device_code[device_id] = row.device_code

        if row.reading_ts is not None:
            current = device_latest.get(device_id)
            if current is None or row.reading_ts > current:
                device_latest[device_id] = row.reading_ts

    notifications: list[NotificationRow] = []
    for device_id, last_reading in sorted(device_latest.items()):
        # Never-reported devices: exclude from formal >24h notification
        if last_reading is None:
            continue

        # Check if reading is older than 24 hours
        age = reference - last_reading
        if age > NO_DATA_NOTIFICATION_AFTER:
            code = device_code.get(device_id)
            notifications.append(
                NotificationRow(
                    key=f"no_data_24h:{device_id}",
                    entity_id=device_id,
                    entity_label=_device_label(device_id, code),
                    entity_type="Device",
                    notification_type=">24h No Data",
                    detail=(
                        f"Last reading {last_reading.strftime('%Y-%m-%d %H:%M UTC')} "
                        f"({age.days}d {age.seconds // 3600}h ago)"
                    ),
                    occurred_at=last_reading,
                    href=device_href(device_id),
                )
            )

    return notifications


def build_current_notifications(
    rows,
    now: datetime | None = None,
) -> list[NotificationRow]:
    """Build all currently derivable notification rows.

    Combines formal >24h no-data notifications with any other categories
    that can be derived from current frontend data.
    """
    reference = now or datetime.now(timezone.utc)
    notifications: list[NotificationRow] = []

    # Only derive from categories that are currently supported
    for category in derivable_categories():
        if category.key == "no_data_24h":
            notifications.extend(build_no_data_notifications(rows, reference))

    return notifications


def current_notifications(
    *,
    reading_rows,
    scope,
    include_unregistered: bool = False,
    now: datetime | None = None,
) -> list[NotificationRow]:
    """The Notification Center's full derivation: BR008 + persisted events.

    Composition point (EVT-D3, simplified per review): the BR008 builder
    above keeps deriving from latest readings exactly as before; persisted
    device_events flow through services/event_semantics — the single owner
    of event meaning (EVT-D1) — and the two row sets merge here. Category
    availability is determined by the semantics registry itself, NOT by a
    new category capability flag.

    ``include_unregistered`` is the admin-only gate for quarantined
    invalid_uid rows (EVT-D5): an unregistered UID belongs to no device
    scope, so technicians and general users never receive those rows.

    Operator-facing order (ENT-4): this function is the SINGLE ordering
    authority — newest event first, stable key ascending as tiebreak. The
    individual builders keep their own deterministic internal order, but
    only the merged result here defines what the operator scans.
    """
    reference = now or datetime.now(timezone.utc)
    notifications = build_current_notifications(reading_rows, reference)

    # Deferred import: event_semantics imports NotificationRow from this
    # module, keeping the dependency one-way at import time.
    from repositories import plant_monitoring_repository as repo
    from services.event_semantics import (
        NOTIFICATION_QUERY_LIMIT,
        build_event_notifications,
        mapped_event_types,
    )

    # No ``since`` bound: Notification Center events do not expire (review
    # correction to EVT-D8). NOTIFICATION_QUERY_LIMIT is a technical
    # pilot-safety capacity bound on the query, never a retention rule.
    events = repo.list_recent_device_events(
        event_types=mapped_event_types(),
        allowed_device_ids=scope.device_ids,
        include_unattributed=include_unregistered,
        limit=NOTIFICATION_QUERY_LIMIT,
    )
    notifications.extend(
        build_event_notifications(events, include_unregistered=include_unregistered)
    )
    return newest_first(notifications)


def newest_first(rows: list[NotificationRow]) -> list[NotificationRow]:
    """The one operator-facing order: occurred_at DESC, stable key ASC.

    A 20-minute-old battery event outranks a 3-day-old no-data row — row
    position answers "what happened most recently". The key tiebreak keeps
    the order deterministic across refreshes when two rows share a
    timestamp. Rows without a timestamp (none exist today) sort last rather
    than crashing the sort.
    """
    return sorted(
        rows,
        key=lambda n: (
            n.occurred_at is None,                       # undated last
            -(n.occurred_at.timestamp()) if n.occurred_at else 0.0,
            n.key,
        ),
    )


def notification_summary(notifications: list[NotificationRow]) -> dict:
    """Build summary statistics for the Notification Center.

    ``by_type`` counts by category label; rendering order is the caller's
    concern (the callback walks the configured category order so the summary
    can never imply priority by count).
    """
    by_type: dict[str, int] = {}
    for n in notifications:
        by_type[n.notification_type] = by_type.get(n.notification_type, 0) + 1
    return {
        "total": len(notifications),
        "by_type": by_type,
    }


def summary_category_order() -> tuple[str, ...]:
    """Labels in configured category order, unregistered UID appended.

    The summary walks THIS order so it can never imply priority by count
    (ENT-4 gate decision): the sequence is the spec-frozen category order
    from config, and the admin-only quarantine surface reads last when
    present.

    FS-ALARM-1 / BR009: delegates to ``event_semantics.summary_notification_
    labels`` rather than reading category labels directly, because a
    ``power_down``/``sensor_error`` row's actual ``notification_type`` is
    now the collapsed "Comms Alarm" label (BR009) — walking the raw
    per-category label list here would silently drop those counts from the
    summary line while the table still shows the rows.
    """
    from services.event_semantics import (
        UNREGISTERED_NOTIFICATION_TYPE,
        summary_notification_labels,
    )

    return summary_notification_labels() + (UNREGISTERED_NOTIFICATION_TYPE,)
