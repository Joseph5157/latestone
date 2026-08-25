"""Device/transformer event vocabulary (INGEST-1).

Constants only — no logic. Deliberately separate from ``config.audit``,
which is exclusively the audit operation/entity vocabulary: notification
and report consumers will need these names later without depending on the
ingestion service.

``device_events.event_type`` is intentionally VARCHAR(30) with NO CHECK
constraint (alembic/versions/006_device_events.py documents the rationale:
a legitimate new event type must not require a migration). This module is
NOT a closed allowlist — it names only the event types that INGEST-1 gives
explicit meaning to:

- EVENT_TYPE_STARTUP      the only type with a domain side effect (ACT-D1:
                          resolved startup drives rtl_active_state activation)
- EVENT_TYPE_INVALID_UID  the storage type for an unresolvable reported UID
                          (legacy invalid_uid_log replacement, migration 006)

Every other known legacy value (check_in, sensor_error, battery_low,
power_down, comms_alarm, high_temperature, vibration_event) persists via
the same canonical service with no behaviour attached yet (INGEST-D7).
All constants must stay within the column's VARCHAR(30) limit.
"""
from __future__ import annotations

#: Startup message — RTL switched on. Drives active-list activation when
#: it resolves to a registered device (ACT-D1..D4); a no-op on an already-
#: active device apart from the persisted history row (ACT-D3).
EVENT_TYPE_STARTUP = "startup"

#: Storage classification for an event whose reported UID matches no
#: registered device. The raw reported UID is preserved in
#: ``device_events.reported_uid``; ``device_id`` stays NULL.
EVENT_TYPE_INVALID_UID = "invalid_uid"

#: Further legacy-vocabulary names (migration 006) that consumers bind
#: semantics to. Defining a name here grants it NO behaviour — behaviour
#: exists only where services/event_semantics.py maps it.
EVENT_TYPE_CHECK_IN = "check_in"
EVENT_TYPE_BATTERY_LOW = "battery_low"
EVENT_TYPE_POWER_DOWN = "power_down"
EVENT_TYPE_SENSOR_ERROR = "sensor_error"


__all__ = [
    "EVENT_TYPE_BATTERY_LOW",
    "EVENT_TYPE_CHECK_IN",
    "EVENT_TYPE_INVALID_UID",
    "EVENT_TYPE_POWER_DOWN",
    "EVENT_TYPE_SENSOR_ERROR",
    "EVENT_TYPE_STARTUP",
]
