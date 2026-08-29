# Active Gate

Status: Approved
Date: 2026-08-29
Gate: CC-1 Phase 5 — Situation Summary
Precondition: Phase 3+4 complete and committed (`cc6b67a`), approved by the
user 2026-08-29.
Flow: PLAN → REVIEW GATE (complete) → **IMPLEMENT** → TEST/VISUAL VERIFY → COMMIT → **FULL STOP (no Phase 6)**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
once every item under "Verification gate" below passes. Push NOT GRANTED.
**Stop after committing — Phase 6 is explicitly withheld** and needs its own
approval.

This file describes exactly one gate. Phase 3+4's record moved to
`docs/context/CC1_ROADMAP.md`; when Phase 5 completes, rewrite this file for
Phase 6 rather than appending.

## Task

Populate only the top operational summary layer — four real components.
Everything else on the page stays a placeholder.

1. **Fleet Health** — monitored RTL count, Fresh/Stale/No Data composition.
   Fresh reads visually quiet. No invented "Healthy/Critical/Warning"
   rollup (ADR-001: those words belong to event types, not freshness).
2. **Needs Attention** — `Stale + No Data` exactly (ADR-002), affected RTL
   count, percentage of the monitored population. No event occurrences
   mixed in.
3. **Communication / Visibility** — No Data RTL count, share of monitored
   population, the exact copy "At least one monitored metric has no
   reading.", plus affected Plant count (derivable from the same
   `FleetHealth` via `device_counts_for_plant`). **No `>24h`/`>48h`/`>72h`
   buckets. Never "never reported"** (ADR-002).
4. **Inventory** — Plants / Transformers / RTL Devices from the
   **monitoring** population (`FleetHealth`), never the Managed-RTL admin
   population. Subtitle frozen by the user: **"Monitored assets in your
   current access scope"**.

## Service rule (frozen)

`services/command_center_service.py` stays the only composition seam.
Extend `CommandCenterSnapshot` with presentation-ready values; components
render, service decides. Components must not inspect `FleetHealth`
themselves, and no second freshness calculation may exist anywhere in
Command Center.

Direction (exact names are an implementation choice): `monitored_rtls`,
`fresh_rtls`, `stale_rtls`, `no_data_rtls`, `attention_rtls`,
`attention_percent`, `plant_count`, `transformer_count`, `device_count`,
`no_data_affected_plants`.

## The regression case this gate exists to protect

```
RTL-A
├── temperature → fresh reading
├── voltage     → fresh reading
└── another monitored metric → no reading
```

Expected: device freshness `NO_DATA`; `device_last_updated` **present**;
Communication count includes RTL-A; Needs Attention includes RTL-A. This is
the exact semantic error corrected during planning (ADR-002) — a dedicated
test is mandatory, not optional.

## Population rule

`services/admin_overview_service.py:15-20` states the split in source:
**Managed RTLs** are administratively active devices regardless of their
transformer's status; **Monitoring Devices** are active devices under active
transformers. Inventory shows the second. Command Center must not import
`admin_overview_service` at all this gate.

## Visual direction

Compact, operational top row — four cards across:

```
┌───────────────┬─────────────────┬───────────────┬─────────────────┐
│ FLEET HEALTH  │ NEEDS ATTENTION │ COMMUNICATION │ INVENTORY       │
│ freshness mix │ 35 affected     │ 18 No Data    │ 8 Plants        │
│               │ 29.2% fleet     │ 15.0% fleet   │ 42 Transformers │
└───────────────┴─────────────────┴───────────────┴─────────────────┘
```

Structure, density and hierarchy — **not** final dark-mode styling. The
route-scoped HMI theme is Phase 11, its own gate.

## Decisions this gate depends on

- [ADR-001](../decisions/ADR-001-event-classification-no-thresholds.md) — no Critical/Warning language on freshness
- [ADR-002](../decisions/ADR-002-fleet-attention-is-freshness-only.md) — Attention = Stale + No Data; the per-metric No Data semantics
- [ADR-004](../decisions/ADR-004-device-scope-is-not-user-selectable.md) — scope is authorization-derived
- [ADR-008](../decisions/ADR-008-command-center-reuses-existing-read-paths.md) — single read path, service composes, no Fleet Overview imports

## Non-goals (explicit — withheld by the user)

Critical/Power Down card logic; Warning/Battery Low card logic; recent
operational events; affected-location bars; Plant selection; transformer
concentration; priority assets; auto-refresh; dark/light theme; Asset
Navigator on Command Center; any change to `/`; any change to Fleet
Overview.

## Relevant files

- `services/command_center_service.py` — extend the snapshot
- `components/command_center/primitives.py` — shared card/stat primitives
- `pages/command_center.py` — mount the four cards
- `callbacks/command_center.py` — populate them
- `assets/app.css` — `.command-center__` namespace only
- `services/monitoring_service.py` — `FleetHealth`, read-only

## Required tests

- The 19 existing CC foundation tests still pass
- New Situation Summary tests (service + components)
- Single `FleetHealth` fetch still proven
- The one-metric-`NO_DATA` regression test above
- Monitoring vs Managed population test
- Zero-denominator behaviour (no `ZeroDivisionError`, no misleading 0%)
- Empty scope behaviour
- Service error behaviour

## Verification gate

Browser: 1440, 1366, 1024. Fleet Overview screenshot unchanged. No new
console errors. Then commit locally and **stop**.
