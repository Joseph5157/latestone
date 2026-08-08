# Database Specification — Powerplant Dashboard

## Goal
Provide a local PostgreSQL schema that mirrors the client's known naming convention while supporting the 30-plant hierarchy with 8 metrics.

## Local PostgreSQL
Run PostgreSQL through Docker Compose.

Database name: `powerplant_demo`

## Schema: `plant_monitoring`

The development schema is `plant_monitoring`, separate from the client's `trfr_temperature`. This keeps the demo independent of the production schema while following the same PostgreSQL conventions.

### DDL

```sql
CREATE SCHEMA IF NOT EXISTS plant_monitoring;

CREATE TABLE plant_monitoring.plants (
    plant_id        TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    country         TEXT NOT NULL,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    primary_fuel    TEXT,
    capacity_mw     DOUBLE PRECISION,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plant_monitoring.transformers (
    transformer_id   TEXT PRIMARY KEY,
    plant_id         TEXT NOT NULL REFERENCES plant_monitoring.plants(plant_id),
    transformer_code TEXT NOT NULL,
    tier             TEXT NOT NULL,
    capacity_mva     DOUBLE PRECISION,
    status           TEXT NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plant_monitoring.devices (
    device_id       TEXT PRIMARY KEY,
    transformer_id  TEXT NOT NULL REFERENCES plant_monitoring.transformers(transformer_id),
    device_code     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plant_monitoring.readings (
    device_id   TEXT NOT NULL REFERENCES plant_monitoring.devices(device_id),
    metric      TEXT NOT NULL,
    reading_ts  TIMESTAMPTZ NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (device_id, metric, reading_ts)
);
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

| Metric          | Unit    | Aggregation | Precision |
|-----------------|---------|-------------|-----------|
| temperature     | °C      | statistics  | 1         |
| voltage         | kV      | statistics  | 3         |
| current         | A       | statistics  | 3         |
| active_power    | MW      | statistics  | 3         |
| reactive_power  | MVAr    | statistics  | 3         |
| power_factor    | —       | statistics  | 3         |
| frequency       | Hz      | statistics  | 3         |
| energy          | MWh     | delta       | 3         |

- **Statistics metrics**: KPIs show current/min/max/average for the selected period.
- **Delta metric** (energy): KPIs show period change (last − first). Energy is monotonically increasing (cumulative meter).

### Data Generation
- 30 days of readings at 30-minute intervals (1,441 timestamps per device).
- 120 devices × 1,441 timestamps × 8 metrics = 1,383,360 rows.
- Deterministic generation using device index as random seed.
- Daily temperature swing, load-correlated current, power-factor stability.

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
POSTGRES_PORT=5432
PLANT_MONITORING_SCHEMA=plant_monitoring
```

Provide `.env.example`; do not commit a real `.env` containing secrets.
