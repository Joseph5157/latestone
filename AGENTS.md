# AGENTS.md — Powerplant Dashboard

Operating rules for any agent working in this repository. Keep this file short;
it points at authority, it does not contain it.

## Mission

The **primary development application**: a Python dashboard visualising 8
metrics across a 30-plant hierarchy from PostgreSQL, modelled on the client's
known structure. Architecture, database design, UI and data access are
production-oriented. Only the *measurements* are synthetic, because real client
data is not yet available. It is not a demo — do not call it one.

## Required reading order

0. Run `python scripts/build_context_pack.py`, then read
   `.agent-context/START_HERE.md`. It is generated and gitignored — never
   trust a copy older than your current session. It fails loudly (non-zero
   exit, a `PROBLEM:` list) if an ADR citation is broken, a frozen pack's
   hash doesn't verify, or the test baseline is red. **Stop and resolve that
   before reading anything else** — do not work around a failed pack by
   reading the source files directly instead.

   **Read-only work uses `--check`.** An audit or review forbidden from
   modifying the repository cannot run the plain command: `CURRENT_STATE.md`
   is tracked and the script stamps a timestamp into it, so an ordinary run
   dirties the tree even when nothing has drifted. `--check` runs every
   validation, prints the same verdict, and writes nothing. It is not a way
   to skip Step 0 — it is Step 0 for a reader.
1. `docs/context/SOURCE_AUTHORITY.md` — which source wins.
2. `docs/context/ACTIVE_GATE.md` — the only task in scope right now.
3. The ADRs that gate names, in `docs/decisions/`.
4. Only the code and tests the gate names.

Step 0 is a verified index into steps 1-4, not a replacement for them — it
tells you where to look and confirms nothing has drifted since those files
were written. Do not read the whole `docs/` tree to start a task. Do not
treat a document you found by grep as in-scope because it is interesting.

Claude Code sessions in this repo: `.claude/skills/project-context/SKILL.md`
packages steps 0-9 of this workflow (through conflict-reporting, testing,
updating context records, and the commit/push gate) as an invocable skill —
equivalent to this section plus "Working behaviour" below, not a second
set of rules.

## Context levels

| Level | Contents | Load when |
|---|---|---|
| Hot | `ACTIVE_GATE.md`, its ADRs, the exact files it names | every task |
| Warm | `PROJECT_CONTEXT.md`, `REQUIREMENTS.md`, `ARCHITECTURE.md`, `DATABASE.md`, `UI_SPEC.md`, `IMPLEMENTATION_PLAN.md`, `REQ-1B_Implementation_Gap_Matrix.md`, `docs/context/CURRENT_STATE.md`, `docs/context/DECISION_INDEX.md` | planning, verification |
| Cold | `docs/archive/`, completed packs, old reports | only when specifically needed |

`docs/archive/` is history. It is never evidence for current behaviour.

## Decision status vocabulary

Every ADR carries two independent fields. They are not one lifecycle:

```
Status: Proposed | Approved | Superseded | Rejected
Implemented-by: <commit sha> | not yet
```

Approved-and-unimplemented is normal. Frozen-and-unimplemented is normal.
When a decision is superseded, edit the **old** record in the same commit that
lands the new one — a supersession discoverable only by reading an index in
order is not an index.

## Scope

30 plants, 71 transformers, 120 devices. Schema `plant_monitoring`; tables
`plants`, `transformers`, `devices`, `readings`. Reserved identifier
`plant-01-t1-d1` = `aa12`/`29017`. 8 metrics: temperature, voltage, current,
active_power, reactive_power, power_factor, frequency, energy.

Do not expand beyond this without explicit instruction.

## Stack

Python, Plotly Dash, Plotly, PostgreSQL, Docker Compose (local PG), SQLAlchemy.
Do not replace Dash. Before adding a dependency, explain why the existing stack
cannot reasonably solve the requirement.

## Architecture rules

