# Power Plant Dashboard — Demo (AA12 / 29017)

Local proof-of-concept dashboard demonstrating one transformer/device
(temperature) from a PostgreSQL structure modelled on the client's known
schema. See `CLAUDE.md`, `PROJECT_CONTEXT.md`, `REQUIREMENTS.md`,
`ARCHITECTURE.md`, `DATABASE.md`, `UI_SPEC.md`, `IMPLEMENTATION_PLAN.md`
for full context.

**Scope:** one transformer (`aa12`), one device (`29017`), one metric
(temperature). Not the full 30-plant system — see "Explicitly Out of
Scope" in `REQUIREMENTS.md`.

## Prerequisites
- Python 3.11+
- Docker + Docker Compose

## Setup

```bash
# 1. Clone/open the project, then create your local env file
cp .env.example .env

# 2. Install Python dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Start PostgreSQL (creates trfr_temperature.aa12_29017 via db/init.sql)
docker compose up -d

# 4. Seed demo data (~30 days, ~30-min intervals, deterministic)
python -m db.seed

# 5. Run the app
python app.py
```

Open http://localhost:8050 and log in with the demo credentials from
`.env` (defaults: `admin` / `demo1234`).

## Reseeding

```bash
python -m db.seed --reset
```

## Running tests

Tests for parsing/validation/KPI logic run without a database:

```bash
pip install pytest
pytest tests/ -v
```

## Project structure

```text
powerplant-dashboard/
├── app.py                     # Dash app, layout, callbacks (thin)
├── config/settings.py         # All environment config, read once
├── pages/                     # login.py, dashboard.py
├── components/                # kpi_card, temperature_chart, period_filter, readings_table
├── services/                  # temperature_service.py, auth_service.py — parsing, KPIs, warnings
├── repositories/              # temperature_repository.py — ONLY place SQL/table names are built
├── db/                        # engine.py, init.sql, seed.py
├── assets/app.css             # styling (auto-loaded by Dash)
└── tests/                     # unit tests, no DB required
```

## Known assumptions (flagged, not client-confirmed)

- **Timestamp format**: stored as `YY/MM/DD,HH:MM` (17 chars), e.g.
  `26/08/01,00:00`. Inferred from `DATABASE.md` examples. **Confirm with
  the client before production integration** — see `db/seed.py` and
  `services/temperature_service.py`.
- **Warning threshold**: 45°C, configured via `DEMO_WARNING_THRESHOLD_C`
  in `.env`. This is a demo-only placeholder, not an official client
  threshold (per `REQUIREMENTS.md` FR-07).

## Architecture rule (do not violate)

UI and page/component code must never execute SQL or know physical table
names. Only `repositories/temperature_repository.py` builds identifiers
like `trfr_temperature.aa12_29017`, and only after validating the
transformer/device against a strict allowlist pattern *and* an explicit
known-device registry.

## Stop condition

Do not expand to more plants, transformers, devices, or electrical
metrics (voltage/current/power/frequency/energy) until this one-device
temperature demo is reviewed with the client.
