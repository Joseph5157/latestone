# Code Audit — 2026-08-08

Audit of the plant monitoring application following completion of the 17-phase
implementation plan. Performed by static analysis of every callback/layout
contract plus targeted execution against the seeded development database.

**Context.** An earlier verification pass had already found and fixed 8 defects
(commit `73c1d01`) covering login, routing and the device dashboard. This audit
covers the remaining surface. The full pytest suite (168 tests) was green both
before and after that pass, and is green now — every finding below was invisible
to it.

Status legend: **Fixed** — corrected in this pass. **Open** — deliberately not
fixed, with reasoning.

---

## Root cause: the callback↔layout wiring layer is untested and silent

Findings 1, 4, 5 and 8 all live in the wiring between Dash callbacks and page
layouts. That layer has no automated coverage: `tests/test_monitoring_service.py`
passes `datetime` objects straight into the service and never exercises the
`datetime.fromisoformat(...)` conversion in `callbacks/device.py` where finding 1
occurs. Combined with finding 3 — two blanket `except Exception` handlers and no
logging anywhere in the codebase — this layer is both unverified and mute when it
breaks.

This is the systemic issue. It is also exactly how the previous round's
`DevicePath` unpacking `TypeError` and layout-arity `TypeError` survived a green
test suite: both were converted into a generic "Something went wrong" panel.

---

## High severity

### 1. Custom date range silently drops the entire end day — **Fixed**

`callbacks/device.py`

`dcc.DatePickerRange` yields calendar dates (`"2026-08-06"`), not instants.
`datetime.fromisoformat` turns that into **midnight**, so the whole of the
selected end day was excluded from the query.

Verified against seeded data — Aug 3 → Aug 6 on `plant-01-t1-d1`:

| | readings returned |
|---|---|
| end parsed as midnight (before) | 145 |
| end covering the full day (after) | 192 |
| **silently dropped** | **47** |

Every period KPI was affected: Minimum, Maximum and Average were computed over
the truncated set, and Energy's Period Change (`last − first`) under-reported by
nearly a full day. A monitoring dashboard presenting confidently wrong numbers is
the most damaging failure mode available here, and nothing in the UI indicated
anything was missing.

**Fix.** Added `_parse_picker_date()`, which widens a date-only end value to the
last microsecond of that day. Covered by new tests in `tests/test_date_range.py`.

### 2. Cascading hierarchy selector never rendered, but four callbacks drive it — **Fixed** (dead code removed in this pass; feature implemented in follow-up commit)

`components/hierarchy_selector.py`, `callbacks/listings.py`

`hierarchy_selector()` had zero call sites, so `hier-plant`, `hier-transformer`
and `hier-device` existed in no layout — while four callbacks in `listings.py`
read and wrote them. `populate_plant_dropdown` fires on every `page-context`
change, i.e. on every navigation, each time raising the same
`ReferenceError: A nonexistent object was used in an Output of a Dash callback`
signature previously observed for `header-freshness`.

