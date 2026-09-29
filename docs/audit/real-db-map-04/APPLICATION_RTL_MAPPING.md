
# REAL-DB-MAP-04 — Current application ↔ client RTL database mapping

Status: analysis only. No application code, PostgreSQL data, SQL Server RTL schema, RTL records, migrations, or client backup was changed.

## Authority and scope

RTL facts come from [the authoritative database model](../real-db-audit-02/AUTHORITATIVE_DATABASE_MODEL.md), especially sections 3–9. Present application behaviour comes from source code. The legacy PostgreSQL client-database description is historical for this purpose and is not used as RTL evidence.

```text
Dash application
  ├─ application repository → PostgreSQL plant_monitoring (application state)
  └─ future RTL read repository → SQL Server RTL, READ ONLY (client source data)
```

The current engine is PostgreSQL-specific: `db/engine.py:25-31` builds one engine from application database settings and `db/engine.py:43-53` commits its session. The existing repository both reads and writes `plant_monitoring` (`repositories/plant_monitoring_repository.py:227-4336`). It must not be pointed at `RTL_DB_*`.

## Executive answer

1. RTL directly contains raw temperature history, device UID/status facts, partial UID-to-transformer mappings, operational logs, and limited asset/organisation context.
2. All useful monitoring presentation needs an adapter: the app has string hierarchy IDs and eight metrics; RTL has nullable integer UIDs, no plant entity, and one temperature stream.
3. PostgreSQL remains owner of application identities, authorisation, assignments, acknowledgements, thresholds, commands, notification state, preferences, and audit history.
4. Voltage, current, active/reactive power, power factor, frequency, energy, client command/activation control, and alarm acknowledgement have no RTL source.
5. Active-fleet eligibility, transformer/asset hierarchy, timestamp timezone, raw-data quality policy, and technician assignment source are unresolved.
6. Smallest safe first slice: a separately configured SELECT-only RTL reader providing latest/range temperature by raw UID for a client-approved population. Keep current PostgreSQL hierarchy, authentication, and all operational writes unchanged.

## 1. Current application model and assumptions

The Alembic baseline creates an enforced PostgreSQL hierarchy:

```text
plants → transformers → devices → readings
```

It has an FK-backed hierarchy plus a unique `(device_id, metric, reading_ts)` reading relation and timezone-aware timestamps (`alembic/versions/001_baseline.py:43-137`). The app's primary key is a string `device_id`, with a string `transformer_id` parent; `device_code` is a display/registration field (`001_baseline.py:82-100`). Navigation and role-scoped listings join that hierarchy directly (`plant_monitoring_repository.py:227-242, 334-348, 402-480`; `services/device_scope.py:47-57`).

That is unlike RTL `master_temperature`: it has no PK, user index, FK, or unique constraint and uses nullable `datetime2(7)` time. The eight app metric definitions and display units are explicitly development metadata awaiting real-database mapping (`config/metrics.py:1-8, 31-43`). The seeder creates generated hierarchy and all eight metric series (`db/seed_plant_monitoring.py:1-18, 150-187`). The old 30/71/120 dataset is not an RTL fact.

## 2. Feature ↔ data classification

The following 39 rows are the classification inventory; totals are therefore feature-map totals, not table or screen counts.

