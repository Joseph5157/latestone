# RTL Command Center Planning Pack

## Purpose
This pack defines the fresh-build Command Center for the RTL / Powerplant application.

The Command Center is a **new parallel operational workspace**. During CC-1, the existing `/plants` Fleet Overview and `/` landing behavior remain unchanged.

## Locked direction
- Research-led high-performance HMI / IIoT visual language.
- Fresh Command Center presentation; do not reuse Fleet Overview presentation components.
- Existing RTL services, repository queries, hierarchy, authorization and persisted events remain the source of business truth.
- Exception-first flow: **condition -> concentration -> recent change -> investigate**.
- No geographic map in CC-1.
- No alarm acknowledgement workflow.
- No invented temperature critical threshold.
- `Location` in Command Center means an existing **Plant** in the current hierarchy. Do not invent Zone/Feeder/GIS semantics.
- `Critical` and `Warning` are UI categories for already-classified persisted event types:
  - `Critical` presentation = `power_down` event occurrence.
  - `Warning` presentation = `battery_low` event occurrence.
  - `< 3.61 V` and `< 3.75 V` are device/Functional-Spec legend copy only; Command Center consumers must **not** reclassify events from numeric voltage payloads.
- There is currently no event clear/resolve/closure contract. Therefore persisted events do **not** prove a current fleet-wide Critical/Warning state. Current Critical/Warning counts must render as unavailable/pending until a future aggregation contract is approved.
- `Stale` and `No Data` remain current data-delivery/freshness states and stay conceptually distinct from event classifications.
- `services/command_center_service.py` is a required semantic/view-model facade for CC-1. It centralizes all Command Center aggregation and prevents callback-level policy drift.
- Dark and light modes are required. The theme applies to the entire visible shell while `/command-center` is active; non-Command-Center routes retain the existing visual theme unchanged.
- Existing light tokens are reused where appropriate. Dark mode is the genuinely new route-scoped token layer.
- Browser verification of Recent Operational Events requires an opt-in deterministic Command Center event demo seed because the existing core/demo seeds do not populate persisted events.

## Final page composition
1. Command Center shell / header
2. Four top summary cards
   - Fleet Health
   - Needs Attention
   - Communication / No Data
   - Inventory
3. Attention summary + semantic legend strip
4. Middle row
   - Affected Locations (Top 5) — `Location = Plant`
   - Recent Operational Events (larger panel)
5. Lower row
   - Selected Location / Transformer Attention Concentration
   - Shortcuts
6. Persistent refresh / data-as-of context where supported by the shell

## Approved shared-source surface
CC-1 is a fresh page, but route authorization and route-scoped theming require small deliberate shared changes. At minimum the approved shared surface includes:
- `routes.py`
- `services/authorization.py`

Any additional shared shell/navigation file needed for the route-scoped theme hook must be named in the read-only planning pass before implementation. No shared change may alter `/plants` presentation.

## Component specs
The pack contains all 12 component specifications under `components/CC01_*.md` through `components/CC12_*.md`.

## Implementation rule
**Reuse data truth, not Fleet Overview presentation.**
