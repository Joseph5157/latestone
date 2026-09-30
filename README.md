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

# 8. (optional) In a second terminal, stream new readings while you look around
python -m db.live_simulator
```

Step 8 is optional: it appends one fresh reading per device every 10s (see
`db/live_simulator.py`) so the freshness badge, latest-value KPIs, and charts
visibly move instead of showing static seeded history. Configurable via
`LIVE_SIM_*` in `.env.example`; stop it with Ctrl+C any time.

### Refreshing development data so it looks live

The seeded readings end when you ran step 5, so after a few days every RTL
reads silent for more than 24 hours. To bring the data back to a realistic,
live-looking state (all synthetic; run from the repo root):

```bash
python -m db.seed_freshness_demo --restore        # only if .freshness-demo-capture.json exists
python -m db.seed_plant_monitoring --reset        # readings re-dated to end now (events, users, history kept)
python -m db.seed_freshness_demo --apply          # 3 RTLs Stale / No Data on purpose (undo: --restore)
LIVE_SIM_EVENTS_PER_DAY=12 python -m db.live_simulator --backfill-events-days 7   # 7 days of events
LIVE_SIM_EVENTS_PER_DAY=12 LIVE_SIM_INTERVAL_SECONDS=300 python -m db.live_simulator   # leave running
```

PowerShell: set the variables first, e.g.
`$env:LIVE_SIM_EVENTS_PER_DAY='12'; python -m db.live_simulator --backfill-events-days 7`.

- `LIVE_SIM_EVENTS_PER_DAY` (default 0 = off) makes the simulator raise
  simulated startup, check-in, battery-low, power-down and sensor-error events
  through the same ingestion path real events use. Events are append-only:
  running the backfill twice doubles them.
- While the freshness demo is applied, the simulator leaves its silenced
  feeds alone, so those RTLs stay Stale / No Data.
- **Test temperature limits:** Administration → Settings → Temperature and
  vibration, warning **36 °C**, critical **40 °C**. These are test values, not
  Eskom values. Synthetic temperatures follow the time of day: around 12:00
  UTC about 19 RTLs reach 36 °C and 4 reach 40 °C; overnight none do.
- The full test suite (`python -m pytest`) expects the plain seed:
  `tests/test_seed_integrity.py` and the repository range tests pin exact row
  counts and 30-minute spacing. Stop the simulator, then
  `python -m db.seed_freshness_demo --restore` and
  `python -m db.seed_plant_monitoring --reset` before running it; re-apply
  the freshness demo afterwards. `python -m pytest -m "not db"` is unaffected.

Open http://127.0.0.1:8050 and log in with the credentials you set as
`DEMO_USERNAME` / `DEMO_PASSWORD` in `.env`. There is no fallback credential:
if they are unset, every login is refused.

On Windows prefer `127.0.0.1` to `localhost`: `localhost` tries IPv6 first
and the dev server listens on IPv4, which adds roughly 0.2–0.3 s to every
request (measured 2026-09-19). Logins are kept per address, so sign in
again after switching.

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

### Client RTL Technician assignments (one-time bootstrap)

Technicians see only the client RTLs assigned to them (ADR-032). The
assignments live in the application database (`rtl_technician_assignments`);
the client SQL Server is only read, never written. To adopt the client's legacy
assignment snapshot once, as transitional evidence:

```bash
python -m scripts.bootstrap_rtl_assignments                               # PREVIEW only
python -m scripts.bootstrap_rtl_assignments --apply --provision-technicians
```

The preview lists the candidate assignments, the excluded
historical/unregistered UIDs and any blocking problem, and writes nothing.
`--apply` imports only from a clean preview, in one transaction, and is safe to
re-run. It is never run at application start-up. Administrators then assign and
reassign RTLs at `/technicians/assignments`.

## Running tests

The test runner is not part of the runtime install:

```bash
pip install -r requirements-dev.txt
```

Pure-logic tests (no Docker required):

```bash
python -m pytest -m "not db" -v
```

This is enforced, not just a convention: an autouse fixture in
`tests/conftest.py` fails any test without the `db` marker that opens a
database connection, so a missing mock cannot pass locally against a running
PostgreSQL and then fail on a clean checkout.

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
│   ├── seed_admin_demo.py          # Opt-in technicians + RTL assignments
│   └── live_simulator.py           # Optional: append live readings on a timer
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
- **Freshness policy**: one configurable global operational threshold,
  `FRESHNESS_STALE_AFTER_MINUTES`, defaults to 1,440 minutes (24 hours).
  This interim policy is not an RTL-specific reporting cadence. The legacy
  `EXPECTED_INTERVAL_MINUTES` / `STALE_AFTER_INTERVALS` pair is ignored.

## Architecture rule (do not violate)

UI and page/component code must never execute SQL. Only
`repositories/plant_monitoring_repository.py` builds SQL queries, and
only after validating hierarchy identifiers through `hierarchy_service`.
