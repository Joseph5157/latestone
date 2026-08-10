# Powerplant Dashboard — Wireframes

## What these are

Interactive HTML wireframes that reflect the **current accepted application state** as of the main branch. They are communication and planning artifacts, not the source of truth — the actual running UI and acceptance records (`docs/UX_ACCEPTANCE_*.md`) remain authoritative.

## How to use

Open `index.html` in a browser to navigate all screens.

```bash
# Windows
start docs/wireframes/index.html

# macOS
open docs/wireframes/index.html
```

## Screen inventory

| File | Screen | Route | Status |
|------|--------|-------|--------|
| `01-login.html` | Login | `/` (unauthenticated) | Implemented |
| `02-global-shell.html` | Equipment selector + app header | persistent architecture | Implemented (with UXD-1 debt) |
| `03-fleet-overview.html` | Fleet Overview | `/plants` | Implemented (Fleet v2) |
| `04-plant-detail.html` | Plant Detail | `/plants/<plant_id>` | Implemented (next consistency slice) |
| `05-transformer-detail.html` | Transformer Detail | `/plants/<id>/<id>` | Implemented (next consistency slice) |
| `06-device-dashboard.html` | Device Dashboard | `/devices/<device_id>` | Implemented (reference implementation) |
| `07-design-status.html` | Design Status | reference | Current accepted/debt/future state |

## Status annotations on wireframes

- **IMPLEMENTED** — accepted and verified in browser
- **ACCEPTED DEBT** — deliberate compromise, documented in `docs/UX_DEBT.md`
- **FUTURE** — blocked on client requirements, not yet implemented

## Key design constraints reflected

- Monitoring width: `max-width: 1550px` (Fleet only)
- Reading width: `max-width: 1200px` (Device, Plant, Transformer)
- Chart vertical budget: top at 406px at 1366×768 (Device page)
- Equipment population: active-only across all counts and listings
- Freshness chain: metric → device → plant → fleet, worst-of
- No fabricated electrical thresholds or monitoring conditions
- Breadcrumb root: `Fleet` at all four hierarchy levels

## Source of truth hierarchy

1. Running application (visual inspection)
2. Acceptance records (`docs/UX_ACCEPTANCE_*.md`)
3. Design specs (`HMI_UI_UX_SPEC.md`, `UI_SPEC.md`)
4. These wireframes (reference/planning)
