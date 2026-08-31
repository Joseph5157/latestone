# Command Center Implementation Plan

## Tranche name
`CC-1 — Fresh Command Center Parallel Build`

## Gate principle
Existing Fleet Overview is frozen. No old Fleet Overview presentation component may be modified merely to support the new Command Center.

## Approved shared-source exceptions
Fresh page does not mean zero shared infrastructure changes. CC-1 requires deliberate shared edits for routing/authorization and route-scoped appearance.

At minimum approved:
- `routes.py`
- `services/authorization.py`

The read-only planning pass must name any additional shell/sidebar/navigation file needed for the theme hook before implementation. Those changes must be strictly route-scoped and regression-tested so `/plants` remains visually unchanged.

## Phase 0 — Repository reconciliation and demo prerequisites
Before implementation:
- record branch and HEAD
- confirm working tree
- identify any unmerged local UX commits
- run current baseline tests
- confirm all 12 `components/CC*.md` specs are present
- confirm `Location = Plant`
- confirm `/` remains existing Overview during CC-1
- inspect existing persisted-event ingestion/read path and create a plan for an **opt-in deterministic Command Center event demo seed** because the existing core/demo seeds do not populate events
- event demo seed must be separate from core seed behavior, must not run implicitly in production, and should use the approved event ingestion/persistence path rather than inventing a second event model
- do not mix unrelated branch cleanup into CC-1

## Phase 1 — Route, authorization and appearance architecture
Implement together rather than deferring theme to polish:
- `/command-center` parsing in `routes.py`
- explicit `ROUTE_POLICY` entry in `services/authorization.py`
- navigation mapping/item only after policy exists
- `/` remains Overview
- minimal route-scoped root/app-shell theme hook
- session-scoped Command Center appearance store
- whole visible shell follows Command Center dark/light appearance while route is active
- non-CC routes remain on current appearance
- Command Center-owned `dcc.Interval` for auto-refresh, cadence read from
  `monitoring.refresh_interval_seconds` (never hardcoded). The application has
  no fleet-wide refresh to reuse, so this is net-new and belongs to CC-1.
- header renders a READ-ONLY scope indicator. No scope selector, no dropdown,
  no scope-changing control: `DeviceScope` is authorization-derived.

Deliverable: empty but fully composed Command Center shell with working route, authorization and dark/light shell appearance.

## Phase 2 — Fresh presentational primitives
Create Command Center-local primitives for:
- card shell
- title/subtitle
- metric pair
- semantic dot/icon
- mini bar
- unavailable state
- empty/error/loading body

Do not depend on `.fleet-condition__*` or `.needs-attention__*` styling. Reuse existing light design tokens where they are truly shared; do not duplicate identical token values merely for namespace purity.

## Phase 3 — Mandatory Command Center service facade
Create `services/command_center_service.py` before data panels.

Responsibilities:
- consume existing scoped FleetHealth/monitoring truth
- expose current Stale/No Data attention counts
- expose current Critical/Warning values as unavailable (`None`) until closure semantics exist
- read/map persisted events without numeric threshold logic
- rank affected Plants
- build selected-Plant transformer rows
- produce presentation-ready view models for callbacks

No new SQL if existing monitoring/event/hierarchy APIs already provide the facts.

## Phase 4 — Summary row
Implement:
- Fleet Health
- Needs Attention
- Communication
- Inventory

Communication (CC-04) ships **without No Data age buckets**. Freshness is
per-metric with a worst-of device rollup, so a `NO_DATA` RTL may hold recent
readings for other metrics; `>24h`/`>48h`/`>72h` would claim a duration the
backend cannot derive. Show count, share of monitored RTLs and the line
"At least one monitored metric has no reading." Duration bucketing waits for a
metric-level missing-since/closure contract.

Current Critical/Warning slots are visible but unavailable/pending. Do not infer current state from historical events.

## Phase 5 — Semantic legend
Explain:
- Critical event = persisted `power_down` event; device meaning documented as `<3.61V`
- Warning event = persisted `battery_low` event; device meaning documented as `<3.75V`
- numeric voltage payload is not evaluated by Command Center consumers
- Stale = existing freshness threshold exceeded
- No Data = existing monitoring no-data state

## Phase 6 — Affected Locations
Build ranked horizontal bars where `Location = Plant`.
Current ranking burden = Stale + No Data RTL leaves.
No second stacked-by-location chart.

## Phase 7 — Recent Operational Events
Build the larger event panel from the approved persisted event read path.
No acknowledgement.
Use the opt-in deterministic event demo seed for browser verification where needed.

## Phase 8 — Selected Location / Transformer Attention Concentration
This replaces the map.
Capabilities:
- Plant selector displayed as Location
- transformer ranking by current freshness attention
- Stale / No Data breakdown
- Critical / Warning current-state columns rendered unavailable in CC-1
- affected/total ratio
- last update
- optional trend sparkline only if supported without inventing meaning
- direct transformer links

## Phase 9 — Shortcuts
Add only real routes and role-filter them.

## Phase 10 — Integration / browser verification
Verify:
- 1440px
- 1366px
- 1024px informational check
- 768px regression check
- auto-refresh fires at the configured cadence and updates `Last updated`
- selected Plant survives a routine refresh
- dark Command Center whole-shell appearance
- light Command Center whole-shell appearance
- leaving Command Center restores unchanged existing appearance
- empty states
- error isolation
- role visibility
- direct links
- event panel with deterministic persisted demo events

## Backend stance
Reuse existing monitoring, hierarchy, authorization and persisted-event truth. `services/command_center_service.py` is mandatory as a view-model/aggregation facade, not a new data store.

## Database stance
No schema migration for CC-1. No duplicate SQL for facts already exposed by existing APIs.

## Stop gate
Stop before commit/push for review unless explicitly instructed otherwise.
