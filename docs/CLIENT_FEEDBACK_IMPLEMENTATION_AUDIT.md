# Client Feedback Implementation Audit

Date: 2026-09-17

Baseline: `main` at `2d9616d`

Gate: `CLIENT-FEEDBACK-AUDIT-1` (documentation-only)

## Executive Summary

This audit covers all 10 requested feedback themes and decomposes them into 29
individually classified findings. The application has substantial operational
functionality already: Fleet Condition and a ranked RTL exception queue exist on
Fleet Overview; Command Center has affected-location, selected-location,
priority-RTL and recent-event drill-downs; Notification Center combines a real
persisted event stream with a derived BR008 projection; Reports support fleet,
Plant, Transformer and Device scopes; and all of these paths preserve the
Technician's assigned-device boundary.

The meeting expectation is not, however, fully represented by the current
entry experience. `/` and `/plants` resolve to Fleet Overview, not Command
Center, and the sidebar presents Overview before Command Center
(`routes.py:84-99`, `components/app_sidebar.py:61-65`). Fleet Overview itself
already places Fleet Condition and RTLs Requiring Attention ahead of the Plant
table (`pages/plants_overview.py:18-88`), so the gap is primarily route and
navigation emphasis rather than absence of operational content.

The material code/feedback conflicts are:

1. **Entry hierarchy:** Fleet Overview remains the landing route even though
   the meeting asked for the condition/attention view first.
2. **Terminology:** `Plant` is structural across routes, schema, repository,
   UI, seed data and tests, while the Functional Specification requires report
   taxonomy fields including Feeder/Feeder Name and the meeting prefers Feeder
   or Network Name.
3. **Generation metadata:** Fuel and Capacity remain visible on Fleet Overview
   and Plant detail and are backed by power-station seed data.
4. **Condition drill-down:** Power Down and Battery Low condition blocks are
   intentionally non-clickable and cannot produce current affected-device
   lists because current condition closure/state is not modelled.
5. **No Data weighting:** No Data is a primary Command Center communication
   card and the first rank in Priority Investigation, contrary to the meeting's
   preference that it not be a primary operational condition.
6. **Report scope wording:** the selector offers Plant rather than Feeder even
   though report columns already reserve Feeder/Feeder Name.

No runtime code, tracker status, threshold or data model is changed by this
audit.

## Evidence Rules

The `Remote Temperature Logger Functional Specification RTL v0.3` identified
in `docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md:4` is the sole formal RTL
requirements authority. The tracker records BR008 as an exact `>24h` no-data
rule and BR009 as the Battery Alarm/Comms Alarm client-facing split
(`docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md:77-80`). It also records
OU/Zone/Sector/CNC/Feeder/Feeder Name as required but currently unmapped report
taxonomy (`docs/RTL_FUNCTIONAL_SPEC_COMPLETION_TRACKER.md:122-125,163`).

The Review Client Videos meeting is supplementary feedback and decision
evidence. An explicit meeting request is not silently promoted into a
Functional Specification requirement. A question or observation is not treated
as approval to alter semantics. Internal proposals remain labelled as such.
Older PADs and archived material were not used as requirements evidence.

Implementation claims below are based on current code and tests. “UI ONLY”
means a label or visual exists without the corresponding state/query behavior;
it does not mean a frontend is fake. “CONFLICTS WITH CLIENT FEEDBACK” means the
current behavior materially differs from the stated meeting preference, not
that it violates the Functional Specification.

## Feedback Matrix

