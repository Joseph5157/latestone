# REAL-DB-AUDIT-02 — Telemetry and time-series analysis

## Measurement sources

| Source | Rows | Measurements | Time / identifier | Findings |
|---|---:|---|---|---|
| `master_temperature` | 2,456,901 | `temperature decimal(6,2)` | `reading_timestamp datetime2(7)`, `device_uid int`, `trfr nvarchar(20)` | Primary historical reading stream; 400 distinct UIDs, 1,732 distinct transformer labels |
| `alarm_log` | 3,346 | temperature, battery voltage, max-reading flag | event and reading timestamps, UID, transformer | All observed status values are `High Temp.` |
| `startup_msg_log` | 397,813 | temperature, battery voltage, max-reading flag | event and reading timestamps, UID, transformer | Statuses: Check-in 332,079; Online 58,060; Battery Low 7,674 |
| `powerdown_log` | 719 | temperature, battery voltage, max-reading flag | event and reading timestamps, UID, transformer | Status `Powerdown` |
| `sensor_error_log` | 1,177 | temperature, battery voltage, max-reading flag | reading timestamp, UID, transformer | Status `Sensor Error` |
| `invalid_uid_log` | 0 | same shape as event logs | reading timestamp, UID, transformer | Empty in this backup |

`device_status` and `comms_alarm` are status sources, not measurements: they contain last-status timestamps / communication flags rather than a measurement value. `settings_upload_log` is configuration/audit data.

## Measurement coverage

The only primary process measurement present is **temperature**. The only other measured numeric payload found is **battery voltage** in event/message logs. The backup contains no columns for voltage, current, active power, reactive power, power factor, frequency, energy, vibration, pressure, humidity, or similar electrical/process telemetry.

No units table or explicit unit field was found. View labels call temperature `Temperature (C)` / `Maximum Temperature (C)` and battery `Battery(V)`, which is the evidence for Celsius and volts. Do not infer further units.

## Master temperature stream

| Measure | Result |
|---|---|
| Total rows | 2,456,901 |
| Distinct UIDs | 400 |
| Distinct transformer labels | 1,732 |
| Distinct UID/transformer pairs | 2,072 |
| Earliest timestamp | 2004-01-01 00:00:00 (see quality qualification) |
| Latest timestamp | 2026-09-17 08:29:00 |
| Valid-range earliest (2010–backup date) | 2013-09-14 16:13:00 |
| Null timestamps / temperature / UID / transformer | 29 / 0 / 0 / 0 |
| Temperature min / max / mean | -3.00 / 493.00 / 34.197436 |
| Duplicate UID+timestamp groups / surplus rows | 330 / 336 |
| Dominant adjacent interval | 30 minutes (1,489,688 intervals) |
| Other common adjacent intervals | 31 min (351,955), 29 min (134,044), 10 min (89,246), ~24h (1,445 min: 69,447) |

The stream has no constraint or index enforcing a unique reading identity. Intervals are calculated only between successive readings for the same UID; this supports a roughly 30-minute intended cadence but also demonstrates substantial irregularity, including repeated same-time rows, short gaps, and multi-day gaps. Timestamps are `datetime2(7)` without offset. The database alone provides no evidence whether values are UTC, local time, or another timezone.

## Event-stream ranges

| Table | Earliest | Latest | Distinct UIDs |
|---|---|---|---:|
| `alarm_log` | 2020-12-04 15:47:55 | 2026-08-17 10:31:14 | 122 |
| `comms_alarm` | 2023-02-02 20:20:00 | 2026-08-24 21:01:00 | 132 |
| `powerdown_log` | 2017-11-07 00:15:49 | 2025-03-03 14:11:27 | 40 |
| `sensor_error_log` | 2000-01-01 00:00:00 | 2026-05-24 13:54:00 | 113 |
| `settings_upload_log` | 2020-03-17 08:22:07 | 2025-08-27 08:26:43 | 366 |
| `startup_msg_log` | 2017-06-07 16:06:43 | 2026-08-26 13:45:27 | 406 |

No timezone conversion was applied during inspection.
