# CLIENT-APP-REALIGNMENT-PLAN-01 — Client application realignment

Status: planning/audit only
Baseline: `ce5deac`
Authority: ADR-029 and `docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md`

## 1. Executive summary

The application is a mature PostgreSQL-backed synthetic Plant → Transformer →
Device dashboard with one completed SQL Server read slice: the registered RTL
Fleet at `/plants`.  Continuing to replace individual panels would leave a
mixed product: one real client list beside synthetic drill-down, metrics,
scope, reports, and administration.  The target is an RTL Monitoring product
whose client-facing hierarchy is **Operating Unit → Zone → Sector → CNC →
Feeder → Transformer → RTL**.  SQL Server remains read-only. PostgreSQL is
transitional until each application-owned capability has an approved SQL Server
target and a safe migration.

Facts, not policy: 339 registered RTLs come from `device_list`; 185 have a
current `trfr_list` mapping; temperature is the sole confirmed continuous
telemetry; and `master_temperature` supplies latest/history. Registered is not
active, lifecycle is unknown, and Online/Offline is not presently displayable.

## 2. Current application inventory

| Area / route | Current visible purpose and source | Hierarchy / access | Classification |
|---|---|---|---|
| `/plants` Fleet Overview | Registered RTL list; SQL Server `device_list`, `master_temperature`, `trfr_list`, hierarchy view | RTL facts; Administrator/General unrestricted; Technician restricted | **ADAPT** |
| `/plants/<plant>` and `/plants/<plant>/<transformer>` | Synthetic plant/transformer detail, temperature roll-ups | PostgreSQL 30/71/120; all roles subject to `DeviceScope` | **REPLACE** |
| `/devices/<app-device-id>` | Eight-metric device dashboard, chart, readings, alarms, operations | Synthetic app device ID and Plant hierarchy; PostgreSQL | **REPLACE** |
| `/` and `/command-center` | Ranked attention, fleet cards/charts, actions | PostgreSQL readings/events; Admin/Technician | **REPLACE** |
| `/reports` | Installed RTLs, 30-day alarms, max temperature, export | PostgreSQL report service and synthetic hierarchy | **ADAPT** |
| `/admin/devices`, `/admin/devices/new` | Device directory, registration, management/deactivation | PostgreSQL synthetic devices; Administrator | **REPLACE** |
| `/devices` | Technician assigned-device roster and operations | PostgreSQL app-device assignment | **BLOCKED BY CLIENT DECISION** |
| `/admin/assignments` | Technician workload/assignment management | PostgreSQL app-device assignment; Administrator | **BLOCKED BY CLIENT DECISION** |
| `/admin/users` | Local users/roles | PostgreSQL identity; Administrator | **ADAPT** |
| `/admin/settings` | Freshness/temperature/vibration configuration | PostgreSQL application-owned state | **ADAPT** |
| `/notifications` | In-app notification center / forwarding settings | PostgreSQL application state | **BLOCKED BY CLIENT DECISION** |
| Audit Log | Local mutation audit | PostgreSQL application audit | **KEEP** |
| Programming drawers/activity | Simulated/request lifecycle and history | PostgreSQL app devices and simulator | **BLOCKED BY CLIENT DECISION** |
| `fleet_overview_service`, `components/fleet_overview.py` | Old synthetic Fleet presentation | Unrouted production legacy path | **RETIRE** |

Supporting implementation remains predominantly synthetic: `hierarchy_service`,
`monitoring_service`, `temperature_condition_service`, `attention_service`,
`report_service`, `plant_monitoring_repository`, metric charts/workspace, and
device/assignment/registration services. SQL Server paths are deliberately
narrow: `rtl_temperature_repository`, `rtl_source_facts_service`,
`rtl_fleet_service`, and the temporary `rtl_uid` device-dashboard slice.

## 3. Mismatches and terminology audit

**Client-facing terms that must change in a real-data screen:** Plant/Plants,
Device/Devices when they mean a client RTL, Asset Navigator, synthetic
Active/Inactive, current Status where it implies lifecycle, freshness shown as
communication state, and any Online/Offline/Healthy wording. The current
Fleet correctly avoids these.

**Acceptable technical/internal use:** `plant_id`, `device_id`, database schema
names, legacy URL parsing, test fixtures, migration history, and the existing
synthetic model during transition. Do not mechanically rename these.

**Business-ambiguous language:** active, installed, mapped, operational,
status, healthy, attention, alarm, lifecycle, offline, and “last data”. Use
only factual qualified wording until the relevant CDB decision is answered.