| ID | Meeting Feedback | Evidence Type | Current Implementation | Status | Files / Components | Risk | Recommended Next Action | Needs Client Confirmation? |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Fleet Condition / RTLs Requiring Attention should be the immediate operational view | EXPLICIT CLIENT MEETING REQUEST | `/` and `/plants` resolve to Fleet Overview; Command Center is separate at `/command-center` | CONFLICTS WITH CLIENT FEEDBACK | `routes.py:84-105`; `callbacks/routing.py:166-168,299-312`; `components/app_sidebar.py:61-65` | High: operators do not land in the requested workflow; General Users cannot access Command Center | Confirm which role-specific page is meant, then change default route/navigation in a focused gate | Yes |
| 1.2 | Fleet Overview should support investigation | EXPLICIT CLIENT MEETING REQUEST | Fleet Overview contains Fleet Condition, fresh coverage, data freshness, a grouped attention queue and Plant table drill-downs | ALREADY IMPLEMENTED | `pages/plants_overview.py:18-88`; `callbacks/listings.py:780-830`; `components/needs_attention.py:53-110` | Low | Retain; avoid duplicating these panels in a redesign | No |
| 1.3 | Operational view must be functional, not merely visual | CLIENT QUESTION / OBSERVATION | Overview panels are callback-populated from one scoped freshness chain; the queue and tables link into hierarchy/device routes | ALREADY IMPLEMENTED | `callbacks/listings.py:780-830,995-1000`; `services/monitoring_service.py:376-490`; `tests/test_fleet_overview.py:242-318` | Low | Preserve the shared query and structural tests | No |
| 2.1 | Reconsider the roughly 90-minute freshness threshold for hourly/6-hourly/daily RTLs | CLIENT QUESTION / OBSERVATION | RESOLVED (CLIENT-FEEDBACK-FRESHNESS-1): global default replaced with a single configurable `FRESHNESS_STALE_AFTER_MINUTES` threshold, defaulting to 1,440 minutes (24 hours) — the client-suggested interim baseline. Legacy `EXPECTED_INTERVAL_MINUTES`/`STALE_AFTER_INTERVALS` are explicitly ignored, never combined | ALREADY IMPLEMENTED (INTERIM POLICY) | `config/settings.py:409-462`; `services/monitoring_service.py:198-207`; `tests/test_freshness_policy.py` | Medium: interim policy, not a per-RTL cadence — see 2.3 | Treat 24 hours as the current baseline; revisit only when 2.3's per-RTL cadence source is answered | No for the interim 24-hour value itself; Yes still applies to 2.3's per-device cadence |
| 2.2 | Distinguish UI freshness from BR008 | FUNCTIONAL SPEC REQUIREMENT | Fresh/Stale now uses the 24-hour interim threshold; BR008 uses its own separate, unchanged strict `age > 24h` constant | ALREADY IMPLEMENTED | `services/notification_service.py:4-21,50-109`; `tests/test_notification_service.py:113-200,633-639` | Low if kept separate; high if merged | Preserve two independent concepts and name them explicitly in UI/copy | No |
| 2.3 | Support reporting interval per RTL if cadence varies | CLIENT QUESTION / OBSERVATION | Still no per-device reporting interval in schema, repository record or configuration; only one global setting exists (now 24h, previously 90 min) — CLIENT-FEEDBACK-FRESHNESS-1 deliberately did not add this | MISSING | `alembic/versions/001_baseline.py:44-114`; `repositories/plant_monitoring_repository.py:31-43`; `config/settings.py:409-462` | High: a global threshold still cannot truthfully classify mixed cadences | Ask whether cadence belongs to RTL, model, feeder, or integration source; then design migration/policy. The authoritative reporting-interval source remains client/integration dependent | Yes |
| 2.4 | Changing freshness must not alter >24h notification semantics | FUNCTIONAL SPEC REQUIREMENT | BR008 does not read `stale_after_minutes` and no longer even imports `services.monitoring_service`; CLIENT-FEEDBACK-FRESHNESS-1 changed the UI threshold value and confirmed BR008 was unaffected, with a regression test asserting the import boundary | ALREADY IMPLEMENTED | `services/notification_service.py:1-21,94-109`; `tests/test_notification_service.py:188-200,626-639` | High regression risk if future work reuses freshness | Add this invariant to any cadence gate acceptance criteria | No |
| 3.1 | Prefer Feeder Name / Network Name to Plant | EXPLICIT CLIENT MEETING REQUEST | Visible hierarchy, routes and internal entity model use Plant throughout | CONFLICTS WITH CLIENT FEEDBACK | `routes.py:84-118`; `pages/plants_overview.py:18-88`; `pages/plant_detail.py:12-69`; `repositories/plant_monitoring_repository.py:31-38` | High: a blind rename may misrepresent Plant as the formal Feeder field | Confirm whether current Plant rows are feeders, networks, or another level | Yes |
| 3.2 | Functional Specification taxonomy includes OU, Zone, Sector, CNC, Feeder/Feeder Name | FUNCTIONAL SPEC REQUIREMENT | Report headers exist, but values are deliberately `None` pending authoritative mapping | PARTIALLY IMPLEMENTED | `config/reports.py:25-90`; `callbacks/report_center.py:221-259`; tracker `:122-125,163` | High: presentation rename alone would not populate required taxonomy | Obtain production taxonomy mapping and implement it independently of cosmetic naming | Yes |
| 3.3 | Determine whether terminology can be presentation-only | INTERNAL DESIGN PROPOSAL | A label-only change is technically possible, but unsafe as a semantic assertion: schema/FKs/routes/API fields/tests remain Plant, and FS Feeder is a currently unmapped report field | NEEDS CLIENT CLARIFICATION | `alembic/versions/001_baseline.py:44-77`; `routes.py:70-118`; `callbacks/report_center.py:147-183` | High: conflates a current development grouping with an authoritative taxonomy level | Permit presentation-only aliasing only after client confirms Plant ≡ Feeder/Network for this application | Yes |
| 4.1 | Remove/question Fuel and Capacity | CLIENT QUESTION / OBSERVATION | Fuel and Capacity have been removed from Fleet Overview columns/row payloads and Plant detail context without replacement fields | ALREADY IMPLEMENTED | `pages/plants_overview.py`; `callbacks/listings.py`; `tests/test_fleet_overview.py`; `tests/test_plant_detail.py`; implementation `55e3eeb` | Low: generic generation metadata could be reintroduced by layout/callback drift | Preserve explicit absence tests and the layout/callback column-parity guard | No |
| 4.2 | Identify storage/dependencies for Fuel and Capacity | INTERNAL DESIGN PROPOSAL | Fields are persisted on `plants`, represented in `PlantRecord`, seeded for all 30 power stations and tested; no report/export column depends on them | ALREADY IMPLEMENTED | `alembic/versions/001_baseline.py:44-58`; `repositories/plant_monitoring_repository.py:31-38,227-256`; `db/seed_plant_monitoring.py:339-350`; `db/seed_data/plants.json`; `config/reports.py:25-90` | Medium migration churn if deleted prematurely | First hide presentation; defer schema/seed removal to a separate data-model decision | Yes for deletion; No for audit conclusion |
| 4.3 | Remove other generation-oriented terminology | CLIENT QUESTION / OBSERVATION | Browser title/login still say Power Plant Monitoring; seed names are real power stations; energy chart comments correctly distinguish consumption from generation | CONFLICTS WITH CLIENT FEEDBACK | `app.py:21`; `pages/login.py:93`; `db/seed_data/plants.json`; `components/metric_chart.py:149` | Medium: domain mismatch in visible branding and seed labels | Replace visible branding/seed presentation only after the product name and feeder/network vocabulary are confirmed | Yes |
| 5.1 | Click Power Down / Battery Low conditions to see affected RTLs | EXPLICIT CLIENT MEETING REQUEST | Both condition surfaces are native buttons with keyboard activation, visible focus/hover and selected state; each populates a scoped list containing the latest matching persisted occurrence per RTL, explicitly not current-state status | ALREADY IMPLEMENTED | `components/command_center/electrical.py`; `components/command_center/condition_investigation.py`; `callbacks/command_center.py::select_condition`; `services/command_center_service.py::get_condition_affected_rtls`; `tests/test_command_center_condition_drilldown.py` | Low: the occurrence/current-state distinction must remain explicit | Preserve the existing event semantics and scope regression tests | No for occurrence drill-down; Yes only for a future current-state model |
| 5.2 | Drill into communication/no-data condition | EXPLICIT CLIENT MEETING REQUEST | Communication now carries an explicit “View affected RTLs” anchor to the existing freshness-only Priority Investigation list | ALREADY IMPLEMENTED | `components/command_center/situation_summary.py`; `components/command_center/priority.py` | Low | Preserve the single Priority Investigation implementation | No |
| 5.3 | Drill into Sensor Error | EXPLICIT CLIENT MEETING REQUEST | Sensor Error appears as persisted recent event/notification semantics and linked event rows, but not as a condition KPI or affected-current-state list | PARTIALLY IMPLEMENTED | `config/notifications.py:63-69`; `services/event_semantics.py`; `components/command_center/recent_events.py:111-184` | Medium: current vs historical meaning can be confused | Offer an event-history filter, labelled as events; do not imply present condition without closure rules | Yes for current-state interpretation |
| 5.4 | Drill from Requires/Needs Attention | EXPLICIT CLIENT MEETING REQUEST | Needs Attention now carries an explicit “View affected RTLs” anchor to the existing ranked Priority Investigation list; Stale + No Data semantics are unchanged | ALREADY IMPLEMENTED | `components/command_center/situation_summary.py`; `components/command_center/priority.py`; `components/command_center/affected_locations.py` | Low | Preserve the shared freshness snapshot and anchor target | No |
| 5.5 | Priority Locations / Selected Location should support investigation | EXPLICIT CLIENT MEETING REQUEST | Affected-location rows select a Plant via query string; Selected Location links to Plant and Transformer pages | ALREADY IMPLEMENTED | `components/command_center/affected_locations.py:64-90,175-227`; `components/command_center/selected_location.py:49-110`; `routes.py:239-260` | Low | Improve wording only if usability testing finds selection unclear | No |
| 5.6 | Recent Operational Events should drill into an RTL | EXPLICIT CLIENT MEETING REQUEST | Resolved device events have “Open asset” links and the panel links to Notification Center; unregistered/unresolved events correctly have no fake device route | ALREADY IMPLEMENTED | `components/command_center/recent_events.py:48,111-184`; `tests/test_command_center_recent_events_panel.py:125-155,207-213` | Low | Retain; optionally expose explicit event filters in Notification Center | No |
| 5.7 | Command Center drill-down behavior should be obvious and fully tested | CLIENT QUESTION / OBSERVATION | Condition buttons expose an action cue, active `aria-pressed` state and a labelled affected-RTL panel; focused tests cover filtering, switching, zero results, scope, semantics and RTL navigation, with Administrator/Technician browser evidence | ALREADY IMPLEMENTED | `assets/app.css`; `tests/test_command_center_condition_drilldown.py`; implementation `d543b1b` | Low | Preserve interaction and browser acceptance coverage | No |
| 6.1 | No Data should not be a primary operational condition | EXPLICIT CLIENT MEETING REQUEST | Communication now leads with complete metric coverage; Stale and No Data are explicitly labelled supporting freshness/investigation detail; the Priority headline no longer promotes No Data. No Data remains visible in Fleet Health and every matching Priority row | ALREADY IMPLEMENTED | `components/command_center/situation_summary.py`; `components/command_center/priority.py`; `assets/app.css`; implementation `40b755e` | Low: future styling must not hide the supporting state | Preserve the presentation hierarchy and semantic regression tests | No |
| 6.2 | Retain No Data as investigation/report/notification information | FUNCTIONAL SPEC REQUIREMENT | Freshness No Data remains a monitoring state; `>24h No Data` is a Notification Center rule; it is not a formal alarm report row | ALREADY IMPLEMENTED | `services/monitoring_service.py:32-45,249-264`; `services/notification_service.py:19-21,50-109`; `services/report_service.py:213-215,2583-2584` | High if removed globally | Keep state and BR008; adjust only placement/weighting | No |
| 7.1 | Notification Center should show latest actual notifications | EXPLICIT CLIENT MEETING REQUEST | It merges derived BR008 rows with real persisted `device_events`, newest first; it is not a persisted notification-delivery inbox | PARTIALLY IMPLEMENTED | `services/notification_service.py:139-192`; `callbacks/notifications.py:157-163`; `pages/notifications.py:45-68` | High ambiguity around “actual notification” (source event vs delivered message) | Ask whether client means device events, generated in-app notices, or SMS/email delivery receipts | Yes |
| 7.2 | Avoid placeholder/demo-only notification rows | CLIENT QUESTION / OBSERVATION | Main table is data-backed; page explicitly states derivation. No hard-coded notification rows are shown | ALREADY IMPLEMENTED | `pages/notifications.py:45-100`; `callbacks/notifications.py:151-173` | Low | Retain provenance copy; remove “prototype” language in a separate copy-only cleanup if still present | No |
| 7.3 | Preserve Battery Alarm / Comms Alarm semantics | FUNCTIONAL SPEC REQUIREMENT | Persisted battery_low maps to Battery Alarm; power_down and sensor_error map to Comms Alarm while underlying event types remain distinct | ALREADY IMPLEMENTED | tracker `:78-80`; `services/event_semantics.py`; `tests/test_event_semantics.py`; `tests/test_notification_service.py:373-418` | High regression risk | Preserve shared semantics for Notification Center and reports | No |
| 8.1 | Reports should support Entire Fleet, Feeder, Transformer, Device filtering | EXPLICIT CLIENT MEETING REQUEST | Actual selector supports Entire Fleet, Plant, Transformer and Device with cascading scoped options | CONFLICTS WITH CLIENT FEEDBACK | `pages/report_center.py:94-176`; `callbacks/report_center.py:684-742` | Medium terminology/semantic mismatch; function otherwise exists | Do not redesign filtering; resolve Plant↔Feeder semantics, then relabel or remap | Yes |
| 8.2 | Report functionality should remain correct | FUNCTIONAL SPEC REQUIREMENT | All three reports use the selected hierarchy scope and caller `DeviceScope`; required Feeder columns exist but values remain unmapped | PARTIALLY IMPLEMENTED | `callbacks/report_center.py:334-342,432-441,541-552,882-917`; `config/reports.py:25-90` | High if a terminology change bypasses scope or taxonomy mapping | Preserve query/scoping pipeline; make terminology a separate concern | No for preservation; Yes for mapping |
| 9.1 | Any changes must preserve Technician assigned-device restriction and operations | FUNCTIONAL SPEC REQUIREMENT | Technician scope is active-assignment based; reports, notifications, Command Center and device actions use it; Program RTL, forwarding, deactivation and alarm acknowledgement are assigned-device-only | ALREADY IMPLEMENTED | `services/device_scope.py:55-80`; `services/authorization.py:192-206`; `tests/test_technician_operations.py:104-217`; `tests/test_report_export_authorization.py:210-222`; `tests/test_alarm_acknowledgement.py:50-75` | Critical security boundary | Every implementation gate must include assigned/unassigned Technician regression tests | No |
| 10.1 | Use Mobbin only for UX reference opportunities | INTERNAL DESIGN PROPOSAL | No Mobbin research is needed to validate requirements; five bounded interaction-pattern candidates are identified below | PROPOSED IMPROVEMENT ONLY | This audit, “Mobbin Research Candidates” | Low if research remains non-authoritative | Research patterns only after behavior/semantics are decided | No |

