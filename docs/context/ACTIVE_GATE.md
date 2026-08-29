# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 8 — Selected Location / Transformer Concentration
Precondition: Phase 7 + 7a complete and committed (`ed59876`, `25b7e81`,
`04d89bb`), plus the cockpit/logout work (`d0d9f3a`, `fb6fae2`).
Flow: DECIDE (complete) → **IMPLEMENT** → TEST/VISUAL VERIFY → COMMIT → **FULL STOP (no Phase 9)**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
once tests and browser verification pass. Push NOT GRANTED. **Stop after
committing — Phase 9 (Recent Operational Events) needs its own approval.**

## Task

Selecting a Plant answers the next question: **"which transformers inside
this Plant are driving the attention?"**

Ranked transformer concentration within the selected plant, and deep links
out to the existing Plant / Transformer / RTL routes — flattening
investigation without duplicating the hierarchy.

## Selection is a URL query parameter, not a Store

`/command-center?plant=<plant_id>`, mirroring the `?assign=` precedent
already in `routes.py`, whose own comment states the reasoning this reuses:
"a query parameter rather than a route: the destination is the existing
page in its existing state."

Chosen over `dcc.Store` deliberately. The gate requires selection to
survive a polling refresh — a URL parameter survives it *by construction*,
since no callback can clear what it does not own. It is also bookmarkable
and shareable ("Command Center with KZN North selected"), and the back
button works. A Store would give none of that and would need explicit
protection from every future refresh callback.

An unknown or out-of-scope `plant_id` selects nothing and shows the
prompt — never an error, and never a message confirming that some plant
the caller cannot see exists. Same posture as `parse_assign_request`'s
"an unknown value simply opens nothing".

## Read paths

No new query for ranking: transformer counts come from
`FleetHealth.transformers_for_plant()`, already fetched.

Transformer CODES need `hierarchy_service.list_transformers(plant_id, *,
scope)` — called for the one selected plant only, never per row. ADR-008
amended before implementation: its three read entry points are now stated
as three read *categories*, with plant and transformer listings as one
"hierarchy labels" category, so reading one more level of the same
hierarchy for the same reason does not re-open the decision each time.

## Ranking

Same rule as plants, one level down: affected count DESCENDING, then
transformer code ascending (case-insensitive), then transformer_id as the
final deterministic key. Affected is still `Stale + No Data` (ADR-002). No
event data participates.

## Non-goals

Recent events (Phase 9); priority assets (Phase 10); auto-refresh;
dark/light theming; Asset Navigator changes; map/GIS; any change to Fleet
Overview or to the ranking rule itself.

## Required tests

- selecting a plant yields its transformers, ranked
- affected = Stale + No Data at transformer level; composition sums
- ranking tie-break deterministic and case-insensitive
- no plant selected → an honest prompt, not an empty panel
- unknown / out-of-scope plant_id selects nothing rather than erroring
- a transformer missing a code keeps its id rather than disappearing
- no new repository query for transformer ranking
- deep links point at the existing Plant / Transformer / RTL routes
- selection survives a re-render (it is in the URL)
- Phase 5/6/7 values unchanged; Fleet Overview unchanged

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
