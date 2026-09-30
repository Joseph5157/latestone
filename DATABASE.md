# Database Specification — Powerplant Dashboard

> This file specifies the **legacy synthetic PostgreSQL development schema**. Before any work involving the client RTL SQL Server, read `docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md`. "Plant" is not a client SQL Server hierarchy level.

## Goal
Provide a local PostgreSQL schema that mirrors the client's known naming convention while supporting the 30-plant hierarchy with 8 metrics.

## Local PostgreSQL
Run PostgreSQL through Docker Compose.

Database name: `powerplant_demo`

## Schema: `plant_monitoring`

The development schema is `plant_monitoring`, separate from the client's `trfr_temperature`. This keeps the demo independent of the production schema while following the same PostgreSQL conventions.

### DDL

**Alembic is the single source of truth for the schema.** Every table is
created by `alembic upgrade head`, which starts from
`alembic/versions/001_baseline.py` and applies each later migration in turn.
The schema name comes from `PLANT_MONITORING_SCHEMA` via `config.settings`,
read by `alembic/env.py`; the default is shown here.

`db/init_plant_monitoring.sql.template` and `db/init_plant_monitoring.sh` are
retained for reference only. They are **no longer mounted** into the postgres
container — while they were, Docker created the baseline tables and
`001_baseline` then failed trying to create the same tables again, so no fresh
clone could migrate. See `tests/test_bootstrap_contract.py`.

```sql
CREATE SCHEMA IF NOT EXISTS plant_monitoring;

CREATE TABLE IF NOT EXISTS plant_monitoring.plants (
    plant_id     VARCHAR(20)  PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    country      VARCHAR(100) NOT NULL,
    latitude     NUMERIC(8,4) NOT NULL,
    longitude    NUMERIC(8,4) NOT NULL,
    capacity_mw  NUMERIC(10,1),
    primary_fuel VARCHAR(50),
    status       VARCHAR(20)  NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS plant_monitoring.transformers (
    transformer_id   VARCHAR(30) PRIMARY KEY,
    plant_id         VARCHAR(20) NOT NULL REFERENCES plant_monitoring.plants(plant_id),
    transformer_code VARCHAR(10) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'active',
    UNIQUE (plant_id, transformer_code)
);

CREATE TABLE IF NOT EXISTS plant_monitoring.devices (
    device_id      VARCHAR(30) PRIMARY KEY,
    transformer_id VARCHAR(30) NOT NULL REFERENCES plant_monitoring.transformers(transformer_id),
    device_code    VARCHAR(10) NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'active',
    UNIQUE (transformer_id, device_code)
);

CREATE TABLE IF NOT EXISTS plant_monitoring.readings (
    id         BIGSERIAL     PRIMARY KEY,
    device_id  VARCHAR(30)   NOT NULL REFERENCES plant_monitoring.devices(device_id),
    metric     VARCHAR(30)   NOT NULL,
    reading_ts TIMESTAMPTZ   NOT NULL,
    value      NUMERIC(12,3) NOT NULL,
    UNIQUE (device_id, metric, reading_ts)
);

CREATE INDEX IF NOT EXISTS ix_transformers_plant_id     ON plant_monitoring.transformers (plant_id);
CREATE INDEX IF NOT EXISTS ix_devices_transformer_id    ON plant_monitoring.devices (transformer_id);
CREATE INDEX IF NOT EXISTS ix_readings_device_metric_ts ON plant_monitoring.readings (device_id, metric, reading_ts DESC);
```

### Reserved Identifiers
- `plant-01-t1-d1` maps to transformer `aa12` / device `29017` (the client-known example).

### Device code (RTL UID) rules
The schema allows any `device_code` up to 10 characters and only requires it
to be unique per transformer. The application is stricter
([ADR-022](docs/decisions/ADR-022-registration-enforces-the-5-digit-uid-fleet-wide.md)):

- Registration and RTL programming accept exactly 5 digits (`0-9`), e.g.
  `29017`. The rule lives in `services/rtl_uid.py`.
- Registration refuses a code already registered anywhere in the fleet,
  because the RTL Master addresses a device by UID alone.