## Detailed Findings

### Fleet Condition / Landing Experience

The current landing behavior is unambiguous: `parse_pathname()` maps an empty
path, `/`, `/plants` and `/plants/` to `overview` (`routes.py:84-90`), and the
router renders `plants_overview.layout()` (`callbacks/routing.py:166-168`). The
sidebar reinforces that hierarchy by listing Overview before Command Center
(`components/app_sidebar.py:61-65`). Tests freeze the behavior
(`tests/test_routing.py:10-17,33-34`; `tests/test_app_sidebar.py:105-122`).

The landing page is not merely an old inventory table. It begins with Fleet
Condition and attention content, then uses Fleet / Plants for investigation
(`pages/plants_overview.py:18-88`). The listing callback obtains one scoped
freshness graph and uses it for the summary, distribution, attention queue and
Plant rows (`callbacks/listings.py:780-830`). This means the meeting request is
partially present inside Fleet Overview but conflicts with the route-level
hierarchy if “immediate operational view” means Command Center.

A role decision is required before changing `/`: General Users may access the
monitoring hierarchy but Command Center is restricted to Administrator and
Technician (`services/authorization.py:60-74`). Redirecting every authenticated
role to `/command-center` would therefore create a forbidden landing page for a
valid General User. A safe implementation must define role-specific landing or
keep a universally accessible condition-first overview.

