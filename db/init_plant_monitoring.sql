-- Plant monitoring schema — our clean, normalized internal model.
--
-- This deliberately does NOT reproduce the client's ~2,112-table physical
-- structure (one table per transformer/device pair, VARCHAR timestamp and
-- value columns). That layout is a property of the client's current database,
-- not a requirement on ours. We model the domain as a normalized
-- Plant -> Transformer -> Device -> Reading hierarchy with real TIMESTAMPTZ
-- and NUMERIC types, and map to whatever the client ships when their
-- consolidated table lands.
--
-- `status` columns are ADMINISTRATIVE status only (active/inactive). They
-- never hold computed monitoring status. Data freshness and monitoring
-- condition are separate concepts, computed in the service layer and never
-- persisted here.
--
-- Metric display metadata (label, unit, precision, chart type, display order,
-- aggregation semantics) lives in `config/metrics.py`, NOT in the database.
-- `readings.metric` is a generic metric key; there are no metric-specific
-- columns.

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
