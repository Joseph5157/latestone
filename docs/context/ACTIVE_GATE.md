# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 3+4 — Foundation and shell
Precondition: `ctx-1-context-architecture` merged to `main`, then a new
branch cut for CC-1 (this repo's convention is one branch per tranche —
`ent-6-ui-and-live-simulator`, `role-3-device-scope`, etc.; CTX-1 is
docs/tooling-only and CC-1 is a new feature, so they should not share a
branch). **Not yet done — see Verification.**
Flow: PLAN → REVIEW GATE (complete — ADR-008, this file) → **IMPLEMENT** → TEST/VISUAL VERIFY → IMPLEMENTATION REVIEW → COMMIT → PUSH GATE
Commit/push permission: NOT GRANTED. The precondition above must be resolved
first. Once on CC-1's own branch: commit only after Phase 13 tests are green
and Phase 14's human review passes (`docs/context/CC1_ROADMAP.md`); push
stays gated separately regardless.

This file describes exactly one gate. When Phase 3+4 completes, rewrite this
file for Phase 5 (Situation summary) rather than appending — the full
sequence lives in `docs/context/CC1_ROADMAP.md` precisely so this file
doesn't have to carry it.

## Task

Build CC-1's foundation and empty shell — route, authorization, page,
service façade, callback layer, fresh component family — enough that
`/command-center` opens and shows the panel skeleton with safe empty/
unavailable states. No panel content yet (Situation Summary onward is
Phase 5+, its own future gate).

Full detail: `docs/context/CC1_ROADMAP.md` §"Phase 3" and §"Phase 4".

## What this gate resolved

The user supplied a full 15-phase execution plan 2026-08-29. Reviewed
against the repo rather than taken on trust — three things confirmed, one
correction made, none of it blocking:

- `app_shell.py`, `app_sidebar.py`, `app_header.py` (the files a bad plan
  would rewrite wholesale for dark mode) are real, at `components/`.
- `FleetHealth` and `list_recent_device_events()` — named only generically
  in the frozen pack — are now pinned to exact functions:
  `services/monitoring_service.py:430` and
  `repositories/plant_monitoring_repository.py:2450`. See ADR-008.
- Route authorization default (`_EVERY_ROLE`) confirmed against
  `command center/01_PRODUCT_BRIEF.md`'s named primary users
  (Administrator, Technician) and the existing `ROUTE_POLICY` pattern.
- **Correction**: ADR-002 originally listed `components/fleet_condition.py`
  as something to reuse. It isn't — it's Fleet-Overview-specific
  presentation with zero classification logic of its own (its own
  docstring says so). The reusable unit is one layer down, in
  `services/monitoring_service.py`. Fixed in ADR-002 the same commit as
  ADR-008, which also formalizes it as the general rule: Command Center's
  fresh `components/` family reuses the service layer, never Fleet
  Overview's presentation layer.

## Decisions this gate depends on

- [ADR-001](../decisions/ADR-001-event-classification-no-thresholds.md) — event classification, no numeric thresholds
- [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) — Requires Attention = Stale + No Data (corrected 2026-08-29)
- [ADR-003](../decisions/ADR-003-location-is-plant.md) — Location = Plant
- [ADR-004](../decisions/ADR-004-device-scope-is-not-user-selectable.md) — device scope is authorization-derived
- [ADR-005](../decisions/ADR-005-auto-refresh-is-page-owned-polling.md) — auto-refresh is page-owned polling
- [ADR-006](../decisions/ADR-006-route-scoped-theming-is-architecture.md) — theming architecture (Phase 11, not this gate)
- [ADR-007](../decisions/ADR-007-event-demo-seed-uses-ingest-event.md) — event seed write path (not this gate — no seed needed to build an empty shell)
- [ADR-008](../decisions/ADR-008-command-center-reuses-existing-read-paths.md) — read-side reuse contract, route policy default

## Non-goals (explicit)

- No panel content (Fleet Health, Needs Attention, events, locations,
  theming, refresh wiring) — that's Phase 5 onward, gated separately.
- No modification to any existing Fleet Overview presentation component
  (`command center/07_IMPLEMENTATION_PLAN.md` gate principle stands).
- No branch cleanup mixed into this gate (same rule as Phase 0).
- No shared-file edits beyond `routes.py` and `services/authorization.py`.
- Do not change `/` — it stays Overview through all of CC-1.

## Relevant files

- `routes.py` — add the `/command-center` route
- `services/authorization.py` — `ROUTE_POLICY["command_center"]`
- `services/monitoring_service.py` — `get_fleet_health`, read-only, called not modified
- `repositories/plant_monitoring_repository.py` — `list_recent_device_events`, read-only, called not modified
- `docs/context/CC1_ROADMAP.md` — Phase 3/4 detail and everything after

## Required tests

- `python -m pytest -m "not db" -v` before and after — must stay green.
- New: route parsing, route authorization for `command_center`, navigation
  visibility, and a `services/command_center_service.py` unit test that
  confirms it calls `get_fleet_health`/`list_recent_device_events` exactly
  once and issues no direct SQL.

## Known ambiguities

- Exact shape of the "fresh presentation-ready snapshot"
  `command_center_service.py` returns is an implementation-time call, not
  pre-specified here — Phase 4's shell (six named panel slots) is the
  contract it needs to satisfy.
- Whether `components/command_center/` needs an `__init__.py` re-export
  surface or whether `pages/command_center.py` imports submodules directly —
  match whatever convention (if any) exists elsewhere before inventing one.

## Verification

Precondition not yet satisfied — `ctx-1-context-architecture` has not been
merged to `main`, and no CC-1-specific branch exists yet. Do not begin
Phase 3 file creation until this is resolved.
