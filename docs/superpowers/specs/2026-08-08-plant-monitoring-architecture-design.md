# Plant Monitoring Architecture — Design Spec

**Date:** 2026-08-08
**Status:** Approved (Sections 1–6)

## Purpose

Promote the 30-plant system from a secondary demo to the **primary development
application**, designed as closely as reasonably possible to the eventual real
power-plant monitoring application.

The 30 plant metadata records (Kaggle / WRI "Global Power Plant Database") are
our **development plant dataset**. Synthetic transformer/device identifiers and
all generated measurements are **development data** — real client measurements
are not yet available. The software architecture, database design, UI structure,
navigation and data-access patterns are production-oriented and are **not**
throwaway demo code.

## Data Provenance — Read This First

| Item | Provenance |
|---|---|
| Plant name, country, lat/long, capacity_mw, primary_fuel | Kaggle / WRI Global Power Plant Database (real) |
| Transformer codes, device codes | **Synthetic development identifiers** |
| Number of transformers per plant, devices per transformer | **Synthetic development distribution**, assigned by a stable hash of `plant_id`. No relationship to plant capacity, real transformer counts, or any client equipment inventory. |
| All 8 metric time series | **Synthetic development measurements** |
| All engineering units | **Development display units**; must be mapped to real client units when the client database/schema is available |
| `AA12` / `29017` | The only client-known naming example (from client pgAdmin screenshots, observed combined form `aa12_29017`). Reserved as one familiar reference point in the development hierarchy. Its placement in the hierarchy is arbitrary and carries no meaning about real equipment. |

**No production warning/critical thresholds are defined anywhere in this design.**

## Tech Stack

Python, Dash, Plotly, PostgreSQL, SQLAlchemy, Docker Compose. No Grafana.

Layering is preserved and enforced: `pages → services → repositories → db`.
Raw SQL only in repositories. KPI/status/domain logic only in services. Layout
and callback wiring only in pages/components.

---

## Section 1 — Database Schema

New schema `plant_monitoring`, replacing both `monitoring` and `trfr_temperature`.

```sql
CREATE SCHEMA plant_monitoring;

CREATE TABLE plant_monitoring.plants (
    plant_id     VARCHAR(20)  PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    country      VARCHAR(100) NOT NULL,
    latitude     NUMERIC(8,4) NOT NULL,
    longitude    NUMERIC(8,4) NOT NULL,
    capacity_mw  NUMERIC(10,1),
    primary_fuel VARCHAR(50),
    status       VARCHAR(20)  NOT NULL DEFAULT 'active'
);

CREATE TABLE plant_monitoring.transformers (
    transformer_id   VARCHAR(30) PRIMARY KEY,
    plant_id         VARCHAR(20) NOT NULL REFERENCES plant_monitoring.plants(plant_id),
    transformer_code VARCHAR(10) NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'active',
    UNIQUE (plant_id, transformer_code)
);

CREATE TABLE plant_monitoring.devices (
    device_id      VARCHAR(30) PRIMARY KEY,
    transformer_id VARCHAR(30) NOT NULL REFERENCES plant_monitoring.transformers(transformer_id),
    device_code    VARCHAR(10) NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'active',
    UNIQUE (transformer_id, device_code)
);

CREATE TABLE plant_monitoring.readings (
    id         BIGSERIAL    PRIMARY KEY,
    device_id  VARCHAR(30)  NOT NULL REFERENCES plant_monitoring.devices(device_id),
    metric     VARCHAR(30)  NOT NULL,
    reading_ts TIMESTAMPTZ  NOT NULL,
    value      NUMERIC(12,3) NOT NULL,
    UNIQUE (device_id, metric, reading_ts)
);

CREATE INDEX ix_transformers_plant_id     ON plant_monitoring.transformers (plant_id);
CREATE INDEX ix_devices_transformer_id    ON plant_monitoring.devices (transformer_id);
CREATE INDEX ix_readings_device_metric_ts ON plant_monitoring.readings (device_id, metric, reading_ts DESC);
```

