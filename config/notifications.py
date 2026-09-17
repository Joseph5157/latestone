"""
Notification categories — frontend source of truth.

Confirmed by the RTL Functional Specification (§3, §11, doc ID 240-137264801).
Each category specifies whether current frontend data supports derivation.

These are schema/definition definitions only. No event data is fabricated.
The backend notification service, when available, must populate these categories.

FS-ALARM-1 / BR009: a category's ``label`` here is its own descriptive
identity (used for bucketing, ordering and the summary line) — it is NOT
automatically the alarm's client-facing notification text. BR009 governs
only two client-facing alarm labels ("Battery Alarm" / "Comms Alarm"); that
narrower mapping lives in ``services/event_semantics.py``
(``EventSemantics.alarm_notification_label``), which a ``power_down``/
``sensor_error`` row now resolves to instead of this category's own label.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationCategory:
    key: str
    label: str
    description: str
    derivable_from_frontend_data: bool
    backend_required: bool


CATEGORIES: tuple[NotificationCategory, ...] = (
    NotificationCategory(
        key="no_data_24h",
        label=">24h No Data",
        description=(
            "RTL device has failed to send data for more than 24 hours "
            "(BR008). Derived from latest reading timestamps."
        ),
        derivable_from_frontend_data=True,
        backend_required=False,
    ),
    NotificationCategory(
        key="battery_alarm",
        label="Battery Alarm",
        description=(
            "Battery voltage below 3.75 V (BR002). "
            "Requires Battery(V) data not currently available in frontend."
        ),
        derivable_from_frontend_data=False,
        backend_required=True,
    ),
    NotificationCategory(
        key="power_down",
        label="Power Down",
        description=(
            "Battery voltage below 3.61 V, device entering power-down mode (BR002, BR011). "
            "Requires Battery(V) data not currently available in frontend."
        ),
        derivable_from_frontend_data=False,
        backend_required=True,
    ),
    NotificationCategory(
        key="sensor_error",
        label="Sensor Error",
        description=(
            "Erroneous temperature reading outside sensor range (BR013, BR014). "
            "Requires sensor error state not currently exposed in frontend."
        ),
        derivable_from_frontend_data=False,
        backend_required=True,
    ),
    NotificationCategory(
        key="startup_checkin",
        label="Startup / Check-In",
        description=(
            "RTL device switched on or sent check-in message (BR010). "
            "Requires event history not currently available in frontend."
        ),
        derivable_from_frontend_data=False,
        backend_required=True,
    ),
    NotificationCategory(
        key="message_forwarding",
        label="Message Forwarding",
        description=(
            "Message forwarding enabled/disabled state (BR003, BR004, BR016). "
            "Operational workflow; not a notification row in the formal sense."
        ),
        derivable_from_frontend_data=False,
        backend_required=True,
    ),
)

_CATEGORIES_BY_KEY: dict[str, NotificationCategory] = {c.key: c for c in CATEGORIES}


def get_category(key: str) -> NotificationCategory | None:
    """Look up a notification category by key."""
    return _CATEGORIES_BY_KEY.get(key)


def all_categories() -> tuple[NotificationCategory, ...]:
    """All confirmed notification categories."""
    return CATEGORIES


def derivable_categories() -> tuple[NotificationCategory, ...]:
    """Categories that can be derived from current frontend data."""
    return tuple(c for c in CATEGORIES if c.derivable_from_frontend_data)


def backend_required_categories() -> tuple[NotificationCategory, ...]:
    """Categories that require backend/event data."""
    return tuple(c for c in CATEGORIES if c.backend_required)
