# Phase 0 — Baseline and Guardrails

## Objective

Freeze the known-good monitoring application before adding any new frontend scope.

This phase must not add new features.

## Why this phase exists

The current repository already has a strong monitoring foundation. The largest risk is not missing functionality; it is accidentally breaking working routing, freshness logic, hierarchy behavior, or device dashboards while adding new pages.

## Tasks

### 1. Inspect current repository state

Confirm the current implementation and record:

- active routes
- page modules
- global layout structure
- navigation structure
- component library
- callback registration
- service/repository boundaries
- existing tests
- current CSS layout tokens
- existing design/spec files

### 2. Run baseline tests

Run the existing non-database test suite first.

Then run the full suite if the local database is available.

Record:

- test command
- number passed
- number failed
- skipped tests
- environment assumptions

Do not “fix” unrelated failing tests in this phase. Report them separately.

### 3. Create a frontend scope guard document

Create:

`docs/rtl_frontend_scope_guard.md`

It must state:

- Current client scope is PAD Sections 1–3.4 only.
- Current work is frontend-focused.
- Existing database is development/mock infrastructure.
- Production database schema is not confirmed.
- Backend ownership is not confirmed.
- No later PAD technical architecture is to be implemented yet.
- New UI must use services/repositories or mock interfaces rather than direct new SQL from pages.

### 4. Create a current-route inventory

Create:

`docs/rtl_current_route_inventory.md`

For every active route include:

- route
- page module
- purpose
- main callback(s)
- main service(s)
- status: preserve / adjust / candidate for later replacement

## Do not change

- existing route behavior
- existing monitoring calculations
- freshness rules
- metric definitions
- database schema
- existing user-facing layouts

## Acceptance criteria

- Existing application still runs.
- Baseline test results are recorded.
- No production behavior changes.
- `docs/rtl_frontend_scope_guard.md` exists.
- `docs/rtl_current_route_inventory.md` exists.
- Git diff contains documentation-only changes unless a tiny test-environment correction was strictly necessary and separately justified.

## OpenCode execution instruction

Before editing, inspect the repository and summarize the current architecture in no more than 20 bullets. Then implement only the documentation and baseline tasks above. Do not add features.
