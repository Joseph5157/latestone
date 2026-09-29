# REAL-DB-REVIEW-03 — Authoritative database model

Status: review model, derived only from the REAL-DB-AUDIT-02 captured evidence.
Database: client-supplied SQL Server database `RTL` (latest backup set restored as read-only `RTL_AUDIT_02`).
Boundary: this document models the client database only. It does not compare, map, or integrate it with the existing application.

## Review result

The audit conclusions are materially supported by the captured schema, view definitions, row counts, and aggregate analyses. No substantive REAL-DB-AUDIT-02 conclusion is contradicted. One precision is important: `trfr_list` has a surrogate PK only; its observed one-to-one business mapping is a **data fact**, not a database-enforced business key.

## 1. All user tables

“Needed” means likely needed by a future Power application integration according to database evidence only: **core**, **conditional**, or **not expected**. It is not an implementation decision.

| Table (rows) | Evidence-supported purpose | PK / important columns / timestamps | Identifiers and relationships | Relationship status | Needed |
|---|---|---|---|---|---|
| `dbo.alarm_log` (3,346) | High-temperature alarm history; all observed `status` values are `High Temp.` | No PK. `device_uid`, `trfr`, `event_timestamp`, `reading_timestamp`, `temperature`, `is_max_reading`, `battery_voltage`, `status`, `firmware` | UID and `trfr` repeat operational identifiers | INFERRED only | Conditional: alarm history |
| `dbo.client_id` (3) | Client/API identity record/history; has `api_key` | No PK. `event_timestamp`, `full_name`, sensitive `api_key` | No declared relationship | None | Not expected for operational data consumption |
| `dbo.comms_alarm` (132) | Communication / no-data alarm data | No PK. `device_uid`, `trfr`, `last_status_timestamp`, `no_data_recorded` | UID and `trfr` match operational namespaces | INFERRED only | Conditional: communication state |
| `dbo.contact_list` (8) | Contact directory | PK `id`. Identity; name, telephone, designation, email | No FK | None | Conditional: contact information |
| `dbo.device_list` (339) | Registered device/RTL directory | No PK; unique `device_uid`; `cell_number` | `device_uid` is target of the assignment FK and overlaps status/mapping/telemetry UIDs | DECLARED only from assignments; otherwise INFERRED | Core: registration |
| `dbo.device_status` (339) | Last/current status by device UID | PK `device_uid`; `trfr`, `last_status`, `last_status_timestamp`, `last_comms_ok`, last powerdown/startup timestamps | Same UID population as `device_list` in captured analysis; optional `trfr` | INFERRED to registration/mapping | Core: latest status |
| `dbo.invalid_uid_log` (0) | Rejected/invalid UID event or reading log, based on name and event-shaped columns | No PK. UID, transformer, read time, temperature, battery, status, firmware | No FKs | INFERRED only | Not expected unless invalid-ingestion reporting is needed |
| `dbo.master_temperature` (2,456,901) | Primary temperature history | No PK/index. `reading_timestamp datetime2(7)`, `temperature decimal(6,2)`, `trfr nvarchar(20)`, `device_uid int` | UID / transformer values; neither governed by key | INFERRED only | Core: historical telemetry |
| `dbo.message_forwarding_list` (1) | Message-forwarding recipient list | PK `id`; identity; sensitive contact fields | No FK | None | Conditional: forwarding context |
| `dbo.persons` (8) | User/person account, role, contact, credential-hash, and forwarding-preference data | PK `person_id`; identity; `role_id`, user/contact fields, sensitive `password_hash`; `message_forwarding_enabled(_at)` | `role_id → roles.role_id` | DECLARED role FK | Conditional: user/account data |
| `dbo.powerdown_log` (719) | Device power-down event history | No PK. UID, transformer, event/read times, `measurement_period`, temperature, battery, status, firmware | Operational UID / transformer namespaces | INFERRED only | Conditional: events |
| `dbo.roles` (3) | Role lookup: Administrator, Technician, General User | PK `role_id`; identity; unique `role_name` | Parent of `persons.role_id` | DECLARED | Conditional: user/account data |
| `dbo.sensor_error_log` (1,177) | Sensor-error event history | No PK. UID, transformer, reading time, temperature, battery, status, firmware | Operational UID / transformer namespaces | INFERRED only | Conditional: diagnostics/events |
| `dbo.settings_upload_log` (3,400) | Device setting/upload audit | No PK. event time, UID, transformer, `data_interval`, sensitive name, `request_method` | Operational UID / transformer namespaces | INFERRED only | Conditional: configuration history |
| `dbo.startup_msg_log` (397,813) | Check-in, online, and battery-low message history | No PK. UID, transformer, event/read times, `measurement_period`, temperature, battery, status, firmware | Operational UID / transformer namespaces | INFERRED only | Conditional: device events/status history |
| `dbo.techmician_device_list` (68) | Denormalized legacy technician-device listing (client spelling retained) | PK identity `id`; sensitive `full_name`; `device_uid` | UID matches registered namespace; name has no FK to persons | INFERRED only | Conditional; ambiguous alongside empty normalized assignments |
| `dbo.technician_assignments` (0) | Normalized person-to-device assignment model | PK identity `assignment_id`; unique `(person_id,device_uid)`; `assigned_date datetime2(7)` | `person_id → persons`; `device_uid → device_list` | DECLARED | Conditional; no rows in backup |
| `dbo.trfr_list` (185) | Device UID to short transformer-code mapping | PK identity `id`; `trfr`, `device_uid`, both NOT NULL; neither uniquely constrained | All 185 mapping UIDs occur in registration and telemetry | INFERRED to all other tables | Core: transformer association |
| `dbo.tug_report` (70,738) | Organisation, substation, asset/class and capacity/customer source data | PK identity `id`; OU, Zone, Sector, CNC, substation/location, `description`, asset/class and capacity columns | View derives a transformer match from first `description` token | INFERRED string-token join | Conditional: hierarchy/asset context |