Neither rule is a database constraint. Both are a development baseline
pending client confirmation. Data written outside the application (seeds,
direct SQL) is not checked, so keep seeded codes 5-digit and fleet-unique.
If the client confirms fleet-wide uniqueness, add `UNIQUE (device_code)`;
the current data already satisfies it (120 devices, 120 distinct codes).

## Hierarchy

| Entity     | Count | Source                   |
|------------|-------|--------------------------|
| Plants     | 30    | `db/seed_data/plants.json` |
| Transformers | 71  | `db/hierarchy.py`        |
| Devices    | 120   | `db/hierarchy.py`        |
| Readings   | 1,383,360 | `db/generators.py` |

## Seed Dataset

### Metrics (8 total)

| Metric | Unit | Aggregation | Precision |
|---|---|---|---|
| temperature | °C | statistics | 1 |
| voltage | kV | statistics | 2 |
| current | A | statistics | 1 |
| active_power | MW | statistics | 2 |
| reactive_power | MVAr | statistics | 2 |
| power_factor | — | statistics | 3 |
| frequency | Hz | statistics | 2 |
| energy | MWh | delta | 1 |

- **Statistics metrics**: KPIs show current/min/max/average for the selected period.
- **Delta metric** (energy): KPIs show period change (last − first). Energy is monotonically increasing (cumulative meter).

### Data Generation
- 30 days of readings at 30-minute intervals (1,441 timestamps per device).
- 120 devices × 1,441 timestamps × 8 metrics = 1,383,360 rows.
- Deterministic generation using device index as random seed.
- Daily temperature swing, load-correlated current, power-factor stability.
- `devices.created_at` carries ~18 months of generated registration history,
  spread deterministically by `device_id`. This is SYNTHETIC DEVELOPMENT SEED
  HISTORY, not a client registration record — the client has supplied no device
  registration dates. Registration is an administrative event and is
  independent of the 30-day reading window, so a device may hold readings that
  predate its own registration.

### Seeding

```bash
python -m db.seed_plant_monitoring --reset
```

Equipment only: plants, transformers, devices, readings. It never writes to
`users` or `user_device_assignments`.

Administration demo data is a separate, opt-in seed:

```bash
python -m db.seed_admin_demo --reset
```

Five synthetic technicians (`demo.tech01`..`demo.tech05`, `.invalid`
addresses) and a deterministic 96/24 assignment split across the 120 Managed
RTLs, giving 80% assignment coverage. Assignments go through
`assign_device_to_user`, so the one-active-assignment-per-device rule and
assignment history semantics apply exactly as they do in the app. Loads are
uneven (24/22/20/16/14) for realism only — no workload, territory, skills or
availability model is implied, and none of those are confirmed client
concepts. DEVELOPMENT/DEMO DATA: never run against production.

Verification:

```bash
docker compose exec postgres psql -U powerplant -d powerplant_demo -c "
SELECT (SELECT COUNT(*) FROM plant_monitoring.plants)       AS plants,
       (SELECT COUNT(*) FROM plant_monitoring.transformers) AS transformers,
       (SELECT COUNT(*) FROM plant_monitoring.devices)      AS devices,
       (SELECT COUNT(*) FROM plant_monitoring.readings)     AS readings;"
```

Expected: `plants=30`, `transformers=71`, `devices=120`, `readings=1383360`.

## Data Access Contract

All SQL lives in `repositories/plant_monitoring_repository.py`. Operations include:
- Hierarchy queries (list plants/transformers/devices, get by ID, breadcrumb)
- Latest readings (single metric or batched across metrics)
- Range queries (single metric or batched, ordered ascending)
- Hierarchy counts (transformer/device counts per plant)

The UI and services never execute SQL directly.

## Dynamic Identifier Safety
1. All hierarchy identifiers are validated through `hierarchy_service`.
2. Parent relationships are checked (confused-deputy guard).
3. Metric names are bound as parameters, never interpolated.
4. SQL identifiers (table/column names) are static strings, never derived from user input.

## Environment Configuration

```text
POSTGRES_DB=powerplant_demo
POSTGRES_USER=powerplant
POSTGRES_PASSWORD=<local-development-password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5436
PLANT_MONITORING_SCHEMA=plant_monitoring
```

Provide `.env.example`; do not commit a real `.env` containing secrets.
