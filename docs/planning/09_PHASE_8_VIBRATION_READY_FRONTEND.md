# Phase 8 — Vibration-Ready Frontend

## Objective

Prepare the existing metric-driven UI so vibration can be added later with minimal redesign.

## Important fact

The audit found vibration absent from the current metric registry.

The client PAD current business process references temperature and vibration, but the exact production data shape is not confirmed.

## Critical rule

Do not create fake vibration readings.

Do not add database columns/tables.

Do not assume unit, sampling model, threshold, or whether vibration is continuous/event-based.

## Tasks

### 1. Audit metric extensibility

Inspect:

- `config/metrics.py`
- monitoring service aggregation dispatch
- device snapshot strip
- metric selector
- charts
- trend grid
- readings table
- tests

Document every place that assumes exactly 8 metrics.

### 2. Remove unnecessary fixed-count assumptions

Where safe, make UI layout driven by `ordered_metrics()` rather than literal `8`.

Do not add vibration itself unless a mock-only feature flag is explicitly required for design demonstration.

### 3. Create a documented future metric contract

Create:

`docs/vibration_frontend_contract.md`

Include required unknowns:

- metric key
- display name
- unit
- precision
- chart type
- aggregation
- freshness behavior
- data source
- sampling cadence
- whether event-based
- whether thresholds exist

### 4. Optional design-only preview

If useful, create a disabled/feature-flagged “Vibration — data contract pending” tile.

It must not look like live data.

### 5. Tests

- existing 8 metrics continue to render
- metric count is configuration-driven where practical
- no vibration values fabricated
- no DB/schema changes

## Acceptance criteria

- Current metrics are unchanged.
- UI is easier to extend to a ninth metric.
- Vibration remains blocked on client data contract.