All tables are in `dbo`. There are no user procedures, functions, triggers, sequences, synonyms, or check constraints. The only declared FKs are `persons.role_id → roles.role_id` and the two `technician_assignments` FKs noted above.

## 2. All views

| View | Underlying tables | Evidence-supported purpose | Integration usefulness |
|---|---|---|---|
| `dbo.vw_transformer_org_hierarchy` | `trfr_list`, `tug_report` | Exposes transformer/UID plus OU, Zone, Sector, CNC, and Feeder by matching the first token of `tug_report.description` to `trfr` | Conditional; convenient but carries an ungoverned text join (178 observed matches for 185 mappings) |
| `dbo.vw_installed_rtls` | `device_status`, `vw_transformer_org_hierarchy`, `master_temperature` | Installed RTL status plus latest temperature through `OUTER APPLY TOP 1 ... ORDER BY reading_timestamp DESC` | Potentially useful latest-status projection; does not repair mapping gaps or define a stable reading key |
| `dbo.vw_maximum_temperature` | `master_temperature`, `vw_transformer_org_hierarchy` | All rows that equal each UID's maximum temperature | Conditional historical analysis; can return ties and uses inferred hierarchy |
| `dbo.vw_rtl_alarms_30days` | `alarm_log`, `vw_transformer_org_hierarchy` | High-temperature alarms in rolling 30 days based on server `SYSDATETIME()` | Conditional operational report; rolling time predicate must be understood, not assumed permanent history |

## 3. Complete domain model

