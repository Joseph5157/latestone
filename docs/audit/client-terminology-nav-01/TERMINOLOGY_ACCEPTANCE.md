# CLIENT-TERMINOLOGY-NAV-01 — client terminology and navigation acceptance

Date: 2026-09-30 · Baseline `5eb3644` · Viewport 1366×900 · Local app against the
restored client `RTL` SQL Server (`rtl_app_reader`, SELECT only).

Terminology only. No route path, database query, role policy, migration or
SQL Server access changed.

## What changed

| Surface | Before | After |
|---|---|---|
| Sidebar item for `/plants` | `Overview` | `Registered RTLs` |
| `/plants` page heading | `Fleet Overview` | `Registered RTLs` |
| `/plants` breadcrumb crumb | `Fleet` | `Registered RTLs` |
| `/plants` subtitle | "Registered RTLs and their latest recorded temperature." | "Every RTL in the client's directory, with its latest recorded temperature." |
| Not-found panel link | `Back to plants` | `Back to Registered RTLs` |
| Forbidden panel link | `Back to Fleet Overview` | `Back to Registered RTLs` |

Four files: `components/app_sidebar.py`, `pages/plants_overview.py`,
`components/status_panels.py`, plus the tests below.

The sidebar item's **key** stays `overview` and its **href** stays `/plants`.
Both are identity, not wording: `routes.NAV_KEY_BY_ROUTE` and
`services.authorization.ROUTE_POLICY` join on that key, so renaming it would
have silently rewritten the authorization map. The canonical `/rtls` route
belongs to RTL-UID-DETAIL-01.

## Observed live (1366×900, fresh app process)

### Administrator (`admin`)

Sidebar, in order: **Registered RTLs**, Command Center · Operations: Devices,
Assignments, Registration · System: Notifications, Reports, Users, Audit Log,
Settings. Ten items, unchanged in count, membership and order.

`/plants`: heading **Registered RTLs**, breadcrumb **Registered RTLs**, 339
table rows. Cards 339 / 185 / 319 / 20. Chips: All registered · 339 · With
temperature data · 319 · No temperature data · 20 · No current transformer
mapping · 154. Table headers: RTL UID, Latest temperature, Last reading,
Transformer, Zone · Sector · CNC / Feeder.

Every figure matches `docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md` and
the SATURDAY-REAL-FLEET-01 record (339 / 185 / 319 / 20 / 154).

Forbidden-word scan over the rendered `/plants` page — `Plant`, `Plants`,
`plant`, `plants`, `Online`, `Offline`, `Healthy`, `Unhealthy`, `voltage`,
`frequency`, `energy`, each matched as a whole word — found **nothing**. The
one occurrence of "online" anywhere on the page is inside the negating scope
note: "This is not a count of active or online RTLs."

Asset Navigator: `.app-shell__utility` carries `--hidden`, computed
`display: none`, measured width `0`. Unchanged from SATURDAY-REAL-FLEET-01
(`callbacks/navigation.py` `UTILITY_ROUTES` still omits `overview`); this gate
did not touch it.

Evidence: `nav-1366-administrator.png`.

### General User (`demo.general01`)

Lands on `/` → the registered RTL directory (ADR-024). Sidebar shows exactly
two destinations: **Registered RTLs**, Reports. Heading and breadcrumb both
**Registered RTLs**; 339 rows; no restricted panel.

Evidence: `nav-1366-general.png`.

### Technician (`demo.tech01`)

Sidebar shows five destinations: **Registered RTLs**, Command Center, Devices,
Notifications, Reports.

`/plants` renders the restricted panel — "Client RTL fleet not available for
your account … There is no approved link between client RTLs and technician
assignments yet." Zero table rows; a regex scan for a rendered RTL UID
(`\b29\d{3}\b`) found none, so the RTL source was not read for this scope.

`/admin/users` (Administrator-only) still refuses with the forbidden panel:
"No access / Your account does not have access to this page." The way back now
reads **Back to Registered RTLs** and still points at `/plants`.

Evidence: `nav-1366-technician-restricted.png`.

## Authorization

