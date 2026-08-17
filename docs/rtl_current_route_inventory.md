# RTL Current Route Inventory

*Phase 0 deliverable — created 2026-08-17.*
*Baseline: git HEAD `ac8c0fa` on `main`.*
*Purpose: record every active route before any new frontend scope is added.*

Status meanings:

- **preserve** — keep as-is; no change needed or planned.
- **adjust** — kept, but planned for a narrow change in a later phase.
- **candidate for later replacement** — expected to be superseded by client
  decisions; do not invest beyond the minimum.

---

## Active routes

### 1. Login (unauthenticated gate)

| Field | Value |
|-------|-------|
| Route | Any pathname while `auth-store` is unauthenticated |
| Page module | `pages/login.py` — `login_layout()` |
| Purpose | Demo authentication gate. Memory-only auth store; full page load resets it. |
| Main callback(s) | `callbacks/routing.py` `route_to_page` (login branch); `callbacks/auth.py` `handle_login`, `toggle_password_visibility` |
| Main service(s) | `services/auth_service.py` `verify_credentials` |
| Status | **preserve** |

### 2. Fleet Overview

| Field | Value |
|-------|-------|
| Route | `/`, `/plants`, `/plants/` |
| Page module | `pages/plants_overview.py` — `layout()` |
| Purpose | 30-plant listing with transformer/device counts, data freshness, KPI cards (Plants/Transformers/Devices/Data Health), fleet health distribution bar, exception-first sortable table. |
| Main callback(s) | `callbacks/routing.py` `route_to_page`; `callbacks/listings.py` `populate_overview`, `navigate_from_plants_table` |
| Main service(s) | `services/hierarchy_service.py` (`list_plants`, `get_plant_hierarchy_counts`); `services/monitoring_service.py` (`get_fleet_health`) |
| Status | **adjust** — Phase 2 adds a "Needs attention" exception panel (HMI §8, audit §10 item 5); Phase 1 may add app-level navigation. |

### 3. Plant Detail

| Field | Value |
|-------|-------|
| Route | `/plants/<plant_id>` |
| Page module | `pages/plant_detail.py` — `layout(plant_name, status)` |
| Purpose | Transformers in one plant, worst data first; plant context fields, KPIs, metric-health grid, hottest-temperature attribution card, entity table. |
| Main callback(s) | `callbacks/routing.py` `route_to_page`; `callbacks/listings.py` `populate_plant_detail`, `navigate_from_transformers_table` |
| Main service(s) | `services/hierarchy_service.py` (`get_plant_or_none`, `list_transformers`, `list_devices`); `services/monitoring_service.py` (`latest_reading_rows`, `fleet_health_from_rows`, `metric_health_from_rows`, `latest_metric_readings`, `hottest_temperature`) |
| Status | **adjust** — Phase 1 visual consistency with Fleet (UX-4); Phase 3 may reuse components for device administration. |

### 4. Transformer Detail

| Field | Value |
|-------|-------|
| Route | `/plants/<plant_id>/<transformer_id>` |
| Page module | `pages/transformer_detail.py` — `layout(plant_name, transformer_code, plant_id, status)` |
| Purpose | Devices on one transformer, worst data first; transformer context fields, KPIs, metric-health grid, hottest-temperature attribution card, entity table. |
| Main callback(s) | `callbacks/routing.py` `route_to_page`; `callbacks/listings.py` `populate_transformer_detail`, `navigate_from_devices_table` |
| Main service(s) | `services/hierarchy_service.py` (`get_plant_or_none`, `get_transformer_in_plant`, `list_devices`); `services/monitoring_service.py` (`latest_reading_rows`, `fleet_health_from_rows`, `metric_health_from_rows`, `latest_metric_readings`, `hottest_temperature`) |
| Status | **adjust** — Phase 1 visual consistency with Fleet (UX-4). |

### 5. Device Dashboard

