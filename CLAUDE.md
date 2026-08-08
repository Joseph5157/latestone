# CLAUDE.md — Powerplant Dashboard Demo

## Mission
Build a local proof-of-concept Python dashboard that visualises temperature readings for one transformer/device from a PostgreSQL database modelled on the client's known structure.

Read these files before making architectural changes:
1. `PROJECT_CONTEXT.md`
2. `REQUIREMENTS.md`
3. `ARCHITECTURE.md`
4. `DATABASE.md`
5. `UI_SPEC.md`
6. `IMPLEMENTATION_PLAN.md`

## Fixed Demo Scope
Implement only:
- Transformer: `AA12` (`aa12` in physical identifier)
- Device: `29017`
- Schema: `trfr_temperature`
- Table: `aa12_29017`
- Metric: temperature

Do not expand to all plants/devices/metrics unless explicitly instructed.

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
2. Put PostgreSQL access in a repository/data-access layer.
3. Put KPI/status/domain calculations in services, not scattered across callbacks.
4. Treat `aa12_29017` as a physical database implementation detail.
5. Resolve transformer/device -> table only inside the data layer.
6. Validate dynamic identifiers strictly; never interpolate arbitrary browser/user input into SQL identifiers.
7. Keep demo authentication isolated so it can later be replaced by client authentication.
8. Use environment configuration; do not commit secrets.
9. Do not redesign the client's database in this demo.
10. Do not add Kubernetes deployment until production requirements are known.

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

Anything beyond this is an assumption. Mark assumptions clearly and do not invent production schemas, thresholds or authentication behaviour.

## Data Rules
- Seed at least 30 days of local data at approximately 30-minute intervals.
- Use deterministic generation where practical.
- Include a few abnormal values for warning UI testing.
- Demo warning threshold must be configurable in one place.
- Parse database strings into proper datetime/numeric types before calculations/visualisation.
- Current temperature means latest available reading.
- Min/max/average apply to the selected time range.

## UI Requirements
After login, dashboard must include:
- AA12 / 29017 identity
- Last data timestamp
- Current temperature KPI
- Minimum KPI
- Maximum KPI
- Average KPI
- 24h / 7d / 30d / custom filter
- Plotly temperature time-series chart
- Recent readings table
- Normal / Warning / No-data status
- Logout

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
- Transformer/device identifier validation.
- Timestamp parsing.
- Temperature numeric parsing.
- KPI calculations.
- Warning-status calculation.
- Empty-data behaviour.
- Repository range filtering where feasible.

## Implementation Behaviour
Work through `IMPLEMENTATION_PLAN.md` phase by phase. Do not perform a broad rewrite when a small change is sufficient. Before introducing a new dependency, explain why the existing stack cannot reasonably solve the requirement.

After each phase:
- Run relevant tests/checks.
- Fix errors before moving on.
- Keep README commands accurate.

## Definition of Done
A developer can locally start PostgreSQL, seed the demo data, run Dash, log in, view the AA12 / 29017 dashboard, change the time range, see correctly calculated KPIs, interact with the temperature chart, inspect recent readings and observe the configurable demo warning state.
