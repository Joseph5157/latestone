# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 9 — Recent Operational Events
Precondition: Phase 8 complete and committed (`825e59b`, `13f2bfc`).
Flow: DECIDE (complete) → IMPLEMENT (complete) → TEST (complete) → **VISUAL VERIFY** → COMMIT → **FULL STOP (no Phase 10)**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
once browser verification passes. Push NOT GRANTED. **Stop after
committing — Phase 10 (Priority Investigation) needs its own approval.**

## Task

The fourth question in the investigation chain:

> How much? → Where? → Which transformer? → **What just happened?**

A read-only operational event panel over persisted events. It must NOT
become an alarm-management system.

## The distinction the whole phase exists to hold

    a recent Power Down EVENT   ≠   an RTL currently in Critical STATE
    a recent Battery Low EVENT  ≠   an RTL currently in Warning  STATE

Events are displayed as occurrences. The Phase 6 card's current state stays
`Unavailable` until a closure contract exists (ADR-001). A test asserts a
storm of Power Down events changes neither the Needs Attention count nor
the plant ranking nor the current-state cards.

## Presentation mapping is derived, never restated

Severity tone comes from Phase 6's `ELECTRICAL_CONDITIONS` at call time, so
re-pointing that table re-points these rows (a test does exactly that).
Event type NAMES come from `services/event_semantics.py`'s new
`display_label`, so no consumer spells out "Battery Low" itself — the same
EVT-D1 rule that keeps "Battery Low" (device condition) and "Battery Alarm"
(notification category) from being flattened into one word.

Everything the device did NOT classify — startup, check-in, sensor error,
invalid UID — takes a neutral tone. Owning a Critical style is not a reason
to spend it.

## Read paths — ADR-008 amended BEFORE the code

Three additions, all recorded in ADR-008 first:

1. `hierarchy_service.list_device_paths(device_ids, *, scope)` — ONE batched
   query resolving plant name / transformer code / device code for the
   VISIBLE rows. A new function rather than the approved per-level listings
   because those would be one query per distinct plant AND per distinct
   transformer on screen — ~20 extra per render on a page the roadmap
   intends to auto-refresh, which is the N+1 ADR-008 exists to prevent.
   Status is deliberately not filtered: an event that already happened does
   not stop needing a name because its RTL was later deactivated.
2. The events read has its own **failure boundary**. It is context around
   the fleet's state, not the state itself, so its failure must not blank
   Needs Attention, Affected Locations and the transformer concentration.
   `recent_events_failed` keeps "nothing happened" and "we could not look"
   structurally apart. One-directional: a `get_fleet_health` failure still
   fails the whole snapshot, because that IS the page.
3. Unregistered-UID rows are **administrator-only**, applying
   `callbacks/notifications.py:106`'s existing precedent rather than
   inventing a rule — an unknown UID belongs to no device set, so scope
   alone cannot express who may see it (EVT-D5).

## Honesty rules on the rows

- `Open asset →` appears ONLY where the asset actually resolved. An
  unregistered UID gets plain text, never a disabled-looking link: a greyed
  control still claims the asset exists.
- Battery voltage is display payload. The Phase 6 AST threshold guard is
  retained; the blanket "never touch `battery_voltage`" guard was
  **narrowed, not deleted**, to "never rank or threshold it, aliases
  included" — checked against a deliberate violation, which the first
  version of the narrowed guard did not catch.
- Empty state says "No recent operational events are available." Never "No
  problems" or "System healthy".

## Non-goals

No acknowledge / clear / resolve / assign / silence / escalate / close.
None has a persisted workflow, and a button that looks like it acknowledges
an alarm and does nothing is worse than no button. The only action is
"Investigate / Open asset".

⛔ No Priority Investigation panel · ⛔ No theming · ⛔ No auto-refresh ·
⛔ No Top-N affected-location collapse · ⛔ No landing-route change ·
⛔ No push

## Demo data

`python -m db.seed_events_demo` — opt-in, through `ingest_event()`, never
`repo.insert_device_event()`. Append-only, so no `--reset`; a second run is
refused unless `--again`.

## Still open after this gate

The FRESHNESS demo seed (one Fresh, one Stale, one mixed-metric NO_DATA
RTL) remains blocking debt for Phase 12 — a different gap from the event
seed this phase closed. See `docs/context/CC1_ROADMAP.md` Phase 12.