| Persona | Before | After |
|---|---|---|
| Administrator | 10 nav items, full fleet | identical |
| General User | Overview + Reports, full fleet | Registered RTLs + Reports, full fleet |
| Technician | 5 items, restricted panel, no UIDs | identical, restricted panel, no UIDs |
| Admin-only route as Technician | forbidden panel | forbidden panel |

`visible_nav_keys` is derived from `ROUTE_POLICY` via `NAV_KEY_BY_ROUTE`, and
neither was touched, so no role gained or lost a destination. Asserted in
`tests/test_client_terminology.py::TestIdentityAndAuthorizationAreUnchanged`
and unchanged in `tests/test_authorization.py`.

## Console

`/plants` reported **0 errors**. Every message captured across the session is
pre-existing and unrelated: React `componentWillMount` /
`componentWillReceiveProps` deprecation warnings from Dash's bundled
react-dom@16, a `login-powerplant-hero.jpg` preload warning, and React's
controlled/uncontrolled input warning raised by filling the **login** form.
None originates in a file this gate changed.

## Database

No SQL Server, PostgreSQL, Alembic or query change. `/plants` runs the same
four SELECTs `rtl_fleet_service` already issued; the diff contains no `.sql`,
no `alembic/`, no repository and no service file.

## Regression

`python -m pytest -m "not db"` → **3259 passed, 3 skipped, 0 failed, 731
deselected** in 34.88 s. The 3221-passing baseline plus the 38 new assertions
in `tests/test_client_terminology.py`.

The seven DB-marked PostgreSQL failures recorded at SATURDAY-REAL-FLEET-01
close (`test_seed_integrity` ×5, `test_plant_monitoring_repository` range ×2)
are local simulator/data drift and are outside the `not db` selection. This
gate touched no PostgreSQL code.

## Remaining terminology debt (NOT this gate)

Recorded so the next gate inherits a list rather than a search:

1. **Synthetic drill-down breadcrumbs.** `pages/plant_detail.py`,
   `pages/transformer_detail.py` and `pages/device_dashboard.py` still open
   their breadcrumb with "Fleet". Deliberate: those pages show the synthetic
   PostgreSQL Plant model, and relabelling their root "Registered RTLs" would
   assert a synthetic plant sits under the client RTL directory. "Fleet" is the
   vaguer and more honest word until the pages themselves are retired.
2. **`overview` still highlights on synthetic routes.** `NAV_KEY_BY_ROUTE` maps
   `plant`/`transformer`/`device` to `overview`, so the "Registered RTLs" item
   stays highlighted on a synthetic drill-down page. Not changed here because
   removing those entries is a navigation-behaviour change, not a wording one,
   and it would drop `test_authorization.py`'s coverage of three routes. It
   belongs to the gate that retires those pages. Mitigating fact: the RTL fleet
   table links nowhere, so those routes are no longer reachable from `/plants`.
3. **"This plant was not found."** `not_found_panel("plant")` on
   `/plants/<unknown>`. Truthful for that legacy route — it really did look for
   a synthetic plant — and renaming the entity to "RTL" would be false.
4. **Synthetic admin/report screens.** `Plant` columns, filters and scope
   selectors remain in `pages/device_admin.py`, `pages/admin_assignments.py`,
   `pages/technician_devices.py`, `pages/report_center.py`,
   `pages/device_register.py`, `components/assign_device_drawer.py`,
   `components/device_manage_drawer.py` and `components/equipment_selector.py`.
   All are REPLACE/ADAPT in the realignment plan; they describe genuinely
   synthetic PostgreSQL objects, so renaming them would be a lie, not a fix.
5. **Sidebar "Devices".** Both entries point at synthetic PostgreSQL device
   directories, not client RTLs. Deliberately NOT renamed to "RTLs": the plan
   forbids implying a synthetic device ID is a client RTL UID.
6. **Target sections not yet built.** Dashboard, Network, Historical Events,
   Technicians and Administration have no safe destination. None was added —
   this gate must not advertise a page that does not exist.

## Deferred (not in this gate)

Route rename to `/rtls`, hierarchy navigation, alarms/programming/lifecycle,
PostgreSQL removal, legacy code deletion, authorization changes.
