# Active Gate

Status: **CLOSED / PUSHED / REMOTE-VERIFIED**
Date: 2026-09-04
Gate: RTL-IF-3 — Simulated incoming device-event integration
Branch: `main`, baseline `f70a15d057f3bb5cf49f661596b38d25adf4b8a2`
Commit: `a89fbf97b523aee6b63f8f6b80d5bda0fd0876e8` — subject
"feat(integration): add simulated RTL event ingestion". Pushed to
`origin/main`; local `HEAD` (at the time of that push), `origin/main`, and
`git ls-remote origin refs/heads/main` all verified to match this SHA (see
Verification below). This paragraph describes that already-completed,
already-verified push of `a89fbf97b523aee6b63f8f6b80d5bda0fd0876e8` — it
does not assert anything about whatever commit this documentation edit
itself becomes part of, which is pushed separately, afterward, as its own
step (RTL-IF-3-CLOSE Step 6).
Commit/push permission: **GRANTED and exercised.** RTL-IF-3 was implemented
against explicit "DO NOT COMMIT OR PUSH" instructions and left
`READY FOR REVIEW / NOT COMMITTED`. It was then independently verified by
Codex (RTL-IF-3V — diff scope, canonical ingestion, simulator allowlist,
startup activation, unknown UID behavior, canonical validation, downstream
consumers, architecture boundary, test quality all PASS; no blockers; one
non-blocking note — no dedicated simulator test for Command Center recent
events, since that consumer reads the same persisted `device_events` path
already exercised by the Notification Center/RTL Alarms report tests), and
this session's own RTL-IF-3-CLOSE task explicitly authorized the commit
and push recorded above.

**Caveats, preserved from implementation through this closure:** the
simulator is not the Eskom protocol; no physical MQTT/device integration
exists yet; no new alarm-rule engine exists; no notification delivery
integration exists; no monitoring semantics changed.

**Caveats, preserved from implementation through this closure:** the
simulator is not the Eskom protocol; no physical MQTT/device integration
exists yet; no new alarm-rule engine exists (battery/power events are
emitted as already-classified types, never derived from a raw voltage
threshold); no notification delivery integration exists; no monitoring
semantics changed.

## Purpose

Add a deterministic incoming-device-event simulator that feeds the
**existing** canonical event-ingestion boundary — no second event store,
no second alarm pipeline:

```
simulated device event
        v
NormalizedEvent                     (services/device_event_service.py, unchanged)
        v
device_event_service.ingest_event() (canonical boundary, INGEST-1I — unchanged)
        v
existing persistence/projections    (device_events, rtl_active_state)
        v
existing notification/event/report consumers  (unchanged)
```

See `docs/decisions/ADR-019-simulated-event-source-reuses-canonical-ingestion.md`
for the full decision record.

## What changed

- **`services/simulated_event_source.py`** (new) — the only new module.
  `emit()` builds one `NormalizedEvent` for a supported `event_type` and
  submits it through `device_event_service.ingest_event()` unchanged — no
  bypass of validation, identity resolution, persistence, projection, or
  audit. `SUPPORTED_EVENT_TYPES` (`startup`, `check_in`, `battery_low`,
  `power_down`, `sensor_error`) is the exact set of `config/events.py`
  constants already given meaning by `services/event_semantics.py` —
  nothing invented, `high_temperature`/`vibration_event` excluded because
  no domain rule exists for them yet. `emit_startup`/`emit_check_in`/
  `emit_battery_low`/`emit_power_down`/`emit_sensor_error` are thin
  convenience wrappers. `EVENT_TYPE_INVALID_UID` is deliberately not a
  supported emit type — it is `ingest_event()`'s own reclassification of
  an unresolvable UID, exercised by simulating a startup/check-in with an
  unregistered `reported_uid`, never emitted directly.
- **`docs/decisions/ADR-019-...md`** (new) — the decision record: why the
  simulator is a thin front end rather than a new pipeline, why its
  allowlist is narrower than `ingest_event()`'s own open vocabulary
  (INGEST-D7, unchanged), and why this stays a separate module from
  `services/simulator_transport.py` (RTL-IF-2) rather than merging the two
  — opposite data-flow direction, opposite failure model.
- **`docs/context/DECISION_INDEX.md`** — ADR-019 row added.
- Tests: `tests/test_simulated_event_source.py` (new, 16 tests) — valid
  event persistence, correct device/event identity, startup activation
  through the existing projection (with audit), ACT-D3 repeat-startup
  idempotency, check-in with no invented activation, unregistered-UID
  quarantine (no device silently created), simulator-level allowlist
  refusal (proven distinct from the canonical service's own unrestricted
  acceptance of the same type), canonical validation rejecting malformed
  input (naive timestamp, non-string device_id, no attribution at all),
  Notification Center + RTL Alarms report consuming a simulated event
  unchanged, and a structural check that no `callbacks/`/`pages/`/
  `components/` file imports any simulator module.