| Field | Value |
|-------|-------|
| Route | `/devices/<device_id>?metric=…&period=…&start=…&end=…` |
| Page module | `pages/device_dashboard.py` — `layout(...)` |
| Purpose | Primary operator workspace: equipment context, 8-metric snapshot strip, metric selector, period filter + custom range, aggregation-aware KPI row, Plotly chart, quick-trend grid, readings table, freshness badge, auto-refresh. URL state is shareable. |
| Main callback(s) | `callbacks/routing.py` `route_to_page` (builds device context); `callbacks/device.py` `refresh_device_dashboard`, `sync_query_string`, `toggle_custom_range` |
| Main service(s) | `services/hierarchy_service.py` (`get_device_context`); `services/monitoring_service.py` (`get_device_full_view`, `choose_bin`, `bin_consumption`, `quick_trend_bars`) |
| Status | **preserve** — reference implementation (audit §6). Phase 8 keeps it as the base for a vibration-ready structure, but no change is planned to its behaviour. |

### 6. Global Equipment Selector (app-level, not a route)

| Field | Value |
|-------|-------|
| Route | Rendered on every authenticated page via global `app.layout`; hidden on login |
| Page module | `components/equipment_selector.py` — `equipment_selector_shell()` |
| Purpose | Cross-plant cascade Plant → Transformer → Device for direct device navigation without drill-down. Must remain globally mounted so its callbacks always have targets (CODE_AUDIT finding 2). |
| Main callback(s) | `callbacks/equipment_selector.py` — `_toggle_visibility`, `_populate_plants`, `_populate_transformers`, `_populate_devices`, `_navigate_to_device` |
| Main service(s) | `services/hierarchy_service.py` (`list_plants`, `list_transformers`, `list_devices`) |
| Status | **adjust** — Phase 1 visual integration with the header (vertical budget, HMI §6.8), while remaining in the global layout. |

### 7. Logout

| Field | Value |
|-------|-------|
| Route | `/logout` (plain `<a href="/logout">` in `components/app_header.py`) |
| Page module | None — no dedicated page |
| Purpose | Client-only sign-out: a full page load resets the memory-backed `auth-store`, landing back on login. |
| Main callback(s) | None |
| Main service(s) | None |
| Status | **preserve** |

### 8. Not Found

| Field | Value |
|-------|-------|
| Route | Any unparseable pathname |
| Page module | `components/status_panels.py` — `not_found_panel("page")` |
| Purpose | Friendly fallback for unknown URLs; also `not_found_panel("plant"|"transformer"|"device")` for valid route shapes with unknown ids. |
| Main callback(s) | `callbacks/routing.py` `route_to_page` |
| Main service(s) | `services/hierarchy_service.py` (entity existence checks) |
| Status | **preserve** |

---

## Route parsing facts (single source of truth)

- `routes.py` owns all URL parsing/building: `parse_pathname`, `parse_query`,
  `parse_custom_range`, `device_href`. `callbacks/routing.py` re-exports them.
- Device routes are flat (`/devices/<device_id>`), not nested under
  plant/transformer; parent breadcrumbs are reconstructed from `page-context`.
- Query params `metric`, `period`, `start`, `end` are shareable and preserved.
- Unknown routes resolve to `Route(name="unknown")`; entity ids are validated
  through `hierarchy_service` before any layout is rendered.

## Route module → callback → service map (summary)

| Layer | Files |
|-------|-------|
| URL contract | `routes.py` |
| Routing callback | `callbacks/routing.py` |
| Auth callbacks | `callbacks/auth.py` |
| Listing/table callbacks | `callbacks/listings.py` |
| Device dashboard callbacks | `callbacks/device.py` |
| Equipment selector callbacks | `callbacks/equipment_selector.py` |
| Services | `services/hierarchy_service.py`, `services/monitoring_service.py`, `services/auth_service.py` |
| Repository | `repositories/plant_monitoring_repository.py` (the only SQL layer) |