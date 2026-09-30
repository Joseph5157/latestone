# TECHNICIAN-REAL-RTL-ACCESS-01 — acceptance evidence

Date: 2026-09-30. Baseline `274020e`. Browser: Chrome (DevTools MCP), 929 px
viewport, three isolated sessions. Local restored client SQL Server + local
Docker PostgreSQL.

## SQL Server integrity

`sqlserver_before.txt` / `sqlserver_after.txt`: `READ_ONLY`, write permissions 0,
`master_temperature` 2,456,901; `device_list` 339; `techmician_device_list` 68;
`technician_assignments` 0; `persons` 8; `settings_upload_log` 3,400 — identical
before and after the migration, bootstrap and browser session.

## Legacy bootstrap (application store only)

- `bootstrap_preview.txt`: 64 candidates, 4 excluded (29024, 29046, 29071,
  29544), 5 Technician persons needing an application user, 0 blocking problems.
- `bootstrap_apply.txt`: imported 64, provisioned 5 login-less users.
- `bootstrap_rerun.txt`: 0 candidates, 64 already present. `--apply` again: imported 0.
- Application store: 64 open `LEGACY_IMPORT` rows, no assigned date/actor.

## Administrator (admin)

`/technicians/assignments`: Registered 339 / Assigned 64 / Unassigned 275
(computed live). Assigned RTL 29006 to Demo Technician 01 (Unassigned 274,
row left the pool), reassigned to Demo Technician 02, History showed both rows
(old ended, new current, assigned by admin). `admin_assign_panel.png`,
`admin_history_after_reassign.png`.

## Technician (demo.tech01, holding 29007 and 29807)

- Landing: factual Dashboard (Assigned RTLs, temperature data, mapping,
  links); nav Assigned RTLs / Network / Historical Events / Dashboard (+
  Notifications, Reports). `technician_dashboard.png`.
- `/rtls` "Assigned RTLs": exactly 29007 and 29807.
- `/rtls/29007` opens; `/rtls/29006` (another Technician's) and `/rtls/29008`
  (unassigned): "No access". `/technicians/assignments`: "No access".
- Network: 1 registered in view (only 29007 at that time), no other rows.
- Historical Events (after assigning 29807, which has 313 alarms): only UID 29807
  rows. `technician_events.png`.

## General User (demo.general01)

Unchanged: Registered RTLs 339, nav Registered RTLs / Network / Historical
Events / Reports, no Technician Assignments item.

## Cleanup

The three acceptance assignments (29006, 29007, 29807) were ended through the
service afterward (history and audit retained). The application store's current
state is the 64 imported assignments.