Decisions:

- `readings.metric` is a **generic metric key**. No metric-specific columns.
- Metric display metadata (label, unit, precision, chart type, order,
  aggregation) lives **outside the database**, in centralized Python config.
- `status` columns are **administrative** status (`active`/`inactive`) only.
  They are never used for computed Normal/Warning/Critical monitoring status.
- No enterprise/audit tables at this stage.
- The client's ~2,112-table physical structure is deliberately **not**
  reproduced. Our internal model is clean and normalized.

## Section 2 — Development Hierarchy Distribution

Scale: **30 plants → 71 transformers → 120 devices**.

Distribution is derived **only** from `plant_id`, never from `capacity_mw`.

1. Sort all 30 `plant_id` values by `sha256(plant_id)` hex digest.
2. Assign transformer counts by position in that sorted order:

| Sorted positions | Transformers per plant | Plants | Transformers |
|---|---|---|---|
| 1–5 | 4 | 5 | 20 |
| 6–13 | 3 | 8 | 24 |
| 14–23 | 2 | 10 | 20 |
| 24–30 | 1 | 7 | 7 |
| **Total** | | **30** | **71** |

3. Devices per transformer cycle by the transformer's 1-based index within its
   plant: `((index - 1) % 3) + 1` → 1, 2, 3, 1, …

| Transformers/plant | Devices/plant | Plants | Devices |
|---|---|---|---|
| 4 | 7 (1+2+3+1) | 5 | 35 |
| 3 | 6 (1+2+3) | 8 | 48 |
| 2 | 3 (1+2) | 10 | 30 |
| 1 | 1 | 7 | 7 |
| **Total** | | **30** | **120** |

Identifier scheme (all synthetic unless noted):

- `transformer_id` — surrogate key `<plant_id>-t<index>`, e.g. `plant-01-t1`.
- `transformer_code` — first two alphanumeric letters of the plant's country,
  lowercased, plus a 2-digit index, e.g. `ch01`. Codes may repeat across plants;
  uniqueness is only required within a plant.
- `device_id` — surrogate key `<transformer_id>-d<index>`, e.g. `plant-01-t1-d1`.
- `device_code` — 5-digit values `29001`–`29120`, assigned in deterministic
  iteration order (plant order → transformer index → device index).

**Reserved reference identifiers:** the first device of the first transformer of
`plant-01` is overridden to `transformer_code = 'aa12'`, `device_code = '29017'`.
The `29017` value is swapped with whichever slot would otherwise have received
it, so all 120 device codes stay unique. Documented in code as matching the one
client-known naming example, with placement carrying no real-world meaning.

## Section 3 — Metric Model

Centralized in `config/metrics.py`. Single source of truth for the metric
selector, chart axis labels, KPI formatting, and KPI/aggregation semantics.

```python
class Aggregation(str, Enum):
    STATISTICS = "statistics"   # Current / Minimum / Maximum / Average
    DELTA = "delta"             # Current meter value / Period change = last - first


@dataclass(frozen=True)
class MetricConfig:
    key: str
    label: str
    unit: str            # development display unit; "" for dimensionless
    precision: int
    chart_type: str
    display_order: int
    aggregation: Aggregation
```

`Aggregation` subclasses `str`, so it satisfies the agreed `aggregation: str`
contract while removing stringly-typed comparisons — the cleaner naming the
approval invited.

| key | label | unit | precision | chart_type | order | aggregation |
|---|---|---|---|---|---|---|
| `temperature` | Temperature | `°C` | 1 | line | 1 | statistics |
| `voltage` | Voltage | `kV` | 2 | line | 2 | statistics |
| `current` | Current | `A` | 1 | line | 3 | statistics |
| `active_power` | Active Power | `MW` | 2 | line | 4 | statistics |
| `reactive_power` | Reactive Power | `MVAr` | 2 | line | 5 | statistics |
| `power_factor` | Power Factor | `` (empty) | 3 | line | 6 | statistics |
| `frequency` | Frequency | `Hz` | 2 | line | 7 | statistics |
| `energy` | Energy | `MWh` | 1 | line | 8 | delta |

