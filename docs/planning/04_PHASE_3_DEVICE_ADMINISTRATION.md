# Phase 3 — Device Administration

## Objective

Create the frontend foundation for RTL device operations without depending on the final production database schema.

## Important constraint

This is a frontend workflow and UI-state implementation.

Do not implement production CRUD against the client database.

Use an abstraction/mock adapter or frontend fixture data where required.

## Target route

`/admin/devices`

## Purpose

Provide a single enterprise-style view for:

- viewing devices
- filtering devices
- locating inactive/unassigned devices if mock data supports those states
- opening future actions such as view, edit, assign, deactivate

## Page design

Header:

`Device Management`

Toolbar:

- Search
- Status filter
- Assignment filter if supported safely
- `Register Device` button

Main table should reuse `components/entity_table.py` if practical.

Suggested conceptual columns:

- Device
- Assignment
- Status
- Data state
- Last seen
- Actions

Only render a column if the current frontend model can support it truthfully.

## Tasks

### 1. Define frontend admin view model

Create a presentation/domain structure independent from raw SQL table shape.

Example concept:

- device_id
- display_name
- assignment_label
- lifecycle_status
- freshness_state
- last_seen

Do not name fields after unconfirmed production columns.

### 2. Introduce admin device data provider boundary

The page must not query SQL directly.

Preferred order:

1. reuse existing hierarchy/repository service if sufficient
2. add a service-level adapter
3. use mock/fixture provider for fields that are not yet available

Document which fields are mock-only.

### 3. Build Device Management page

Requirements:

- full-width
- searchable
- sortable if existing table supports it
- supports active/inactive view if existing data allows
- preserves stable row identity
- clicking “View Device” opens existing device dashboard
- action menu exists but unsupported actions may be disabled or labeled design-only

### 4. Do not pretend CRUD is complete

Until production persistence rules are confirmed:

- Register may open a frontend-only form in Phase 4
- Edit may open frontend-only form/drawer
- Deactivate may be a UI prototype
- Assign may be a UI prototype

No fake success message that implies the client database changed.

### 5. Tests

Test:

- page renders
- current devices appear through approved data provider
- stable navigation to device dashboard
- inactive records handled safely
- empty state
- loading/error state
- no direct SQL import in page module

## Acceptance criteria

- `/admin/devices` works.
- Existing device monitoring dashboard is untouched.
- Device admin uses reusable components.
- No production persistence added.
- No production schema assumptions introduced.