- **RTL/device:** `device_uid int` is the closest device/RTL identity. It is unique in `device_list`, primary-keyed in `device_status`, labelled UID by RTL-named views, and repeated through telemetry/logs. The database does not declare a separate RTL entity.
- **Registration:** `device_list` is the registered-device evidence (339 unique UIDs, plus a contact telephone field). `device_status` has the same observed UID population and provides current/last state, but lacks an FK to registration.
- **Transformer:** `trfr` is a short transformer code. `trfr_list` supplies 185 observed UID-to-code rows. It is neither a declared transformer entity key nor a foreign key target.
- **Device ↔ transformer association:** `trfr_list(device_uid,trfr)` is strongest evidence. The data is currently one-to-one on both fields, but DDL does not enforce one-to-one. `device_status.trfr`, telemetry `trfr`, and log `trfr` values are repetitions, not governed relationships.
- **Telemetry:** `master_temperature` is the canonical continuous/historical temperature stream. Its payload is one temperature value with time, UID and transformer label.
- **Events/messages:** high-temperature alarms; startup/check-in/online/battery-low messages; powerdown; sensor errors; invalid UID logging; communications/no-data; and settings uploads appear in separate log tables.
- **Communication/status:** `device_status` stores last status/time, last communication boolean, and last powerdown/startup times. `comms_alarm` stores `no_data_recorded` and last-status time.
- **Configuration:** settings-upload history carries data interval and request method. Person forwarding fields/list exist. There is no dedicated threshold/configuration master table.
- **User/account concepts:** `persons` plus `roles` is the declared account/role model. Contacts and forwarding recipients are also represented separately. Credentials/contact values exist but are out of scope for content disclosure.

## 4. Identifier model and reconciliation

Captured audit figures permit a complete set reconciliation:

| Set | Count |
|---|---:|
| `T` = distinct telemetry UIDs (`master_temperature`) | 400 |
| `R` = registered UIDs (`device_list`) | 339 |
| `T ∩ R` | 319 |
| `T - R` = telemetry-only UIDs | 81 |
| `R - T` = registered UIDs without telemetry | 20 |
| `M` = transformer-mapping UIDs (`trfr_list`) | 185 |

Arithmetic reconciles: `319 + 81 = 400` and `319 + 20 = 339`; therefore `|T ∪ R| = 420`. Every one of the 185 mapping UIDs is present in both `T` and `R`, so `M ⊆ T ∩ R`. The captured counts do **not** establish why any non-overlap exists.

Additional namespaces: surrogate identity IDs (`contact_list`, `message_forwarding_list`, `persons`, `roles`, `techmician_device_list`, `technician_assignments`, `trfr_list`, `tug_report`); user/role IDs; `source_contact_id`; user ID; phone/MSISDN; transformer code `trfr`; and the derived first token from `tug_report.description`. Only the three FKs make namespace relationships declared.

## 5. Transformer model

`trfr nvarchar(20)` is the database's transformer identifier representation. It is a short code, not a unique or foreign-key constrained entity key. The current `trfr_list` data has 185 rows, 185 distinct codes, and 185 distinct UIDs: observed 1:1 mapping. It has no duplicate code/UID rows in captured evidence.

The relationship becomes ambiguous outside `trfr_list`:

- Telemetry has 1,732 distinct `trfr` labels and 2,072 UID/transformer pairs—far more than the 185 current mapping codes.
- All 185 mapped UIDs occur in telemetry; 183 exact mapping `(UID,trfr)` pairs occur. Two do not, without evidence that they are invalid.
- 215 telemetry UIDs lack a `trfr_list` mapping (`400 - 185`); the captured evidence cannot distinguish historical devices from errors.
- 154 `device_status` rows have a null `trfr`; 185 non-null values occur, numerically aligning with mapping codes but not declared against them.
- The organisation view joins transformer code to a token extracted from an asset description. It yields 178 matches and leaves seven mapping rows without that hierarchy result.

Thus the mapping is 1:1 **within the current mapping table data**, but the broader telemetry-to-transformer relationship is ambiguous and potentially historical/many-label-per-UID. No plant hierarchy exists in the database; only the separate TUG organisational/asset attributes exist.

## 6. Telemetry model — `dbo.master_temperature`

### Raw database facts

