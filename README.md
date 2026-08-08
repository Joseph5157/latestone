# Power Plant Dashboard

Local proof-of-concept dashboard visualising 8 metrics across a 30-plant
hierarchy from a PostgreSQL database. See `CLAUDE.md`, `PROJECT_CONTEXT.md`,
`REQUIREMENTS.md`, `ARCHITECTURE.md`, `DATABASE.md`, `UI_SPEC.md` for
full context.

## Prerequisites
- Python 3.11+
- Docker + Docker Compose

## Setup

```bash
# 1. Clone/open the project, then create your local env file
cp .env.example .env

# 2. Install Python dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Start PostgreSQL
docker compose up -d

# 4. Seed demo data (30 plants, 120 devices, ~1.38M readings)
python -m db.seed_plant_monitoring --reset

# 5. Run the app
python app.py
```

Open http://localhost:8050 and log in with the demo credentials from
`.env` (defaults: `admin` / `demo1234`).

## Reseeding

```bash
python -m db.seed_plant_monitoring --reset
```

## Running tests

Pure-logic tests (no Docker required):

```bash
python -m pytest -m "not db" -v
```

Full test suite (requires Docker + seeded DB):

```bash
python -m pytest -v
```

## Project structure

```text
powerplant-dashboard/
├── app.py                          # Dash app, layout, callback registration
├── config/
│   ├── settings.py                 # All environment config, read once
│   └── metrics.py                  # 8-metric registry, aggregation types
├── pages/
│   ├── login.py                    # Login page shell
│   ├── plants_overview.py          # 30-plant listing
│   ├── plant_detail.py             # Transformer listing for a plant
│   ├── transformer_detail.py       # Device listing for a transformer
│   └── device_dashboard.py         # Device monitoring dashboard
├── callbacks/
│   ├── routing.py                  # URL parsing, page routing, page-context
│   ├── auth.py                     # Login/logout callbacks
│   ├── listings.py                 # Plant/transformer/device table population
│   └── device.py                   # Device dashboard data loading
├── components/
│   ├── kpi_card.py                 # Aggregation-aware KPI row
│   ├── metric_chart.py             # Metric-parameterized line chart
│   ├── metric_snapshot_strip.py    # 8-metric summary tiles
│   ├── readings_table.py           # Recent readings table
│   ├── freshness_badge.py          # Fresh/stale/no-data badge
│   ├── status_panels.py            # Not-found and error panels
│   ├── breadcrumb.py               # Navigation breadcrumb
│   ├── entity_table.py             # Generic DataTable wrapper
│   ├── equipment_context.py        # Plant/transformer/device identity bar
│   ├── app_header.py               # Shared header with selector and logout
│   └── hierarchy_selector.py       # Cascading plant/transformer/device dropdowns
├── services/
│   ├── auth_service.py             # Demo credential verification
│   ├── monitoring_service.py       # View models, freshness, statistics/delta
│   └── hierarchy_service.py        # Active filtering, parent validation
├── repositories/
│   └── plant_monitoring_repository.py  # ALL raw SQL, hierarchy + readings
├── db/
│   ├── engine.py                   # SQLAlchemy engine/session
│   ├── init_plant_monitoring.sql   # Schema DDL
│   ├── generators.py               # Deterministic multi-metric data generation
│   ├── hierarchy.py                # 71 transformers, 120 devices
│   └── seed_plant_monitoring.py    # Bulk seed via COPY (~1.38M rows)
├── assets/
│   └── app.css                     # Responsive styling
└── tests/
    ├── test_generators.py          # Multi-metric data generation
    ├── test_hierarchy_generation.py # Hierarchy determinism
    ├── test_metrics_config.py      # Metric registry
    ├── test_monitoring_service.py  # View models, freshness, statistics
    ├── test_hierarchy_service.py   # Active filtering, parent validation
    ├── test_plant_monitoring_repository.py  # DB-dependent repo tests
    ├── test_components.py          # Component rendering
    ├── test_routing.py             # URL parsing/building
    ├── test_freshness_policy.py    # Configuration-driven thresholds
    └── test_seed_integrity.py      # DB-dependent seed contract
```

## Known assumptions

- **Reserved identifiers**: `plant-01-t1-d1` maps to `aa12`/`29017` (the
  client-known example). All other IDs are synthetically generated.
- **Freshness policy**: 30-minute expected interval, 3 missed intervals
  = stale. This is a development policy, not a client-confirmed threshold.

## Architecture rule (do not violate)

UI and page/component code must never execute SQL. Only
`repositories/plant_monitoring_repository.py` builds SQL queries, and
only after validating hierarchy identifiers through `hierarchy_service`.
