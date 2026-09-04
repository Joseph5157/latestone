"""Simulated incoming device-event source (RTL-IF-3).

    simulated device event
            v
    NormalizedEvent                    (services/device_event_service.py)
            v
    device_event_service.ingest_event()  (canonical boundary, INGEST-1I — unchanged)
            v
    existing persistence/projections    (device_events, rtl_active_state)
            v
    existing notification/event/report consumers  (unchanged)

This module builds `NormalizedEvent` instances and submits them through the
**existing** `ingest_event()` boundary — it is not a second event store, not
a second alarm pipeline, and it adds no persistence, projection, or
consumer logic of its own. Every behaviour a simulated event exercises
(identity resolution, append-only persistence, startup activation,
audit) is `device_event_service.ingest_event()`'s, unchanged.

**Distinct from `services/simulator_transport.py`** (RTL-IF-2), which is
the opposite direction:

    SimulatorTransport      = outgoing command execution simulation
                               (an authorized PROGRAM RTL command, dispatched
                               through a deterministic transport)
    simulated event source  = incoming device-event simulation
                               (this module — a device "sending" startup,
                               check-in, or alarm events INTO the system)

Both are internal test/demo foundations. Neither defines or claims an
Eskom wire payload, MQTT topic, or any real transport format.

**`SUPPORTED_EVENT_TYPES` is a simulator-only restriction, not a change to
the canonical service's vocabulary policy.** `device_event_service.
ingest_event()` still accepts any `event_type` string (INGEST-D7, open
vocabulary, no CHECK constraint — `alembic/versions/006_device_events.py`);
this module simply refuses to *originate* a simulated event outside the
five types RTL-IF-3 inspected and confirmed already carry real meaning in
`config/events.py`/`services/event_semantics.py`. A test calling
`device_event_service.ingest_event()` directly with an unlisted type still
succeeds exactly as it did before this tranche — only `emit()` here is
narrower than the service it calls.
"""
from __future__ import annotations

from datetime import datetime

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)
from services.device_event_service import IngestResult, NormalizedEvent, ingest_event

#: Every event type this simulator may originate. Chosen by inspecting
#: config/events.py FIRST (RTL-IF-3 section 3) — these are exactly its five
#: named constants, nothing invented. EVENT_TYPE_INVALID_UID is deliberately
#: absent: it is not something a device ever declares itself as — it is the
#: canonical service's OWN reclassification of an unresolvable reported_uid
#: (services/device_event_service.py's `_resolve_identity`), exercised by
#: sending a startup/check-in/etc with an unregistered `reported_uid`, never
#: emitted directly.
SUPPORTED_EVENT_TYPES = (
    EVENT_TYPE_STARTUP,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
)


class UnsupportedSimulatedEventType(Exception):
    """Refused before any NormalizedEvent is built or submitted: the
    requested event_type is not in SUPPORTED_EVENT_TYPES.

    This is a simulator-boundary refusal, not a canonical-service one — see
    the module docstring. It exists so a test or future demo caller cannot
    accidentally originate a simulated event type nobody has confirmed the
    application actually understands.
    """


def emit(event_type: str, *, event_ts: datetime, **kwargs) -> IngestResult:
    """Build one NormalizedEvent for a supported ``event_type`` and submit
    it through ``device_event_service.ingest_event()`` — the exact same
    validation, identity resolution, persistence and projection any other
    caller gets. No shortcut, no pre-trusted flag.

    ``**kwargs`` forwards directly to ``NormalizedEvent`` (device_id,
    transformer_id, reported_uid, severity, temperature, battery_voltage,
    message, source) — this function adds no fields of its own and applies
    no default trust: an untrusted/malformed value here fails exactly where
    it would fail for any other caller of ``ingest_event()``, inside its
    canonical `_validate()`.
    """
    if event_type not in SUPPORTED_EVENT_TYPES:
        raise UnsupportedSimulatedEventType(
            f"{event_type!r} is not a supported simulated event type; "
            f"choose one of {SUPPORTED_EVENT_TYPES!r}."
        )
    event = NormalizedEvent(event_type=event_type, event_ts=event_ts, **kwargs)
    return ingest_event(event)


def emit_startup(*, event_ts: datetime, **kwargs) -> IngestResult:
    """A simulated RTL startup message.

    Resolved against a registered device, this exercises the existing
    rtl_active_state activation projection exactly as any real startup
    would (RTL-IF-3 section 4) — this module adds no separate activation
    path. An unregistered ``reported_uid`` quarantines as invalid_uid per
    existing behaviour (section 6), unchanged.
    """
    return emit(EVENT_TYPE_STARTUP, event_ts=event_ts, **kwargs)


def emit_check_in(*, event_ts: datetime, **kwargs) -> IngestResult:
    """A simulated RTL check-in message. No activation side effect —
    only EVENT_TYPE_STARTUP drives rtl_active_state (INGEST-1's own rule,
    unchanged here)."""
    return emit(EVENT_TYPE_CHECK_IN, event_ts=event_ts, **kwargs)


def emit_battery_low(*, event_ts: datetime, **kwargs) -> IngestResult:
    """A simulated Battery Low event. No voltage-threshold evaluation
    happens here or anywhere in this tranche — the simulator emits the
    already-classified event type directly (RTL-IF-3 section 8); it does
    not convert an arbitrary voltage reading into an alarm decision."""
    return emit(EVENT_TYPE_BATTERY_LOW, event_ts=event_ts, **kwargs)


def emit_power_down(*, event_ts: datetime, **kwargs) -> IngestResult:
    """A simulated Power Down event — same non-threshold-evaluating
    contract as emit_battery_low."""
    return emit(EVENT_TYPE_POWER_DOWN, event_ts=event_ts, **kwargs)


def emit_sensor_error(*, event_ts: datetime, **kwargs) -> IngestResult:
    """A simulated Sensor Error event."""
    return emit(EVENT_TYPE_SENSOR_ERROR, event_ts=event_ts, **kwargs)


__all__ = [
    "SUPPORTED_EVENT_TYPES",
    "UnsupportedSimulatedEventType",
    "emit",
    "emit_battery_low",
    "emit_check_in",
    "emit_power_down",
    "emit_sensor_error",
    "emit_startup",
]
