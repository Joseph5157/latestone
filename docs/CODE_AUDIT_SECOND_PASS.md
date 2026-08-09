# Code Audit — Second Pass

**Project:** Power Plant Monitoring Dashboard  
**Audited build:** `powerplant-monitoring-worktree-plant-monitoring-architecture.zip`  
**Date:** 2026-08-08  
**Purpose:** Find defects not already covered by `docs/CODE_AUDIT.md` findings 1–12.

This pass deliberately does **not** repeat the already-fixed custom end-date bug, snapshot-period reset, custom URL bounds, DB-password encoding, auth-service bypass, login initial error, password Show button, dead equipment component, unused imports, or schema-name validation. The known open cross-plant equipment selector is also not counted again.

## Executive summary

The most important remaining issues are not in KPI arithmetic. They are in **Dash dynamic callback wiring, table navigation, time-window semantics, and timezone handling**. These can produce runtime errors or confidently show the wrong data even while unit tests are green.

Recommended order tomorrow:

1. Fix callback/layout wiring in `callbacks/listings.py`.
2. Fix DataTable row navigation under sort/filter/page transforms.
3. Decide and correct 24h/7d/30d semantics (wall-clock now vs latest sample).
4. Make custom-range timestamps explicitly timezone-aware.
5. Fix the header freshness component contract.
6. Restore the required equipment context/status and parent breadcrumb links.
7. Add callback integration tests before addressing lower-severity items.

---

## NEW-01 — Page-specific listing Outputs are driven by a global Input

**Severity: HIGH**  
**Files:** `callbacks/listings.py:34-38`, `62-66`, `95-99`; `app.py:23`

All three listing-population callbacks use global `page-context` as their only Input, but each writes to a table that exists on only one route:

- `plants-table` only on overview
- `transformers-table` only on plant detail
- `devices-table` only on transformer detail

`page-context` changes on every route. Therefore, on a given route, two of these callbacks can be triggered while their Outputs are absent from the current layout. This is the same callback/layout mismatch class that caused the removed hierarchy selector errors.

The guards such as `if context.get("route") != "overview": return no_update` do **not** solve a missing-Output contract problem because the browser has to resolve callback dependencies before the Python function result can protect it.

**Why tests missed it:** no browser/callback-layout integration test exercises navigation across dynamic layouts.

**Suggested fix:** make each callback route-scoped by using an Input that only exists with its page, or move listing data loading into a pattern where callback Inputs and Outputs are inserted together. Do not solve this by adding hidden duplicate tables everywhere.

**Regression test:** navigate `login -> /plants -> plant -> transformer -> device -> /plants` with dev-tools error capture and assert zero nonexistent-object callback errors.

---

## NEW-02 — Clicking a sorted/filtered/paged table row can navigate to the wrong entity

**Severity: HIGH**  
**Files:** `components/entity_table.py:41-47`; `callbacks/listings.py:124-162`

Tables enable native sorting and filtering, but navigation callbacks use:

```python
row = rows[active_cell["row"]]
```

`active_cell["row"]` may be changed by sorting, filtering, or paging, while `State(..., "data")` remains the base data order. A user can click the first visible plant after sorting and be sent to a different plant whose original index was 0. The same defect exists for transformer and device tables.

**Suggested fix:** give each row an `id` and navigate using `active_cell["row_id"]`, or use the correct derived viewport/virtual data property.

**Regression tests:** sort Plant descending and click first visible row; filter to one transformer and click it; page a table and click a row. Assert URL entity matches visible row identity.

---

## NEW-03 — “Last 24h / 7d / 30d” is anchored to the last sample, not the current time

**Severity: HIGH — data correctness**  
**File:** `services/monitoring_service.py:194-207` (also `249-259` in unused full-view path)

For non-custom periods, the code does:

```python
latest = repo.get_latest_reading(...)
anchor = latest.timestamp
window = (anchor - period, anchor)
```

So if a device stopped reporting five days ago, selecting **24h** queries the 24 hours before that five-day-old reading, not the last 24 hours from now.

Targeted simulation from this audit:

- current time: `2026-08-08 12:00 UTC`
- latest reading: `2026-08-03 12:00 UTC` (5 days stale)
- UI period: `24h`
- actual query: `2026-08-02 12:00` to `2026-08-03 12:00`

The freshness badge says stale, but the chart/KPIs can still be fully populated with old data under a label users naturally interpret as “last 24 hours”.

**Suggested fix:** for relative periods, use wall-clock `now` as the window end. Keep `current` independently defined as the latest available reading, as the requirements already state.

**Regression test:** pin `now`, set latest reading 5 days old, request 24h, assert repository range ends at `now` and series is empty unless there are readings in the actual last 24h.

---

## NEW-04 — Custom date bounds remain naive against a `TIMESTAMPTZ` column

**Severity: HIGH — data correctness / production integration**  
**Files:** `callbacks/device.py:19-35`; `services/monitoring_service.py:164-176, 200-207`; `db/init_plant_monitoring.sql:54`

`_parse_picker_date()` returns naive Python datetimes. In the custom-period branch `_resolve_window()` returns those values unchanged. `_align_tz()` is **not applied to the custom start/end bounds**.

