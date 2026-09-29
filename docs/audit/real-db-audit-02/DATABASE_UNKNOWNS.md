# REAL-DB-AUDIT-02 — Unresolved questions

The following cannot be resolved from database evidence alone:

1. Whether `device_uid` identifies an RTL, another logger type, or an installed device more broadly; views call it `UID` and use RTL names, but no formal entity definition exists.
2. Whether telemetry-only UIDs and extra transformer labels are retired equipment, historical imports, data errors, or valid non-registered devices.
3. The intended canonical mapping when a UID appears with several `trfr` values, and the reason for the two mapping pairs absent from telemetry.
4. Timestamp timezone. `datetime2(7)` stores no offset and no timezone/configuration metadata establishes UTC or local time.
5. The operational meaning and unit conventions for all status values and `measurement_period`/`data_interval` strings.
6. Whether the source-of-truth organisation/asset system is `tug_report` and whether its description-token join is stable enough for integration.
7. Whether `High Temp.`, `Battery Low`, `Sensor Error`, `Powerdown`, and communication/no-data rows are current state, immutable history, or both.
8. Threshold values, alarm acknowledgement workflow, command execution semantics, notification delivery behavior, and retention policies. No dedicated threshold, acknowledgement, command, or notification-history tables were found.
