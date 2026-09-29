# REAL-DB-AUDIT-02 — Final database audit

## 1. Database overview

The client-supplied `RTL.bak` is a SQL Server backup for database `RTL`, not the historical PostgreSQL database described in prior repository documents. It contains two verified full backup sets; the newest set (position 2, 2026-09-27) restored successfully as isolated, read-only `RTL_AUDIT_02`. The complete backup/restore evidence is in [DATABASE_OVERVIEW.md](DATABASE_OVERVIEW.md).

## 2–3. Object and table catalogues

The database has 19 `dbo` user tables, 4 views, no user stored procedures/functions/triggers/sequences/synonyms, three declared FKs, and no check constraints. The complete column/type/nullability/default/identity/computed-column, constraint, and index catalogue is in [SCHEMA_CATALOG.md](SCHEMA_CATALOG.md). The 19-table row-count/purpose/relationship/sample-shape catalogue is in [TABLE_CATALOG.md](TABLE_CATALOG.md).

## 4. Relationship model

Only user/role and normalized technician-assignment relationships are declared. Device, transformer, telemetry, events, and asset hierarchy relationships are identifier/value matches, not FKs. [RELATIONSHIP_MAP.md](RELATIONSHIP_MAP.md) separates declared from inferred links.

## 5–7. Transformer, device/RTL, and telemetry models

- The database calls the transformer value `trfr`, a short code that occurs in readings, logs, status, and a 185-row mapping table.
- The closest device/RTL key is integer `device_uid`, used by device tables, logs, reading data, mappings, and views named for RTLs.
- `trfr_list` is the strongest device-to-transformer mapping: 185 currently one-to-one code/UID rows, without DDL enforcement.
- `master_temperature` is the canonical telemetry history: 2,456,901 temperature rows. Event/message logs additionally carry battery voltage and contextual temperature; no other requested electrical metrics exist.
- `tug_report` provides OU/Zone/Sector/CNC/substation/asset context. Its connection to a transformer is a view's text-token comparison, not a relational key.

## 8–10. Identifiers, time series, and operational/support evidence

The UIDs and transformer codes do not describe one complete consistent population: 400 telemetry UIDs, 339 device/status UIDs, and 185 mapped transformer UIDs. There are 81 telemetry-only and 20 registered-without-telemetry UIDs. Full identifier findings are in [IDENTIFIER_ANALYSIS.md](IDENTIFIER_ANALYSIS.md); cadence, timestamps, telemetry columns and event stream ranges are in [TELEMETRY_ANALYSIS.md](TELEMETRY_ANALYSIS.md).

Operational evidence is present:

| Capability | Evidence | Assessment |
|---|---|---|
| High-temperature alarms/history | `alarm_log`, `vw_rtl_alarms_30days` | PRESENT |
| Communication/no-data state | `comms_alarm`, `device_status.last_comms_ok` | PRESENT |
| Startup/online/battery-low messages | `startup_msg_log` | PRESENT |
| Powerdown and sensor-error history | `powerdown_log`, `sensor_error_log` | PRESENT |
| Device configuration/upload history | `settings_upload_log` | PRESENT |
| Contacts, users, roles | `contact_list`, `persons`, `roles` | PRESENT; sensitive values redacted |
| Technician assignment | normalized empty `technician_assignments`; 68-row legacy `techmician_device_list` | AMBIGUOUS |
| Message-forwarding data | `message_forwarding_list`, person forwarding fields | PRESENT |
| API/client credential data | `client_id.api_key` | PRESENT; redacted |
| Threshold/configuration master | no dedicated table discovered | NOT FOUND |
| Alarm acknowledgement | no acknowledgement column/table discovered | NOT FOUND |
| Commands/activation/deactivation | no dedicated command/lifecycle table discovered | NOT FOUND |
| Notification/SMS/email delivery history | recipient/preference fields exist; no delivery history found | AMBIGUOUS |
| Audit/history | multiple specialized logs, no general audit table | PRESENT (specialized only) |

## 11–14. Quality, orphans, and unknowns

There are timestamp, outlier, duplicate, mapping coverage, nullability, and assignment-model concerns, but no corrective action was taken. See [DATA_QUALITY.md](DATA_QUALITY.md). The evidence cannot resolve terminology boundaries, mapping discrepancies, timestamp timezone, or operational semantics; these are listed in [DATABASE_UNKNOWNS.md](DATABASE_UNKNOWNS.md).

## Audit boundary

This audit intentionally makes **no comparison to the application UI**, proposes no redesign, adds no SQL Server support, makes no migrations, and changes no client database data or schema. Integration is explicitly deferred pending review.