The repository then compares them against `readings.reading_ts TIMESTAMPTZ`. PostgreSQL interprets timezone-less timestamps using the database/session `TimeZone` during conversion. The local Docker database may happen to behave as expected, while a client PostgreSQL session in another timezone can shift the selected day.

The demo dataset itself spans plants in many countries, and the UI currently does not state whether times are UTC, browser-local, or plant-local.

**Suggested fix:** choose one explicit policy now (UTC is simplest for the demo), convert custom bounds to aware datetimes before repository calls, and label displayed timestamps. Later, if the client requires plant-local time, add a plant timezone field and convert at the UI/service boundary.

**Regression tests:** custom range with database/session timezone non-UTC; test aware UTC bounds passed to repository; test displayed time label.

---

## NEW-05 — Header freshness callback writes a badge component inside an existing badge

**Severity: MEDIUM**  
**Files:** `components/app_header.py:29-35`; `callbacks/device.py:104-109`; `components/freshness_badge.py:25-29`

`app_header()` creates:

```python
freshness_badge(Freshness.NO_DATA, component_id="header-freshness")
```

So `header-freshness` is itself a `<span>` with class `freshness-badge--no_data`.

The callback Output is only:

```python
Output("header-freshness", "children")
```

but the returned value is another complete `freshness_badge(...)` component. This nests a second badge inside the original badge and leaves the outer class stuck at `freshness-badge--no_data`. The error path is worse: it inserts a full error `<div>` inside that badge `<span>`.

**Suggested fix:** either make `header-freshness` a neutral container and return a badge into it, or output both text/children and `className` on the badge itself.

**Regression test:** inspect rendered component after FRESH -> STALE -> NO_DATA and assert one badge node only, with the correct class each time.

---

## NEW-06 — Required equipment context/status was removed, and device breadcrumb parents are not links

**Severity: MEDIUM — client-facing functional gap**  
**Files:** `pages/device_dashboard.py:31-47`; `callbacks/routing.py:90-113`; `UI_SPEC.md:41-47`

UI spec requires the device context bar to show:

`Plant Name | Transformer Code | Device Code | Status`

Current implementation shows only:

`Last data: <timestamp>`

The repository already returns `plant_id`, `transformer_id`, and `device_status` in `DevicePath`, but the router drops those fields from `page-context`, and `device_dashboard.layout()` does not accept them.

Also, on the device breadcrumb only **Plants** is a link. Plant and Transformer are rendered as current-text items, so the breadcrumb cannot navigate back one level even though their IDs are available from `DevicePath`.

**Suggested fix:** pass full device hierarchy context into the layout, restore the specified identity/status bar, keep Last Data as an additional field, and link Plant/Transformer breadcrumb items to their parent routes.

**Regression test:** device page contains plant, transformer, device, admin status, last-data value; parent breadcrumb links resolve correctly.

---

## NEW-07 — Inactive hierarchy counts can disagree with visible drill-down rows

**Severity: MEDIUM**  
**Files:** `callbacks/listings.py:44-57`; `services/hierarchy_service.py:25-34, 59-60`; `repositories/plant_monitoring_repository.py:171-187`

Overview plants are filtered to active entities through `hierarchy_service.list_plants()`, and detail pages filter transformers/devices to active entities by default. But `get_plant_hierarchy_counts()` calls a repository count with **no status filters**.

Once real data contains inactive equipment, an overview row can say e.g. 4 transformers / 8 devices while clicking into it shows only 3 / 6.

There is a related direct-route inconsistency: `get_plant_or_none`, `get_transformer_in_plant`, and `get_device_context` do not reject inactive entities, so an entity hidden from selection can still be opened by direct URL.

**Suggested fix:** explicitly decide whether listings/counts should include inactive equipment. Then apply the same policy to counts, lists, and direct-route validation.

**Regression tests:** seed active + inactive transformer/device and assert overview count equals the intended visible population; direct URL behavior matches policy.

---

## NEW-08 — Database-unavailable handling is incomplete in listing callbacks

**Severity: MEDIUM**  
**Files:** `callbacks/listings.py:40-116`; `REQUIREMENTS.md` Non-Functional Requirements

Routing and device callbacks now log/catch failures, but listing callbacks call services directly without an error boundary. The overview route itself performs no database access, so a DB outage after login reaches `populate_overview()` and raises through the Dash callback rather than rendering the required useful error state.

`db.engine.check_connection()` even claims it is “used by the UI”, but it is not referenced by application UI code.

**Suggested fix:** introduce a consistent page-level loading/error container for listings, log exceptions, and render a user-safe database-unavailable message without exposing internals.

**Regression test:** monkeypatch repository calls to raise and verify overview/plant/transformer pages render the error state rather than a callback exception.

---

## NEW-09 — `PLANT_MONITORING_SCHEMA` is advertised as configurable, but Docker DDL is hard-coded

**Severity: MEDIUM — configuration correctness**  
**Files:** `config/settings.py:96-99`; `.env.example:13-14`; `db/init_plant_monitoring.sql:21-61`

