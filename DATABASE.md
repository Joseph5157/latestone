# Database Specification — Powerplant Dashboard Demo

## Goal
Mirror the known client PostgreSQL naming convention sufficiently to test real integration behaviour without reproducing the complete production database.

## Local PostgreSQL
Run PostgreSQL through Docker Compose.

Recommended development database name:
`powerplant_demo`

## Schema
Create:

```sql
CREATE SCHEMA IF NOT EXISTS trfr_temperature;
```

## Demo Table
Create one physical table:

```text
trfr_temperature.aa12_29017
```

Naming interpretation:
- `aa12` = transformer name
- `29017` = device name

## Compatibility Decision
The client's screenshot showed the following types:
- `timestamp character varying(17)`
- `temperature character varying(4)`
- primary key on `timestamp`

For this demo, mirror those observed types so the repository is forced to handle the same conversion problem expected during integration.

Suggested DDL:

```sql
CREATE TABLE IF NOT EXISTS trfr_temperature.aa12_29017 (
    "timestamp" VARCHAR(17) NOT NULL,
    temperature VARCHAR(4) NOT NULL,
    CONSTRAINT aa12_29017_pkey PRIMARY KEY ("timestamp")
);
```

Do not redesign the client's production schema from this demo. In a greenfield system, timestamp/numeric database types would normally be preferable, but compatibility is the current objective.

## Timestamp Format
The observed client data resembles:

```text
16/12/29,13:53
16/12/29,14:23
```

Confirm the exact date interpretation with the client before production integration. For local seed data, choose and document one unambiguous parsing convention in code and test it.

## Seed Dataset
Generate at least 30 days of readings at approximately 30-minute intervals.

Example conceptual rows:

```text
timestamp          temperature
--------------------------------
26/08/01,00:00     31
26/08/01,00:30     32
26/08/01,01:00     31
...
```

Seed data should:
- Have realistic gradual variation rather than purely random noise.
- Contain daily variation where practical.
- Include a few high values for warning demonstrations.
- Be deterministic/reproducible by using a fixed random seed if randomness is used.
- Be idempotent or provide a clear reset/reseed command.

## Data Access Contract
Repository should expose domain-oriented operations such as:
- latest temperature
- readings between start/end
- min/max/average for a period
- recent N readings

The UI should not know SQL table details.

## Dynamic Identifier Safety
Because table names are derived from transformer/device identifiers:
1. Normalise to lowercase.
2. Validate transformer against a conservative pattern such as lowercase letters/digits only.
3. Validate device as digits only if that remains consistent with client data.
4. Prefer an explicit registry/allowlist of known demo devices.
5. Build identifiers only in the repository.
6. Never use raw browser input as a SQL identifier.

## Environment Configuration
Use environment variables for connection information, e.g.:

```text
POSTGRES_DB=powerplant_demo
POSTGRES_USER=powerplant
POSTGRES_PASSWORD=<local-development-password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Provide `.env.example`; do not commit a real `.env` containing secrets.