### Freshness / Stale Semantics

**Resolved by CLIENT-FEEDBACK-FRESHNESS-1.** The client's superior stated field
RTLs may report hourly, every 6 hours, or daily, so the previous ~90-minute
threshold could produce false stale conditions. The interim baseline is now a
24-hour global operational threshold. Per-RTL cadence-aware freshness remains
a separate, unresolved future design/integration item (see 2.3) — the
authoritative reporting-interval source is still client/integration dependent.

There remain two independent clocks:

- UI freshness now defaults to `FRESHNESS_STALE_AFTER_MINUTES=1440` (24 hours)
  (`config/settings.py:409-462`). A timestamp is Stale only when age is
  strictly greater than that threshold (`services/monitoring_service.py:
  198-207`) — the boundary itself is unchanged, only the value moved from 90
  minutes to 24 hours. A missing metric reading is No Data, and
  device/Transformer/Plant rollups take the worst metric state
  (`services/monitoring_service.py:249-264,376-490`). The legacy
  `EXPECTED_INTERVAL_MINUTES`/`STALE_AFTER_INTERVALS` pair is still accepted
  as explicit, named, ignored input — never silently combined with the new
  setting (`config/settings.py::resolve_freshness_stale_after_minutes`).
- BR008 uses `NO_DATA_NOTIFICATION_AFTER = timedelta(hours=24)` and emits only
  when age is strictly greater than 24 hours. Exactly 24 hours does not trigger
  (`services/notification_service.py:18-21,89-109`;
  `tests/test_notification_service.py:131-142`). A never-reported device is
  excluded because the system cannot prove it has been active for more than 24
  hours (`services/notification_service.py:61-65,89-93`). This gate did not
  change BR008's value or boundary; it did remove `notification_service.py`'s
  now-dead import of `services.monitoring_service`, with a regression test
  proving the module no longer references it at all
  (`tests/test_notification_service.py::TestArchitecture::
  test_notification_service_does_not_import_configurable_freshness`).