| Capability / concept | Class | Evidence and consequence |
|---|---|---|
| Raw temperature readings | DIRECT RTL | `dbo.master_temperature` is the 2,456,901-row temperature source by UID/time. |
| Raw high-temperature alarms | DIRECT RTL | `dbo.alarm_log` has 3,346 observed High Temp. rows; it lacks acknowledgement. |
| Raw event/message records | DIRECT RTL | Startup, powerdown, sensor-error, communications and settings logs are source records. |
| Registered UID directory | DIRECT RTL | `device_list` has 339 unique observed UIDs; it is not the app `devices` entity. |
| Latest temperature | RTL WITH ADAPTER | `vw_installed_rtls` is useful but app IDs, duplicate handling and eligibility differ. |
| Temperature charts/ranges | RTL WITH ADAPTER | Convert `datetime2`, nullable dates, duplicates, decimals, and raw UID to app series. |
| Temperature KPIs/freshness | RTL WITH ADAPTER | App is UTC/window based; RTL timezone is unknown and cadence irregular. |
| Device/RTL selector/context | RTL WITH ADAPTER | Map raw `int device_uid` to safe app identity/display representation. |
| Transformer context | RTL WITH ADAPTER | `trfr_list` has 185 observed UID/code mappings but no business uniqueness. |
| Organisation/asset context | RTL WITH ADAPTER | TUG hierarchy view uses an ungoverned description-token join; 178/185 matches. |
| Communication/last status | RTL WITH ADAPTER | `device_status` and `comms_alarm` offer source facts, not proven app semantics. |
| Battery information | RTL WITH ADAPTER | Battery voltage is event payload, not a periodic battery/electrical series. |
| Installed RTLs report | RTL WITH ADAPTER | RTL view can source it, but current report assumes the PG hierarchy/status (`services/report_service.py:20-95`). |
| Maximum-temperature report | RTL WITH ADAPTER | RTL has a source view; range/tie/quality/attribution policy is required. |
| 30-day alarm report | RTL WITH ADAPTER | RTL has alarm source/view; current report reads app events and UTC policy (`report_service.py:101-190`). |
| Plant hierarchy/fleet overview | AMBIGUOUS | RTL has no plant entity; TUG attributes do not declare one. |
| Canonical active fleet | AMBIGUOUS | 400 telemetry, 339 registered, and 185 mapped UIDs do not select an active population. |
| UID-to-transformer history | AMBIGUOUS | 2,072 telemetry UID/trfr pairs versus 183 exact current mapping-pair matches. |
| Technician assignment source | AMBIGUOUS | Normalized table is empty; misspelled legacy list has 68 rows. |
| Timezone and data-validity policy | AMBIGUOUS | No offset; null dates, duplicates, outliers exist but no source rule says how to filter. |
| Authentication/users | APPLICATION-OWNED | App stores/authenticates `users` (`003_users.py:38-60`); RTL persons/roles lifecycle is unproven. |
| Roles/permissions/session authorisation | APPLICATION-OWNED | App role/scope policy relies on PG users/assignments (`device_scope.py:47-57`). |
| Technician access assignments | APPLICATION-OWNED | App has enforced `user_device_assignments` (`004_user_device_assignments.py:37-73`). |
| Alarm acknowledgement | APPLICATION-OWNED | App writes acknowledgement to `device_events` (`repository.py:4026-4064`); RTL has none. |
| Event projection/notification state | APPLICATION-OWNED | RTL is a source log, not an app acknowledgement/delivery lifecycle. |
| Preferences/message forwarding | APPLICATION-OWNED | App per-user forwarding (`repository.py:1549-1662`) is not client auth/delivery policy. |
| Threshold/freshness configuration | APPLICATION-OWNED | App configuration accessors at `repository.py:1906-2178`; no RTL threshold master. |
| Commands/programming/deactivation | APPLICATION-OWNED | App command/active state at `repository.py:3216-3796, 4251-4336`; no RTL command model. |
| Application audit trail | APPLICATION-OWNED | App audit log (`repository.py:3042-3114, 3366-3464`) differs from client operational history. |
| Synthetic hierarchy/readings | REMOVED FROM PRODUCTION PATH | Seeder is explicitly synthetic; retain only local/demo fixture use. |
| Synthetic live events/status | REMOVED FROM PRODUCTION PATH | Simulator/demo seeds must not stand in for client data in production. |
| Voltage | NOT AVAILABLE | No RTL line-voltage series; TUG voltage group is asset classification. |
| Current | NOT AVAILABLE | No RTL current series. |
| Active power | NOT AVAILABLE | No RTL active-power series. |
| Reactive power | NOT AVAILABLE | No RTL reactive-power series. |
| Power factor | NOT AVAILABLE | No RTL power-factor series. |
| Frequency | NOT AVAILABLE | No RTL frequency series. |
| Energy | NOT AVAILABLE | No RTL energy series. |
| Client activation/deactivation | NOT AVAILABLE | No RTL command or lifecycle object. |

**Totals:** DIRECT RTL **4**; RTL WITH ADAPTER **11**; APPLICATION-OWNED **9**; NOT AVAILABLE **8**; AMBIGUOUS **5**; REMOVED FROM PRODUCTION PATH **2**. The requested five-class total is **37**; removal is reported separately because it describes synthetic dependencies, not a client-database capability.

## 3. Hierarchy and identifier mapping

Current application:

```text
plant_id (string) → transformer_id (string) → device_id (string)
                                               └→ readings(metric, reading_ts, value)
```

RTL:

```text
device_list.device_uid (339 registered)
       │ inferred UID match, not FK
device_status.device_uid (339 current/last-status rows)
       │
master_temperature.device_uid (400 telemetry UIDs)
       │ incomplete inferred association
trfr_list.device_uid ↔ trfr (185 observed 1:1 current rows; not enforced)
       │ inferred description-token join; 178 observed matches
tug_report (asset / organisation attributes)
```

No RTL plant/site entity was found. TUG might become contextual evidence but cannot be represented as the app’s plant level without client approval.

Set reconciliation from authoritative model §4:

