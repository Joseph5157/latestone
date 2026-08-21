# Power Plant Dashboard

Primary development application: a dashboard visualising 8 metrics across a 30-plant
hierarchy from a PostgreSQL database. See `PROJECT_CONTEXT.md`,
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

# 4. Seed development data (30 plants, 120 devices, ~1.38M readings)
python -m db.seed_plant_monitoring --reset

# 5. Run the app
python app.py
```

### Upgrading an existing checkout

The schema DDL moved from `db/init_plant_monitoring.sql` to
`db/init_plant_monitoring.sql.template` plus `db/init_plant_monitoring.sh`, so
the schema name honours `PLANT_MONITORING_SCHEMA` instead of being hard-coded.

If you already have a `powerplant_demo_postgres` container, recreate it rather
than restarting it:

```bash
docker compose up -d          # recreates with the new mounts
```

`docker start <container>` will fail with exit 127, because the old container
still bind-mounts the file that was renamed — and Docker silently recreates the
missing source as an empty directory. Your data is safe either way: it lives in
the `powerplant_pgdata` volume, not the container. Delete any stray
`db/init_plant_monitoring.sql` *directory* if one appears.

Open http://localhost:8050 and log in with the credentials you set as
`DEMO_USERNAME` / `DEMO_PASSWORD` in `.env`. There is no fallback credential:
if they are unset, every login is refused.

## Reseeding

```bash
python -m db.seed_plant_monitoring --reset
```

`--reset` is required, not optional. Without it the device insert's
`ON CONFLICT DO NOTHING` skips rows that already exist, so an existing database
keeps whatever `devices.created_at` it was first given and never picks up the
generated registration history. That is deliberate: a `DO UPDATE` would also
overwrite the genuine registration timestamp of any device registered through
the app.

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
│   ├── logging_config.py           # Logging setup, called once at startup
│   └── metrics.py                  # 8-metric registry, aggregation types
├── pages/
│   ├── login.py                    # Login page shell
│   ├── plants_overview.py          # 30-plant listing
│   ├── plant_detail.py             # Transformer listing for a plant
│   ├── transformer_detail.py       # Device listing for a transformer
│   └── device_dashboard.py         # Device monitoring dashboard
├── routes.py                       # URL parsing/building, shared by both layers
├── callbacks/
│   ├── routing.py                  # Page routing, page-context assembly
│   ├── auth.py                     # Login/logout callbacks
│   ├── listings.py                 # Table population and row-click navigation
│   ├── equipment_selector.py       # Cascade + cross-plant device navigation
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
│   ├── app_header.py               # Brand, breadcrumb, freshness slot, logout
│   └── equipment_selector.py       # Cascading plant/transformer/device dropdowns
├── services/
│   ├── auth_service.py             # Placeholder credential verification
│   ├── monitoring_service.py       # View models, freshness, statistics/delta
│   └── hierarchy_service.py        # Active filtering, parent validation
├── repositories/
│   └── plant_monitoring_repository.py  # ALL raw SQL, hierarchy + readings
├── db/
│   ├── engine.py                   # SQLAlchemy engine/session
│   ├── init_plant_monitoring.sql.template  # Schema DDL (@SCHEMA@ placeholder)
│   ├── init_plant_monitoring.sh    # Substitutes PLANT_MONITORING_SCHEMA at init
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