The UI threshold is consumed across Fleet Overview, Plant/Transformer/device
freshness displays and Command Center through the central monitoring service.
The rendered Fleet Overview explicitly shows the configured threshold, worded
as an operational threshold rather than a per-RTL cadence
(`components/fleet_condition.py:33-42,177-220`). Command Center consumes the
same `FleetHealth`, not a separate threshold (`services/command_center_service.py:
877-917`). Notifications intentionally use the separate BR008 constant. Reports
do not calculate freshness: their data services are separate, and report code
explicitly avoids owning that axis (`repositories/plant_monitoring_repository.py:
2583-2584`).

There is still no per-device expected cadence column in the baseline device
schema or `PlantRecord`/device records, and no repository API for one — this
gate deliberately did not add one (see 2.3, still MISSING). Changing the
global freshness value changed visible Fresh/Stale classification and all
freshness-derived attention rankings, but it did **not** change BR008; the
separation is tested both ways (BR008 independence, and rollup/attention-count
tests updated for the new 24-hour threshold).

### Terminology

`Plant` is not only UI copy. It is a database table and foreign-key parent,
repository entity, route segment (`/plants/...`), query parameter, callback
context key, component vocabulary, seed identifier and broad test contract.
Consequently, a full rename is a data-model/API migration.

A presentation-only alias is mechanically possible: UI labels can say Feeder
or Network while retaining `plant_id` internally. It is not semantically safe
without confirmation, because the Functional Specification separately names
OU, Zone, Sector, CNC, Feeder/Feeder Name, Transformer and UID, while current
report services populate the taxonomy fields with `None`. Calling every current
Plant a Feeder could falsely claim the missing mapping is complete. “Network
Name” is meeting vocabulary, not a field named by the Functional Specification.

Recommended decision question: **Does each current `plants` row represent one
Feeder, one Network, or a temporary top-level grouping that will later contain
Feeders?** The answer determines label-only alias, additive Feeder entity, or
replacement migration.

