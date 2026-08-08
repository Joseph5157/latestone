# Implementation Plan — Powerplant Dashboard Demo

## Phase 0 — Project Bootstrap
- Create Python project structure.
- Add dependency management.
- Add `.env.example` and configuration module.
- Add README with local commands.
- Confirm application starts with a minimal Dash page.

**Done when:** Dash starts locally with no database dependency errors during import.

## Phase 1 — PostgreSQL in Docker
- Add `docker-compose.yml`.
- Start PostgreSQL locally.
- Create `trfr_temperature` schema.
- Create `aa12_29017` table using the known client-compatible structure.
- Add health check where practical.

**Done when:** database starts from a clean environment and table existence can be verified.

## Phase 2 — Seed Data
- Build repeatable seed script.
- Generate at least 30 days of approximately 30-minute temperature readings.
- Add realistic variation and a few demo warning values.
- Ensure timestamps are unique.

**Done when:** reseeding produces a usable deterministic dataset without duplicate-key failures.

## Phase 3 — Repository and Service Layer
- Configure SQLAlchemy engine/session/connection handling.
- Implement validated transformer/device -> physical table resolution.
- Implement readings-by-range query.
- Implement latest/min/max/average/recent operations.
- Parse timestamp strings and temperature strings safely.
- Add tests for conversions and identifier validation.

**Done when:** tests can retrieve correct values without Dash being involved.

## Phase 4 — Local Authentication
- Implement login page.
- Isolate demo credentials/configuration.
- Protect dashboard route/page from unauthenticated access.
- Add logout.

**Done when:** invalid login fails and valid demo login reaches dashboard.

## Phase 5 — Dashboard UI
- Build header/device context.
- Build four KPI cards.
- Build 24h/7d/30d/custom period control.
- Build Plotly temperature line chart.
- Build recent readings table.
- Build Normal/Warning/No-data state.

**Done when:** changing the period updates all relevant components consistently.

## Phase 6 — Resilience and UX
- Handle database unavailable state.
- Handle empty ranges.
- Handle malformed source values without crashing the whole dashboard.
- Add loading states where useful.
- Improve desktop/laptop responsiveness.

## Phase 7 — Demo Verification
Test the full path:

```text
Docker up
-> database ready
-> seed data
-> Dash start
-> login
-> AA12 / 29017 dashboard
-> KPI calculations
-> time filters
-> chart hover/zoom
-> readings table
-> warning demonstration
```

## Stop Condition
Do not expand to more plants, transformers, devices or electrical metrics until the one-device temperature demo is working and reviewed.
