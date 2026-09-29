# REAL-DB-AUDIT-02 — Schema and object catalogue

All application objects are in `dbo`. Lengths below are SQL Server declared lengths: `nvarchar` is shown in characters (the catalog `max_length` in bytes is half this value). `datetime2(7)` is eight-byte storage.

## Objects

Views:

- `dbo.vw_installed_rtls` — device status plus inferred organisation fields and latest temperature.
- `dbo.vw_maximum_temperature` — every per-device maximum temperature row plus inferred organisation fields.
- `dbo.vw_rtl_alarms_30days` — alarms where `event_timestamp >= DATEADD(DAY,-30,SYSDATETIME())`.
- `dbo.vw_transformer_org_hierarchy` — `trfr_list` joined to `tug_report` by the first token of `tug_report.description`.

There are no user stored procedures, scalar/table functions, triggers, sequences, synonyms, or check constraints.

## Columns

`NULL` means nullable; `NOT NULL` means required. `I` marks identity; defaults are shown where present.

| Table | Columns in ordinal order |
|---|---|
| `alarm_log` | `device_uid int NULL`; `trfr nvarchar(20) NULL`; `event_timestamp datetime2(7) NULL`; `reading_timestamp datetime2(7) NULL`; `temperature decimal(10,2) NULL`; `is_max_reading bit NULL`; `battery_voltage decimal(10,2) NULL`; `status nvarchar(40) NULL`; `firmware nvarchar(20) NULL` |
| `client_id` | `event_timestamp datetime2(7) NULL`; `full_name nvarchar(120) NULL`; `api_key nvarchar(100) NULL` |
| `comms_alarm` | `device_uid int NULL`; `trfr nvarchar(20) NULL`; `last_status_timestamp datetime2(7) NULL`; `no_data_recorded bit NULL` |
| `contact_list` | `id int NOT NULL I`; `full_name nvarchar(60) NOT NULL`; `cell_number nvarchar(20) NOT NULL`; `designation nvarchar(30) NOT NULL`; `email_address nvarchar(100) NOT NULL` |
| `device_list` | `device_uid int NULL`; `cell_number nvarchar(25) NULL` |
| `device_status` | `device_uid int NOT NULL`; `trfr nvarchar(40) NULL`; `last_status nvarchar(80) NULL`; `last_status_timestamp datetime2(7) NULL`; `last_comms_ok bit NULL`; `last_powerdown_timestamp datetime2(7) NULL`; `last_startup_timestamp datetime2(7) NULL` |
| `invalid_uid_log` | `device_uid int NULL`; `trfr nvarchar(20) NULL`; `reading_timestamp datetime2(7) NULL`; `temperature decimal(10,2) NULL`; `is_max_reading bit NULL`; `battery_voltage decimal(10,2) NULL`; `status nvarchar(40) NULL`; `firmware nvarchar(20) NULL` |
| `master_temperature` | `reading_timestamp datetime2(7) NULL`; `temperature decimal(6,2) NULL`; `trfr nvarchar(20) NULL`; `device_uid int NULL` |
| `message_forwarding_list` | `id int NOT NULL I`; `full_name nvarchar(60) NOT NULL`; `cell_number nvarchar(20) NOT NULL`; `designation nvarchar(30) NOT NULL` |
| `persons` | `person_id int NOT NULL I`; `source_contact_id int NULL`; `full_name nvarchar(120) NULL`; `cell_number nvarchar(40) NULL`; `email_address nvarchar(200) NULL`; `role_id int NULL`; `user_id nvarchar(60) NULL`; `password_hash nvarchar(256) NULL`; `personal_number nvarchar(40) NULL`; `msisdn_rtl_client nvarchar(40) NULL`; `notification_type nvarchar(20) NULL`; `message_forwarding_enabled bit NOT NULL DEFAULT ((0))`; `message_forwarding_enabled_at datetime2(7) NULL` |
| `powerdown_log` | `device_uid int NULL`; `trfr nvarchar(20) NULL`; `event_timestamp datetime2(7) NULL`; `measurement_period nvarchar(10) NULL`; `reading_timestamp datetime2(7) NULL`; `temperature decimal(10,2) NULL`; `is_max_reading bit NULL`; `battery_voltage decimal(10,2) NULL`; `status nvarchar(40) NULL`; `firmware nvarchar(20) NULL` |
| `roles` | `role_id int NOT NULL I`; `role_name nvarchar(60) NOT NULL` |
| `sensor_error_log` | `device_uid int NULL`; `trfr nvarchar(20) NULL`; `reading_timestamp datetime2(7) NULL`; `temperature decimal(10,2) NULL`; `is_max_reading bit NULL`; `battery_voltage decimal(10,2) NULL`; `status nvarchar(40) NULL`; `firmware nvarchar(20) NULL` |
| `settings_upload_log` | `event_timestamp datetime2(7) NULL`; `device_uid int NULL`; `trfr nvarchar(20) NULL`; `data_interval nvarchar(10) NULL`; `full_name nvarchar(120) NULL`; `request_method nvarchar(40) NULL` |
| `startup_msg_log` | `device_uid int NULL`; `trfr nvarchar(20) NULL`; `event_timestamp datetime2(7) NULL`; `measurement_period nvarchar(10) NULL`; `reading_timestamp datetime2(7) NULL`; `temperature decimal(10,2) NULL`; `is_max_reading bit NULL`; `battery_voltage decimal(10,2) NULL`; `status nvarchar(40) NULL`; `firmware nvarchar(20) NULL` |
| `techmician_device_list` | `id int NOT NULL I`; `full_name nvarchar(60) NOT NULL`; `device_uid int NOT NULL` |
| `technician_assignments` | `assignment_id int NOT NULL I`; `person_id int NOT NULL`; `device_uid int NOT NULL`; `assigned_date datetime2(7) NOT NULL DEFAULT `(sysdatetime())` |
| `trfr_list` | `id int NOT NULL I`; `trfr nvarchar(20) NOT NULL`; `device_uid int NOT NULL` |
| `tug_report` | `id int NOT NULL I`; `operating_unit nvarchar(60) NOT NULL`; `zone nvarchar(40) NOT NULL`; `sector nvarchar(40) NOT NULL`; `cnc nvarchar(40) NOT NULL`; `ohl_substation_description nvarchar(100) NOT NULL`; `ohl_substation_location nvarchar(20) NOT NULL`; `location nvarchar(20) NOT NULL`; `description nvarchar(80) NOT NULL`; `ohl_substation_standard_label nvarchar(60) NULL`; `ohl_substation_voltage_group_desc nvarchar(20) NOT NULL`; `ohl_substation_class_description nvarchar(10) NOT NULL`; `class_structure_id bigint NOT NULL`; `class_description nvarchar(30) NOT NULL`; `kva int NULL`; `lpu int NULL`; `spu int NULL`; `ppu int NULL`; `total_customers int NOT NULL` |

No computed columns were found. Only the five tables marked `I` above have identities.

## Keys, constraints, and indexes

Primary keys: `contact_list(id)`, `device_status(device_uid)`, `message_forwarding_list(id)`, `persons(person_id)`, `roles(role_id)`, `techmician_device_list(id)`, `technician_assignments(assignment_id)`, `trfr_list(id)`, and `tug_report(id)`.

Unique constraints: `device_list(device_uid)`, `roles(role_name)`, and `technician_assignments(person_id, device_uid)`.

Declared foreign keys (all `NO ACTION` on update/delete):

- `persons.role_id` → `roles.role_id`.
- `technician_assignments.device_uid` → `device_list.device_uid`.
- `technician_assignments.person_id` → `persons.person_id`.

The corresponding clustered primary-key indexes and nonclustered unique indexes are the complete user-index inventory. The remaining tables—including `master_temperature`—have no declared primary key, unique constraint, foreign key, or user index.