Aggregation semantics:

- `statistics` — Current (latest available) / Minimum / Maximum / Average over
  the selected period.
- `delta` — Current (latest meter reading) / Period Change = `last − first`
  over the selected period. Average/Min/Max are **not** the primary KPI
  semantics for `delta` metrics.

`energy` is modelled as a **cumulative meter** that increases monotonically.
A negative delta would indicate a counter reset or data-quality condition; this
is documented but **not** handled with sophisticated reset logic at this stage.

All units above are development display units. Real client units and metric
definitions must be mapped when the client database is available.

## Section 4 — Repository API

Module: `repositories/plant_monitoring_repository.py`. The only place raw SQL
exists. No generic raw-query helpers. No SQL leaks outside this module.

Records: `PlantRecord`, `TransformerRecord`, `DeviceRecord`, `DevicePath`,
`RawReading(device_id, metric, timestamp, value)`.

Hierarchy:

```
list_plants()                        -> list[PlantRecord]
get_plant(plant_id)                  -> PlantRecord | None
list_transformers(plant_id)          -> list[TransformerRecord]
get_transformer(transformer_id)      -> TransformerRecord | None
list_devices(transformer_id)         -> list[DeviceRecord]
get_device(device_id)                -> DeviceRecord | None
get_device_breadcrumb(device_id)     -> DevicePath | None   # single JOIN
count_hierarchy_by_plant()           -> dict[str, tuple[int, int]]  # transformer/device counts for overview
```

Readings:

```
get_latest_reading(device_id, metric)                            -> RawReading | None
get_latest_readings_for_device(device_id, metrics=None)          -> dict[str, RawReading]
get_readings_in_range(device_id, metric, start, end)             -> list[RawReading]
get_readings_for_device_in_range(device_id, metrics, start, end) -> dict[str, list[RawReading]]
```

Rules:

- `get_latest_reading` returns the latest available reading **regardless of the
  selected historical period**. This semantic is never changed for period views.
- Bounded queries use explicit inclusivity: `reading_ts >= start AND reading_ts <= end`.
- Batched calls (`*_for_device`) issue **one** SQL statement for all requested
  metrics — never one query per metric.
- Metric lists are bound safely (`expanding` bind parameters), never interpolated
  into SQL strings.
- No separate `MIN`/`MAX`/`AVG` SQL query. At 30-minute sampling a period holds
  at most ~1,441 rows per metric, so the service computes statistics/delta from
  the bounded rows already fetched for the chart and table.
- No unbounded `get_all_readings`. PostgreSQL always performs
  device/metric/time-range filtering.

## Section 5 — Service Layer

Two modules: `services/hierarchy_service.py` and `services/monitoring_service.py`.

### Three independent concepts — never merged

| Concept | Values | Source |
|---|---|---|
| Administrative status | `active`, `inactive` | Stored column; read only by `hierarchy_service` |
| Data freshness | `fresh`, `stale`, `no_data` | Computed from latest reading timestamp |
| Monitoring condition (future) | `normal`, `warning`, `critical`, `unknown` | Not implemented; always `unknown` today |

`is_stale` is a data-delivery signal and is **never** used as an electrical
warning condition. Freshness is represented as a `Freshness` enum, not a boolean.

### Hierarchy validation

Route path segments are untrusted. They are never interpolated into SQL, but
must still be validated against real rows before a page renders, so a stale or
wrong ID produces a friendly "not found" rather than a broken page or a leaked
exception.