Application and seed code accept `PLANT_MONITORING_SCHEMA`, but the Docker init SQL always creates and references `plant_monitoring` literally.

If `.env` sets another valid schema, the app/seed will query that schema while a fresh Docker database created only `plant_monitoring`.

**Suggested fix:** either make the schema intentionally fixed and remove the misleading config option, or make schema initialization genuinely configurable (e.g. controlled bootstrap/migration step rather than a static SQL file).

**Regression test:** start a clean stack with a non-default schema and run seed + repository smoke test.

---

## NEW-10 — Chart zoom persists when the user changes the time period

**Severity: MEDIUM UX / interpretation risk**  
**File:** `components/metric_chart.py:48-57`

`uirevision` is only `metric.key`. Plotly preserves user zoom/pan while `uirevision` stays unchanged. Therefore:

1. user zooms into a few hours on Temperature / 24h;
2. user switches to Temperature / 30d;
3. metric key is unchanged, so the old x-axis interaction can remain;
4. the chart can look as if it is still showing only a small slice of the new 30-day dataset.

**Suggested fix:** revision identity should stay stable for refreshes of the same view but change when the selected period/custom window changes. Pass an explicit view revision such as metric + period + custom bounds.

**Regression test:** browser test: zoom, switch period, assert axis autoranges/reset; then wait for refresh and assert zoom is preserved within the unchanged period.

---

## NEW-11 — Capacity sorts as formatted text, not as a number

**Severity: LOW**  
**File:** `callbacks/listings.py:10-17, 50-57`

Capacity is emitted as strings such as `"1,250 MW"` while native table sorting is enabled. That produces lexical rather than numeric ordering and makes numeric filtering impossible/reliable only as text.

**Suggested fix:** keep capacity as numeric data with a numeric column and use DataTable formatting/presentation for the `MW` display.

**Regression test:** rows 900 MW, 1,000 MW, 12,000 MW sort numerically ascending/descending.

---

## NEW-12 — Interrupted seed can leave a partial database that future seed runs silently skip

**Severity: LOW/MEDIUM developer reliability**  
**File:** `db/seed_plant_monitoring.py:99-119`

Without `--reset`, the seed guard checks only whether **any reading exists**. If a previous seed dies after loading only part of the devices, the next ordinary seed reports “Readings already exist” and exits, preserving an incomplete dataset.

**Suggested fix:** validate expected seed integrity/count/version, or use a seed metadata/version marker committed only after the whole load succeeds. At minimum, detect incomplete counts and instruct/reset safely.

**Regression test:** insert a small subset of readings and run seed without reset; assert it does not declare the dataset complete.

---

## NEW-13 — Documentation drift after the last cleanup

**Severity: LOW/MEDIUM — implementation handoff risk**

Examples:

- `README.md` and `ARCHITECTURE.md` still list deleted `components/equipment_context.py` and `components/hierarchy_selector.py`.
- `DATABASE.md` documents fields (`created_at`, transformer `tier`, `capacity_mva`) that do not exist in `db/init_plant_monitoring.sql`.
- `DATABASE.md` metric precision differs from `config/metrics.py` for voltage/current/active power/reactive power/frequency.

For a project that will later be implemented in short remote-SSH windows on another machine, stale architecture/database docs are likely to cause wrong implementation decisions.

**Suggested fix:** choose code as source of truth and regenerate/update the docs after the next functional fixes.

---

## NEW-14 — Login fields expose `n_submit`, but Enter does not submit

**Severity: LOW UX**  
**Files:** `pages/login.py:16-35`; `callbacks/auth.py:12-18`

Both inputs set `n_submit=0`, but the login callback only listens to `login-button.n_clicks`. Pressing Enter in username/password does not perform login.

**Suggested fix:** include password `n_submit` (and optionally username) as an Input and use `dash.ctx.triggered_id`/combined guard to handle button or Enter safely.

---

# Production blockers that are intentional demo limitations (do not count as demo bugs)

These are consistent with the current requirement “do not implement production authentication”, but they must be changed before any real government/client deployment:

1. `dcc.Store(storage_type="memory")` authentication is browser-controlled and is not a server-side authorization boundary.
2. Data callbacks do not independently enforce authenticated server sessions.
3. Default `DASH_HOST=0.0.0.0` exposes the app on network interfaces.
4. Default `DASH_DEBUG=true` should never be used on the client environment.
5. Demo credentials have known defaults in `.env.example`.

Treat these as a separate production-hardening phase when the client authentication/deployment mechanism is known.

---

# Tests to add before another “green suite = done” conclusion

The current suite is strong on services/repositories but still weak at the browser wiring boundary. Add at least:

- callback/layout contract test across every route;
- end-to-end route navigation with browser console error assertion;
- DataTable sort/filter/page + row-click navigation tests;
- stale-device relative-period test;
- explicit timezone custom-range test;
- freshness badge DOM/class test;
- database-unavailable listing-state test;
- inactive hierarchy consistency test;
- period-change chart reset vs same-period refresh preservation test.

The highest-value change is not simply increasing unit-test count. It is adding tests at the **Dash layout ↔ callback ↔ browser state** boundary where the previous defects survived.
