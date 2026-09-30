# LEGACY-SYNTHETIC-UX-CLEANUP-01 — Browser acceptance

Environment: local `python app.py` on `http://localhost:8050` (DASH_DEBUG on),
both databases healthy (`plant_monitoring_postgres`, `client_rtl_sqlserver`).
Demo login enabled (`AUTH_DEMO_LOGIN_ENABLED=true`, non-production). Normal
viewport. Date: 2026-09-30.

Result: **PASS.** No synthetic Plant/Device/Command Center/Needs Attention UX
appears in any role's normal navigation; every legacy synthetic route is
answered by the "This view has been retired" panel; the real client-RTL product
is intact. No new console errors (the single dev-mode React
"controlled/uncontrolled input" warning on the login field is pre-existing and
unrelated to this gate; debug mode is on).

## Administrator (`admin`)

- Login → lands on the **factual Dashboard** (`/command-center` route renders
  the client-RTL dashboard, not the synthetic Command Center): Registered RTLs
  339, Mapped 185, Unmapped 154, Temperature data available 319, No temperature
  data 20, network hierarchy counts, RTLs by zone, "Most recent reading on
  record: 17 Sep 2026 SAST". `acc-01-administrator-dashboard.jpg`.
- Sidebar: Registered RTLs, Network, Historical Events, Dashboard | Technician
  Assignments | Notifications, Reports, Users, Audit Log, Settings. **No
  "Devices" or "Registration" item; no Asset Navigator** (the blue bottom-right
  control is Dash's debug toggle, debug mode on).
- Registered RTLs (`/rtls`): real client data — RTL UID, latest temperature
  (°C), last reading (SAST), transformer mapping, zone/sector/CNC/feeder;
  temperature-only, no synthetic status/metrics. `acc-03-administrator-registered-rtls.jpg`.
- Legacy routes:
  - `/plants` → **HTTP 302 → `/rtls`** (verified; query string preserved:
    `/plants?filter=mapped` → `/rtls?filter=mapped`).
  - `/plants/plant-01` → **legacy retired panel**. `acc-02-administrator-legacy-plant-retired.jpg`.
  - `/devices/plant-01-t1-d1` → **legacy retired panel**.
  - `/admin/devices` → **legacy retired panel**.
- No authorization regression; no broken navigation; no new console errors.

## General User (`demo.general01`)

- Login → lands on **Registered RTLs** (`/rtls`) with real client data.
- Sidebar: Registered RTLs, Network, Historical Events | Reports. **No
  Dashboard, no Technician Assignments, no Notifications, no Users/Audit
  Log/Settings, no Devices/Registration.** (Matches `visible_nav_keys(GENERAL)`
  = overview, network, events, reports.)
- No synthetic Plant UX anywhere.

## Technician (`demo.tech01`, activated demo account, no assignments)

- Login → lands on the **factual Dashboard** (assignment-scoped). Content:
  "The RTLs assigned to you, their current network mapping and the temperature
  data on record. No RTLs are assigned to you yet. An Administrator assigns RTLs
  to Technicians." (demo.tech01 has no assignments, so the empty-assignment
  state is correct — ADR-032.)
- Sidebar: **Assigned RTLs** (the ADR-032 relabel of the overview item),
  Network, Historical Events, Dashboard | Notifications, Reports. **No synthetic
  Command Center, no Needs Attention, no Devices, no admin surfaces.**
- `/devices/plant-01-t1-d1` → **legacy retired panel** (role-independent
  retirement). `acc-04-technician-legacy-device-retired.jpg`.

## Notes

- The legacy-route retirement is role-independent (the `legacy_retired` route is
  absent from the policy and renders a static panel), verified live for both
  Administrator and Technician.
- The Technician's factual landing, assignment scope and absence of synthetic
  UX are additionally pinned by the green test suite
  (`tests/test_factual_dashboard.py`, `tests/test_rtl_scope.py`,
  `tests/test_authorization.py`, `tests/test_rtl_assignments_ui.py::TestLegacyCommandCenterUnreachable`).
</content>