```
get_plant_or_none(plant_id)                        -> PlantRecord | None
get_transformer_in_plant(plant_id, transformer_id) -> TransformerRecord | None
get_device_in_transformer(transformer_id, device_id) -> DeviceRecord | None
get_device_context(device_id)                      -> DevicePath | None
list_plants(include_inactive=False)                -> list[PlantRecord]
list_transformers(plant_id, include_inactive=False)-> list[TransformerRecord]
list_devices(transformer_id, include_inactive=False) -> list[DeviceRecord]
```

`get_transformer_in_plant` / `get_device_in_transformer` return `None` when the
entity exists but belongs to a different parent, closing off confused-deputy
bugs where valid-but-wrong-parent IDs render data under the wrong breadcrumb.

Listings default to `active` only, since an inactive entity should not be
selectable for live monitoring. `include_inactive=True` supports a future
admin-style view.

### Freshness policy — centralized configuration

Lives in `config/settings.py`, not hard-coded in the service:

- Expected sampling interval = **30 minutes** — current project/client-known
  requirement.
- Stale after **3 missed expected intervals** — **development application
  policy, requires client confirmation before production**.
- Therefore current development stale threshold = **90 minutes**.

### View models

```python
@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    value: float

@dataclass(frozen=True)
class MetricSnapshot:          # lightweight, for the snapshot strip
    metric: MetricConfig
    current: float | None
    last_updated: datetime | None
    freshness: Freshness
    condition: MonitoringCondition   # always UNKNOWN today

@dataclass(frozen=True)
class MetricView:              # full, for the active metric
    metric: MetricConfig
    current: float | None          # always latest available, period-independent
    minimum: float | None          # populated only when aggregation == "statistics"
    maximum: float | None          # populated only when aggregation == "statistics"
    average: float | None          # populated only when aggregation == "statistics"
    period_change: float | None    # populated only when aggregation == "delta"
    series: list[Reading]
    last_updated: datetime | None
    freshness: Freshness
    condition: MonitoringCondition
    has_data: bool
```

### Aggregation dispatch

The service is the only place that branches on `MetricConfig.aggregation`.

- `_compute_statistics(series)` → `(min, max, average)`.
- `_compute_delta(series)` → `series[-1].value - series[0].value`, or `None` if
  **fewer than 2 readings** are in range. A period delta requires at least two
  readings.

### Service API

```
get_metric_view(device_id, metric_key, period, custom_start=None, custom_end=None) -> MetricView | None
get_device_snapshot(device_id)  -> list[MetricSnapshot]     # one batched latest query
get_device_full_view(device_id, period, custom_start=None, custom_end=None) -> dict[str, MetricView]
```

`get_device_full_view` uses **one common dashboard time window** for all metrics:

1. Batched latest-reading call for the device.
2. Dashboard anchor = the **latest timestamp across the requested metrics**.
3. `start = anchor - period`, `end = anchor`; for a custom range use the
   explicit custom start/end instead of deriving from the latest timestamp.
4. **One** batched historical query for all metrics over that common range.

Each `MetricView.last_updated` still retains that metric's **own** latest
timestamp, so freshness is evaluated per metric independently.

### Empty-data behaviour

| Case | Result |
|---|---|
| No reading ever for device+metric | `current=None`, `last_updated=None`, `series=[]`, all stats/`period_change=None`, `freshness=NO_DATA`, `has_data=False` |
| Latest reading exists, selected range contains no points | `current` = latest available, `last_updated` = latest timestamp, `series=[]`, stats/`period_change=None`, freshness computed from `last_updated` |

Pages render `"—"` and an empty-state panel through one shared code path — never
per-metric branching.

## Section 6 — UI Architecture

Framing: an operator needs to **find** equipment fast, **see** its state at a
glance, and **drill into** one signal without losing place in the hierarchy.

### Routes

```
/                                     -> redirect to /plants (post-login landing)
/plants                               -> 30-plant overview
/plants/<plant_id>                    -> transformers for that plant
/plants/<plant_id>/<transformer_id>   -> devices for that transformer
/devices/<device_id>?metric=&period=  -> device monitoring dashboard
```