```text
T = telemetry UIDs                 400
R = registered UIDs                339
T ∩ R                              319
T − R (telemetry only)              81
R − T (registered/no telemetry)     20
M = mapped UIDs                    185; M ⊆ T ∩ R
```

The arithmetic reconciles: `319 + 81 = 400`; `319 + 20 = 339`. It does not establish the operational fleet. A future adapter must expose unmatched records as such, not fabricate application parent records. In particular, the current `DeviceScope` expects complete application `device_id` values rather than raw source UIDs.

## 4. Metric mapping

| Dashboard metric | Current representation | RTL equivalent | Unit/confidence | Status |
|---|---|---|---|---|
| Temperature | Synthetic `readings(metric='temperature')`; displayed °C | `master_temperature.temperature decimal(6,2)` by UID/time | °C strongly indicated by use, but no audited unit column; medium | RTL WITH ADAPTER |
| Voltage | Synthetic, display kV | None; TUG voltage group is not telemetry | Development unit only | NOT AVAILABLE |
| Current | Synthetic, display A | None | Development unit only | NOT AVAILABLE |
| Active Power | Synthetic, display MW | None | Development unit only | NOT AVAILABLE |
| Reactive Power | Synthetic, display MVAr | None | Development unit only | NOT AVAILABLE |
| Power Factor | Synthetic dimensionless | None | None | NOT AVAILABLE |
| Frequency | Synthetic, display Hz | None | None | NOT AVAILABLE |
| Energy | Synthetic cumulative/delta, display MWh | None | None | NOT AVAILABLE |

Do not label event-log `battery_voltage` as dashboard Voltage. It occurs only on event/message records and is not a continuous electrical source (authoritative model §7).

## 5. Latest, history, aggregation, freshness and online assumptions

The current repository uses PostgreSQL `LEFT JOIN LATERAL`, `LIMIT`, and an indexed `(device_id, metric, reading_ts DESC)` relation for bounded latest reads (`plant_monitoring_repository.py:544-638, 670-793`). Range/latest APIs assume unique per-metric readings (`:1182-1351`). The service retrieves latest independently of selected period, anchors relative windows to UTC wall time, and evaluates freshness under an application setting (`services/monitoring_service.py:352-433, 117-146`).

RTL has one metric source. Its latest-reading view uses SQL Server `OUTER APPLY TOP 1`, useful evidence but not an interchangeable contract. A future adapter must provide parameterized SQL Server latest/range queries; deterministic equal-timestamp/duplicate handling; explicit timestamp normalization before comparing to UTC; an approved raw-data policy for null dates, pre-2010 candidates and -3 to 493 values; and bounded/paginated query performance for a 2.45M-row table without an audited user index.

These are translation requirements, not permission to discard source data. `device_status.last_comms_ok` and `comms_alarm.no_data_recorded` may later be displayed as source facts, but must not silently replace configured application freshness.

## 6. Application-owned data

| Concern | Current storage | RTL support | Recommended ownership |
|---|---|---|---|
| Login/users | PostgreSQL users/auth/session | persons/roles, lifecycle unknown | PostgreSQL |
| Roles/permissions | app policy/session | roles table only | PostgreSQL |
| Technician visibility | user_device_assignments + DeviceScope | conflicting/empty assignment sources | PostgreSQL initially |
| Alarm acknowledgement | app device_events acknowledgement | not found | PostgreSQL |
| Notifications/delivery | app projection/delivery boundary | contacts/forwarding only | PostgreSQL |
| Thresholds/freshness | app config tables | not found | PostgreSQL |
| Commands/programming/deactivation | app requests/commands/active state | not found | PostgreSQL; never RTL writes |
| Audit trail | app audit_log | operational logs, different meaning | PostgreSQL |
| Preferences/forwarding | app user settings | client contacts/recipients only | PostgreSQL |

Reading a client source log never transfers ownership of acknowledgement, delivery, command, or audit state to the client database.

## 7. Screen-by-screen impact

| Screen | Current data | RTL availability | Impact |
|---|---|---|---|
| Login/header/routing | app users, sessions, roles | no safe compatible source | Unchanged PostgreSQL |
| Fleet Overview | scoped plant/tree, latest temp/freshness | temp/status yes; no plant hierarchy | Adapter + product clarification |
| Plant detail | plant metadata, transformers, attribution | no plant entity | No truthful direct RTL data |
| Transformer detail | transformer path/devices | partial trfr mapping | Adapter + mapping decision |
| Device dashboard | 8 snapshots, metric history/KPIs/chart/table | temperature only | Temperature adapter; 7 unsupported metrics |
| Command Center | temperature, app events/acks/commands, hierarchy | partial source events/status | Mixed; retain PG operational state |
| Device admin/registration | hierarchy/device writes | source registration only, RTL immutable | PostgreSQL only |
| Technician views | assignments/scope | ambiguous source assignments | PostgreSQL initially |
| Admin settings | thresholds/freshness | none | PostgreSQL only |
| Notifications | app projections/acknowledgements | source logs only | PG projection; optional source read |
| Audit Log | application audit | client operational logs | Separate sources |
| Report Center | PG hierarchy/report models | three related RTL views | Each report needs adapter/policy |
| Programming/device management | commands/active state writes | none | PostgreSQL only; no RTL write path |

