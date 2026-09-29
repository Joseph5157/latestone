# REAL-DB-AUDIT-02 — Table catalogue

Samples were inspected under read-only access. To avoid copying client operational/person data, this catalogue gives each representative row's **redacted shape** rather than values. Sensitive columns are explicitly noted.

| Table | Rows | Evidence-backed purpose | Identifier / relationship evidence | Representative redacted row shape |
|---|---:|---|---|---|
| `alarm_log` | 3,346 | High-temperature alarm history | `device_uid`, `trfr`; no FK | UID, transformer, event/read timestamp, temperature, max flag, battery voltage, status, firmware |
| `client_id` | 3 | API/client identity history | no key; contains `api_key` | event time, full name, `[REDACTED API key]` |
| `comms_alarm` | 132 | Communication/no-data alarm state/history | `device_uid`, `trfr`; no FK | UID, transformer, last status time, no-data flag |
| `contact_list` | 8 | Contact directory | PK `id`; no FK | id, `[REDACTED name]`, `[REDACTED phone]`, designation, `[REDACTED email]` |
| `device_list` | 339 | Registered RTL/device directory | unique `device_uid`; referenced by assignment FK | UID, `[REDACTED phone]` |
| `device_status` | 339 | Current/last status per registered UID | PK `device_uid`; inferred same UID as device list | UID, transformer (nullable), last status/time, comms flag, powerdown/startup times |
| `invalid_uid_log` | 0 | Rejected reading/event records for invalid UIDs | `device_uid`, `trfr`; no FK | UID, transformer, reading time, temperature, flags/status/firmware |
| `master_temperature` | 2,456,901 | Canonical temperature-reading history | `device_uid` + `trfr`, neither declared as key | reading time, temperature, transformer code, UID |
| `message_forwarding_list` | 1 | Message-forwarding recipient list | PK `id`; no FK | id, `[REDACTED name]`, `[REDACTED phone]`, designation |
| `persons` | 8 | Application users/persons and notification preferences | PK `person_id`; `role_id` has FK | ids, `[REDACTED identity/contact]`, role ID, `[REDACTED password hash]`, forwarding fields |
| `powerdown_log` | 719 | RTL power-down events | `device_uid`, `trfr`; no FK | UID, transformer, event/reading time, period, temperature, battery, status, firmware |
| `roles` | 3 | Role lookup | PK `role_id`, unique role name | id, role name |
| `sensor_error_log` | 1,177 | Sensor-error event history | `device_uid`, `trfr`; no FK | UID, transformer, reading time, temperature, max flag, battery, status, firmware |
| `settings_upload_log` | 3,400 | Device configuration/upload audit | `device_uid`, `trfr`; no FK | event time, UID, transformer, interval, `[REDACTED name]`, request method |
| `startup_msg_log` | 397,813 | RTL check-in/startup/battery messages | `device_uid`, `trfr`; no FK | UID, transformer, event/reading time, period, temperature, battery, status, firmware |
| `techmician_device_list` | 68 | Legacy/denormalized technician-to-device listing (table spelling is client artifact) | no FK; UID and name are implied references | id, `[REDACTED technician]`, UID |
| `technician_assignments` | 0 | Normalized technician-to-device assignment table | PK and unique `(person_id,device_uid)`; two FKs | assignment id, person ID, device UID, assigned time |
| `trfr_list` | 185 | Explicit one-to-one transformer-code to device UID mapping | PK surrogate; no unique constraint but actual values are unique | id, transformer code, UID |
| `tug_report` | 70,738 | Source organisational/asset hierarchy data | PK `id`; view uses inferred text-token match | id, OU/zone/sector/CNC, substation/location, asset description/class, capacity/customer fields |

## Table-level observations

- Nullable fields are exactly those marked `NULL` in [SCHEMA_CATALOG.md](SCHEMA_CATALOG.md). In particular, the measurement table permits null timestamp, UID, transformer, and temperature; observed counts are in [DATA_QUALITY.md](DATA_QUALITY.md).
- `device_status.trfr` is null for 154 of 339 records; it contains 185 distinct non-null transformer codes, matching the `trfr_list` mapping count.
- `trfr_list` has 185 rows and in this backup both `trfr` and `device_uid` are individually distinct, although the database does not enforce either uniqueness.
- `technician_assignments` is structurally referentially complete but empty. `techmician_device_list` has 68 rows across five distinct technician-name values and 68 distinct UIDs, and is not protected by FKs.
- The user/identity tables were inspected only for schema, counts, declared relationships, and non-sensitive categorical values. Password hashes, API keys, names, telephone numbers, emails, personal numbers, and MSISDNs are deliberately excluded from all audit outputs.