### Generic Power-Plant Remnants

The remaining remnants and their dependency class are:

| Occurrence | Classification | Evidence |
|---|---|---|
| Fleet table `Fuel`, `Capacity (MW)` | Removed from visible production UI by `55e3eeb` | `pages/plants_overview.py`; `callbacks/listings.py`; `tests/test_fleet_overview.py` |
| Plant detail `Primary fuel`, `Capacity` | Removed from visible production UI by `55e3eeb` | `callbacks/listings.py`; `tests/test_plant_detail.py` |
| Dash title `Power Plant Monitoring` | Visible production UI/browser metadata | `app.py:21` |
| Login copy `Power Plant Monitoring` and powerplant hero asset | Visible production UI | `pages/login.py:93`; `app.py:63` |
| `plants.capacity_mw`, `plants.primary_fuel` | Preserved internal model/schema fields; no longer rendered by Fleet/Plant presentation | `alembic/versions/001_baseline.py:44-58`; `repositories/plant_monitoring_repository.py:31-38,227-256` |
| 30 real-world power-station names and fuel/capacity values | Seed/development data, also visible through normal UI | `db/seed_data/plants.json`; `db/seed_plant_monitoring.py:339-350` |
| Fuel/capacity tests | Presentation tests now prove absence; migration/repository tests preserve storage compatibility | `tests/test_fleet_overview.py`; `tests/test_plant_detail.py`; `tests/test_migration_foundation.py:135` |
| Reports/exports | **No dependency** on fuel/capacity; they depend on OU/Zone/Sector/CNC/Feeder/Transformer/UID and report facts | `config/reports.py:25-90` |
| “generation” in energy chart comments | Correct domain clarification, not generic metadata or visible copy | `components/metric_chart.py:149`; `components/metric_workspace.py:63` |

Fuel/capacity remain stored compatibility data but are no longer visible on the
RTL monitoring screens. No schema, repository, seed or migration changed.
Generic product branding and real-world seeded Plant names remain pending an
authoritative replacement name/taxonomy; neither is bundled with Feeder mapping.

### Command Center Drill-Down

| Surface | Clickable? | Result/state change | Affected devices shown? | RTL drill-in? | Obvious? | Test position |
|---|---|---|---|---|---|---|
| Power Down | No | None; current state is “Unavailable” | No current list; recent matching events may appear elsewhere | From a resolved Recent Event only | The absence is explained, but not the requested interaction | Static/unavailable behavior tested |
| Battery Low | No | Same as Power Down | Same | From a resolved Recent Event only | Same | Static/unavailable behavior tested |
| Communication / No Data | KPI card no; priority rows yes | No KPI filter; lower list is pre-ranked No Data then Stale | Yes, in Priority Investigation | Yes, “Open asset” | Relationship is indirect | Service/ranking/link tests exist |
| Sensor Error | Not a condition card | Can appear as persisted recent event and Notification Center row | Event occurrences, not current affected set | Yes when device resolves | Event/history distinction is not a drill-down filter | Event semantics and links tested |
| Needs Attention | Card no; downstream panels yes | No direct filter; same snapshot powers Priority/Affected Locations | Yes | Yes via priority row | Indirect | Composition/ranking/link tests exist |
| Priority Locations (Affected Locations) | Yes | `?plant=<id>` selects Plant lens | Plant counts, not device list | Via Selected Location Transformer, then hierarchy | Reasonably clear | Selection, ranking and cap behavior tested |
| Selected Location | Yes | Links to Plant/Transformer pages | Transformer concentration | Hierarchy drill-down reaches devices | Clear links | Link destinations tested |
| Recent Operational Events | Yes for resolved devices; View all link to Notifications | Opens device or Notification Center | Event rows identify devices | Yes | Clear “Open asset” action | Strong component/service link tests |

Power Down/Battery Low occurrence drill-down was implemented by
CLIENT-FEEDBACK-DRILLDOWN-1 (`d543b1b`). The system still has no event closure
contract, so it does not assert how many RTLs are **currently** in those states.
The condition card retains “Current state — Unavailable,” while selecting it
shows the latest matching persisted occurrence per scoped RTL in a separately
labelled investigation panel. A current-state list still requires client-defined
closure semantics.

### No Data

Implementation `40b755e` reduced No Data's Command Center visual weight without
changing its meaning:

- Fleet Health keeps exact Fresh/Stale/No Data counts, with Stale and No Data
  styled as supporting rows;
- Communication now headlines complete metric reporting coverage and places No
  Data count/share/affected plants under an explicit supporting-detail label;
- Needs Attention remains the primary Stale + No Data total and exposes both
  constituent counts as supporting freshness detail;
- Priority Investigation retains ADR-009's No Data-before-Stale service order,
  but its headline now describes freshness exceptions rather than promoting No
  Data; every No Data row retains its textual badge and explanation;
