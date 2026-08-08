# Architecture — Powerplant Dashboard Demo

## High-Level Architecture

```text
Browser
  |
  v
Plotly Dash application
  |
  +-- UI components/pages
  +-- callbacks/controllers
  |
  v
Service layer
  |
  v
Repository / data-access layer
  |
  v
SQLAlchemy
  |
  v
PostgreSQL (Docker)
  |
  +-- schema: trfr_temperature
       +-- table: aa12_29017
```

## Core Rule
The dashboard must never issue SQL directly from page/component code.

Preferred flow:

```text
UI asks:
get_temperature(transformer="aa12", device="29017", range=...)

        -> Temperature service
        -> Repository resolves validated physical identifier
        -> trfr_temperature.aa12_29017
        -> PostgreSQL query
        -> Typed/normalised data
        -> UI
```

## Suggested Project Structure

```text
powerplant-dashboard/
├── CLAUDE.md
├── README.md
├── docker-compose.yml
├── .env.example
├── requirements.txt or pyproject.toml
├── app.py
├── config/
│   └── settings.py
├── pages/
│   ├── login.py
│   └── dashboard.py
├── components/
│   ├── kpi_card.py
│   ├── temperature_chart.py
│   ├── period_filter.py
│   └── readings_table.py
├── services/
│   ├── auth_service.py
│   └── temperature_service.py
├── repositories/
│   └── temperature_repository.py
├── db/
│   ├── engine.py
│   ├── init.sql
│   └── seed.py
├── assets/
│   └── app.css
└── tests/
    ├── test_temperature_service.py
    └── test_temperature_repository.py
```

This structure is guidance; keep it simple and adjust only when there is a clear benefit.

## Database Boundary
The known client convention uses dynamic physical table names. Therefore:
- Validate transformer and device identifiers with a strict pattern/allowlist.
- Construct physical table names only inside the repository/data-access layer.
- Never accept an arbitrary table name directly from a browser request.
- Keep the schema name configurable where practical.

## Data Normalisation
Although the client's observed DDL stores timestamp and temperature as character varying fields, application code should convert them immediately after retrieval into:
- Python/Pandas datetime for timestamp
- Numeric value for temperature

For the local mirror, see `DATABASE.md` for the deliberate compatibility decision.

## Authentication Boundary
Demo authentication is intentionally local/mock. Keep it behind an authentication service so it can later be replaced by the client's real API/session/SSO mechanism.

## Error Handling
The UI should gracefully handle:
- PostgreSQL unavailable
- Empty selected period
- Invalid/failed value conversion
- Invalid device identifiers
- Authentication failure

Do not expose database stack traces or credentials in the browser.

## Future Production Integration
Expected migration path:

```text
LOCAL
Docker PostgreSQL -> Repository -> Services -> Dash

PRODUCTION
Client PostgreSQL/API -> Updated repository/adapter -> Same services/UI where possible
```

Do not prematurely implement Kubernetes manifests until the client's deployment requirements are known.
