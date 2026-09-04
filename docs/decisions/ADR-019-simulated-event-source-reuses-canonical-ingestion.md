# ADR-019: The simulated event source reuses canonical ingestion; it does not become a second pipeline

Status: Approved
Date: 2026-09-04
Evidence: `services/simulated_event_source.py`;
`services/device_event_service.py` (`ingest_event`, unchanged);
`services/event_semantics.py` (unchanged); `services/notification_service.py`
(unchanged); `services/report_service.py` (unchanged);
`tests/test_simulated_event_source.py`
Implemented-by: not yet
Supersedes: nothing — reuses INGEST-1I's `ingest_event()` boundary and
ADR-018's transport-vs-simulator framing without changing either.

## Context

RTL-IF-1/RTL-IF-2 built `SimulatorTransport`: a deterministic stand-in for
*outgoing* command delivery. RTL-IF-3 needed the mirror case — a
deterministic way to originate *incoming* device events (startup, check-in,
battery low, power down, sensor error) for tests and future demos, without
a real MQTT/SMS/Eskom producer. The canonical event pipeline
(`device_event_service.ingest_event()`, INGEST-1I) already does everything
a producer needs: validation, conservative identity resolution, append-only
persistence, the startup→`rtl_active_state` activation projection, and
system-originated audit. The only thing missing was a way to *build* a
`NormalizedEvent` deterministically and hand it to that boundary — not a
new place for events to go.

## Decision

**`services/simulated_event_source.py` is a thin front end onto
`ingest_event()`, nothing else.** It builds `NormalizedEvent` instances and
submits them through the existing boundary; it does not touch
`repositories/plant_monitoring_repository.py`, does not add a table, does
not duplicate `event_semantics.py`'s type→meaning mapping, and does not
give any event type new behaviour. Every test in
`tests/test_simulated_event_source.py` that checks activation, audit,
notification composition, or report inclusion is checking
`device_event_service`/`event_semantics`/`notification_service`/
`report_service` — code this tranche did not modify.

**Two simulator modules, one direction each — deliberately not merged:**

| | Direction | Module |
|---|---|---|
| `SimulatorTransport` | outgoing (an authorized command is dispatched to a device) | `services/simulator_transport.py` (RTL-IF-2) |
| simulated event source | incoming (a device "sends" an event into the system) | `services/simulated_event_source.py` (RTL-IF-3) |

Overloading `SimulatorTransport` to also originate events was considered
and rejected: the two have opposite data flow, opposite failure models (a
transport reports an outcome for a command it was given; an event source
originates the input in the first place), and no shared contract — forcing
one class to do both would be an artificial merge, not a simplification.
Both remain internal test/demo foundations; **neither defines or claims an
Eskom wire payload.**

## Why the simulator's event-type allowlist is narrower than the service it calls

`device_event_service.ingest_event()` accepts any `event_type` string
(INGEST-D7, open vocabulary, no CHECK constraint on
`device_events.event_type`) — that policy is unchanged and this module does
not touch it (`tests/test_simulated_event_source.py::
test_g_canonical_service_still_accepts_the_same_type_directly` pins this).
`simulated_event_source.SUPPORTED_EVENT_TYPES`, by contrast, lists only the
five types RTL-IF-3 actually inspected in `config/events.py` and confirmed
carry real meaning in `event_semantics.py`: `startup`, `check_in`,
`battery_low`, `power_down`, `sensor_error`. `emit()` refuses anything
outside that list before building a `NormalizedEvent` at all.

This is a **simulator-only** restriction, layered on top of (never instead
of) the canonical validation — not a new closed vocabulary for the
application. A future event type gets ingested by the real system the
moment `event_semantics.py` gives it meaning, same as always; a *simulator*
for that type is separate follow-up work, added deliberately, not silently
implied by the vocabulary being open.

`EVENT_TYPE_INVALID_UID` is deliberately not in `SUPPORTED_EVENT_TYPES`: no
device ever declares itself `invalid_uid` — it is `ingest_event()`'s own
reclassification of an unresolvable `reported_uid`
(`device_event_service._resolve_identity`), exercised by simulating a
startup/check-in with an unregistered UID, never emitted directly.

## What this does not claim

No voltage-threshold evaluation exists anywhere in this tranche.
`emit_battery_low()`/`emit_power_down()` emit the already-classified event
type directly — they do not accept a raw voltage and decide whether it
crosses the client-documented `<3.75V`/`<3.61V` thresholds (ADR-001 already
forbids a consumer holding such a threshold; this module does not become
the first exception). No high-temperature or vibration event type is
simulated — those remain structurally absent from `event_semantics.py`
pending client clarification, unchanged.

No schema migration exists for this tranche. `device_events` and
`rtl_active_state` are reused exactly as INGEST-1I left them.

No browser-facing wiring exists. Nothing in `callbacks/`, `pages/`, or
`components/` imports `simulated_event_source` — confirmed by
`tests/test_simulated_event_source.py::
TestNoBrowserAuthorizationSurfaceIntroduced`, which also pins the same
absence for `simulator_transport`/`rtl_command_dispatch_service`.
