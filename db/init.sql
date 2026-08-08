-- Demo schema mirroring the client's known trfr_temperature convention.
-- Deliberately uses VARCHAR types to match the client's observed DDL so the
-- repository layer is forced to handle the same conversion problem expected
-- during production integration. Do not "fix" these types here.

CREATE SCHEMA IF NOT EXISTS trfr_temperature;

CREATE TABLE IF NOT EXISTS trfr_temperature.aa12_29017 (
    "timestamp" VARCHAR(17) NOT NULL,
    temperature VARCHAR(4) NOT NULL,
    CONSTRAINT aa12_29017_pkey PRIMARY KEY ("timestamp")
);
