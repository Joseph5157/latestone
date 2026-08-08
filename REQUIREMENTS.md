# Requirements — Powerplant Dashboard Demo

## 1. Demo Objective
Create a locally runnable proof of concept that demonstrates how the client's PostgreSQL transformer/device temperature data can be presented through an interactive Python dashboard.

## 2. Functional Requirements

### FR-01 Local Login
- Provide a professional login page.
- Use local/mock credentials for the demo only.
- Do not implement production authentication.
- Invalid credentials must show a clear error.
- Successful login opens the dashboard.
- Credentials must not be embedded throughout UI code; keep demo authentication isolated for later replacement.

### FR-02 Device Context
The demo represents:
- Transformer: `AA12`
- Device: `29017`
- Database table: `aa12_29017`
- Metric: temperature

Show transformer and device identity clearly on the dashboard.

### FR-03 KPI Cards
For the selected time range, show:
1. Current/latest temperature
2. Minimum temperature
3. Maximum temperature
4. Average temperature

Values must be calculated from database data, not hard-coded.

### FR-04 Temperature Trend
- Display temperature over time using Plotly.
- Hover must expose timestamp and temperature.
- Chart must respond to selected time range.
- The chart should remain readable with hundreds/thousands of readings.

### FR-05 Time Filtering
Provide convenient filters for:
- Last 24 hours
- Last 7 days
- Last 30 days
- Custom date/time range

### FR-06 Recent Readings
Show a table containing recent readings, including at minimum:
- Timestamp
- Temperature
- Derived demo status

Support sensible ordering with newest readings first.

### FR-07 Demo Warning
- Implement a configurable demonstration threshold.
- Clearly treat it as a demo configuration, not an official client threshold.
- Display Normal/Warning status based on the configured rule.
- Do not hard-code the threshold separately in multiple UI components.

### FR-08 Data Generation
- Seed realistic temperature data into local PostgreSQL.
- Approximate a 30-minute measurement interval.
- Include enough historical data to demonstrate 24-hour, 7-day and 30-day views.
- Include a small number of deliberately abnormal values to demonstrate warnings.
- Seed generation should be repeatable/reproducible where practical.

## 3. Non-Functional Requirements
- Local-first development.
- Application must run without access to the client's network.
- PostgreSQL must run in Docker.
- Keep UI, business/service logic and database access separated.
- Configuration and secrets must use environment variables where appropriate.
- Do not commit real credentials.
- Queries must be parameterised where parameters are supported.
- Dynamic SQL identifiers must be validated against strict naming rules/allowlists; never interpolate arbitrary user input as a schema/table identifier.
- Code should be modular and understandable for later production integration.
- Responsive layout suitable for a normal desktop/laptop dashboard.
- Provide useful error states when the database is unavailable or no readings exist.

## 4. Explicitly Out of Scope for Demo
- All 30 plants
- All 2,112 temperature tables
- Production authentication/SSO
- Production Kubernetes deployment
- Predictive maintenance/ML
- SMS/email alerts
- Production threshold definitions
- Editing client data
- Assuming unknown voltage/current/power schemas

## 5. Acceptance Criteria
The demo is complete when a developer can clone/open the project, start PostgreSQL using Docker Compose, seed the database, start Dash, log in locally, view AA12 / 29017 temperature KPIs, filter the time period, interact with the Plotly chart, inspect recent readings and see a demo warning generated from seeded data.