| Property | Captured fact |
|---|---|
| Schema/table | `dbo.master_temperature` |
| Rows | 2,456,901 |
| Identifier | `device_uid int NULL`; observed non-null |
| Transformer label | `trfr nvarchar(20) NULL`; observed non-null |
| Temperature | `temperature decimal(6,2) NULL`; observed non-null |
| Time | `reading_timestamp datetime2(7) NULL` |
| Earliest / latest | 2004-01-01 00:00:00 / 2026-09-17 08:29:00 |
| Plausible historical candidate range | 2013-09-14 16:13:00 through 2026-09-17 08:29:00 when the audit excludes values before 2010 and later than backup date; this is an analytical qualification, not a database rule |
| Null behaviour | 29 null timestamps; 0 null temperature, UID, or transformer values |
| Duplicates | 330 duplicated `(device_uid,reading_timestamp)` groups; 336 surplus rows |
| Sampling | 30-minute adjacent interval dominates (1,489,688); 29/31, 10-minute, ~24-hour and many other intervals occur |
| Value range | -3.00 to 493.00; 1,383 values >150, 370 >200, one exactly 493 |
| Integrity | No PK, unique constraint, FK, or user index |
| Timezone | Unknown; `datetime2(7)` contains no offset |

### Potential application filtering rules — not decided

The database provides no rule that says to exclude null timestamps, dates before 2010, negative values, high values, duplicate rows, or irregular intervals. Those are possible future filtering/deduplication/freshness decisions only. No rule is adopted by this model.

## 7. Other measurements

The captured complete column catalogue supports the audit conclusion: no production telemetry column was found for line voltage, current, active power, reactive power, power factor, frequency, or energy. `tug_report.ohl_substation_voltage_group_desc` is an asset classification field, not time-series line-voltage telemetry.

`battery_voltage decimal(10,2)` occurs only in `alarm_log`, `invalid_uid_log` (empty), `powerdown_log`, `sensor_error_log`, and `startup_msg_log`. These are event/message records with context values; no independent battery series table, battery timestamped cadence, or continuous electrical-measurement contract is evidenced. It must not automatically be treated as continuous electrical telemetry.

## 8. Data quality classification

| Observation | Classification | Evidence / consequence |
|---|---|---|
| 29 null telemetry timestamps | FACT | Permitted by DDL and observed; handling policy unknown |
| 10 readings before 2010, earliest 2004; sensor error at 2000 | LIKELY DATA QUALITY ISSUE | Sentinel/placeholder candidate, not proven |
| -3 to 493 temperature values | FACT | Observed range |
| Values >150 / >200 / 493 | LIKELY DATA QUALITY ISSUE | Outlier candidates; limits are not established by database |
| 330 duplicate UID/time groups, 336 surplus rows | FACT | No uniqueness enforcement; duplicate-selection policy unknown |
| Irregular cadence, long gaps and same-time rows | FACT | ~30-minute cadence is dominant, not guaranteed |
| 81 telemetry-only UIDs | FACT | Meaning is UNKNOWN REQUIRING CLIENT CLARIFICATION |
| 20 registered UIDs without telemetry | FACT | Meaning is UNKNOWN REQUIRING CLIENT CLARIFICATION |
| 215 telemetry UIDs without transformer mapping | FACT | Meaning is UNKNOWN REQUIRING CLIENT CLARIFICATION |
| Two mapping pairs absent as exact telemetry pairs | FACT | Historical reassignment versus quality issue is UNKNOWN |
| Seven mappings lacking TUG view join | FACT | String-rule validity is UNKNOWN REQUIRING CLIENT CLARIFICATION |
| `device_status.trfr` null for 154 devices | FACT | Whether missing mapping/status is expected is UNKNOWN |
| Empty normalized assignments vs 68 legacy rows | FACT | Canonical technician-assignment source is UNKNOWN |

## 9. Database capability matrix