## 8. Smallest safe data-access boundary

When a later integration gate authorizes code, add a distinct SQL Server `rtl_read_repository` with its own configuration and SELECT-only typed methods:

```text
list_registered_uids()
get_temperature_latest(raw_uid)
get_temperature_range(raw_uid, start, end)
get_device_status(raw_uid)
list_temperature_events(raw_uid, ...)
```

It should use only `RTL_DB_HOST`, `RTL_DB_PORT`, `RTL_DB_NAME`, `RTL_DB_USER`, and `RTL_DB_PASSWORD` with the documented `rtl_app_reader` account. Use parameterized SQL Server queries and a deliberately narrow read model.

Keep `db/engine.py`, Alembic, seeders, and `plant_monitoring_repository.py` on PostgreSQL configuration. Never pass `RTL_DB_*` to migration, seeding, a transactional writer, or any app write repository. Source-to-app linkage requires an application-owned mapping/eligibility record or a client-approved deterministic rule; it must not mutate RTL.

## 9. Integration risk register

| Rank | Risk | Control |
|---|---|---|
| HIGH | Seven metrics lack RTL sources | First slice is temperature-only; never present synthetic values as client data. |
| HIGH | RTL has no plant hierarchy | Do not derive plants from TUG strings; obtain a client mapping. |
| HIGH | UID population mismatch | Obtain active population policy before default fleet construction. |
| HIGH | Existing repository writes and commits | Separate configuration, engine, repository, and read-only login. |
| HIGH | Time/quality policy undecided | Do not silently filter/deduplicate; obtain policy before freshness/latest claims. |
| MEDIUM | Mapping is ungoverned/historical labels vary | Preserve source associations and show unmapped status. |
| MEDIUM | SQL Server differs from PostgreSQL | Separate parameterized query implementations and tests. |
| MEDIUM | 2.456M unindexed source rows | Bound queries; inspect plans and performance locally. |
| MEDIUM | Event semantics differ | Retain source provenance; app acknowledgement stays independent. |
| MEDIUM | Status ≠ freshness | Present/derive separately until client alignment. |
| LOW | Battery context could be mislabelled as Voltage | Keep it out of the electrical metric family. |
| LOW | Client contact/credential fields are sensitive | Never import them into browser/auth data without explicit approval. |

## 10. Client decisions

### Blocks initial temperature integration

1. Which initial monitored population is authorized: 319 registered-and-telemetry UIDs, all 400 telemetry UIDs, or a supplied active list? How should 81 telemetry-only and 20 registered/no-telemetry UIDs appear?
2. Is `trfr_list` authoritative for current UID-to-transformer association? How should historical UID/trfr changes, two nonmatching current pairs, and 215 unmapped telemetry UIDs be handled?
3. What timezone do temperature, status, and event timestamps use?
4. What approved validity/deduplication policy applies to null/implausible timestamps, duplicates, and values such as -3 and 493?

### Does not block initial temperature integration

1. Is the TUG description-token join approved, and what is the authoritative asset/site key?
2. Which technician-assignment representation is canonical if source assignments must ever be displayed?
3. Should source event logs remain immutable source history, and how should they relate to app acknowledgement?
4. Are source communications flags complementary to, or replacements for, application freshness?
5. Is another source available for the seven missing electrical/energy metrics?

## Final model

```text
SQL Server RTL (final client source, READ ONLY)
  device_list / device_status ─ raw UID registration and status
  trfr_list ────────────────── partial UID ↔ transformer code
  master_temperature ───────── raw temperature series
  event/message logs ───────── source events and battery context
  tug_report ───────────────── optional ungoverned asset context
                    │
                    │ SELECT-only typed adapter; no migrations / writes
                    ▼
Power application
  PostgreSQL ─────── users, roles, assignments, mapping eligibility,
                     thresholds, freshness, acknowledgements, commands,
                     notifications, preferences, and audit trail
```

The safe first integration is **read-only latest/range temperature by an approved raw UID population**. It does not replace the current hierarchy, operational state, or unsupported metric sources.
