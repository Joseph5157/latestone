# Database Specification — Powerplant Dashboard

## Goal
Provide a local PostgreSQL schema that mirrors the client's known naming convention while supporting the 30-plant hierarchy with 8 metrics.

## Local PostgreSQL
Run PostgreSQL through Docker Compose.

Database name: `powerplant_demo`

## Schema: `plant_monitoring`

The development schema is `plant_monitoring`, separate from the client's `trfr_temperature`. This keeps the demo independent of the production schema while following the same PostgreSQL conventions.

### DDL

Generated from `db/init_plant_monitoring.sql.template`, which is the single
source of truth. `db/init_plant_monitoring.sh` substitutes
`PLANT_MONITORING_SCHEMA` for `@SCHEMA@` at container init; the default is
shown here.

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
