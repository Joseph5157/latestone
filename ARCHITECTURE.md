# Architecture — Powerplant Dashboard

## High-Level Architecture

```text
Browser
  |
  v
Plotly Dash application
  |
  +-- UI components/pages
  +-- callbacks/controllers
  |
  v
Service layer
  |
  v
Repository / data-access layer
  |
  v
SQLAlchemy
  |
  v
PostgreSQL (Docker)
  |
  +-- schema: plant_monitoring
       +-- plants (30 rows)
       +-- transformers (71 rows)
       +-- devices (120 rows)
       +-- readings (~1.38M rows, 8 metrics)
```

## Core Rule
The dashboard must never issue SQL directly from page/component code.

Preferred flow:

```text
UI asks:
get_metric_view(device_id="plant-01-t1-d1", metric="temperature", period=24h)

        -> Monitoring service
        -> Hierarchy service validates device exists
        -> Repository queries plant_monitoring.readings
        -> Typed/normalised data
        -> View model (MetricView)
        -> UI
```

## Project Structure

```text
powerplant-dashboard/
├── app.py                          # Dash app, layout, callback registration
├── config/
│   ├── settings.py                 # All environment config
│   └── metrics.py                  # 8-metric registry
├── pages/
│   ├── login.py
│   ├── plants_overview.py
│   ├── plant_detail.py
│   ├── transformer_detail.py
│   └── device_dashboard.py
├── callbacks/
│   ├── routing.py                  # URL parsing, page routing
│   ├── auth.py
│   ├── listings.py
│   └── device.py
├── components/
│   ├── kpi_card.py
│   ├── metric_chart.py
│   ├── metric_snapshot_strip.py
│   ├── readings_table.py
│   ├── freshness_badge.py
│   ├── status_panels.py
│   ├── breadcrumb.py
│   ├── entity_table.py
│   ├── equipment_context.py
│   ├── app_header.py
│   └── hierarchy_selector.py
├── services/
│   ├── auth_service.py
│   ├── monitoring_service.py
│   └── hierarchy_service.py
├── repositories/
│   └── plant_monitoring_repository.py
├── db/
│   ├── engine.py
│   ├── init_plant_monitoring.sql
│   ├── generators.py
│   ├── hierarchy.py
│   └── seed_plant_monitoring.py
├── assets/
│   └── app.css
└── tests/
```

## Layering Rules
1. **Pages** render layout only; no queries, no business logic.
2. **Callbacks** gather inputs, call services, format outputs.
3. **Services** contain KPI calculations, freshness evaluation, view models.
4. **Repositories** are the only place SQL is written. Raw SQL lives in `plant_monitoring_repository.py`.
5. **Config** centralises metric metadata and aggregation types.

## Schema Design
The `plant_monitoring` schema uses a normalised hierarchy:
- `plants` → `transformers` → `devices` → `readings`
- Each reading row stores one metric value (no wide tables).
- All hierarchy identifiers are validated through `hierarchy_service`.

## Authentication Boundary
Demo authentication is intentionally local/mock. Keep it behind an authentication service so it can later be replaced by the client's real API/session/SSO mechanism.

## Error Handling
The UI should gracefully handle:
- PostgreSQL unavailable
- Empty selected period
- Invalid/failed value conversion
- Invalid device identifiers
- Authentication failure

Do not expose database stack traces or credentials in the browser.

## Future Production Integration
Expected migration path:

```text
LOCAL
Docker PostgreSQL -> Repository -> Services -> Dash

PRODUCTION
Client PostgreSQL/API -> Updated repository/adapter -> Same services/UI where possible
```

Do not prematurely implement Kubernetes manifests until the client's deployment requirements are known.
