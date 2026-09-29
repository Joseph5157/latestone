# SQL Server capability catalog

Status: factual SELECT-only audit, 2026-09-29. **FACT** means system-catalog evidence; interpretations are labelled. No contact, API-key, password-hash, or cellular values are reproduced.

## Safety and inventory

`DATABASEPROPERTYEX(...,'Updateability') = READ_ONLY`; `HAS_PERMS_BY_NAME(...,'UPDATE') = 0`. The 19 tables and four views below were inspected. Catalog FKs exist only for `persons.role_id` and `technician_assignments` to `persons`/`device_list`; many apparent relations are therefore inference, not enforced.

| Object(s) | Rows | FACT / usable capability | Direction and limitation |
|---|---:|---|---|
| `master_temperature` | 2,456,901 | `reading_timestamp datetime2(7)`, `temperature decimal(6,2)`, `trfr`, `device_uid`; heap, no key/index | ADAPT: source temperature only; SAST per ADR-029; ties must stay ambiguous. |
| `device_list` | 339 | UID unique; cellular contact excluded | DIRECT registration directory; no state/mapping. |
| `trfr_list` | 185 | identity PK, `trfr`, `device_uid`; no FK/unique mapping constraint | REVIEW_REQUIRED for operational assignment authority; it is reference evidence, not authoritative. |
| `device_status`, `comms_alarm` | 339 / 132 | UID PK status record; source status/timestamps/comms bit; no status semantics | ADAPT, client decision required for offline/status meaning. |
| `alarm_log`, `powerdown_log`, `sensor_error_log`, `startup_msg_log`, `invalid_uid_log` | 3,346 / 719 / 1,177 / 397,813 / 0 | UID, transformer, source times, temperature/battery/status/firmware; powerdown/startup include period | ADAPT raw event ingestion. No acknowledgement or application severity lifecycle. |
| `persons`, `roles` | 8 / 3 | person identity, role, user/password-hash, notification/forwarding flags; role FK and unique role name | REVIEW_REQUIRED: security/authentication contract and hash algorithm must be approved; never copy hashes blindly. |
| `technician_assignments` | 0 | person/device/date, FK both, unique person+device | ADAPT prospective assignment only after identity, UID and workflow confirmation; `techmician_device_list` (68) is legacy/unenforced reference evidence. |
| `settings_upload_log` | 3,400 | UID/transformer/interval/actor/request method | ADAPT source history only; no command lifecycle. |
| `message_forwarding_list`, `contact_list` | 1 / 8 | contact fields | REVIEW_REQUIRED; sensitive delivery/contact data, ownership and consent unknown. |
| `client_id` | 3 | event/name/API key | REVIEW_REQUIRED; security-sensitive, no direct app use. |
| `tug_report` | 70,738 | organisational/transformer reference attributes | ADAPT only after client validates its business keys/currentness. |
| `vw_installed_rtls` | — | hierarchy + UID + latest source data/status | ADAPT reporting projection; definition/currentness needs client confirmation. |
| `vw_maximum_temperature` | — | hierarchy/installation/max temperature | ADAPT historical report, not current telemetry. |
| `vw_rtl_alarms_30days` | — | hierarchy/UID/alarm source facts | ADAPT read projection; no acknowledgement. |
| `vw_transformer_org_hierarchy` | — | transformer/UID/org hierarchy | ADAPT/reference only; does not settle canonical hierarchy. |

All source log columns are nullable and no source timestamp timezone offset exists. **FACT:** per ADR-029, source timestamps are interpreted as South African Standard Time (SAST, UTC+2). Representative source values were not exported. Client SQL Server contains no observed complete application audit log, temperature-limit configuration, command state/acknowledgement, or durable alarm acknowledgement. Existing contact/forwarding structures mean application notification preference storage remains REVIEW_REQUIRED rather than a confirmed gap.

## Boundary for later design

**FACT:** assignment/hierarchy, identity/roles, technician assignment and notification/forwarding all have relevant existing SQL Server structures. Their authority and permitted operational use are unknown. No new tables for those capabilities are proposed by this audit. The stronger likely application-owned candidates are application audit, alarm acknowledgement/response, application configuration, and — only if production commands are approved — command lifecycle/action state.