| Capability | Database support | Evidence |
|---|---|---|
| Temperature monitoring | SUPPORTED | `master_temperature` plus temperature-bearing logs |
| Transformer identification | PARTIALLY SUPPORTED | `trfr` / `trfr_list`, no enforced transformer entity key |
| RTL/device identification | SUPPORTED | unique `device_list.device_uid`, PK `device_status.device_uid`, RTL views |
| Device-transformer mapping | PARTIALLY SUPPORTED | 185 observed 1:1 `trfr_list` rows, no DDL enforcement and incomplete telemetry coverage |
| Historical trends | SUPPORTED | 2.456M timestamped temperature rows |
| Latest reading | PARTIALLY SUPPORTED | `vw_installed_rtls` computes latest temperature; no stable reading key/uniqueness |
| Device communication/status | SUPPORTED | `device_status`, `comms_alarm`, startup messages |
| Battery information | PARTIALLY SUPPORTED | battery voltage only in event/message tables |
| Alarm/event information | SUPPORTED | alarm, startup, powerdown, sensor error, communication logs |
| Alarm acknowledgement | NOT FOUND | No acknowledgement object/field captured |
| Activation/deactivation | NOT FOUND | No lifecycle/command object captured |
| Technician assignment | AMBIGUOUS | Empty normalized table; 68-row denormalized listing |
| User management | PARTIALLY SUPPORTED | persons/contacts/credential hash exist; lifecycle semantics not evidenced |
| Role management | SUPPORTED | roles table and declared persons FK |
| Threshold configuration | NOT FOUND | No threshold master/configuration table captured |
| Voltage | NOT FOUND | No line-voltage telemetry column |
| Current | NOT FOUND | No current telemetry column |
| Active power | NOT FOUND | No active-power telemetry column |
| Reactive power | NOT FOUND | No reactive-power telemetry column |
| Power factor | NOT FOUND | No power-factor telemetry column |
| Frequency | NOT FOUND | No frequency telemetry column |
| Energy | NOT FOUND | No energy telemetry column |

## 10. Client questions, prioritized by integration impact

1. Which source and rule establish the canonical active device population: `device_list`, `device_status`, `trfr_list`, or another process? How should the 81 telemetry-only and 20 registered-without-telemetry UIDs be treated?
2. Is `trfr_list` the authoritative current device-to-transformer association? How should historical or conflicting UID/`trfr` values in telemetry be resolved, including the two exact-pair mismatches?
3. Is the `tug_report.description` first-token join a supported, stable transformer-to-asset relationship? If not, what authoritative asset key joins it to transformer/device data?
4. What timezone is used for all `datetime2` timestamps, and which timestamp is authoritative when an event has both `event_timestamp` and `reading_timestamp`?
5. Which raw-reading validity, deduplication, and freshness rules are client-approved, particularly for null timestamps, pre-2010 values, -3/493 values, duplicate UID/timestamps, and irregular cadence?
6. Which technician-assignment representation is canonical: the empty normalized table or the populated legacy listing?
7. Are alarm/communication/startup/powerdown/sensor-error logs immutable history, current-state projections, or both; and is acknowledgement handled outside this database?

## 11. Final database model

```text
                       dbo.tug_report (asset / organisation context)
                                    │
                 inferred description-token join (178 mapping matches)
                                    │
dbo.trfr_list (185 observed UID ↔ trfr pairs; no business-key constraint)
                  │                         │
                  │ inferred UID / trfr      │ inferred UID / trfr
                  ▼                         ▼
 dbo.device_list (339 registered UIDs)   dbo.master_temperature (2,456,901)
                  │                         │
                  │ inferred UID             ├── historical temperature readings
                  ▼                         │    (400 UIDs; UID/trfr values not constrained)
 dbo.device_status (339 last-status rows) │
                                            └── UID/trfr-repeating event/message logs
                                                alarm | startup | powerdown | sensor-error |
                                                comms | settings upload | invalid UID

 dbo.roles ── declared FK ──< dbo.persons
 dbo.persons + dbo.device_list ── declared FKs ──< dbo.technician_assignments (empty)
 dbo.techmician_device_list is a separate, inferred legacy assignment representation.
```

The arrows labelled inferred are value relationships, not database constraints. No application integration is implied or designed here.
