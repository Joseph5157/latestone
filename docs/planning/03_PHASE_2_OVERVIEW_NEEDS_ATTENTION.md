# Phase 2 — Overview / Needs Attention

## Objective

Make the existing Fleet/Overview page more operational by surfacing exceptions first.

## Why

The current monitoring foundation already computes freshness and health. The audit identifies a “Needs attention” panel as a high-value missing piece that can be implemented using existing data without inventing backend behavior.

## Scope

Enhance the existing Fleet/Overview page only.

## Target layout

Full-width operational page:

1. Page title / context
2. Existing KPI summary
3. Needs Attention panel
4. Existing fleet/entity table

## Needs Attention content

Use only conditions already supported by existing logic, such as:

- stale data
- no data
- inactive state if already represented safely

Do not create new alarm thresholds.

Do not label stale data as equipment failure.

Do not fabricate “warning” or “critical” equipment health.

## Tasks

### 1. Reuse existing health/freshness view models

Inspect `services/monitoring_service.py` and existing fleet health structures.

Do not add duplicate health calculations in the page layer.

### 2. Create a reusable exception list/panel component

Suggested location:

`components/needs_attention.py`

The component should accept presentation-ready rows/view models.

Possible columns:

- Entity
- Type
- Issue
- Last update / age
- Action/link

Only include values already known by current services.

### 3. Add exception-first ordering

Highest operational concern first:

1. NO_DATA
2. STALE
3. other already-defined non-normal state

Do not create severity labels unsupported by the current model.

### 4. Empty state

If nothing needs attention:

Display a truthful message such as:

`No current data-freshness exceptions.`

Avoid claiming “All equipment healthy” unless the application actually knows equipment condition.

### 5. Navigation

Clicking an item should use existing stable routes to the relevant page.

### 6. Tests

Test:

- no-data before stale
- empty-state behavior
- stable entity links
- no fake exception rows
- no regression to existing overview table

## Acceptance criteria

- Overview remains full-width.
- Existing KPIs and fleet table remain.
- Needs Attention shows only existing, defensible states.
- No thresholds added.
- No database changes.
- Existing freshness semantics remain unchanged.
