# REAL-DB-AUDIT-02 — Data quality observations

- `master_temperature` permits all four fields to be null; 29 rows have a null timestamp. Temperature, UID, and transformer are non-null in observed data.
- Ten temperature rows predate 2010 (nine UIDs); the absolute earliest is 2004-01-01. `sensor_error_log` also has an apparent 2000-01-01 timestamp. These are likely placeholder/sentinel candidates, but that conclusion requires client confirmation.
- Observed temperature range is -3.00 to 493.00 °C. There are 1,383 values above 150, 370 above 200, and one exactly 493. These are candidates for invalid/outlier investigation; the audit does not alter or discard them.
- 330 duplicate `(device_uid, reading_timestamp)` groups contain 336 surplus rows. No table constraint prevents them.
- The table has no primary key, FK, unique constraint, or index, so readings are neither referentially governed nor physically indexed by the visible user-index inventory.
- The intended cadence appears approximately 30 minutes, but the interval distribution has extensive 29/31 minute variation, 10-minute reads, and long gaps. No supported maximum-gap rule exists in the database.
- `device_status.trfr` is null for 154 of 339 devices. Its 185 non-null distinct codes align numerically with the transformer mapping count but are not constrained to it.
- `trfr_list` happens to be one-to-one by both code and UID in this backup, but neither business field is unique in DDL.
- The view hierarchy's text parsing joins only 178 `trfr_list` rows to `tug_report`; seven mappings do not produce an organisation-hierarchy join under that view rule.
- All 8 person rows have null `notification_type`; user/auth tables contain sensitive fields and were redacted from documents.
- `technician_assignments` is empty while the separate typo-named `techmician_device_list` carries 68 denormalized name-to-UID rows. The two assignment models are not reconciled by declared relationships.
