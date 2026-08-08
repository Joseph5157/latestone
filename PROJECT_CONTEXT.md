# Powerplant Dashboard — Project Context

## Purpose
Build a local proof-of-concept dashboard for a client that operates power-plant monitoring infrastructure. The production backend/database already exists; this demo is intended to prove the Python frontend/dashboard approach before integration with the client's environment.

## Known Client Context
- Client has approximately 30 plants in different locations.
- Plants use mostly similar metrics and dashboard patterns.
- Production data is stored in PostgreSQL.
- Production deployment/infrastructure involves Kubernetes.
- Final development/integration may occur through restricted VS Code Remote SSH access.
- Measurements appear to arrive approximately every 30 minutes.
- Client wants interactive visualisations, KPIs, tables and warnings.
- Frontend/dashboard should be implemented in Python.

## Known Database Convention
A PostgreSQL schema shown by the client is `trfr_temperature`.

Within that schema, tables are named using:

`<transformer_name>_<device_name>`

Example:
- Transformer: `aa12`
- Device: `29017`
- Table: `aa12_29017`

Another observed table is `aa28_29044`.

The observed temperature table contains:
- `timestamp` — currently represented in the client's example as `character varying(17)` and used as the primary key.
- `temperature` — currently represented as `character varying(4)`.

The client screenshot showed approximately 2,112 tables in the `trfr_temperature` schema. Do not assume all production schemas or metrics until confirmed.

## Demo Scope
The demo uses a development schema (`plant_monitoring`) that models the client's hierarchy:

- 30 plants, 71 transformers, 120 devices
- 8 metrics: temperature, voltage, current, active_power, reactive_power, power_factor, frequency, energy
- Reserved identifier: `plant-01-t1-d1` = `aa12` / `29017`

Generate realistic local demo readings at approximately 30-minute intervals (1,383,360 total rows).

## Technology Decisions
- Python
- Plotly Dash for the application/dashboard
- Plotly for charts
- PostgreSQL for local data
- Docker / Docker Compose for local PostgreSQL
- SQLAlchemy for database access

## Architectural Principle
Dash components must not contain raw database access or depend directly on physical PostgreSQL table names. A data-access/service layer must translate domain requests (device ID, metric, time range) into the correct schema/table query.

This is important because the demo database is only a local representation of the client's known structure. Production integration may require changes to database mappings without changing the UI.

## Demo Goal
Demonstrate this journey:

Login → Plants overview → Plant detail → Transformer detail → Device dashboard → Metric selection → KPIs → Interactive chart → Period filtering → Recent readings → Data freshness.

The demo should be professional enough to show the client and serve as a foundation for production integration.
