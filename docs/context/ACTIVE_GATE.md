# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 7 — Affected Locations
Precondition: Phase 6 complete and committed (`04e3bfa`), approved by the
user 2026-08-29.
Flow: PLAN → REVIEW GATE (complete) → **IMPLEMENT** → TEST/VISUAL VERIFY → COMMIT → **FULL STOP (no Phase 8)**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
once every item under "Required tests" and "Verification gate" passes. Push
NOT GRANTED. **Stop after committing — Phase 8 needs its own approval.**

## Task

Answer **"Where is attention concentrated?"** using only existing
monitoring/freshness truth.

Location = Plant (ADR-003). No Zone, Feeder, GIS, map, or electrical
severity ranking.

A ranked horizontal bar view of affected RTLs per Plant:

```
Affected Locations

KZN North       ███████████████  18
Durban          ██████████       12
Pinetown        ███████           8
Richards Bay    ████              5
Newcastle       ██                2
```

Affected is still `Stale + No Data` (ADR-002). Each bar may show the
Stale/No Data composition, but only while it stays readable — the total
ranking stays dominant.

## Ranking (deterministic, frozen)

1. affected RTL count **descending**
2. then Plant name **ascending** as tie-breaker

No Critical/Warning precedence. This visualisation is freshness exceptions
only — event data contributes nothing to it (ADR-001/ADR-002).

## Service rule

Derive from the **same `FleetHealth` snapshot already fetched** for the
page. No new SQL to rank Plants.

Row shape (exact dataclass is an implementation choice): `plant_id`,
`plant_name`, `affected_rtls`, `stale_rtls`, `no_data_rtls`,
`total_monitored_rtls`, `affected_percent`.

**One read-path amendment, recorded in ADR-008 before implementation:**
`FleetHealth` is keyed by `plant_id` and carries no names, so Plant
*labels* come from `hierarchy_service.list_plants(*, scope)` — a third
approved entry point, scope-aware, supplying **labels only**. Every number
and the ranking order still come from `FleetHealth`. A Plant in
`FleetHealth` but missing from the name lookup keeps its `plant_id` as its
label rather than disappearing.

## Interaction

Minimal. Clicking a Plant bar may set a selected Plant for Phase 8, but the
transformer panel is **not** built here. If selection state is added, make
it explicit and testable, and preserve it through later polling work.

## Decisions this gate depends on

- [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) — affected = Stale + No Data
- [ADR-003](../decisions/ADR-003-location-is-plant.md) — Location = Plant; no Zone/Feeder/GIS
- [ADR-004](../decisions/ADR-004-device-scope-is-not-user-selectable.md) — scope is authorization-derived
- [ADR-008](../decisions/ADR-008-command-center-reuses-existing-read-paths.md) — read paths; amended this gate for the Plant-label lookup

## Non-goals (explicit — withheld by the user)

Selected-Plant transformer concentration; recent events; priority assets;
auto-refresh; dark/light theming; Asset Navigator changes; event-based
Critical/Warning ranking; map/GIS; any change to Fleet Overview.

## Required tests

- affected count = Stale + No Data
- a Fresh-only Plant ranks below any affected Plant
- NO_DATA and STALE composition sums to the affected total
- no event data contributes to Plant ranking
- tie-break is deterministic
- zero-affected Plant behaviour is defined
- all-zero fleet renders an honest empty/quiet state
- current scope is respected
- **no new repository query for location ranking**
- existing Phase 5/6 values unchanged

## Verification gate

Browser at 1440 / 1366 / 1024, with attention to: long Plant names, five or
more ranked rows, zero affected rows, and bar-label readability. Fleet
Overview unchanged. No new console errors. Then commit locally and **stop**.

## Relevant files

- `services/command_center_service.py` — the ranked-row model
- `services/hierarchy_service.py` — `list_plants`, read-only, labels only
- `components/command_center/` — a new sibling module for the bar view
- `pages/command_center.py` / `callbacks/command_center.py` — mount + populate
- `assets/app.css` — `.command-center__` namespace only
