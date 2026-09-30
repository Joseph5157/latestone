# RTL-UID-DETAIL-01 — canonical client RTL detail acceptance

Date: 2026-09-30 · Baseline `ea94bd5` · Viewport 1366×900 · Local app against the
restored client `RTL` SQL Server (`rtl_app_reader`, SELECT only).

## What was added

The canonical real-client RTL detail route, `/rtls/<uid>`, whose identity is the
numeric client RTL UID from `dbo.device_list`. No synthetic PostgreSQL
`device_id` is involved and none is inferred.

| Layer | File | Role |
|---|---|---|
| Route | `routes.py` | `/rtls/<uid>` parsing, `Route.rtl_uid`, `rtl_detail_href` |
| Policy | `services/authorization.py` | `ROUTE_POLICY["rtl_detail"]` = Administrator + General User |
| Service | `services/rtl_detail_service.py` (new) | registration gate, facts, history windows |
| Page | `pages/rtl_detail.py` (new) | layout only, no queries |
| Render | `components/rtl_detail.py` (new) | summary, network context, history |
| Callback | `callbacks/rtl_detail.py` (new) | one snapshot per load / window change |
| Router | `callbacks/routing.py` | route branch + scope gate |
| Fleet link | `components/rtl_fleet.py` | UID cell links to `/rtls/<uid>` |
| Decision | `docs/decisions/ADR-030-...md` (new) | history windows anchor on the last reading |

No repository change: the five reads this page needs already existed.

## Identity and registration

Registration is the gate, checked **first**, so an unregistered UID never causes
a temperature, mapping or hierarchy read. Verified live against the source:

| Population | Count |
|---|---:|
| Registered (`device_list`) | 339 |
| Telemetry UIDs (`master_temperature`) | 400 |
| Telemetry-only — has real readings, **not** registered | 81 |

UID **29002** is one of those 81: it has genuine temperature history and no
`device_list` row. `/rtls/29002` returns "RTL not found", renders no
temperature, no chart and no transformer, and hides the history control. That
is the case the gate names specifically, proven against real data rather than a
fixture.

| Path | Result |
|---|---|
| `/rtls/29042` registered, mapped, telemetry | full detail |
| `/rtls/29006` registered, telemetry, unmapped | detail; `No current transformer mapping` |
| `/rtls/29504` registered, no telemetry, unmapped | detail; `No temperature data` |
| `/rtls/29002` telemetry-only, unregistered | RTL not found; no facts |
| `/rtls/12345` unknown to every table | RTL not found; no facts |
| `/rtls/abc`, `/rtls/-1`, `/rtls/0`, `/rtls/2147483648`, `/rtls/٢٩` | route `unknown` → not-found |
| `/rtls` (bare list) | route `unknown` → not-found; the list route is a later gate |
| `/devices/plant-01-t1-d1` | route `device`, unchanged |

## Observed live — General User `demo.general01`

**RTL 29042** (mapped, hierarchy, telemetry):

- Latest temperature **29.0 °C**, "Latest reading on record"
- Last reading **18 Sep 2022 20:20 SAST**, "As recorded by the RTL source (SAST)"
- Transformer **EMV35**, "Current mapping"
- Network context: KwaZulu-Natal Operating Unit · Pietermaritzburg Zone ·
  Pietermaritzburg Sector · Howick CNC · Edendale NBEC 22kV Cable Overhead Line
- History 24 h → `17 Sep 2022 20:20 SAST to 18 Sep 2022 20:20 SAST`, 1 reading
- History 30 d → `19 Aug 2022 20:20 SAST to 18 Sep 2022 20:20 SAST`, 27 readings,
  27 plotted points

**RTL 29006** (unmapped, telemetry from 2017): 18.0 °C at 20 Oct 2017 05:41 SAST;
24-hour window `19 Oct 2017 05:41 to 20 Oct 2017 05:41 SAST`, **48 readings**.

That last row is the clearest evidence for ADR-030. Measured from wall-clock
now, this RTL's "last 24 hours" would contain zero readings — as it would for
effectively all 339, since client telemetry stops at 17 Sep 2026 and this RTL
stopped in 2017. Anchored to its own last reading it shows 48 real readings, and
the page states the exact period.

**RTL 29504** (registered, no telemetry, unmapped): every missing value stated
in words — `No temperature data`, `No reading on record`, `No current transformer
mapping`, and "This RTL has no current transformer mapping in the client source,
so it has no network context." The history control is hidden; the chart carries
the annotation `No temperature readings in this period.`

Forbidden-word scan of each rendered page — `Plant`, `Plants`, `plant`,
`Online`, `Offline`, `Healthy`, `Unhealthy`, `Inactive`, `voltage`, `frequency`,
`energy`, `null`, `undefined`, `NaN`, `None`, each as a whole word — found
**nothing** on any of them.

## Authorization

| Persona | `/plants` | `/rtls/<uid>` typed directly |
|---|---|---|
| Administrator | full fleet | full detail |
| General User | full fleet | full detail |
| Technician | restricted panel | **forbidden panel**; no UID, temperature, transformer or hierarchy in the DOM |
| Unauthenticated | login | login |
| Unknown role | forbidden | forbidden |

Two independent gates, both before any client SQL Server read:

1. `ROUTE_POLICY["rtl_detail"]` excludes the Technician, evaluated in
   `route_decision` before a scope is even resolved.
2. `may_view_real_fleet(scope)` — the same predicate the Fleet page uses — in
   the router's route branch.

