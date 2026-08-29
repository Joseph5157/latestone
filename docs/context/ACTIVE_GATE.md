# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 7a — Affected Locations full view
Precondition: Phase 7 complete and committed (`ed59876`, `25b7e81`), plus
the cockpit/logout work (`d0d9f3a`, `fb6fae2`).
Flow: DECIDE (complete) → **IMPLEMENT** → TEST/VISUAL VERIFY → COMMIT → **FULL STOP (no Phase 8)**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
once tests and browser verification pass. Push NOT GRANTED. **Stop after
committing — Phase 8 still needs its own approval.**

## Task

A "View all" from the Affected Locations panel to a full, unbounded ranked
list of plants.

Decided 2026-08-29 after weighing modal vs route: **a route**, at
`/command-center/locations`.

Why not a modal, recorded so it is not relitigated: the request was for a
"full resizable page", and a modal is precisely what cannot be that — it
floats inside the viewport, and making it resizable means hand-built drag
handles. A route already is full-page and resizable, plus bookmarkable,
shareable and back-button-friendly ("open /command-center/locations on the
wall display" is a thing someone will want). The three existing overlays
here (`assign_device_drawer`, `user_form_drawer`, `device_manage_drawer`)
also carry no modal a11y at all — no `role="dialog"`, `aria-modal`, focus
trap, ESC handling or scroll lock — so a modal would either inherit those
gaps on a frequently-opened surface or require machinery this codebase has
never needed.

**Not** added to Electrical Conditions. It holds exactly two conditions and
renders both completely at 1080p; a "View all" there would open the same two
blocks, teaching operators the control means nothing. Revisit only if
Phase 9's event-window counts make that card grow.

## Scope

- `/command-center/locations` route, `ROUTE_POLICY` entry, dispatch
- Nav key maps to `command_center` so the sidebar keeps Command Center
  highlighted — this is the same destination, one level deeper
- A normal scrolling page, NOT the fixed cockpit: the whole point is an
  unbounded list
- Shows the same population as the panel (affected plants, ranked). A
  "View all" that shows a different set than the panel it came from is
  a trap, not a feature
- Reuses the panel's row rendering rather than a second copy
- "View all" link in the panel header; a way back on the full page

## Non-goals

Plant selection / transformer concentration (Phase 8); sorting or filtering
controls; any change to the ranking rule; anything on Electrical Conditions.

## Required tests

- route parses, policy entry exists, sidebar stays on Command Center
- the page renders every affected plant with no height cap
- panel and page render the same rows from the same data
- the panel's "View all" points at the route
- empty/all-healthy scope behaves honestly
- Command Center and Fleet Overview unchanged

## Decisions this gate depends on

- [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) — affected = Stale + No Data
- [ADR-003](../decisions/ADR-003-location-is-plant.md) — Location = Plant; no Zone/Feeder/GIS
- [ADR-004](../decisions/ADR-004-device-scope-is-not-user-selectable.md) — scope is authorization-derived
- [ADR-008](../decisions/ADR-008-command-center-reuses-existing-read-paths.md) — read paths; amended this gate for the Plant-label lookup

## Verification gate

Browser at 1920x1080 and 1440x900: the full list scrolls normally (this
page is deliberately not the fixed cockpit), the panel's "View all" reaches
it, and the sidebar still highlights Command Center. Command Center itself
and Fleet Overview unchanged. No new console errors. Then commit locally
and **stop**.

## Relevant files

- `routes.py` — the route and its nav-key mapping
- `services/authorization.py` — `ROUTE_POLICY` entry
- `components/command_center/affected_locations.py` — shared row rendering
- `pages/command_center_locations.py` — the full view (new)
- `callbacks/routing.py` / `callbacks/command_center.py` — dispatch + populate
- `assets/app.css` — `.command-center__` namespace only
