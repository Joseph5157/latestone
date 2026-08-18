# RTL Frontend Current Status

## Current Source Basis

Frontend planning now uses:

- **PAD Sections 1–3.4** for the currently approved architecture/business-flow scope
- **docs/RTL_FUNCTIONAL_SPEC_EXTRACT.md** for newly confirmed functional requirements

Do not use later PAD technical sections to expand implementation scope automatically.

---

## Current Checkpoint

```
009828f  docs: complete RTL client review and implementation gate
553d142  Phase 8 vibration-ready metric UI
9fdabd4  docs: update RTL frontend status through Phase 7R
78af1e3  Phase 7R notification center
9e83856  Phase 6A report alignment
e83472e  Phase 4A device workflow alignment
3504d1b  Phase 5A role alignment
```

Working tree: clean

---

## Completed Alignment Phases

### Phase 8 — Metric / Vibration Readiness — COMPLETE

Metric registry remains 8 metrics; UI is now configuration-driven (`ordered_metrics()`)
with no fixed-8 assumptions. Vibration is **not activated** — its data contract is
unresolved (`docs/VIBRATION_METRIC_CONTRACT_TBD.md`). No fabrication, no DB/schema changes.

Latest Phase 8 test baseline (2026-08-18 fast suite):

```
1085 passed (non-DB)
63 deselected (DB)
1148 total
```

### Phase 9 — Client Review Gate — COMPLETE

Deliverable: `docs/RTL_CLIENT_REVIEW_GATE.md`. Closes the frontend planning cycle with an
audit (complete / prototype / backend-blocked), prioritized client decisions, data/API
contract checklist, demo flow, and Go/No-Go gates.

**Next state: CLIENT / BACKEND REVIEW REQUIRED.**

There is no Phase 10 planned automatically. Further production implementation is gated on
client/backend/data-contract decisions.

### Phase 5A — Role Alignment — COMPLETE

Confirmed roles:

- Administrator
- Technician
- General User

Implemented:

- Real prototype role selector (3 options, not disabled TBD)
- Prototype role storage/display
- Legacy users safely shown as Unassigned

Still not production authorization.

### Phase 4A — Device Workflow Alignment — COMPLETE

Implemented prototype frontend workflows:

- View Device
- Asset Assignment (Plant → Transformer)
- Technician Assignment (separate from asset assignment)
- Program RTL
- Message Forwarding
- Deactivate RTL

Architecture:

- Shared prototype users in `services/prototype_users.py`
- Permission helpers in `services/prototype_access.py`

Important:

- Technician assignment is separate from Plant/Transformer assignment
- Active-list state is not assumed to equal administrative device status
- No production commands or persistence

### Phase 6A — Report Definition Alignment — COMPLETE

Confirmed reports:

- RTL Alarms (30 Days)
- Installed RTLs
- Maximum Temperature

Report definitions live in: `config/reports.py`

Date semantics:

- RTL Alarms (30 Days) → fixed 30 days
- Installed RTLs → no date-period control
- Maximum Temperature → reporting period not defined by Functional Specification

Report generation remains prototype-only.

### Phase 7R — Revised Notification Center — COMPLETE

Route: `/notifications`

Notification definitions live in: `config/notifications.py`

Current derivable formal notification:

- Active RTL whose latest reading is more than 24 hours old

Important:

- Formal >24h notification is separate from existing STALE freshness
- STALE remains approximately the existing configurable freshness policy
- Never-reported RTLs are excluded from the formal >24h notification because activation timestamp is unavailable

Confirmed but backend/data-dependent categories (no fake rows generated):

- Battery Alarm
- Power Down
- Sensor Error
- Startup / Check-In
- Message Forwarding

---

## Current Application Structure

```
Overview
└── Fleet → Plant → Transformer → Device

Devices
├── Device Administration
├── Register Device
├── Asset Assignment
├── Technician Assignment
└── Manage
    ├── Program RTL
    ├── Message Forwarding
    └── Deactivate RTL

Reports
├── RTL Alarms (30 Days)
├── Installed RTLs
└── Maximum Temperature

Notifications
└── Formal >24h data-loss notification center

Administration
└── User Administration
    ├── Administrator
    ├── Technician
    └── General User
```

Several actions remain prototype-only.

---

## Current Architecture Rules

1. Existing monitoring architecture must be preserved.
2. Top-level application navigation and equipment navigation are separate concepts.
3. Monitoring is not currently a separate top-level navigation destination.
4. /plants is the current Overview.
5. No backend is being built at this stage.
6. No production database assumptions should be introduced.
7. No later PAD sections should expand current scope.
8. Existing service/repository boundaries should remain intact.
9. Functional Specification confirmed roles must not be confused with PAD project stakeholder roles.
10. Current freshness and formal business notifications are different domains.
11. Prototype user state is centralized; callback modules must not become cross-module data stores.
12. Technician assignment is independent of asset assignment.
13. Report definitions are confirmed, but report data generation remains backend-dependent.
14. Notification definitions may exist even when event data required to generate rows is unavailable.

---

## Current Known Data Gaps

The following production/current frontend data fields are not available. Do not fabricate any of them:

- OU
- Zone
- Sector
- CNC
- Feeder / Feeder Name
- Battery(V)
- Firmware
- Operational RTL Status
- Date Installed
- Alarm/event history
- Sensor-error state
- Activation timestamp
- Notification history
- RTL Master MSISDN

---

## Current Test Baseline

Latest confirmed non-DB result (Phase 8 baseline, verified during Phase 9):

```
1085 passed
0 failures
63 deselected (DB)
1148 total
```

Run the full DB suite again before major implementation if required.

Known test issue: `test_batched_latest_returns_all_eight_metrics` may exceed the 80 ms performance budget. Not a functional regression.

---

## Git Checkpoint

Current checkpoint: `009828f`

Working tree: clean

---

## Next State

**CLIENT / BACKEND REVIEW REQUIRED**

There is no Phase 10 planned automatically.

Further production implementation is gated on client/backend/data-contract decisions. Before any further implementation:

1. Verify Git working tree is clean.
2. Read `docs/RTL_CLIENT_REVIEW_GATE.md`.
3. Review the Priority 1–2 client decisions (backend/data ownership, authentication/roles).
4. Obtain the production/current database schema or API contract.
5. Confirm the vibration data contract (`docs/VIBRATION_METRIC_CONTRACT_TBD.md`).
6. Wait for explicit client/backend approval.
