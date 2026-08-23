# Power Plant Dashboard

Primary development application: a dashboard visualising 8 metrics across a 30-plant
hierarchy from a PostgreSQL database. See `PROJECT_CONTEXT.md`,
`REQUIREMENTS.md`, `ARCHITECTURE.md`, `DATABASE.md`, `UI_SPEC.md` for
full context.

## Prerequisites
- Python 3.11+
- Docker + Docker Compose

## Setup

From a fresh clone on a machine that has never run this project:

```bash
# 1. Clone/open the project, then create your local env file
cp .env.example .env                 # PowerShell: Copy-Item .env.example .env

# 2. Install Python dependencies
python -m venv .venv
source .venv/bin/activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Start an EMPTY PostgreSQL
docker compose up -d postgres        # omit `postgres` to get pgAdmin on :5050 too

# 4. Build the schema — creates it and applies every migration
alembic upgrade head

# 5. Seed development data (30 plants, 71 transformers, 120 devices, ~1.38M readings)
python -m db.seed_plant_monitoring --reset

# 6. Seed the administration demo (5 technicians, 96 of 120 RTLs assigned)
python -m db.seed_admin_demo --reset

# 7. Run the app
python app.py
```

Open http://localhost:8050 and log in with the credentials you set as
`DEMO_USERNAME` / `DEMO_PASSWORD` in `.env`. There is no fallback credential:
if they are unset, every login is refused.

Stop the database with `docker compose stop` (keeps your data) or
`docker compose down -v` (destroys the volume, so step 4 onwards runs again).

### Alembic owns the schema

`docker compose up` starts an **empty** database and nothing else.
`alembic upgrade head` creates the schema and every table in it.

Postgres' `/docker-entrypoint-initdb.d` hook is deliberately unused. It
previously created the four baseline tables on first container init, which
meant `alembic upgrade head` then failed trying to create tables that already
existed — `001_baseline` uses `op.create_table`, which has no `IF NOT EXISTS`.
A fresh clone could not migrate, and the seed could not run either, because it
writes columns that migration 002 adds. `alembic stamp 001_baseline` worked
around that only by hiding which component owned the schema.

**No `alembic stamp` is needed on a fresh database, ever.**
`tests/test_bootstrap_contract.py` pins this.

### Upgrading a checkout that predates this change

Your data lives in the `powerplant_pgdata` volume, not the container, so
recreating the container does not touch it:

```bash
docker compose up -d postgres        # recreates without the init mounts
alembic upgrade head                 # no-op if you are already at head
```

If you have a database created by the old init script that has **no**
`alembic_version` table, that one — and only that one — still needs
`alembic stamp 001_baseline` once before `alembic upgrade head`.

## Signing in

The credential pair is checked by `services/auth_service.py`; the identity
behind it — `user_id`, `full_name` and `role` — is loaded from the
`plant_monitoring.users` row with that username. A first login on an empty
database creates that row with the `administrator` role, because the
workflows this application is built around are Administrator ones.

**If your database predates this** (its demo row was seeded as `general`),
correct it once, explicitly — nothing changes it for you at runtime. Either
edit the user in the User Administration screen, or:

```bash
python -c "from config.settings import demo_auth; \
from repositories import plant_monitoring_repository as repo; \
u = repo.get_user_by_username(demo_auth.username); \
repo.create_or_update_user(username=u.username, full_name=u.full_name, \
role='administrator', status=u.status, email_address=u.email_address, \
mobile_number=u.mobile_number)"
```

The role on that row now decides what the application shows you. An
Administrator sees the whole fleet plus the Administration section on the Fleet
Overview. A General user sees the whole fleet and may change nothing. A
Technician sees only the RTLs currently assigned to them, and the plants,
transformers and fleet counts they see are computed over that same set — so a
technician with no assignments sees an empty fleet rather than everything.
Reaching an out-of-scope resource by typing its URL gives "No access", which is
kept distinct from the "not found" a genuinely nonexistent id produces.

Note that the session is held in a browser-side store and the data callbacks
do not verify it independently. This establishes a consistent identity and a
consistent set of answers, not a secure authorization boundary — see
`docs/CODE_AUDIT.md`, "Security posture".

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

### Administration demo data (optional)

The monitoring seed above creates equipment only — no users, no assignments.
To demonstrate the Administrator screens against representative state rather
than an empty fleet:

```bash
python -m db.seed_admin_demo --reset
```

That creates five synthetic technicians and assigns 96 of the 120 RTLs,
leaving 24 unassigned so the exception workflow has something to show.
Development data only — never run it against production. It touches only the
identities it creates (`demo.tech01`..`demo.tech05`): `--reset` removes just
those users and the assignments they hold, a username collision with a real
account is refused rather than overwritten, and a device already assigned
outside the seed keeps its technician.

The two seeds are deliberately separate. The monitoring seed describes
equipment; this one describes people and responsibilities, and refreshing
readings should never silently create a staff list.

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
│   ├── init_plant_monitoring.sql.template  # Reference only — NOT mounted
│   ├── init_plant_monitoring.sh    # Reference only — Alembic owns the schema
│   ├── generators.py               # Deterministic multi-metric data generation
│   ├── hierarchy.py                # 71 transformers, 120 devices
│   ├── seed_plant_monitoring.py    # Bulk seed via COPY (~1.38M rows)
│   └── seed_admin_demo.py          # Opt-in technicians + RTL assignments
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