1. UI/page/component code must not execute raw SQL.
2. PostgreSQL access lives in `repositories/plant_monitoring_repository.py`.
3. KPI/status/domain calculations live in services, not scattered in callbacks.
4. Resolve hierarchy identifiers through `hierarchy_service`; validate parents.
5. Validate dynamic identifiers strictly; never interpolate browser input into
   SQL identifiers.
6. Keep demo authentication isolated so client auth can replace it.
7. Environment configuration only; never commit secrets.
8. Dependency direction is one-way: `components/` → `services/`, never reversed.
9. Alembic is the sole fresh-database authority. No Kubernetes until production
   requirements are known.

## Data rules

- 30 days of local data at ~30-minute intervals (1,383,360 readings),
  deterministic where practical.
- Energy is cumulative (monotonically increasing); all others aggregate by
  statistics.
- Parse database strings into real datetime/numeric types before calculating.
- "Current temperature" means the latest available reading; min/max/average
  apply to the selected range.
- No Eskom-confirmed warning/critical thresholds exist. Temperature condition
  (Normal/Warning/Critical/Limits not set/No recent data) is evaluated only by
  `services/temperature_condition_service.py`, against Administrator-configured
  limits (ADR-023). Device-page `MonitoringCondition` stays `UNKNOWN`.

## UI requirements

After login, Administrators and Technicians land on the Command Center (`/`)
and General Users on the Fleet Overview (`/plants`). The two pages answer
different questions and share no panel (ADR-024): Fleet Overview — 30 plants,
each expanding inline to transformers and RTLs with temperature first →
Device dashboard; Command Center — the ranked problems needing attention now.
Plant and transformer detail pages remain, reached from the device
breadcrumb. The device dashboard carries equipment context,
an 8-metric snapshot strip, metric selector, period filter, aggregation-aware
KPIs, a Plotly chart, a readings table and a freshness badge.

Do not add gauges, pie charts, animations or unrelated screens.

## Coding style

Small explicit modules. Type hints on service/repository interfaces. Thin
callbacks: gather inputs → call service → format outputs. No global mutable
state. Reuse components rather than duplicating markup. Fail safely — never
expose stack traces, SQL, passwords or connection strings in UI errors.

## Testing

```
python -m pytest -m "not db" -v     # pure logic
python -m pytest -v                 # full suite (needs Docker + seeded DB)
```

Tests must never write to the real `plant_monitoring` schema — use the
`isolated_schema` fixture. Unmarked tests may not open a DB connection.
Prefer structural/rendered Dash assertions over `repr()` comparisons.

Minimum coverage: hierarchy generation (30/71/120); metric configuration
(8 metrics, aggregation types); timestamp parsing; numeric parsing; KPI
calculations (statistics and delta); freshness evaluation; routing/URL parsing;
repository range filtering; seed integrity (row counts, per-metric coverage,
energy monotonicity).

## Definition of done

A developer can locally start PostgreSQL, seed the development data, run Dash,
log in, navigate the plant hierarchy, view a device dashboard, change the time
range, switch metrics, see correctly calculated KPIs, interact with the chart,
inspect recent readings, and observe the data freshness status.

## Working behaviour

- Do not perform a broad rewrite when a small change is sufficient.
- Report an authority conflict **before** editing, not after.
- Run the relevant tests and fix failures before moving on.
- Keep README commands accurate.
- Stop before commit/push when the active gate requires review.
- **A gate opens and closes on a green pack.** Run
  `python scripts/build_context_pack.py` (or `--check`) when a gate is
  written, and again before it is closed. Both, not one: the open run proves
  the gate's own citations resolve, and the close run proves the work did not
  break someone else's. This catches what the test suite structurally cannot
  — a broken ADR citation, an `Implemented-by` naming a commit that does not
  exist, a `Relevant files` path that has moved, a frozen manifest that no
  longer verifies. FIX-1's open run caught an ADR-012 `Implemented-by` field
  that 2,464 passing tests had nothing to say about.
