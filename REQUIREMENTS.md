# Requirements — Powerplant Dashboard

## 1. Objective
Build the primary development application, demonstrating how the client's PostgreSQL power-plant monitoring data can be presented through an interactive Python dashboard with a 30-plant hierarchy and 8 metrics.

## 2. Functional Requirements

### FR-01 Local Login
- Provide a professional login page.
- Use local/mock credentials as a placeholder only, pending the client's authentication.
- Do not implement production authentication.
- Invalid credentials must show a clear error.
- Successful login opens the plants overview.
- Credentials must not be embedded throughout UI code; keep demo authentication isolated for later replacement.

### FR-02 Hierarchy Navigation
The application represents:
- 30 plants, 71 transformers, 120 devices
- Schema: `plant_monitoring`
- Reserved identifier: `plant-01-t1-d1` = `aa12` / `29017`

Navigation flow: Plants overview → Plant detail → Transformer detail → Device dashboard.

### FR-03 Metric Monitoring
Eight metrics with appropriate aggregations:
- Temperature (°C), Voltage (kV), Current (A), Active Power (MW), Reactive Power (MVAr), Power Factor, Frequency (Hz): statistics aggregation (current/min/max/average)
- Energy (MWh): delta aggregation (period change)

### FR-04 KPI Cards
Aggregation-aware KPIs:
- **Statistics metrics**: Current / Minimum / Maximum / Average for the selected time range
- **Delta metric** (energy): Current / Period Change

Values must be calculated from database data, not hard-coded. Current means latest available reading.

### FR-05 Metric Trend
- Display any metric over time using Plotly.
- Hover must expose timestamp and value.
- Chart must respond to selected time range and metric.
- The chart should remain readable with hundreds/thousands of readings.

### FR-06 Time Filtering
Provide convenient filters for:
- Last 24 hours
- Last 7 days
- Last 30 days
- Custom date/time range

### FR-07 Recent Readings
Show a table containing recent readings, including at minimum:
- Timestamp
- Selected metric value

Support sensible ordering with newest readings first.

### FR-08 Data Freshness
- Evaluate freshness based on the last reading timestamp.
- Display fresh / stale / no_data status.
- Freshness threshold is globally configurable (default: 1,440 minutes / 24
  hours). This is an interim operational policy, not a per-RTL cadence.
- No production warning/critical thresholds — monitoring condition is always `UNKNOWN`.

### FR-09 Data Generation
- Seed realistic multi-metric data into local PostgreSQL.
- Approximate a 30-minute measurement interval.
- Include 30 days of historical data.
- Energy metric is cumulative (monotonically increasing).
- Seed generation should be deterministic/reproducible.

## 3. Non-Functional Requirements
- Local-first development.
- Application must run without access to the client's network.
- PostgreSQL must run in Docker.
- Keep UI, business/service logic and database access separated.
- Configuration and secrets must use environment variables where appropriate.
- Do not commit real credentials.
- Queries must be parameterised where parameters are supported.
- Dynamic SQL identifiers must be validated against strict naming rules/allowlists.
- Code should be modular and understandable for later production integration.
- Responsive layout suitable for desktop/laptop dashboard.
- Provide useful error states when the database is unavailable or no readings exist.

## 4. Explicitly Out of Scope (for now)
- Production authentication/SSO
- Production Kubernetes deployment
- Predictive maintenance/ML
- SMS/email alerts
- Production threshold definitions
- Editing client data

## 5. Acceptance Criteria
The application is feature-complete when a developer can clone/open the project, start PostgreSQL using Docker Compose, seed the database, start Dash, log in, navigate the plant hierarchy, view a device dashboard, change the time range, switch between metrics, see correctly calculated KPIs, interact with the chart, inspect recent readings, and observe the data freshness status.
