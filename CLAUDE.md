# CLAUDE.md — Powerplant Dashboard

## Mission
Build the **primary development application**: a Python dashboard visualising 8 metrics across a 30-plant hierarchy from a PostgreSQL database modelled on the client's known structure.

This is not a demo or throwaway proof-of-concept. Architecture, database design, UI structure and data-access patterns are production-oriented. Only the *measurements* are synthetic, because real client data is not yet available.

Read these files before making architectural changes:
1. `PROJECT_CONTEXT.md`
2. `REQUIREMENTS.md`
3. `ARCHITECTURE.md`
4. `DATABASE.md`
5. `UI_SPEC.md`
6. `IMPLEMENTATION_PLAN.md`

## Hierarchy Scope
- 30 plants, 71 transformers, 120 devices
- Schema: `plant_monitoring`
- Tables: `plants`, `transformers`, `devices`, `readings`
- Reserved identifier: `plant-01-t1-d1` = `aa12`/`29017`
- 8 metrics: temperature, voltage, current, active_power, reactive_power, power_factor, frequency, energy

Do not expand beyond this scope unless explicitly instructed.

## Required Stack
- Python
- Plotly Dash
- Plotly
- PostgreSQL
- Docker Compose for local PostgreSQL
- SQLAlchemy for database access

Do not replace Dash with Streamlit/Taipy/another frontend framework without explicit instruction.

## Critical Architecture Rules
1. UI/page/component code must not execute raw SQL.
2. Put PostgreSQL access in `repositories/plant_monitoring_repository.py`.
3. Put KPI/status/domain calculations in services, not scattered across callbacks.
4. Resolve hierarchy identifiers through `hierarchy_service`; validate parent relationships.
5. Validate dynamic identifiers strictly; never interpolate arbitrary browser/user input into SQL identifiers.
6. Keep demo authentication isolated so it can later be replaced by client authentication.
7. Use environment configuration; do not commit secrets.
8. Do not add Kubernetes deployment until production requirements are known.

## Client Database Facts vs Assumptions
Known from supplied screenshots:
- PostgreSQL is used.
- A schema named `trfr_temperature` exists.
- Tables include names such as `aa12_29017` and `aa28_29044`.
- Naming represents transformer + `_` + device.
- Example temperature table has `timestamp` and `temperature` varchar columns.
- Timestamp is the primary key in the shown DDL.
- The schema screenshot showed approximately 2,112 tables.
- Example readings are roughly 30 minutes apart.

The `plant_monitoring` schema is our development schema, not the client's production schema.

## Data Rules
- Seed 30 days of local data at approximately 30-minute intervals (1,383,360 readings).
- Use deterministic generation where practical.
- Energy metric is cumulative (monotonically increasing); all others use statistics aggregation.
- Parse database strings into proper datetime/numeric types before calculations/visualisation.
- Current temperature means latest available reading.
- Min/max/average apply to the selected time range.
- No production warning/critical thresholds — `MonitoringCondition` is always `UNKNOWN`.

## UI Requirements
After login, the operator workflow is:
- Plants overview (30 plants with transformer/device counts)
- Plant detail (list of transformers)
- Transformer detail (list of devices)
- Device dashboard with: equipment context, 8-metric snapshot strip, metric selector, period filter, aggregation-aware KPIs, Plotly chart, readings table, freshness badge

Do not add unnecessary gauges, pie charts, animations or unrelated screens.

## Coding Style
- Prefer small, explicit modules and functions.
- Add type hints to service/repository interfaces where useful.
- Keep callbacks thin: gather inputs -> call service -> format outputs.
- Avoid global mutable application state.
- Reuse components rather than duplicating markup.
- Fail safely and show user-friendly errors.
- Never expose stack traces, SQL, passwords or connection strings in UI errors.

## Testing Expectations
At minimum test:
- Hierarchy generation (30 plants, 71 transformers, 120 devices).
- Metric configuration (8 metrics, aggregation types).
- Timestamp parsing.
- Numeric parsing.
- KPI calculations (statistics and delta).
- Freshness evaluation.
- Routing/URL parsing.
- Repository range filtering.
- Seed integrity (row counts, per-metric coverage, energy monotonicity).

Run tests:
- Pure logic: `python -m pytest -m "not db" -v`
- Full suite: `python -m pytest -v` (requires Docker + seeded DB)

## Implementation Behaviour
Work through `IMPLEMENTATION_PLAN.md` phase by phase. Do not perform a broad rewrite when a small change is sufficient. Before introducing a new dependency, explain why the existing stack cannot reasonably solve the requirement.

After each phase:
- Run relevant tests/checks.
- Fix errors before moving on.
- Keep README commands accurate.

## Definition of Done
A developer can locally start PostgreSQL, seed the development data, run Dash, log in, navigate the plant hierarchy, view a device dashboard, change the time range, switch metrics, see correctly calculated KPIs, interact with the chart, inspect recent readings, and observe the data freshness status.
