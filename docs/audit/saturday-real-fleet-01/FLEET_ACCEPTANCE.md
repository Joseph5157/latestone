# SATURDAY-REAL-FLEET-01 — Real Fleet Overview acceptance

Date: 2026-09-30 · Baseline `d0ff59e` · Viewport 1366×900 · Local app against the
restored client `RTL` SQL Server (`rtl_app_reader`, SELECT only).

## What the page shows

`/plants` (route unchanged) lists the registered client RTL directory:

| Source | Used for |
|---|---|
| `dbo.device_list` | the population (one row per registered UID) |
| `dbo.master_temperature` | latest temperature + last-reading time (one batched set-based read) |
| `dbo.trfr_list` | raw transformer mapping |
| `dbo.vw_transformer_org_hierarchy` | Zone / Sector / CNC / Feeder, exact transformer-code match only |

Not used: `vw_installed_rtls`, `device_status`, `comms_alarm`, PostgreSQL, any
synthetic value. No Online/Offline verdict and none of the seven electrical
metrics. Source times are naive SAST values shown unconverted.

## Observed (live, as General User `demo.general01`)

| Fact | Value | Knowledge base |
|---|---:|---|
| Registered RTLs (rows rendered) | 339 | 339 |
| Current transformer mappings | 185 | 185 |
| With temperature data | 319 | 319 |
| No temperature data | 20 | 20 |
| No current transformer mapping | 154 | 154 |
| Mapped RTLs with hierarchy unavailable | 7 (service) | 7 |
| Ambiguous latest temperatures | 0 | 0 in current snapshot |

Fleet load time: ~0.4 s (4 SELECT round trips; latest read batched).

## Visual checks

Evidence: `fleet-1366-general.png`, `fleet-1366-mapped-rows.png`,
`fleet-1366-no-temperature.png`, `fleet-1366-technician-restricted.png`.

- Summary cards use factual wording; a note states 339 is not an active/online count.
- RTLs without telemetry read "No temperature data" (filter shows exactly 20, none mapped).
- Unmapped RTLs stay visible with "No current transformer mapping" and "—" location.
- A mapped RTL shows its transformer and "Zone · Sector · CNC / Feeder" (e.g. UID 29042).
- Page text contains no "plant" (only "online" inside the negating scope note),
  no electrical metric names, no null/undefined text, console 0 errors.
- The shell's Plant/Transformer/Device Asset Navigator is hidden on this route
  (it walks the synthetic PostgreSQL model); `callbacks/navigation.py`
  `UTILITY_ROUTES` no longer lists `overview`.

## Authorization

| Persona | Result |
|---|---|
| General User (unrestricted scope) | full registered fleet |
| Administrator (unrestricted scope) | full registered fleet (same policy; covered by unit tests) |
| Technician (`demo.tech01`) | explicit "Client RTL fleet not available for your account"; RTL source not read; no UID rendered |
| No session / unknown role | EMPTY scope → same restricted panel (unit tested) |

Rationale: there is no approved raw-client-UID-to-technician-assignment map
(`technician_assignments` is empty), so nothing is widened.

## Safety verification

- Database `RTL` `Updateability = READ_ONLY`; for `rtl_app_reader`
  `HAS_PERMS_BY_NAME` UPDATE/INSERT/DELETE on `dbo.device_list` and ALTER on the
  database are all 0.
- Counts unchanged: `master_temperature` 2,456,901 · telemetry UIDs 400 ·
  `device_list` 339 · `trfr_list` 185.
- No PostgreSQL schema, Alembic or seed change.

## Deferred (not in this gate)

Operational-evidence classification (111 in 2026), Online/Offline, lifecycle,
technician-scoped RTL visibility, linking rows to a device page.