`/devices/<device_id>` alone resolves the full breadcrumb via
`get_device_context`, so device links are shareable without parent IDs.

Active metric and period are **URL query parameters**, so an engineer can send a
direct link to `AA12 / 29017 → Voltage`. Custom start/end dates are not encoded
in the URL initially.

### Navigation

1. **Breadcrumb drill-down** (primary path): Plants › Plant › Transformer ›
   Device, each crumb a link back up.
2. **Persistent cascading selector** (quick jump): Plant → Transformer → Device
   dropdowns in the header, always reflecting the current route. Selecting a
   device navigates straight to its dashboard.

### 30-plant overview

Dense sortable table — **not** a map. Columns: Plant, Country, Primary fuel,
Capacity (MW), Transformers, Devices. Each row links into the plant.

No live status rollup in this phase: aggregating freshness across 120 devices on
every overview load adds query surface for a value whose "warning" definition
does not yet exist. Natural phase-2 addition once monitoring condition exists.

No geographic visualization in this phase.

### Plant detail / transformer detail

Same table pattern one level down. Administrative `status` shown as a plain
badge here — this is the one place it is genuinely relevant, since these pages
are literally listings of administrative equipment state.

### Device dashboard

Top to bottom:

1. **Header** — breadcrumb, cascading selector, logout. The header shows
   **data freshness**, not "connection state": *Fresh / Stale / No data*
   describes measurement freshness and does **not** prove database/network
   connectivity. Genuine application/database errors are a separate error state
   until a real health check is implemented.
2. **Equipment context** — compact strip (not oversized cards): Plant,
   Transformer, Device, Administrative status, Last data received.
3. **Metric snapshot strip** — 8 compact tiles from one batched query, each with
   metric label, current value, unit, and a freshness indicator. Tiles are
   architected so an **independent** monitoring-condition indicator can be added
   later without redesigning the component. Clicking a tile sets the active metric.
4. **Metric selector** — ordered by `display_order`, synced with the strip and
   the URL.
5. **KPI row** — one shared component branching once on
   `metric_view.metric.aggregation`: `statistics` → Current/Minimum/Maximum/
   Average; `delta` → Current/Period Change (labelled distinctly so a meter
   reading is not misread as a fluctuating value).
6. **Time-period controls** — 24h / 7d / 30d / custom.
7. **Chart** — single line trace for the active metric, axis from
   `MetricConfig.label`/`unit`.
8. **Readings table** — active metric's series, newest first, column header from
   metric config.

### Component responsibilities

Components **may** receive `MetricConfig` through the view models and use
presentation fields (`label`, `unit`, `precision`, `chart_type`,
`display_order`). Components must **not** contain business logic such as
`if metric.key == "energy"`. Aggregation/KPI semantics belong in `MetricConfig`
plus service logic.

| Component | Purpose |
|---|---|
| `app_header.py` | Brand, breadcrumb slot, hierarchy selector slot, freshness slot, logout |
| `breadcrumb.py` | Plants › Plant › Transformer › Device trail |
| `hierarchy_selector.py` | Cascading Plant → Transformer → Device dropdowns |
| `entity_table.py` | Generic sortable table for plants/transformers/devices |
| `equipment_context.py` | Compact device context strip |
| `metric_snapshot_strip.py` | 8-tile multi-metric snapshot |
| `kpi_card.py` | `kpi_row(metric_view)`; branches once on `aggregation` |
| `metric_chart.py` | Line chart parameterized by `MetricConfig` |
| `readings_table.py` | Readings table with metric-driven column header |
| `period_filter.py` | 24h / 7d / 30d / custom |
| `status_panels.py` | `not_found_panel`, `error_panel`, `empty_data_panel` |
| `freshness_badge.py` | Renders a `Freshness` value |

### Refresh architecture

One **device refresh trigger** keeps the device dashboard internally consistent.
When it fires, it refreshes together:

- latest multi-metric snapshot values and freshness,
- the active metric's latest value,
- the active metric's historical range as appropriate.

The active metric chart must never refresh while the snapshot strip stays
indefinitely stale.

The interval is **configurable** (`config/settings.py`, env-overridable) and
never hard-coded into callbacks. The real system is expected to receive
~30-minute updates, so aggressive polling is unnecessary; a shorter development
interval is acceptable for testing.

### State management

`dcc.Store` holds **lightweight UI/navigation state only**: resolved
plant/transformer/device context, selected metric, selected period. Browser-side
stores are **never** used as a cache for large historical reading datasets to
avoid PostgreSQL queries — PostgreSQL is designed for this, and the
`device_id + metric + time range` query is cheap.

### Loading, not-found, error, empty states

- **Loading** — routing returns a page *shell* immediately (header, breadcrumb,
  empty containers wrapped in `dcc.Loading`); a second callback populates data.
  This replaces the current pattern where `plants_dashboard_layout()` calls
  `list_plants()` synchronously inside the layout function, blocking first paint
  on a database round trip.
- **Not found** — invalid ID → hierarchy validation returns `None` → shared
  `not_found_panel(entity_type)` with a link back to the overview. No raw SQL,
  stack traces, or connection details are ever surfaced.
- **No data** — `has_data == False` → KPIs show `"—"`, chart and table show
  empty-state placeholders, through one shared code path.
- **Application/database error** — shared `error_panel()` used by every
  data-populating callback. Distinct from freshness.

### Responsive behaviour

Snapshot strip wraps/scrolls horizontally on narrow viewports; KPI row degrades
4 → 2 → 1 columns; chart always full width; the header's three-dropdown selector
collapses into a single "Jump to device" affordance below a breakpoint; tables
remain usable via horizontal scrolling.

### Callback organization

One router callback per navigation change, one data-populating callback per
page, each keyed to the narrowest input that should trigger it:

1. `render_page(pathname, search, auth)` — resolves the route, validates
   hierarchy IDs with cheap indexed lookups, returns the page shell, writes
   resolved context into `dcc.Store(id="page-context")`.
2. `populate_overview` — one `list_plants()` + one `count_hierarchy_by_plant()` call.
3. `populate_plant_detail` / `populate_transformer_detail` — one listing call
   each; read identity from `page-context` rather than re-fetching it.
4. `refresh_device_dashboard` — the single device refresh trigger; fires on
   navigation, metric change, period change, or the configurable interval, and
   updates snapshot strip **and** active metric detail together.

Device breadcrumb/identity is fetched once per page load and shared via
`page-context`; nothing downstream re-queries `get_plant`/`get_transformer`/
`get_device`.

## Legacy Retirement

The single-device demo is removed entirely: `pages/dashboard.py`,
`pages/plants_dashboard.py`, `services/temperature_service.py`,
`services/monitoring_service.py` (old), `repositories/temperature_repository.py`,
`repositories/monitoring_repository.py`, `components/temperature_chart.py`,
`components/plant_selector.py`, `db/seed.py`, `db/seed_multi_plant.py`,
`db/init.sql`, `db/init_monitoring.sql`, and the `trfr_temperature` and
`monitoring` schemas.

## Open Item Reconciled

An earlier answer in this design conversation selected "all metrics, with
placeholder thresholds" for status colouring. Later instructions superseded it:
**no warning/critical thresholds are defined**. `MonitoringCondition` exists as
an enum and always evaluates to `UNKNOWN`; `MetricConfig` carries **no**
threshold fields. This keeps the tile/KPI components' shape final so thresholds
can be added later without redesign.

## Out of Scope

- Production warning/critical thresholds
- Geographic/map visualization
- Kubernetes deployment
- Grafana or any alternative frontend framework
- Enterprise/audit tables
- Real client authentication (demo auth stays isolated)
- Sophisticated energy counter-reset handling