The sidebar currently labels real Fleet as “Overview”, retains “Devices”, and
routes operators into Plant/device-derived screens. Reports expose Plant and
Device scopes. The device page exposes eight metrics and calls an RTL a
“device”. These are production terminology leaks, not merely cosmetic labels.

## 4. Target information architecture

| Destination | Target name | Timing | Notes |
|---|---|---|---|
| Dashboard | Dashboard | LATER | factual registered/mapping/temperature/event summaries only |
| RTL Fleet | Registered RTLs | NOW | existing real Fleet, renamed in a terminology gate |
| RTL detail | RTL details / Temperature history | LATER | UID route; temperature only initially |
| Network | Network hierarchy | LATER | OU through Transformer, using reference hierarchy caveat pending CDB-03 |
| Attention | Historical events | LATER | occurred events, not unresolved alarms |
| Technicians | Technicians and RTL assignments | CLIENT-DECISION BLOCKED | CDB-04/05 |
| Reports | Reports | LATER | real-source reports only, scoped by UID/network |
| Administration | Administration | LATER | users/roles, lifecycle, thresholds, notifications, programming split by decision |

“Needs Attention” is appropriate only after CDB-08 defines an actionable
lifecycle; before then call the page **Historical events**.

## 5. Route and RTL identity strategy

Use a future canonical UID route: `/rtls/<uid>`; list at `/rtls`; network at
`/network` with hierarchy paths keyed by stable source/reference identifiers.
`/plants` should redirect compatibly to `/rtls` after the new route is live.
Legacy `/plants/<plant>` and `/devices/<app-device-id>` should remain temporary
compatibility routes only while synthetic data is still intentionally available;
then redirect if an approved, auditable mapping exists, otherwise retire with a
clear not-available response. Never manufacture a redirect from
`?rtl_uid=`.

The client RTL UID is the sole list/detail/callback/audit/command identity for
real fleet work. It must be strictly numeric and source-provenanced.
Technician authorization must be an application-owned UID assignment relation,
not a join guessed from synthetic `device_id`; audit and command references use
that UID plus immutable application request/audit IDs. Retire the assumptions
that a synthetic device ID has a corresponding client UID, belongs to a Plant,
or represents an active logger.

## 6. Feature and data-source migration matrix

| Capability | Current → target | Action / decision |
|---|---|---|
| Fleet population | PostgreSQL devices → SQL `device_list` | Reuse; complete |
| Latest temperature / history | synthetic readings → `master_temperature` | Reuse latest; add UID-bounded history |
| Transformer mapping / hierarchy | synthetic tables → `trfr_list` + hierarchy view | Adapt; CDB-03 caveat |
| Network navigation | Plant hierarchy → client OU…Transformer reference | Replace |
| Event history | synthetic events → `alarm_log`, sensor/startup/powerdown logs | Adapt; CDB-08 |
| Communication evidence | synthetic freshness → source Check-in facts | Blocked by CDB-02 for state |
| Programming history | app requests → `settings_upload_log` plus app lifecycle | Adapt/blocked CDB-06 |
| Users / roles | PostgreSQL demo users → application auth plus SQL `persons`/roles candidate | Adapt; CDB-04 |
| Technician assignments | app-device assignment → application-owned RTL UID assignments, possibly adapt SQL table | Blocked CDB-05 |
| Notifications / thresholds / acknowledgement / audit / commands | PostgreSQL state → application-owned SQL Server target later | New capability; CDB-07/08/06 as applicable |
| Seven electrical metrics | synthetic readings → no verified target source | Retire; CDB-11 |

## 7. Authorization, dashboard, events, programming, reporting

Administrator and General User can safely read the registered Fleet. Technician
Fleet visibility remains restricted until a UID assignment model is approved;
no raw UID mapping may be inferred. Existing all-role synthetic drill-down is
therefore transitional, not product authorization.

The target dashboard has only registered population, mappings, temperature
availability/latest factual temperature, explicit ambiguity/no-data, and
historical event summaries with source/date. It excludes seven metrics,
synthetic plant health, lifecycle state, communication state, and unresolved
alarm counts.

Current Command Center/attention and device alarm UX are **REPLACE/ADAPT**:
high temperature, sensor error, battery and powerdown can be historical event
views, but no event is an unresolved alarm. Acknowledgement, resolution,
comments and escalation are blocked by CDB-08.

