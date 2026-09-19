"""Simulated RTL events for the live simulator (DATA-REFRESH-1).

SYNTHETIC DEVELOPMENT DATA. Nothing here came from a real RTL.

Planning is pure (`plan_events`, seeded `random.Random`) so it is testable
without a database. Emission (`emit_planned`) goes through
`services.simulated_event_source.emit()` -> `ingest_event()` only — the
canonical boundary (ADR-007, ADR-019). The voltages below are the payload a
device reports alongside an event it has ALREADY classified; nothing
downstream evaluates them (ADR-001).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from config.events import (
    EVENT_TYPE_BATTERY_LOW,
    EVENT_TYPE_CHECK_IN,
    EVENT_TYPE_POWER_DOWN,
    EVENT_TYPE_SENSOR_ERROR,
    EVENT_TYPE_STARTUP,
)

#: Relative weights. Routine traffic (check-in) dominates; power-down and
#: sensor errors are rarer.
EVENT_MIX: tuple[tuple[str, float], ...] = (
    (EVENT_TYPE_CHECK_IN, 0.40),
    (EVENT_TYPE_BATTERY_LOW, 0.25),
    (EVENT_TYPE_POWER_DOWN, 0.15),
    (EVENT_TYPE_STARTUP, 0.10),
    (EVENT_TYPE_SENSOR_ERROR, 0.10),
)

#: Out of the sensor's range (BR013) — the same value db/seed_events_demo.py uses.
SENSOR_ERROR_TEMPERATURE = 512.0


@dataclass(frozen=True)
class PlannedEvent:
    event_type: str
    device_id: str
    event_ts: datetime
    battery_voltage: float | None = None
    temperature: float | None = None


def _payload(rng: random.Random, event_type: str) -> dict:
    if event_type == EVENT_TYPE_BATTERY_LOW:
        return {"battery_voltage": round(rng.uniform(3.62, 3.74), 2)}
    if event_type == EVENT_TYPE_POWER_DOWN:
        return {"battery_voltage": round(rng.uniform(3.45, 3.60), 2)}
    if event_type == EVENT_TYPE_SENSOR_ERROR:
        return {"temperature": SENSOR_ERROR_TEMPERATURE}
    return {}


def plan_events(
    rng: random.Random,
    device_ids: Sequence[str],
    start: datetime,
    end: datetime,
    events_per_day: float,
) -> list[PlannedEvent]:
    """Events for the window [start, end), sorted by time.

    The count is the expected number for the window, with the fractional
    part decided by one draw — so a 5-minute tick at 12/day yields 0 or 1,
    and a 7-day window at 12/day yields exactly 84.
    """
    if events_per_day <= 0 or not device_ids or end <= start:
        return []
    window = end - start
    expected = events_per_day * window.total_seconds() / 86400.0
    count = math.floor(expected)
    if rng.random() < expected - count:
        count += 1
    types = [t for t, _ in EVENT_MIX]
    weights = [w for _, w in EVENT_MIX]
    devices = list(device_ids)
    planned = []
    for _ in range(count):
        event_type = rng.choices(types, weights)[0]
        planned.append(
            PlannedEvent(
                event_type=event_type,
                device_id=rng.choice(devices),
                event_ts=start + window * rng.random(),
                **_payload(rng, event_type),
            )
        )
    return sorted(planned, key=lambda e: e.event_ts)