This also means the cross-plant equipment selector required by the plan
(Phase 16 Step 3 — "use the header selector to jump directly to a device under a
different plant") **is not implemented**.

**Action taken (audit pass).** The dead component and its four callbacks were
removed, which eliminates the runtime error. The feature itself was deliberately
**not** implemented in that pass: making it work correctly requires a design
decision that belongs outside a bugfix — the selector must exist in every layout
that its callbacks can fire against, so it needs to live either in the global app
layout (and therefore be suppressed on the login page) or be driven by
route-scoped callbacks. Half-shipping it would have reintroduced the same class
of defect.

**Resolution (follow-up).** The global-layout option was chosen. The selector is
now mounted once in `app.layout` (`components/equipment_selector.py`) and hidden
via `style` on the login route rather than unmounted, so its callbacks in
`callbacks/equipment_selector.py` always have their targets. Three consequences
were designed in explicitly:

- **No pre-auth data.** The component sits in the DOM on the login page, so
  `plant_options()` returns `[]` unless `auth-store` says authenticated. No
  hierarchy query runs before login.
- **One-way data flow.** The selector writes to `url.pathname`; the route never
  writes back into the dropdowns. A route → selector sync would close the loop
  `selector → url → page-context → selector`. `device_navigation_target()`
  additionally returns `no_update` when the chosen device is already on screen.
- **Cascade resets its children.** Changing plant clears the transformer and
  device values, so a stale selection cannot navigate somewhere unintended.

`app_header()` lost its unused `selector_children` slot, since a header rendered
inside a page layout is precisely the wrong place for this component.

**Regression guard.** `tests/test_equipment_selector.py` walks `app.layout` plus
every page layout, walks `app._callback_list`, and asserts that no callback
references a component id that no layout renders. That assertion fails on the
original code, and covers the whole class rather than this one instance.

### 3. Blanket exception handlers with no logging anywhere — **Fixed**

`callbacks/routing.py`, `callbacks/device.py`

Both handlers caught bare `Exception` and returned a friendly error panel. No
`logging` import existed anywhere in the application, so genuine programming
errors were indistinguishable from expected database failures and left no trace
at all.

**Fix.** Added `config/logging_config.py` and `logger.exception(...)` at both
sites. User-facing output is unchanged — no stack traces, SQL, or connection
details reach the UI, per `CLAUDE.md`.

---

## Medium severity

### 4. Snapshot tiles reset the selected period to 24h — **Fixed**

`components/metric_snapshot_strip.py`

Tile links were built as `/devices/{id}?metric={key}`, omitting `period`. Since
`parse_query` defaults a missing period to `24h`, clicking any metric tile while
viewing 7d, 30d or a custom range silently snapped the dashboard back to 24 hours.
`device_href()` already existed to build these URLs correctly but was not used
here.

**Fix.** URL helpers moved to a new top-level `routes.py` so components and
callbacks share one implementation; the strip now threads the active period
through `device_href()`.

### 5. Shared `period=custom` URLs lose their dates — **Fixed**

`callbacks/device.py`

`sync_query_string` emitted `period=custom` with no start/end, so a copied link
opened on an empty "No data available for the selected period" dashboard.

**Fix.** Custom bounds are now round-tripped as `start`/`end` query parameters,
parsed back by `parse_query`, and applied to the picker by
`device_dashboard.layout()`.

### 6. Database password is not URL-encoded — **Fixed**

`config/settings.py`

`sqlalchemy_url` interpolated the password directly. Verified: a password of
`p@ss:w0rd/1` produced an unparseable URL failing with a thoroughly misleading
`ValueError: invalid literal for int() with base 10: 'w0rd'`. Special characters
in database passwords are common, and the client's production credentials are
unknown to us.

**Fix.** Username and password are now passed through `urllib.parse.quote_plus`.

### 7. `auth_service.verify_credentials()` was dead code — **Fixed**

`services/auth_service.py`, `callbacks/auth.py`

The callback compared against `config.settings.demo_auth` inline, bypassing the
service entirely. This violates the project's own Architecture Rule 6 — "keep
demo authentication isolated so it can later be replaced by client
authentication" — since swapping in real auth would have required editing
callback code. The service docstring also referenced an `is_authenticated()`
function that did not exist.

**Fix.** The callback now calls `auth_service.verify_credentials()`. The stale
docstring reference was corrected.

---

## Medium severity (found during fix verification)

### 12. Login page accused every visitor before they typed anything — **Fixed**

`callbacks/auth.py`

The login form greeted every arrival with **"Invalid username or password."**
already displayed. `pages/login.py` sets `n_clicks=0` on the button, and the
router inserts the login form *dynamically* into `page-content` —
`prevent_initial_call=True` only suppresses the application's very first load,
not the insertion of new components. So `handle_login` ran immediately with
`n_clicks=0`; the guard tested `n_clicks is None`, which `0` does not satisfy,
and execution fell straight through to the failure branch.

This was visible in every screenshot taken during the previous verification pass
and went unremarked — a good reminder that "looks roughly right" is not
verification.

**Fix.** The guard is now `if not n_clicks:`, which catches both `None` and `0`.

---

## Low severity

### 8. "Show" password button did nothing — **Fixed**

`pages/login.py` declared `toggle-password-btn` with no callback anywhere.
Added one that toggles the field between `password` and `text` and updates the
button label.

### 9. `components/equipment_context.py` was dead code — **Fixed (removed)**

Never called; `device_dashboard` builds its own inline "Last data" strip.

### 10. Unused imports — **Fixed**

`callbacks/device.py` imported `callback` and `html` without using either.

### 11. Schema identifier interpolated into SQL without validation — **Fixed**

`repositories/plant_monitoring_repository.py` interpolates `monitoring.schema`
into every statement. The value comes from application configuration and is not
reachable from browser input, so this was not exploitable — but there was no
guard if `PLANT_MONITORING_SCHEMA` were ever sourced from somewhere less trusted.
Added a strict identifier validation at import time.

---

## Verified correct (no action)

- **Repository SQL** — all user-supplied values are bound parameters; metric
  lists use SQLAlchemy expanding `bindparam`. No injection surface found.
- **`_compute_delta` ordering assumption** — relies on ascending series;
  confirmed every range query orders `reading_ts ASC`.
- **`count_hierarchy_by_plant`** — `COUNT(DISTINCT t.transformer_id)` correctly
  compensates for LEFT JOIN row multiplication.
- **Confused-deputy protection** — `get_transformer_in_plant` verifies parent
  ownership; confirmed live that `/plants/plant-11/plant-01-t1` returns not-found.
- **Generator determinism** — seeded per device via SHA-256; `build_timestamps`
  correctly yields 1,441 inclusive points.
- **Energy monotonicity** — meter accumulates `max(0.0, ...)`, never decreasing.

---

# Second-pass audit (external) — dispositions

An independent second-pass audit (`CODE_AUDIT_SECOND_PASS.md`, 2026-08-08)
reviewed the same build for defects outside findings 1–12 above. Its findings
were re-verified against the code and, where the claim was behavioural, against
the running application. Dispositions:

| Finding | Verdict | Status |
|---|---|---|
| NEW-01 page-specific Outputs driven by a global Input | **Does not reproduce** | Closed — see below |
| NEW-02 row click wrong under sort/filter/page | Confirmed | **Fixed** |
| NEW-03 relative periods anchored to last sample | Confirmed | **Fixed** |
| NEW-11 capacity sorts as formatted text | Confirmed | **Fixed** (adjacent to NEW-02) |
| NEW-08 listing callbacks lack an error boundary | Confirmed | **Fixed** |
| NEW-05 badge rendered inside a badge | Confirmed | **Fixed** |
| NEW-06 equipment context/status + breadcrumb links | Confirmed | **Fixed** |
| NEW-04 naive bounds vs `TIMESTAMPTZ` | Confirmed | **Fixed** (UTC assumed — see below) |
| NEW-07 inactive hierarchy count mismatch | Confirmed | **Fixed** (policy chosen — see below) |
| NEW-09 schema configurable but DDL hard-coded | Confirmed | **Fixed** |
| NEW-10 chart `uirevision` keeps zoom across periods | Confirmed | **Fixed** |
| NEW-12 interrupted seed passes the "already seeded" guard | Confirmed | **Fixed** |
| NEW-13 documentation drift | Confirmed | **Fixed** (live docs; historical plan/spec left as records) |
| NEW-14 Enter does not submit login | Confirmed | **Fixed** |

## NEW-01 — not reproducible on Dash 2.17.1

The audit's stated mechanism is that the browser must resolve callback
dependencies before a Python-side `no_update` guard can protect them, so the two
listing callbacks whose tables are absent from the current route raise on every
navigation.

Its own prescribed regression test was run against the live application:
`login -> /plants -> plant -> transformer -> device -> /plants`, capturing
`console.error`. Every route rendered its expected content and **zero**
nonexistent-object errors were logged.

With `suppress_callback_exceptions=True`, dash-renderer prunes callbacks whose
Outputs are not in the currently rendered tree. The distinction from the real
finding 2 failure is that `hier-plant` existed in *no* layout at any time,
whereas `plants-table` exists in a layout that is sometimes mounted.

Restructuring the three working listing callbacks was therefore not done. Note
that `tests/test_equipment_selector.py` does *not* cover this claim: it asserts
each referenced id exists in **some** layout, not the currently mounted one. The
browser run is the evidence here.

## NEW-02 — fixed

Rows now carry an `id`, and the three navigation callbacks read
`active_cell["row_id"]` instead of indexing `State(table, "data")` by
`active_cell["row"]`. Verified live: with Plant sorted descending, the top row
(`Zaporozhye`) navigates to `/plants/plant-09` — under the old code it would
have followed base-order index 0 (`Az Zour South CCGT`).

## NEW-03 — fixed

`get_metric_view` and `get_device_full_view` now anchor relative periods to
wall-clock `now`. `current` / `last_updated` remain tied to the latest available
reading, which is what REQUIREMENTS.md specifies.

Consequence worth knowing when demoing: a device whose data ends before `now`
shows a *partially* filled 24h chart plus a stale badge, instead of a full chart
of older readings. On the seeded dataset (`latest = 2026-08-08 13:30`) a 24h
window returns 25 points rather than 48. That is the corrected behaviour, not a
data problem.

## NEW-08 — partially fixed

The three listing callbacks were being rewritten for NEW-02, so they gained
`logger.exception` plus a safe empty-table fallback rather than raising through
Dash. The shared page-level loading/error container the finding asks for is
**not** built; a database outage now yields an empty table, not an explanatory
panel. Still open.

## NEW-05 — fixed

`header-freshness` is now a neutral `header__freshness-slot` container holding
exactly one badge, instead of being the badge itself. The device callback writes
a badge into that slot via `header_freshness_children()`.

The visible symptom was that the header pill kept the class the layout first
rendered (`freshness-badge--no_data`) regardless of the data, because the real
badge was nested one level inside it. Verified live on a stale device: one badge
node, class `freshness-badge--stale`, slot carries no badge styling.

The error path no longer writes an `error_panel()` `<div>` into that slot — a
block element inside the header span was invalid markup. `error_outputs()` now
returns a no-data badge for the slot; the error panel still renders in the body.

## NEW-06 — fixed

`build_device_context()` was extracted from the router and carries the whole
`DevicePath`, including `plant_id`, `transformer_id` and `device_status`, which
the router previously discarded.

`device_dashboard.layout()` renders the UI_SPEC 6a bar —
`Plant | Transformer | Device | Status` — with `Last data` retained as a fifth
item. Device breadcrumb parents are now links (`/plants/{plant_id}` and
`/plants/{plant_id}/{transformer_id}`); they degrade to plain text when the ids
are unknown rather than emitting a half-built href.

`Status` here is administrative state only. It is deliberately not merged with
data freshness (the header badge) or monitoring condition, per CLAUDE.md.

## Note on the test suite

`tests/test_plant_monitoring_repository.py::TestLatestReadings::test_batched_latest_returns_all_eight_metrics`
failed once at 84.5ms against an 80ms budget on a cold connection, then passed
on five consecutive runs and two further full-suite runs. The timing assertions
in `tests/timing.py` have no warm-up, so the first query of a session pays
connection setup. Pre-existing fragility, not a regression — but it will
intermittently redden CI.

## NEW-09, NEW-10, NEW-12, NEW-13, NEW-14 — fixed

**NEW-09.** `db/init_plant_monitoring.sql` hard-coded `plant_monitoring` in all
11 identifier positions while `config/settings.py` and `.env.example` advertised
`PLANT_MONITORING_SCHEMA` as configurable, so any non-default value produced an
app and seed pointed at a schema the database had never created. The DDL is now
`db/init_plant_monitoring.sql.template` with an `@SCHEMA@` placeholder, applied
by `db/init_plant_monitoring.sh`, which validates the name against the same
identifier rule as `_validate_identifier()` before substituting.

Verified with a disposable stack on port 5497 using
`PLANT_MONITORING_SCHEMA=trfr_temperature`: the container logged
`Initialising monitoring schema: trfr_temperature`, created all four tables under
that schema, and did **not** create `plant_monitoring`. Stack and volume removed
afterwards; the working stack was untouched.

**NEW-10.** `chart_revision(metric, period, start, end)` now supplies
`uirevision`, so zoom survives the refresh interval but resets whenever the
operator changes metric, period or custom bounds.

**NEW-12.** The seed guard measured "does any reading exist". It now measures
(device, metric) pairs against devices × metrics, classified by
`evaluate_seed_state()`. COMPLETE skips as before; PARTIAL prints the shortfall
and exits 1 instead of reporting success. Verified against the live database:
full coverage reads 960/960 → complete, and simulating a device that never
finished loading gives 952/960 → partial.

**NEW-13.** `README.md` and `ARCHITECTURE.md` listed the deleted
`equipment_context.py` and `hierarchy_selector.py` and omitted `routes.py`,
`config/logging_config.py`, `callbacks/equipment_selector.py` and
`components/equipment_selector.py`. Both trees now match the filesystem, checked
programmatically rather than by eye.

`DATABASE.md` carried an invented DDL — `TEXT` columns instead of `VARCHAR(n)`,
`DOUBLE PRECISION` instead of `NUMERIC`, plus `created_at`, transformer `tier`
and `capacity_mva` columns that have never existed. It is now spliced directly
from the template. Its metric table had **six of eight precisions wrong**
(voltage 3→2, current 3→1, active_power 3→2, reactive_power 3→2, frequency 3→2,
energy 3→1); it is regenerated from `config/metrics.py`.

The plan and spec under `docs/superpowers/` still name the deleted components.
They are dated records of what was planned, not reference documentation, and
were deliberately left alone.

**NEW-14.** `login_was_submitted()` accepts the button click and Enter in either
field. The zero-counter guard is preserved: the router inserts the login form
dynamically, so the callback still fires on insertion with every counter at 0
and must stay silent.

## NEW-08 — now fully fixed

The earlier pass gave the listing callbacks logging and a safe empty-table
fallback but no explanatory state, so a database outage and a genuinely empty
result looked identical. Each listing page now carries an error slot
(`plants-error`, `transformers-error`, `devices-error`) that
`listing_outputs()` fills.

Verified by stopping the Postgres container and loading the overview: the page
rendered "Something went wrong loading this data. Please try again." while the
server log recorded `Listing failed while loading the plants overview` with the
full `OperationalError`. No stack trace, SQL or connection string reached the UI.
The same run confirmed NEW-14 — the session was logged in with Enter rather than
the button.

**Migration note discovered during that test.** Renaming the DDL to
`*.sql.template` (NEW-09) breaks `docker start` on a container created before the
change: the old container still bind-mounts the old path, exits 127, and Docker
silently recreates the missing mount source as an empty *directory* in `db/`.
`docker compose up -d` recreates the container correctly and the data survives,
since it lives in the `powerplant_pgdata` volume. Documented in README under
"Upgrading an existing checkout".

## NEW-04 — fixed, under a stated assumption

**Assumption.** The demo treats every instant as UTC. This was not an open
choice so much as an inconsistency: `_now()` already returns UTC-aware and
`_align_tz()` already attaches UTC, while only the date-picker bounds stayed
naive. If the client later wants plant-local display, that is a presentation
layer on top of UTC storage, not a change to any of this.

`_parse_picker_date()` now returns UTC-aware values and `_resolve_window()`
aligns custom bounds to the anchor's timezone before they leave the service.

**Demonstrated on the seeded database.** Selecting Aug 3 on `plant-01-t1-d1`,
comparing naive against aware bounds under three session timezones:

| session `TimeZone` | window actually selected | |
|---|---|---|
| `UTC` | 08-03 00:00Z .. 08-03 23:30Z | same either way |
| `Asia/Kolkata` | naive gave 00:00+05:30 .. 23:30+05:30 | **shifted 5h30** |
| `America/Los_Angeles` | naive gave 00:00−07:00 .. 23:30−07:00 | **shifted 7h** |

The row count is identical in every case — a 24-hour window holds 48 half-hourly
readings wherever it starts — which is precisely why this would not have been
noticed. The *readings* differ.

Displayed instants are now labelled: `Timestamp (UTC)` in the readings table,
`Last data (UTC)` in the equipment context bar, and `Time (UTC)` on the chart
x-axis. `tests/test_date_range.py` was updated to expect aware values, since the
bounds it asserts on deliberately changed.

## NEW-07 — fixed, policy chosen

**Policy.** Inactive equipment is excluded from listings *and* counts, so the two
finally agree, but remains reachable by direct URL with a notice. A monitoring
system for decommissioned plant still holds readings worth inspecting; making
them unreachable would lose that, while listing them would clutter operational
views with equipment that is no longer reporting.

`count_hierarchy_by_plant()` takes `include_inactive` (default `False`) and
applies the status filters **in the JOIN, not a WHERE clause** — a WHERE would
turn the LEFT JOINs inner and drop plants with no active equipment off the
overview entirely.

**Demonstrated against the seeded database** by inserting an inactive
transformer and device under `plant-07` inside a transaction, then rolling back:

| query | result |
|---|---|
| unfiltered (previous behaviour) | 2 transformers, 2 devices |
| what the drill-down page lists | 1 transformer, 1 device |
| filtered (current behaviour) | 1 transformer, 1 device |

`inactive_notice()` marks inactive plants, transformers and devices when opened
directly. It is styled as an informational strip rather than an error panel,
because inactive is a normal administrative state. As everywhere else,
administrative status stays separate from data freshness and monitoring
condition.

Note that the seeded dataset is entirely `active`, so this finding was latent —
it could not have been observed in the demo, only once real data arrives.

---

# Second-pass audit — closed

All 14 findings are dispositioned: 13 fixed, 1 (NEW-01) closed as not
reproducible with the evidence recorded above. Test count went from 180 to 315.
