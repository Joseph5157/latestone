# Active Gate

Status: Implemented, awaiting commit
Date: 2026-08-29
Gate: CC-1 Phase 3+4 — Foundation and shell
Precondition: resolved 2026-08-29 (merge + branch cut).
Flow: PLAN → REVIEW GATE (complete) → IMPLEMENT (complete) → **TEST/VISUAL VERIFY (complete)** → IMPLEMENTATION REVIEW → COMMIT → PUSH GATE
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
— condition met (2051 tests green, TDD throughout, browser-verified at
1440/1024). Push stays NOT GRANTED regardless; Phase 13/14's full gate still
governs before this branch merges to `main`.

## Phase 3+4 — done, verified 2026-08-29

`/command-center` opens: route (`routes.py`), `ROUTE_POLICY["command_center"]
= _EVERY_ROLE` (`services/authorization.py`), sidebar item (`components/app_sidebar.py`,
own icon `assets/icons/nav-command-center.svg`), dispatch branch
(`callbacks/routing.py`), façade (`services/command_center_service.py`,
TDD — calls `get_fleet_health`/`list_recent_device_events` exactly once
each, verified by test), fresh presentation family
(`components/command_center/`, `.command-center__` CSS namespace, no
imports from Fleet Overview components), static shell with six named panel
slots (`pages/command_center.py`), one callback populating the header's
real scope indicator (`callbacks/command_center.py`) — "Current access ·
120 monitored RTLs" against the live database, exactly ADR-004's example
text. 19 new tests, all TDD (RED confirmed before every GREEN). Fixed 5
pre-existing completeness-check fixtures the new route correctly triggered
(`ROUTE_PATHS`/`SHARED` in test_authorization.py, two hardcoded label lists,
`PAGE_LAYOUT_IDS` in test_equipment_selector.py) — each verified as the
right kind of failure before fixing, not silenced.

Browser-verified at 1440 and 1024: scope indicator shows real live data,
all six panels render honest "Not yet available in this build." placeholders
(never "No Data"/"Unavailable" — ADR-001/002 reserve those), sidebar
highlights correctly, Asset Navigator correctly absent (Command Center not
added to `UTILITY_ROUTES` — deliberate, matches Reports/Notifications
precedent, reversible at Phase 8 if the design wants it), zero new console
errors/warnings, responsive reflow to 2 columns at 1024, Fleet Overview
pixel-identical and zero-error before/after.

Deliberately not built this gate: any panel content (Phase 5+), theming
(Phase 11), auto-refresh interval (Phase 5+ per ADR-005 — the shell has no
`dcc.Interval` yet).

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

- `routes.py` — add the `/command-center` route and `NAV_KEY_BY_ROUTE` entry
- `services/authorization.py` — `ROUTE_POLICY["command_center"]`
- `components/app_sidebar.py` — `SIDEBAR_SECTIONS` nav item, only after the
  policy entry exists (found missing from this list 2026-08-29 — the
  roadmap's own Phase 3 bullet already called for it, mirroring `command
  center/07_IMPLEMENTATION_PLAN.md` Phase 1's "navigation mapping/item only
  after policy exists"; this was a gap in this file, not in the roadmap)
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

Precondition resolved — see the field above. Phase 3 file creation may
begin on `cc-1-command-center-foundation`.
