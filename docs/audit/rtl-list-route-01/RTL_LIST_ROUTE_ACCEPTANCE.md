# RTL-LIST-ROUTE-01 — canonical Registered RTLs list route acceptance

Date: 2026-09-30 · Baseline `7ca7a33` · Viewport 1366×900 · Local app against the
restored client `RTL` SQL Server (`rtl_app_reader`, SELECT only).

## What changed

The Registered RTLs list moved to its canonical address, `/rtls`. It is the
same page (`pages/plants_overview.py`), the same callback
(`callbacks/fleet_overview.py`) and the same service (`rtl_fleet_service`); the
route name is still `overview`, so `ROUTE_POLICY`, `NAV_KEY_BY_ROUTE` and the
Fleet callback's own route check apply exactly as before.

`/plants` is now compatibility only:

| How `/plants` is reached | Handled by | Result |
|---|---|---|
| Full page load (bookmark, typed, shared) | Flask rule, `callbacks.routing.register_legacy_redirects` | `302` → `/rtls`, query carried verbatim, before Dash renders |
| In-app navigation (nothing links there now) | `callbacks.auth._path_command` | pathname rewritten to `/rtls`, `url.search` untouched |
| Router | `callbacks.routing.route_to_page` | alias returns `no_update`; no session, scope or data read |

**Why an HTTP redirect as well as the Dash one.** Dash 2.17's `dcc.Location`
has no `replaceState`, only `pushState`. A Dash-only redirect leaves `/plants`
in the browser history, and Back returns to it and is sent forward again. A
302 replaces the history entry. It is temporary (302) rather than permanent
because browsers cache 301/308 indefinitely.

The decision itself ("list at `/rtls`", "`/plants` should redirect compatibly")
is `docs/plans/CLIENT_APP_REALIGNMENT_PLAN_01.md` §5, so no ADR was added.

## Links

Every in-app link to the directory now uses the canonical constant: the
sidebar item, the forbidden and not-found panels' way back, the RTL detail
breadcrumb and its not-registered panel, the page's own Refresh link, and the
synthetic drill-down breadcrumbs' "Fleet" crumb (label unchanged; it pointed at
the same page). `tests/test_rtl_list_route.py` asserts by AST that no
application module spells `/plants` as a string any more except the
compatibility constant itself; the synthetic `/plants/<id>` f-strings are a
different route and are untouched.

## Observed live

**General User** (`demo.general01`):

1. Sidebar "Registered RTLs" has `href="/rtls"`; clicking it lands on
   `/rtls`, with that item highlighted.
2. Registered RTLs 339 · current transformer mappings 185 · with temperature
   data 319 · no temperature data 20; 339 rows. Forbidden-word scan (Plant,
   Plants, Online, Offline, Healthy, Voltage, Frequency, Energy, Power factor,
   null, undefined, NaN, None) — nothing found. `01-general-rtls-list.png`
3. Filter "No current transformer mapping · 154" → 154 rows.
   `02-general-rtls-filter-unmapped.png`
4. Row 29006 → `/rtls/29006` (18.0 °C, 20 Oct 2017 05:41 SAST, no mapping).
5. Breadcrumb `Registered RTLs` → `href="/rtls"`, returns to `/rtls`.
   `03-general-rtl-detail-breadcrumb.png`

**Compatibility**:

| Request | Final URL | Fleet loads | Router calls |
|---|---|---:|---:|
| full load `/rtls` | `/rtls` | 1 | 1 |
| full load `/plants` | `/rtls` | 1 | 1 |
| full load `/plants?filter=mapped` | `/rtls?filter=mapped` | 1 | 1 |
| in-app navigation to `/plants?q=1` | `/rtls?q=1` | 1 | 2 (first renders nothing) |

Counted from the browser's `_dash-update-component` requests by output. One
page, one heading, no duplicate render. Back after a full load of `/plants`
went to the previous page (`/rtls/29042`), not to `/plants` again.
`04-compat-plants-redirected-to-rtls.png`

The directory's filter is page state, not URL state, so no query parameter is
meaningful to it today; the query is carried only so a legacy link loses
nothing. `/rtls?filter=mapped` therefore shows all 339, as `/plants?filter=mapped`
always did.

**Technician** (`demo.tech01`):

| Path | Result |
|---|---|
| `/rtls` | "Client RTL fleet not available for your account" — no stat cards, 0 rows, no UID in the DOM. `05-technician-rtls-restricted.png` |
| `/plants` | redirected to `/rtls`, same restricted panel |
| `/rtls/29042` | forbidden panel, no UID in the DOM. `06-technician-rtl-detail-forbidden.png` |

The restriction is the Fleet callback's scope check (`may_view_real_fleet`),
evaluated before `get_real_fleet`; it keys on page-context, not on the address,
so it applies at `/rtls` exactly as it did at `/plants`.

**Unauthenticated**: `/plants` → `/rtls` → login form.

**Administrator** (`admin`): `/rtls` 339 rows with the same counts; `/plants`
→ `/rtls`; `/rtls/29042` full detail; `/devices/plant-01-t1-d1` still serves the
synthetic device dashboard at its own address, not redirected.
`07-administrator-rtls-list.png`

## Query behaviour

No repository, service or SQL change. `/rtls` issues the same set-based
directory reads the page issued at `/plants`: one registered-directory read,
one latest-temperature read, one mapping read, one hierarchy read. The
redirect adds none: the HTTP 302 is answered before Dash starts, and the
in-app alias writes no page-context, so the Fleet callback cannot fire for it.

## Console

`console-errors.log`: 4 error-level entries, all the same React warning ("A
component is changing an uncontrolled input … to be controlled"), one per
render of the login form. The login form is not in this diff. No error on
any `/rtls`, `/plants` or `/rtls/<uid>` render. Two React lifecycle
deprecation warnings from Dash's bundled react-dom@16 appear on every page,
as before.

## SQL Server integrity (verified at closure)

- `DATABASEPROPERTYEX(DB_NAME(), 'Updateability')` = **`READ_ONLY`**
- `HAS_PERMS_BY_NAME` for `rtl_app_reader`: UPDATE/INSERT/DELETE on
  `dbo.device_list` = `0`, UPDATE on `dbo.master_temperature` = `0`, ALTER on
  the database = `0`

| Reference count | Expected | Observed |
|---|---:|---:|
| `master_temperature` | 2,456,901 | **2,456,901** |
| telemetry UIDs | 400 | **400** |
| `device_list` | 339 | **339** |
| `trfr_list` | 185 | **185** |

These are validation reference values only; no application logic hard-codes them.

## PostgreSQL

Unchanged. No schema, Alembic, seed or data change, and no reseed.

## Regression

`python -m pytest -m "not db"` → **3539 passed, 3 skipped, 0 failed, 731
deselected**. The `7ca7a33` baseline was 3445. `tests/test_rtl_list_route.py`
adds 92; `test_app_sidebar.py` and `test_routing.py` gained one alias test each.

Seventeen existing assertions pinned the old `/plants` address — the
sidebar href, the directory constant, `parse_pathname("/plants") == overview`,
the way-back and breadcrumb hrefs, and RTL-UID-DETAIL-01's "`/rtls` is not a
list yet". Each was updated to the canonical address with a comment naming
this gate. None was weakened: every one still asserts a specific path.
The RTL-UID-DETAIL-01 route-field parity guard is unchanged and restated here.
