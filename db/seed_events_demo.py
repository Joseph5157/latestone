"""
Operational-event demo seed — synthetic device events for visual verification.

DEVELOPMENT / DEMO DATA. Every event this module creates is invented. No RTL
actually powered down, no battery is actually low, and none of it comes from
the client. It exists so the Command Center's Recent Operational Events panel
(and the Notification Center behind it) can be looked at against
representative activity instead of an empty table.

DELIBERATELY SEPARATE FROM THE MONITORING SEED, and opt-in:

    python -m db.seed_plant_monitoring --reset   plants/transformers/devices/readings
    python -m db.seed_admin_demo --reset         technicians/assignments
    python -m db.seed_events_demo                device events

The monitoring seed describes equipment, which is a claim about what exists.
This one describes incidents, which is a claim that things went wrong. A
developer refreshing readings must never silently acquire an incident history.

IT GOES THROUGH THE CANONICAL BOUNDARY, NOT AROUND IT:

    demo fixture -> device_event_service.ingest_event()
                 -> existing validation (INGEST-D1/D4)
                 -> existing identity resolution (INGEST-D2)
                 -> existing persistence (INGEST-D3)

never `repo.insert_device_event()` directly (ADR-007). Two consequences worth
stating plainly rather than discovering later:

- The unregistered UID below is NOT declared as `invalid_uid`. It is sent as
  an ordinary event carrying a UID that matches no device, and the existing
  resolution retypes it. That is the only way to seed a quarantine row that
  is genuinely the same shape as a real one.
- A `startup` event ACTIVATES its RTL and writes a system-originated audit
  row (ACT-D1..D5). That is what a real startup does, so it is what this
  does. It is a real state change, from a script that says DEMO on the tin.

APPEND-ONLY, SO THERE IS NO `--reset`. Event persistence is append-only by
contract (INGEST-D3); a seed that deleted events would be modelling something
the ingestion path cannot do. Re-running is refused instead unless `--again`
is passed, so a second run is a decision rather than an accident.

NEVER RUN THIS AGAINST PRODUCTION.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from repositories.plant_monitoring_repository import list_recent_device_events
from services import event_semantics
from services.device_event_service import IngestError, NormalizedEvent, ingest_event
from services.hierarchy_service import list_all_devices

#: Stamped on every event this module creates, so a reader of the raw table
#: can tell demo activity from anything a real transport ever delivers.
#: `device_events.source` is VARCHAR(30).
DEMO_SOURCE = "demo_seed"

#: A UID chosen to match no registered device. Real device codes in this
#: fleet are five digits (29001..), so an eight-digit value cannot collide
#: with one, and the resolution quarantines it as `invalid_uid`.
UNREGISTERED_UID = "99000042"


class DemoSeedRefused(RuntimeError):
    """The seed declined to run rather than doing something surprising."""


@dataclass(frozen=True)
class _DemoEvent:
    """One invented event, positioned relative to the run time.

    `minutes_ago` values are spread unevenly on purpose: a batch landing on
    exact five-minute boundaries reads as generated, and the panel's job is
    to be looked at as though it were real.
    """

    minutes_ago: int
    event_type: str
    #: Index into the deterministically ordered device list; None means the
    #: event carries no device at all (the unregistered-UID case).
    device_slot: int | None
    battery_voltage: float | None = None
    temperature: float | None = None
    message: str | None = None


#: The batch. Covers every mapped event type so each presentation path is
#: actually exercised on screen — the two device-classified conditions
#: (Critical/Warning), the neutral informational types, and the quarantine
#: row that must render without a link.
#:
#: More rows than the old Command Center's recent-events panel showed (10), so the newest-first bound and the scroll region are
#: both visible rather than only unit-tested.
#: EVERY presentation path must land inside the newest RECENT_EVENT_ROWS,
#: not merely somewhere in the batch. The first version of this list put the
#: unregistered UID oldest, which meant the one row whose whole point is
#: that it carries NO link was the one row nobody would ever see on the
#: panel. A test now pins the visible window rather than the batch.
DEMO_EVENTS: tuple[_DemoEvent, ...] = (
    _DemoEvent(7, "power_down", 0, battery_voltage=3.54),
    _DemoEvent(23, "battery_low", 1, battery_voltage=3.68),
    _DemoEvent(41, "startup", 2),
    _DemoEvent(56, "check_in", 3),
    # No device and no transformer: only a UID that resolves to nothing.
    _DemoEvent(68, "check_in", None),
    _DemoEvent(78, "battery_low", 4, battery_voltage=3.71),
    _DemoEvent(94, "sensor_error", 5, temperature=512.0),
    _DemoEvent(133, "power_down", 6, battery_voltage=3.49),
    _DemoEvent(168, "check_in", 7),
    _DemoEvent(212, "startup", 8),
    _DemoEvent(266, "battery_low", 9, battery_voltage=3.74),
    _DemoEvent(331, "check_in", 10),
    _DemoEvent(408, "power_down", 11, battery_voltage=3.60),
)


def _devices() -> list:
    """Fleet devices in a stable order.

    Sorted by `device_id` rather than hashed: this seed has no reason to
    look randomly distributed, and a reader comparing two runs benefits from
    the same RTLs appearing both times.
    """
    return sorted(list_all_devices(), key=lambda d: d.device_id)


def _already_seeded() -> bool:
    """Whether a previous run's events are still in the table.

    Reads through the same consumer API everything else uses
    (`list_recent_device_events`) rather than a bespoke count query.
    """
    events = list_recent_device_events(
        event_types=event_semantics.mapped_event_types(),
        include_unattributed=True,
        allowed_device_ids=None,
        limit=len(DEMO_EVENTS) * 4,
    )
    return any(e.source == DEMO_SOURCE for e in events)


def seed(*, now: datetime | None = None, again: bool = False) -> list[str]:
    """Ingest the demo batch. Returns one outcome line per accepted event."""
    devices = _devices()
    needed = max(e.device_slot for e in DEMO_EVENTS if e.device_slot is not None) + 1
    if len(devices) < needed:
        raise DemoSeedRefused(
            f"Only {len(devices)} devices exist; the demo batch needs "
            f"{needed}. Run `python -m db.seed_plant_monitoring` first."
        )

    if not again and _already_seeded():
        raise DemoSeedRefused(
            "Demo events are already present. Event persistence is "
            "append-only (INGEST-D3), so this seed cannot remove them — "
            "pass --again to add another batch deliberately."
        )

    reference = (now or datetime.now(timezone.utc)).replace(
        second=0, microsecond=0
    )
    outcomes: list[str] = []
    for demo in DEMO_EVENTS:
        device = devices[demo.device_slot] if demo.device_slot is not None else None
        event = NormalizedEvent(
            event_type=demo.event_type,
            event_ts=reference - timedelta(minutes=demo.minutes_ago),
            device_id=device.device_id if device else None,
            transformer_id=device.transformer_id if device else None,
            # Unattributed rows carry the unmatched UID and nothing else, so
            # the existing resolution is what decides they are quarantine.
            reported_uid=None if device else UNREGISTERED_UID,
            battery_voltage=demo.battery_voltage,
            temperature=demo.temperature,
            message=demo.message,
            source=DEMO_SOURCE,
        )
        result = ingest_event(event)
        label = device.device_code if device else f"UID {UNREGISTERED_UID}"
        outcomes.append(
            f"{demo.event_type:<13} {label:<10} -> {result.outcome} "
            f"(event {result.event_id})"
        )
    return outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seed invented device events for demo/visual verification. "
            "Never run against production."
        )
    )
    parser.add_argument(
        "--again",
        action="store_true",
        help=(
            "Add another batch even though demo events already exist. "
            "Events are append-only; nothing is removed."
        ),
    )
    args = parser.parse_args(argv)

    try:
        outcomes = seed(again=args.again)
    except (DemoSeedRefused, IngestError) as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1

    for line in outcomes:
        print(line)
    print(
        f"\n{len(outcomes)} demo events ingested (source={DEMO_SOURCE!r}). "
        "Startup events also activated their RTL and wrote a "
        "system-originated audit row, exactly as a real startup would."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