Program RTL remains **BLOCKED**: SQL history proves past transformer-code and
interval configuration, not delivery, result or approved transport. Retain no
live transmission claim. Reports can next support registered RTL directory,
temperature history/maxima, historical events, settings history and reference
hierarchy exports; retire synthetic metric/freshness reports.

## 8. PostgreSQL retirement and legacy cleanup

PostgreSQL already replaced for Fleet population/latest temperature/mapping
summary only. It remains temporary for current identity, auth, scope,
synthetic hierarchy/readings/events, reports, configuration, audit and command
simulation. These last application-owned records require a separately approved
SQL Server target and migration plan; they are not client records by default.

Retirement order: (1) real terminology/navigation and UID identity; (2) real
RTL detail/history and network; (3) real reports/events; (4) approved
application-owned auth/assignment/lifecycle/event workflow; (5) migrate and
validate state; (6) retire synthetic routes/services/data; (7) remove
PostgreSQL only after production parity acceptance. No big-bang deletion.

Cleanup candidates: `services/fleet_overview_service.py` and
`components/fleet_overview.py` are currently unrouted and may be removed after
the real navigation/route transition is accepted. Then assess synthetic
plant/detail/listing/metric/report services only after their replacements and
bookmark policy are accepted. Nothing is deleted by this gate.

## 9. Client-decision map

| Decision | Affected work | Partial work possible? |
|---|---|---|
| CDB-01 lifecycle | fleet labels, admin lifecycle | factual registered/mapped views |
| CDB-02 communication | dashboard/attention status | source Check-in history only |
| CDB-03 TUG authority | network/transformer identity | reference hierarchy with caveat |
| CDB-04 auth | production login/users | UI/route preparation only |
| CDB-05 assignments | technician fleet/actions | Admin/General factual Fleet |
| CDB-06 programming | command UI/execution | historical settings display |
| CDB-07 notifications | recipients/delivery | no behavior beyond local temporary UI |
| CDB-08 alarm workflow | Needs Attention/acknowledgement | historical event display |
| CDB-09 conflicts | RTL detail temperature display | preserve ambiguity |
| CDB-10 unusual values | temperature presentation | show raw values |
| CDB-11 metrics | device/dashboard/report metrics | temperature-only target |

## 10. Ordered implementation waves

1. **CLIENT-TERMINOLOGY-NAV-01** — rename Fleet/navigation/product wording and
hide synthetic navigation from real paths; LOW; no client decision; browser and
route tests.
2. **RTL-UID-DETAIL-01** — `/rtls/<uid>` temperature-only detail/history and
UID authorization boundary; MEDIUM; CDB-09/10 guardrails; SQL read tests.
3. **RTL-NETWORK-01** — reference OU→Transformer navigation; MEDIUM; CDB-03;
exact-match/caveat acceptance.
4. **RTL-DASHBOARD-01** — factual dashboard replacement; MEDIUM; CDB-01/02
limits; no synthetic metrics.
5. **RTL-HISTORICAL-EVENTS-01** — historical event views/reports; MEDIUM;
CDB-08; no unresolved semantics.
6. **RTL-ASSIGNMENT-01**, **RTL-LIFECYCLE-01**, **RTL-PROGRAMMING-01**,
**RTL-NOTIFICATION-01** — HIGH and individually gated by CDB-05, 01, 06, 07.
7. **POSTGRESQL-RETIREMENT-01** — HIGH; only after parity/migration acceptance.

## 11. Next gate specification

**Nominee: CLIENT-TERMINOLOGY-NAV-01.** Scope: rename routed real-Fleet UI
from Overview/Plant/Device wording to Registered RTLs/RTL where factual;
make sidebar and breadcrumbs reflect the real Fleet; remove/hide the synthetic
Asset Navigator from every real-RTL route; retain legacy routes and internal
identifiers unchanged; do not add a new detail route, database query, role
rule, migration, or SQL Server write. Likely areas: `routes.py`, sidebar,
Fleet page/components/callbacks, headers/breadcrumbs, navigation tests and
route render tests. Validate with context pack, non-DB tests, and browser
checks for Administrator, General User and Technician. Risk: LOW.

## 12. Risks and guardrails

Read SQL Server only; never equate registration with lifecycle/health; bind
UIDs and exact hierarchy identifiers; no fallback to synthetic data on a real
path; preserve raw source values and ambiguity; do not expose contacts or
credentials; do not broaden Technician visibility; stage compatibility
redirects only after the canonical UID route exists; and keep every decision-
blocked capability visibly factual or absent.
