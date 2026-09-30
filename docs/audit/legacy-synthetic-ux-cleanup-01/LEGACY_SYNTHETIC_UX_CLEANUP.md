# LEGACY-SYNTHETIC-UX-CLEANUP-01 — Retire legacy synthetic client paths

Gate: LEGACY-SYNTHETIC-UX-CLEANUP-01
Status: implemented
Baseline (starting SHA): `3c7f936c3582e935f44d0d1a7e110dd134d7901b`
Authority: `docs/plans/CLIENT_APP_REALIGNMENT_PLAN_01.md` §8 (retirement order,
"no big-bang deletion"); ADR-032 ("the synthetic Command Center is no longer
reachable from production routing; its code is legacy cleanup debt"); ADR-033
(auth unchanged); `docs/context/SOURCE_AUTHORITY.md`.

This gate is **code/UX cleanup**, not a database-layer purge and not PostgreSQL
retirement. Its mandatory outcome: the superseded synthetic Plant → Transformer
→ Device experience (and the synthetic Command Center, Needs Attention, Device
Management, Asset Navigator and unsupported metrics) is **no longer reachable
through production navigation or by direct URL**, while the real client-RTL
product is untouched. Where deleting a synthetic module would touch shared
infrastructure or amount to a big-bang deletion, the module is **isolated and
documented** for the later POSTGRESQL-RETIREMENT gate (plan §8, wave 7).

---

## 1. Removed routes (retired to the legacy/not-found panel)

Every synthetic address below now parses to the route name `legacy_retired`
(`routes.py:parse_pathname`), which — like `unknown` — is deliberately absent
from `ROUTE_POLICY`. The router (`callbacks/routing.py`) answers it with
`components.status_panels.legacy_retired_panel()`: a static panel that resolves
no identifier, reads no scope and no source, and links back to `/rtls`.

| Retired address | Former route name | Was |
|---|---|---|
| `/plants/<id>` | `plant` | synthetic plant detail |
| `/plants/<id>/<tf>` | `transformer` | synthetic transformer detail |
| `/devices/<id>` | `device` | synthetic 8-metric device dashboard |
| `/devices` | `technician_devices` | synthetic technician device roster (already denied, ADR-032) |
| `/admin/devices` | `admin_devices` | synthetic Device Management |
| `/admin/devices/new` | `device_register` | synthetic device registration |
| `/admin/assignments` | `admin_assignments` | old synthetic app-device assignment |

The synthetic device id / plant id / transformer id carried by these addresses
is **dropped** during parsing, so nothing downstream can resolve it and no
existence oracle is possible. **No fabricated `/devices/<id>` → `/rtls/<uid>`
redirect** was created — no approved synthetic-id → client-UID mapping exists
(§6, §22).

## 2. Retained compatibility routes

- `/plants` → `/plants/` → **302 → `/rtls`** (RTL-LIST-ROUTE-01, pre-existing,
  unchanged). `routes.legacy_redirect_path` and
  `routing.register_legacy_redirects` are untouched. Only the bare list address
  redirects; the drill-down beneath it is retired per §1.
- `/rtls`, `/rtls/<uid>`, `/rtls/network`, `/events`, `/command-center` (factual
  Dashboard), `/technicians/assignments`, `/admin/users`, `/admin/audit-log`,
  `/admin/settings`, `/reports`, `/notifications`, `/set-password` — all real,
  all unchanged.

## 3. Removed navigation

- Sidebar (`components/app_sidebar.py`): the **"Devices"** item
  (`/admin/devices`) and the **"Registration"** item (`/admin/devices/new`) were
  removed from the Operations section. The Technician synthetic "Devices" item
  was already gone (ADR-032). Operations now holds only the real
  **"Technician Assignments"** (`/technicians/assignments`).
- `routes.NAV_KEY_BY_ROUTE`: the entries for `plant`, `transformer`, `device`,
  `admin_devices`, `technician_devices`, `admin_assignments` and
  `device_register` were removed. The retired addresses now highlight nothing
  (`legacy_retired` names no nav key).
- The Asset Navigator (equipment selector) is now hidden on **every** route:
  `callbacks/navigation.py` `UTILITY_ROUTES` is empty (its only home was the
  synthetic drill-down, now retired).
- Retained (proven still real): Registered RTLs, Network, Historical Events,
  Dashboard, Technician Assignments, Notifications, Reports, Users, Audit Log,
  Settings.

## 4. Removed pages / components (deleted — cleanly dead)

| File | Evidence it was dead |
|---|---|
| `pages/command_center.py` | synthetic Command Center page; only importers were `callbacks/command_center.py` (deleted) and `callbacks/routing.py` (fallback removed). Fallback was unreachable: every role that passes the `command_center` route gate (Administrator/Technician) has a permitted fleet scope, so `may_view_real_fleet` is always True and the factual `rtl_dashboard` always rendered instead. |
| `callbacks/command_center.py` | registered the CC callbacks; deregistered from `app.py`; no other importer. |
| `components/attention.py` | imported only by `callbacks/command_center.py` (deleted). |
| `components/command_center/` (`__init__`, `primitives.py`, `refresh.py`) | imported only by the deleted CC page/callback/attention. |
| `assets/command_center.js` | referenced only by the deleted CC page. |
| `components/fleet_overview.py` | old synthetic Fleet presentation; no production importer (only its own tests). Plan §8 explicit RETIRE candidate. |
| `services/fleet_overview_service.py` | old synthetic Fleet service; no production importer (only its own tests). Plan §8 explicit RETIRE candidate. |

Reachability was proved by import-graph search over `app.py`, `callbacks/`,
`pages/`, `components/`, `services/` (excluding `.kilo/` — a separate agent
worktree — and `__pycache__`), not by grep alone: the router's dynamic
`command_center` fallback was analysed against `may_view_real_fleet` to confirm
it could never be taken in production.

## 5. Removed callbacks / callback registration

- `callbacks/command_center.py` deleted; `command_center.register(app)` and its
  import removed from `app.py`.
- `callbacks/routing.py`: the `plant`, `transformer`, `device`, `admin_devices`,
  `technician_devices`, `admin_assignments`, `device_register` and synthetic
  `command_center` render branches were removed; the helper
  `build_device_context` and the imports `hierarchy_service`, `entity_in_scope`,
  `current_device_scope`, `DeviceScope`, `parse_rtl_uid` (used only by those
  branches) were removed. A single `legacy_retired` branch was added.
- The callback/layout ownership guard (`tests/test_equipment_selector.py::
  test_every_callback_id_exists_in_some_layout`) stays green: the CC page/
  callback were removed **together**, and the still-isolated synthetic pages'
  layouts remain in the guard's mountable-id collection.

## 6. Removed services

- `services/fleet_overview_service.py` (dead — §4).
- **No other service was removed.** `attention_service`, `hierarchy_service`,
  `monitoring_service`, `device_timeline_service`, `temperature_condition_service`,
  `plant_monitoring_repository` and the device/registration/assignment services
  remain — they are shared by the isolated synthetic cluster and/or by retained
  code, and their deletion belongs to the POSTGRESQL-RETIREMENT gate (§16: "not
  a database-layer purge").

## 7. Retained legacy code and why (isolated, unrouted)

The following synthetic modules are **kept, isolated and no longer reachable**
(their routes are retired, their nav items removed). They are not deleted in
this gate because doing so is a big-bang deletion of the transitional synthetic
model — explicitly sequenced into a later wave (plan §8, wave 7,
POSTGRESQL-RETIREMENT-01) and gated on parity/migration acceptance:

- Pages: `pages/plant_detail.py`, `pages/transformer_detail.py`,
  `pages/device_dashboard.py`, `pages/device_admin.py`, `pages/device_register.py`,
  `pages/technician_devices.py`, `pages/admin_assignments.py`.
- Components: `components/equipment_selector.py` (Asset Navigator, now
  always-hidden), `components/device_alarms.py`, `components/metric_chart.py`,
  `components/metric_workspace.py`, `components/metric_health.py`,
  `components/status_colors.py`, `components/entity_context.py`,
  `components/entity_table.py`, `components/readings_table.py`,
  `components/device_manage_drawer.py`, `components/device_operations.py`,
  `components/assign_device_drawer.py`, `components/programming_activity.py`,
  and other device/metric render helpers.
- Callbacks: `callbacks/listings.py`, `callbacks/device.py`,
  `callbacks/equipment_selector.py`, `callbacks/device_admin.py`,
  `callbacks/device_register.py`, `callbacks/device_assign.py`,
  `callbacks/device_manage.py`, `callbacks/technician_devices.py`,
  `callbacks/admin_assignments.py`, `callbacks/programming_activity.py` — still
  registered in `app.py` and inert (their inputs never fire on a real page;
  `suppress_callback_exceptions=True`).
- Services/repositories: as listed in §6.
- The `REGISTER_DEVICE`, `MANAGE_DEVICES`, `VIEW_OWN_DEVICES`,
  `MANAGE_ASSIGNMENT` capability/action-policy entries in
  `services/authorization.py` are retained because the isolated callbacks above
  still check them — removing them would leave that isolated code ungated.

## 8. Synthetic metric / status exposure removed

- The **synthetic status colour system** (Online / Offline / Healthy / Needs
  Attention / synthetic Active) is not present on any active production surface.
  `components/status_colors.py` is retained only because the isolated device
  cluster uses it; the real fleet page is guarded to show no status key
  (`tests/test_status_colors.py::test_the_real_fleet_overview_uses_no_status_colours_so_shows_no_key`).
- The **eight-metric UI** (voltage, current, active/reactive power, power factor,
  frequency, energy) lives only on the now-retired synthetic device dashboard.
  Temperature remains the sole metric on active production surfaces (real RTL
  detail, dashboard). No fake replacement data was introduced.
- **Synthetic Needs Attention** was the synthetic Command Center, now deleted.
  `/events` (Historical Events) remains factual history only; no active-alarm
  workflow was introduced.
- Source scan of every active production page/component module found **no**
  visible `Plant`/`Plants`/`Asset Navigator`/`Needs Attention` string; guard
  tests (`tests/test_client_terminology.py`) confirm no synthetic hierarchy or
  Online/Offline/Healthy wording on the fleet page, navigation or status panels.

## 9. Reports / Settings remaining debt

- **Reports** (`/reports`, `report_center`): NOT realigned in this gate (§17).
  Its navigation entry is retained. Whether any report tab still exposes
  synthetic/unsupported client data is **next-gate debt** (a dedicated Reports
  realignment gate). No report was hidden or redesigned here.
- **Settings / programming** (`/admin/settings`, programming drawers): retained
  and isolated (§18); it is the subject of a later forensic/implementation gate
  and exposes no false client data on the active settings page.

## 10. Database objects deliberately retained

- **SQL Server**: READ_ONLY, untouched. No schema change, no write.
- **PostgreSQL**: no table dropped, no migration added, no data change. The
  synthetic `plant_monitoring.*` tables, `user_device_assignments`, the
  synthetic device/registration/assignment/simulator state and all
  application-owned auth/assignment/audit tables remain in place. This gate
  touches no database object (§21).

## 11. Browser acceptance

See `BROWSER_ACCEPTANCE.md` in this directory.

## 12. Next cleanup / development dependencies

- **POSTGRESQL-RETIREMENT-01** (plan wave 7): delete the isolated synthetic
  cluster listed in §7 (pages, components, callbacks, services, and their
  tests), remove their callback registrations from `app.py`, and drop the
  synthetic `plant_monitoring.*` schema — only after parity/migration
  acceptance.
- **Reports realignment gate**: audit and realign `report_center` to
  real-source, UID-scoped reports (§9 debt).
- **Program RTL / Settings gate**: the isolated programming/settings area
  (§18).
</content>