- affected-location and selected-location composition;
- Fleet Overview condition, coverage and freshness panels;
- formal `>24h No Data` Notification Center rule.

The meeting preference is now reflected in the Command Center presentation.
Freshness classification, attention and communication totals, ADR-009 ordering,
DeviceScope, drill-down behavior, and BR008's independent `>24h` rule are
unchanged. Fleet Overview remains outside this presentation-only gate.

### Notification Center

The live table is neither wholly persisted nor placeholder-only. It is a merged
projection:

1. BR008 rows are derived on read from latest-reading timestamps; they are not
   stored notification records (`services/notification_service.py:50-109`).
2. Battery Low, Power Down, Sensor Error and other mapped occurrences come from
   persisted `device_events` (`services/notification_service.py:139-184`).
3. The merged result is sorted newest-first (`services/notification_service.py:
   158-192`).
4. Persisted alarm events can be acknowledged; derived freshness rows cannot
   (`callbacks/notifications.py:90-122,209-252`).

BR009 semantics are correct: client-facing alarm labels collapse battery_low to
Battery Alarm and power_down/sensor_error to Comms Alarm, while retaining the
underlying event type for operational detail. This is complete application
semantics, not evidence of external SMS/email delivery.

Thus “latest actual notifications” is only partially satisfied. If “actual”
means actual persisted device events plus current BR008 conditions, yes. If it
means a durable history of messages sent/received, delivery receipts, or an
authoritative RTL Master notification feed, no. The client must disambiguate.

### Report Center

The selector currently offers exactly Entire Fleet, Plant, Transformer and
Device (`pages/report_center.py:104-110`). Plant/Transformer/Device selectors
cascade and are populated within the trusted user's `DeviceScope`
(`callbacks/report_center.py:684-742`). All three report builders receive the
same scope dimensions and `DeviceScope`, so filtering functionality is real,
not UI-only (`callbacks/report_center.py:334-342,432-441,541-552`).

Functionality therefore matches the client's understood four-level filtering
shape, but terminology does not: Feeder is represented as Plant in the scope
control. Separately, the report output schemas already carry Feeder or Feeder
Name, as the Functional Specification requires, but values remain intentionally
unavailable pending mapping. The correct next step is not a Reports redesign;
it is resolution of the Plant/Feeder semantic mapping followed by the smallest
label or model change that truthfully represents it.

The “Recent Reports” table is explicitly mock/demo-only UI
(`pages/report_center.py:291-330`), but report generation and CSV/PDF/XLSX
downloads are data-backed. That placeholder history is unrelated to the asset
scope selector and should not be used to judge filtering correctness.

### Technician Impact

Every proposed change intersects scope presentation even when it does not alter
authorization. The non-negotiable boundary is `DeviceScope`: a Technician with
no active assignments receives an empty scope; an active assignment is required
for visibility (`services/device_scope.py:55-80`).

Impact by capability:

- **Device visibility:** landing, condition filters, event lists, Feeder aliases
  and reports must all derive options/counts/rows from the current scope. A new
  affected-device endpoint must not query unrestricted ids then filter in UI.
- **Program RTL:** Administrator may act on any RTL; Technician only on an
  assigned RTL (`services/authorization.py:203`). A renamed hierarchy must not
  create an alternate path around `require_action`.
- **Forwarding:** same assigned-only Technician boundary
  (`services/authorization.py:204`). Terminology changes affect context labels,
  not permission.
- **Deactivation:** same assigned-only Technician boundary
  (`services/authorization.py:205`).
- **Alarms:** Notification Center route is operational-role-only and
  acknowledgement is assigned-only for Technicians
  (`services/authorization.py:60-74,206`). Event filter links must preserve that
  route and row scope.
- **Reports/export:** all roles have export capability, but a Technician's rows
  and selector options remain assigned-device scoped
  (`tests/test_report_export_authorization.py:210-222`). “Entire Fleet” for a
  Technician therefore means their entire visible scope, not all 120 devices.

No proposed presentation improvement justifies weakening these rules.

### Mobbin Research Candidates

Mobbin is not requirement authority and no visual redesign is recommended for
concepts the client already validated. External reference research could help
only with these bounded UX gaps:

1. **KPI → affected-device drill-down.** Current problem: Needs Attention and
   Communication are static even though a related ranked device list exists
   lower on the page. Research pattern: clickable KPI with anchored, filtered
   result list and visible active-filter state. Why useful: makes the causal
   relationship clear without inventing new semantics.
2. **Alert investigation list.** Current problem: electrical condition cards
   have no drill-down, while event occurrences live in Recent Events and
   Notifications. Research pattern: event-category chip/tab opening a time-
   bounded event list with “historical event” labelling. Why useful: helps keep
   event history visibly distinct from current condition.
3. **Filter drawer.** Current problem: adding event/status/cadence filters to
   Command Center could overwhelm its fixed cockpit layout. Research pattern:
   compact filter drawer with applied-filter count, clear-all and keyboard
   focus behavior. Why useful: preserves the validated cockpit while adding
   investigation controls.