**Nothing in `repositories/plant_monitoring_repository.py`,
`services/device_event_service.py`, `services/event_semantics.py`,
`services/notification_service.py`, or `services/report_service.py` was
modified.** This tranche is additive-only: one new module, one new test
file, one new ADR, and the two context documents.

## Explicitly NOT implemented (out of scope, per the task)

MQTT, RabbitMQ, a raw Eskom protocol parser, worker, scheduler, retries,
SMS/email, notification delivery adapters, recipient-routing redesign,
18:30 forwarding, desired/reported device state, monitoring changes based
on `rtl_active_state`, high-temperature rules, vibration rules, UI
redesign. No schema migration — `device_events`/`rtl_active_state` are
reused exactly as they were. No voltage-threshold evaluation exists
anywhere in this tranche: `emit_battery_low`/`emit_power_down` emit the
already-classified event type directly; they do not convert a raw voltage
into an alarm decision (ADR-001 unchanged). No new runtime dependencies
were installed. No browser-facing wiring — confirmed by a structural test,
not merely asserted.

## Verification

- Focused: `tests/test_simulated_event_source.py` — 16 passed.
- Regression: `tests/test_device_event_ingestion_db.py` +
  `tests/test_event_consumption_db.py` + `tests/test_rtl_alarms_report_db.py`
  + `tests/test_notification_service.py` +
  `tests/test_rtl_command_service_lifecycle.py` +
  `tests/test_rtl_command_dispatch.py` +
  `tests/test_migration_rtl_command_lifecycle.py` — all passed, run
  together in one invocation, unmodified.
- `python -m pytest -m db -q` — all passed, exit 0, no failures (Windows
  Git Bash swallows this pytest install's final summary line; exit code 0
  plus an unbroken dot sequence with no `F`/`E` markers across every
  progress chunk is the evidence available this session — same caveat
  recorded at RTL-IF-1 and RTL-IF-2's close).
- `python -m pytest -m "not db" -q` — all passed, exit 0, same evidence
  shape as above.
- `python -m pytest -q` (full suite) — all passed, exit 0, same evidence
  shape as above.
- `python scripts/build_context_pack.py --check` — CLEAN, at both open and
  close of this gate.
- `git diff --check` — clean, no whitespace errors.
- `git status --short` — matches the file list above plus untouched
  `debug.log`; no unexpected changes.
- Push verification (RTL-IF-3-CLOSE Step 4): after `git push origin main`,
  `git rev-parse HEAD`, `git rev-parse origin/main`, and
  `git ls-remote origin refs/heads/main` all returned
  `a89fbf97b523aee6b63f8f6b80d5bda0fd0876e8`.

## Codex RTL-IF-3V independent verification

Result: **VERIFIED**, no blockers — diff scope PASS; canonical ingestion
PASS; simulator allowlist PASS; startup activation PASS; unknown UID
behavior PASS; canonical validation PASS; downstream consumers PASS;
architecture boundary PASS; test quality PASS.

Non-blocking note: no dedicated simulator test exercises Command Center
recent-events specifically. Accepted as non-blocking because that consumer
reads the same `repo.list_recent_device_events`/persisted `device_events`
path already exercised end-to-end by
`tests/test_simulated_event_source.py`'s Notification Center and RTL
Alarms report assertions — the read path is shared, not reimplemented per
consumer, so those two are representative rather than partial coverage.

This gate does not overstate what was built: the simulator is not the
Eskom protocol, no physical MQTT/device integration exists, no new
alarm-rule engine exists, no notification delivery integration exists, and
no monitoring semantics changed.

## Known ambiguity

None encountered. One judgment call, not a conflict: whether
`EVENT_TYPE_INVALID_UID` belongs in `SUPPORTED_EVENT_TYPES`. Decided
**no** — a device never declares itself invalid; the type is the ingestion
service's own output for an unresolved UID (`_resolve_identity`'s zero-
match branch), and a simulator "emitting" it directly would misrepresent
where that classification actually comes from. Coverage for it instead
goes through simulating a startup with an unregistered UID and observing
the existing reclassification, which is what the real system does too.

## Next queued gate

None queued. This gate is implemented, independently verified (Codex
RTL-IF-3V), committed as `a89fbf97b523aee6b63f8f6b80d5bda0fd0876e8`, and
pushed to `origin/main` with the remote match confirmed above. What comes
next is a separate, later decision — most plausibly a Command Center
recent-events simulator test filling Codex's non-blocking note, or a
future RTL-IF tranche that gives high-temperature/vibration events their
client-confirmed domain rules, but neither is decided by this gate.
