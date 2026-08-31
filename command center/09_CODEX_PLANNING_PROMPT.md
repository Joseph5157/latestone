# Codex Prompt — CC-1 Planning Pass

Act as a Senior Frontend Architect and Industrial IoT UX Engineer.

We are building a brand-new `/command-center` page in the existing RTL / Powerplant Dash application.

## Read-only first
Do not modify code during this pass.

## Locked rules
1. Existing Fleet Overview `/plants` must remain visually and behaviorally untouched.
2. `/` remains the existing Overview during CC-1. Command Center is parallel, not yet the default landing route.
3. Do not reuse Fleet Overview presentation components or CSS as the basis of Command Center.
4. Reuse backend/service truth only; do not add duplicate SQL for facts already available.
5. `Location = Plant`. Do not invent Zone, Feeder or GIS entities.
6. No map.
7. No alarm acknowledgement.
8. No invented temperature critical threshold.
9. Event presentation semantics are type-derived, not threshold-derived:
   - persisted `power_down` event occurrence -> Critical presentation
   - persisted `battery_low` event occurrence -> Warning presentation
   - `<3.61V` and `<3.75V` are explanatory Functional-Spec/device legend copy only
   - Command Center consumers must not classify from numeric battery-voltage payloads (EVT-D4 boundary)
10. There is no approved event clear/resolve/closure model. Therefore current fleet-wide Critical/Warning state is **not derivable** from event history. Build UI slots but plan them as explicit unavailable/pending current-state values.
11. Current CC-1 Requires Attention = Stale + No Data from existing freshness semantics.
12. `services/command_center_service.py` is mandatory and owns Command Center view models/aggregation policy.
13. Middle row must not contain duplicate Plant/location visualizations.
14. Keep `Affected Locations (Top 5)` and make `Recent Operational Events` the larger adjacent panel.
15. Lower-left primary investigation panel is `Selected Location / Transformer Attention Concentration`.
16. Dark/Light is an architectural decision, not late polish: on `/command-center`, the selected appearance covers the whole visible app shell; non-CC routes keep their existing appearance. Existing light tokens should be reused where appropriate; dark is route-scoped new tokens.
17. Existing seed/demo scripts do not populate persisted events. Plan an opt-in deterministic Command Center event demo seed for browser verification, using the approved event ingestion/persistence path and without changing default production seed behavior.
18. Route policy is default-deny. `routes.py` and `services/authorization.py` are explicitly approved shared-modify files for CC-1. Identify any additional shared shell/navigation file needed for the theme hook.
19. **Do not plan No Data duration buckets from `device_last_updated`.** A `NO_DATA` RTL may still have readings for other monitored metrics: freshness is evaluated per (device, metric) and the RTL takes the worst state, so latest-any-data time does not establish the duration of the missing metric. `>24h`/`>48h`/`>72h` buckets are out of scope for CC-1 and must not be reconstructed from event age either. Plan the Communication card as count + share of monitored RTLs + the line "At least one monitored metric has no reading."
20. The header scope element is a **read-only indicator**. `DeviceScope` is authorization-derived and there is no user-selectable scope concept; do not plan a scope selector, dropdown or scope-changing control.
21. Auto-refresh is a real CC-1 deliverable, not a reused cadence. The application has no fleet-wide `dcc.Interval`. Plan a Command Center-owned interval whose cadence reads from `monitoring.refresh_interval_seconds`, plus `Last updated`. Polling only — never describe it as live/streaming.

## Target composition
- Header / search / read-only scope indicator / theme / Command Center auto-refresh
- Fleet Health
- Needs Attention
- Communication
- Inventory
- Semantic legend strip
- Affected Locations (Top 5) [Plants]
- Recent Operational Events
- Selected Location / Transformer Attention Concentration [selected Plant]
- Shortcuts

## Audit tasks
Inspect the repository and report:
- repository checkpoint
- exact files to add
- exact files to modify
- route parsing + NAV mapping + `ROUTE_POLICY` changes required for `/command-center`
- confirmation that `/` remains Overview
- smallest route-scoped whole-shell theming hook that leaves non-CC pages visually unchanged
- existing light tokens that should be reused vs new dark tokens needed
- service functions/data already sufficient for Fleet Health, Plant ranking and transformer concentration
- current event read API and how to reuse it
- the exact **event occurrence -> current state gap** caused by absence of clear/resolve/closure semantics
- proof that no numeric battery threshold derivation belongs in Command Center consumers
- design of mandatory `services/command_center_service.py`
- design of deterministic opt-in event demo seed
- tests to add

## Approved shared surface
At minimum:
- `routes.py`
- `services/authorization.py`

If another shared app-shell/sidebar/navigation file is needed for the route-scoped theme hook, name and justify it explicitly. Do not widen the shared-change surface casually.

## Output
Return a read-only implementation plan with:
1. repository checkpoint
2. architecture map
3. data-source map per component
4. new files
5. modified files
6. callback graph
7. Command Center service/view-model design
8. semantic risks and unavailable-state contract
9. theme architecture
10. event demo-seed plan
11. test plan
12. browser-verification plan
13. stop gate

End with:
`Planning complete. No source files modified. Awaiting approval to implement CC-1.`
