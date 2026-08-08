-- Multi-plant monitoring demo schema.
--
-- Built to demonstrate the consolidated single-table design proposed to
-- the client's DB team as a replacement for the one-table-per-device
-- pattern (trfr_temperature.<transformer>_<device>, 2,112 tables in
-- production). This schema is additive: it does not touch or replace
-- trfr_temperature, which continues to mirror the client's current
-- production shape for the single-device demo.
--
-- Seeded with real plant names/locations from the Kaggle "Global Power
-- Plant Database" (WRI) and synthetic temperature readings - see
-- db/seed_multi_plant.py.

CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.plants (
    plant_id     VARCHAR(20) PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    country      VARCHAR(100) NOT NULL,
    latitude     NUMERIC(8, 4) NOT NULL,
    longitude    NUMERIC(8, 4) NOT NULL,
    capacity_mw  NUMERIC(10, 1),
    primary_fuel VARCHAR(50),
    transformer  VARCHAR(10) NOT NULL,
    device       VARCHAR(10) NOT NULL
);

CREATE TABLE IF NOT EXISTS monitoring.readings (
    id          BIGSERIAL PRIMARY KEY,
    plant_id    VARCHAR(20) NOT NULL REFERENCES monitoring.plants (plant_id),
    transformer VARCHAR(10) NOT NULL,
    device      VARCHAR(10) NOT NULL,
    metric      VARCHAR(20) NOT NULL,
    reading_ts  TIMESTAMPTZ NOT NULL,
    value       NUMERIC(10, 2) NOT NULL,
    UNIQUE (plant_id, metric, reading_ts)
);

CREATE INDEX IF NOT EXISTS ix_monitoring_readings_lookup
    ON monitoring.readings (plant_id, metric, reading_ts DESC);