The second is not redundant: the policy answers "may this ROLE open the route",
the scope answers "may THIS SESSION see raw client RTL facts", and a future
scope change must not silently widen this page.
`tests/test_rtl_detail_route.py::TestAuthorizationBoundary` pins the two to the
same answer for every role.

## Bug found by browser acceptance

The first run rendered **`RTL UID None`**. `parse_pathname` was correct and its
unit tests passed; `callbacks/routing.py` rebuilds the parsed `Route` to apply
landing-page rules, and that rebuild lists its fields explicitly — `rtl_uid` was
not among them, so it was silently blanked. No exception was raised anywhere.

Fixed, and pinned by
`TestTheRouterPreservesEveryIdentityField::test_the_rebuild_in_the_router_matches_this_field_list`,
which compares the router's `Route(...)` kwargs against the dataclass fields, so
any future field added to `Route` fails until the rebuild is updated.

A second, smaller defect from the same run: an RTL with exactly one reading in
its window read "1 readings". Fixed and pinned.

## Unsupported claims

None of voltage, current, active power, reactive power, power factor, frequency
or energy appears on the page, and the synthetic eight-metric device dashboard
is not reused — asserted structurally, not by text scan:
`test_the_synthetic_device_dashboard_is_not_reused` walks the page and component
ASTs for `metric_chart`, `metric_workspace`, `ordered_metrics`, `METRIC_KEYS`,
`readings_table`, `freshness_badge`, `Freshness`, `device_operations` and
`device_manage_drawer`.

No Online/Offline, Active/Inactive or Healthy state is shown or derived.
`device_status.last_status`, `comms_alarm`, `vw_installed_rtls` and
`last_comms_ok` are never consulted —
`test_it_reads_only_the_four_approved_source_methods` enumerates the service's
entire source surface as exactly five repository reads.

No status colour is defined for this page; `status_colors` and `KIND_TONE` are
absent from both modules by assertion.

## Latest-temperature ambiguity

Inherited from `rtl_source_facts_service`, not re-implemented. One value → use
it; identical tied values → the common value; conflicting values → `Ambiguous
latest temperature`, both source values shown, none chosen.
`test_ambiguity_semantics_match_the_fleet_page` asserts the detail page and the
Fleet page agree for the same UID. The current snapshot has 0 ambiguous latest
values, so this path is covered by fixture rather than live data.

## Query behaviour

Per detail page load: registered directory (339 rows), transformer mappings
(185), latest temperature (1 UID), hierarchy view (185). Per window change: one
bounded range read for one UID between two source timestamps. No write SQL, no
unbounded fetch — there is deliberately no "all time" window, which would be an
unbounded read of a 2.4M-row heap.

## SQL Server integrity (verified at closure)

- `DATABASEPROPERTYEX(DB_NAME(), 'Updateability')` = **`READ_ONLY`**
- `HAS_PERMS_BY_NAME` for `rtl_app_reader`: UPDATE/INSERT/DELETE on
  `dbo.device_list` = `0`, UPDATE on `dbo.master_temperature` = `0`,
  ALTER on the database = `0`

| Reference count | Expected | Observed |
|---|---:|---:|
| `master_temperature` | 2,456,901 | **2,456,901** |
| telemetry UIDs | 400 | **400** |
| `device_list` | 339 | **339** |
| `trfr_list` | 185 | **185** |

These are validation reference values only; no application logic hard-codes them.

## PostgreSQL

Unchanged. No schema, Alembic, seed or data change; the diff contains no
`alembic/`, no `db/`, and no PostgreSQL repository or service. The detail
service reaches for no PostgreSQL path — asserted by AST walk for
`plant_monitoring_repository`, `monitoring_service`, `hierarchy_service`,
`sqlalchemy` and `db.engine`.

## Console

**0 errors** on a clean run of `/rtls/29042` after a fresh app start
(`console-errors.log`). Two pre-existing React lifecycle deprecation warnings
from Dash's bundled react-dom@16 remain, as everywhere else in the application.

Earlier entries in the session predate a clean restart: one 500 occurred inside
the Flask hot-reload window while the fifth callback output was being added, and
several "server did not respond" entries were the browser's pending requests
when the app process was deliberately stopped. Neither is reproducible after
restart, and the server log for the final run contains no traceback.

## Regression

`python -m pytest -m "not db"` → **3445 passed, 3 skipped, 0 failed, 731
deselected** in 35.85 s. The `ea94bd5` baseline was 3259 passed; this gate adds
186 assertions across `test_rtl_detail_route.py`, `test_rtl_detail_service.py`
and `test_rtl_detail_page.py`.

One existing test required updating for a real reason:
`test_equipment_selector.py::test_every_callback_id_exists_in_some_layout` is an
inventory of every layout a callback may target, and it correctly failed until
the new page was registered in it. PostgreSQL was not reseeded or modified to
repair the known DB-marked simulator drift.

## Not in this gate (recorded, not defects)

Canonical `/rtls` list route and the `/plants` → `/rtls` redirect; full Network
hierarchy navigation; Online/Offline or any communication-state engine; alarm
acknowledgement; technician UID assignment mapping; lifecycle/deactivation;
programming and commands; notifications; the seven electrical metrics;
PostgreSQL retirement; dead-code cleanup; any SQL Server write.

`/devices/<app-device-id>` remains legacy and synthetic. It was **not**
redirected to `/rtls/<uid>`: there is no approved mapping from a synthetic
application device id to a client RTL UID, and manufacturing one is exactly what
the realignment plan forbids. `test_the_legacy_device_route_is_unchanged` pins
that it still parses to `device` with `rtl_uid` unset.