4. **Selected-device investigation panel.** Current problem: existing lists
   jump directly to the full device dashboard, which can lose list context.
   Research pattern: master-detail side panel with an explicit full-device
   link. Why useful: supports rapid triage across several RTLs without changing
   the validated device page.
5. **Status hierarchy.** Current problem: Fresh/Stale/No Data, event categories,
   Battery Alarm/Comms Alarm and acknowledgement status are correct but occupy
   adjacent surfaces and can appear to be one severity system. Research
   pattern: layered status taxonomy and neutral provenance labels. Why useful:
   clarifies “data freshness,” “event,” “alarm label” and “workflow state”
   without changing their domain definitions.

Do not research a wholesale Command Center or Fleet Overview visual redesign:
the client validated the concepts, and the known gaps are interaction and
semantic clarity.

## Safe Internal Changes

These can be implemented without deciding new business semantics, provided
existing authorization and scope tests remain green:

1. Add explicit anchor/filter affordances from Needs Attention and
   Communication to the existing scoped Priority Investigation list.
2. Make existing Affected Location, Selected Location and Recent Event links
   more visibly actionable without changing destinations or data.
3. Add provenance copy distinguishing freshness condition, persisted device
   event and client-facing alarm label.
4. De-emphasize No Data visually in the Command Center while retaining the
   state, counts, investigation detail and BR008 notification rule.
5. Add interaction-level tests for any new anchors/filters, including empty
   Technician scope and assigned/unassigned device behavior.
6. Remove stale “prototype”/“demo” wording from the live Notification Center if
   any remains, while retaining honest statements about derived versus
   persisted data. This is copy-only; it must not claim external delivery.

Fuel/Capacity hiding is technically small, but because the meeting language was
a question rather than a confirmed removal decision, it is listed below as a
client-decision change.

## Client-Decision Changes

Wait for confirmation before implementing:

1. Which roles should land on Fleet Condition/Command Center, especially since
   General Users are not authorized for Command Center.
2. The reporting-cadence source, granularity, defaults and grace rule for
   hourly, 6-hourly and daily RTLs.
3. Whether current `Plant` means Feeder, Network, or a parent grouping, and
   whether “Network Name” is accepted vocabulary alongside the Functional
   Specification's Feeder/Feeder Name.
4. The authoritative OU/Zone/Sector/CNC/Feeder mapping and production source.
5. Whether Fuel, Capacity, power-station seed names and Power Plant branding
   should be hidden, replaced, or removed from the model.
6. The event closure/current-state contract needed to list RTLs currently in
   Power Down or Battery Low.
7. Whether Sensor Error drill-down means current state or recent event history.
8. What “latest actual notifications” means: persisted source events, generated
   in-app notices, authoritative RTL Master messages, or external delivery
   receipts.

## Recommended Implementation Gates

1. **CLIENT-FEEDBACK-UX-1 — existing drill-down affordances.** Add scoped
   Needs Attention/Communication anchors or filters to Priority Investigation;
   clarify actionable links; add interaction and Technician-scope tests. No
   domain or schema change.
2. **CLIENT-FEEDBACK-NODATA-1 — COMPLETED (`40b755e`).** No Data is supporting
   Command Center investigation detail while all freshness, scope, drill-down,
   ADR-009 ordering and BR008 semantics remain unchanged.
3. **CLIENT-FEEDBACK-ENTRY-1 — role-aware landing.** After client confirmation,
   change entry route/navigation with explicit Administrator, Technician and
   General User acceptance tests.
4. **CLIENT-FEEDBACK-TERMS-1 — confirmed presentation vocabulary.** Apply only
   confirmed Feeder/Network labels and hide/replace confirmed generation UI
   remnants. Do not migrate schema in this gate.
5. **FS-TAXONOMY-1 — authoritative taxonomy mapping.** Add production-backed
   OU/Zone/Sector/CNC/Feeder fields and populate report output. This is the
   formal Functional Specification gate and is distinct from labels.
6. **FRESHNESS-CADENCE-1 — cadence-aware policy.** After the client identifies
   source and ownership, add the smallest data/config model for per-device (or
   confirmed higher-level) cadence. Preserve the separate BR008 `>24h` rule.
7. **EVENT-CURRENT-STATE-1 — closure contract and condition drill-down.** Once
   current-state semantics are authoritative, model open/closed Power Down,
   Battery Low and any confirmed Sensor Error state, then make condition counts
   and device drill-downs real.
8. **NOTIFICATION-ACTUAL-1 — notification provenance/delivery history.** Only if
   the client defines “actual notifications” beyond current persisted events
   plus derived BR008; design persistence/integration from that definition.

Each gate should open and close on a clean context-pack check. None should
silently change BR008, report taxonomy semantics, event meaning, or Technician
scope as collateral work.
