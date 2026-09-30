# FACTUAL-DASHBOARD-01 — acceptance

Date: 2026-09-30 · Baseline `1961908` · Viewport 1366×900 · local app, restored client `RTL` SQL Server (SELECT only). Raw log: `acceptance-run.log`; console: `console-errors.log`.

## Behaviour

- **Administrator** — `/command-center` (and the bare root, and `/login` after sign-in) renders **Dashboard**: five cards, a Network section, a Temperature data section. Nothing from the synthetic Command Center is rendered or fetched (0 attention slots in the page; the legacy callbacks' outputs are absent, so they do not fire).
- **General User** — landing is unchanged (`/rtls`), which is already the factual directory plus the "Network coverage" line. `/command-center` is still "No access" (unchanged policy).
- **Technician** — unchanged: Command Center as before (synthetic, technician-scoped); `/rtls`, `/rtls/network`, `/rtls/29042` are "No access"; no factual dashboard, no raw counts, no zone/network text. Their sidebar still carries the pre-existing Registered RTLs link, which lands on "No access".

## Observed values (Administrator, live)

| Block | Values |
|---|---|
| Cards | Registered 339 · Mapped 185 · Unmapped 154 · Temperature data 319 · No temperature data 20 |
| Network | Hierarchy resolved 178 · unavailable 7 · Mapping review 2 · by zone: Empangeni 16, Pietermaritzburg 162 |
| Temperature | 319 / 20 · most recent reading on record 17 Sep 2026 08:29 SAST |
| Links | only `/rtls` and `/rtls/network`; both followed successfully |

All match the reference values; none is hard-coded (tests vary the fixture and the numbers follow).

Forbidden-word scan (Plant, Online, Offline, Healthy, Inactive, Active, Voltage, Frequency, Power factor, Energy, Needs Attention, Asset Navigator, undefined, NaN, null, None): no hits on the dashboard or `/rtls`.

Console: the only entry per role is React's "uncontrolled input" warning emitted by the **login page** before sign-in (reproduced with a bare login; not from this gate). No error on any dashboard page.

## Composition and reads

`services/rtl_dashboard_service.get_dashboard` = one `get_real_fleet` (4 reads) + one `get_current_network` (6 reads), once per page load, no polling, no N+1. Three of the ten reads (directory, mappings, hierarchy) overlap. That is accepted at this size (~1 s) rather than duplicating either service's rules; a shared-snapshot refactor is listed as debt. Either source failing shows an "unavailable" notice, never zeros.

## Legacy dashboard debt (nothing deleted in this gate)

| Module | Still reachable? | Referenced by | Suggested cleanup |
|---|---|---|---|
| `pages/command_center.py`, `callbacks/command_center.py`, `components/command_center/*` | **Yes — Technician landing** | app, tests, docs | after technician assignment (TECH-ASSIGN gate) |
| `services/attention_service.py`, fleet glance/hottest/trend/activity blocks | Yes, via the above | tests | with the row above |
| `pages/plants_overview.py` synthetic plant lists, `/plants/<id>`, `/devices/...` | Yes (routes) | tests, sidebar for some roles | PostgreSQL retirement / legacy-route gate |
| `components/rtl_fleet.rtl_summary_panel`, `callbacks/rtl_summary.py` | **Removed** (superseded by this dashboard) | — | — |

## SQL Server

`Updateability = READ_ONLY`; write permissions 0; `master_temperature` 2,456,901 · distinct telemetry UIDs 400 · `device_list` 339 · `trfr_list` 185 — unchanged. PostgreSQL untouched.
