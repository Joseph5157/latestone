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
from services.monitoring_service import Freshness, evaluate_freshness
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


def notification_summary(notifications: list[NotificationRow]) -> dict:
    """Build summary statistics for the Notification Center."""
    return {
        "total": len(notifications),
        "by_type": {},  # Future: group by notification_type if needed
    }
