# Phase 4 — Device Registration and Assignment UX

## Objective

Design and implement frontend-only workflows for registering and assigning RTL devices.

## Critical rule

The PAD Sections 1–3.4 do not provide enough confirmed field-level detail to define the final device record.

Therefore this phase must use a minimal, clearly provisional frontend contract.

Do not infer hardware, firmware, networking, SIM, APN, or commissioning fields from later PAD sections.

## Part A — Register Device

### Target interaction

From `/admin/devices`:

`Register Device` → registration page or modal → review → frontend-only submit

### Recommended route

`/admin/devices/new`

### Minimum provisional fields

Use only fields already supported by the existing repository/domain model.

If even those are uncertain, label them internally as prototype fields.

Do not invent production-required fields.

### UX states

- initial
- validation error
- review
- prototype success

Prototype success message must clearly say the operation is not yet persisted to the production client database.

## Part B — Assign / Reassign Device

### Interaction

Device row action → assignment drawer/modal

Display:

- selected device
- current assignment if known
- destination selection from current frontend hierarchy
- confirmation action

Do not add effective-date/history/audit behavior unless current requirements already support it.

## Data boundary

Assignment action should call a frontend/domain command interface such as:

`assign_device(...)`

During this phase the implementation can be a mock/in-memory adapter.

The UI must not know whether future persistence is SQL, API, or another client service.

## Reuse

Prefer existing:

- form styles
- dropdowns
- entity selector patterns
- buttons
- status panels
- breadcrumbs
- hierarchy service

## Tests

- registration form renders
- required prototype validation works
- review state
- assignment selector uses valid hierarchy values
- cancellation causes no change
- mock submit does not mutate production database
- direct SQL not introduced

## Acceptance criteria

- User can walk through the entire UX.
- The workflow is demonstrable to the client.
- No claim of real production persistence.
- Unknown fields remain explicitly unresolved.
