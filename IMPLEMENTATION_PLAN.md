# Implementation Plan — Powerplant Dashboard

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
- Create `plant_monitoring` schema with DDL.
- Add health check.

**Done when:** database starts from a clean environment and table existence can be verified.

## Phase 2 — Hierarchy Generation
- Build deterministic hierarchy generator (30 plants, 71 transformers, 120 devices).
- Reserve `plant-01-t1-d1` = `aa12`/`29017`.
- Add hierarchy generation tests.

**Done when:** hierarchy counts and determinism tests pass.

## Phase 3 — Multi-Metric Data Generation
- Build 8-metric series generator (temperature, voltage, current, active_power, reactive_power, power_factor, frequency, energy).
- Implement cumulative energy with monotonic guard.
- Add generator tests.

**Done when:** generation tests pass and energy is monotonically increasing.

## Phase 4 — Metric Configuration
- Create `config/metrics.py` with 8-metric registry.
- Define aggregation types (statistics vs delta), units, precision.
- Add metric config tests.

**Done when:** metric registry tests pass.

## Phase 5 — Repository Layer
- Implement `repositories/plant_monitoring_repository.py`.
- Hierarchy queries (list/get plants/transformers/devices, breadcrumb, counts).
- Latest readings (single metric or batched).
- Range queries (single metric or batched, ordered ascending).
- Add DB-dependent repository tests.

**Done when:** repository tests pass against seeded database.

## Phase 6 — Service Layer
- Implement `services/monitoring_service.py` (view models, freshness, statistics/delta).
- Implement `services/hierarchy_service.py` (active filtering, parent validation).
- Add service tests (pure logic, no DB).

**Done when:** service tests pass.

## Phase 7 — Components
- Build reusable components: kpi_card, metric_chart, metric_snapshot_strip, readings_table, freshness_badge, status_panels, breadcrumb, entity_table, equipment_context, app_header, hierarchy_selector.
- Add component tests.

**Done when:** component tests pass.

## Phase 8 — Routing and Navigation
- Implement URL parsing and hierarchy routing in `callbacks/routing.py`.
- Implement auth callbacks in `callbacks/auth.py`.
- Create page shells (login, plants_overview, plant_detail, transformer_detail, device_dashboard).
- Add routing tests.

**Done when:** routing tests pass and all valid URLs render.

## Phase 9 — Plant, Transformer and Device Listings
- Implement `callbacks/listings.py` (populate overview/plant/transformer tables).
- Wire cascading hierarchy selector callbacks.
- Add listing population tests.

**Done when:** listing callbacks populate tables correctly.

## Phase 10 — Device Monitoring Dashboard
- Implement `callbacks/device.py` (snapshot strip, KPIs, chart, readings, URL sync).
- Wire metric/period to URL for shareability.
- Add device dashboard tests.

**Done when:** device dashboard renders with metric selection and period filtering.

## Phase 11 — Refresh and Data-Freshness Behaviour
- Add freshness policy tests (configuration-driven thresholds).
- Verify refresh trigger respects configuration.

**Done when:** freshness policy tests pass.

## Phase 12 — Responsive CSS
- Update `assets/app.css` with responsive breakpoints.
- Add styles for all new components.

**Done when:** layout works on desktop and tablet widths.

## Phase 13 — Legacy Retirement
- Delete legacy files (old pages, services, repositories, components, SQL, seed scripts, tests).
- Implement router callback in `callbacks/routing.py`.
- Slim `app.py` to layout + callback registration.
- Clean `config/settings.py` and `.env.example`.

**Done when:** no legacy imports remain, full test suite passes.

## Phase 14 — Test Consolidation
- Add `pytest.ini` with `db` marker configuration.
- Create seed-integrity tests (row counts, per-metric coverage, sampling cadence, energy monotonicity, referential integrity).
- Two suite modes: pure-logic and full.

**Done when:** `python -m pytest -m "not db"` (131 tests) and `python -m pytest` (168 tests) both pass.

## Phase 15 — Performance Guardrails (pending)
- Add query timing assertions.
- Verify batched queries are efficient.

## Phase 16 — e2e Verification (pending)
- Verify full operator workflow end-to-end.
- Test all navigation paths.

## Phase 17 — Documentation (pending)
- Update all project documentation to reflect current state.

## Stop Condition
Do not expand beyond the current scope unless explicitly instructed.
