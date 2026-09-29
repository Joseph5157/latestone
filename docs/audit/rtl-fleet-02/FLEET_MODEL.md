# RTL-FLEET-02 — Fleet model

Status: factual local restored-RTL inspection, 2026-09-29. This is source
evidence only; it does not select a canonical monitored fleet.

## UID sets

| Set/intersection | Count |
|---|---:|
| `TELEMETRY` = distinct `master_temperature.device_uid` | 400 |
| `REGISTERED` = `device_list.device_uid` | 339 |
| `MAPPED` = `trfr_list.device_uid` | 185 |
| `REGISTERED ∩ TELEMETRY` / `REGISTERED - TELEMETRY` / `TELEMETRY - REGISTERED` | 319 / 20 / 81 |
| `REGISTERED ∩ MAPPED` / `REGISTERED - MAPPED` / `MAPPED - REGISTERED` | 185 / 154 / 0 |
| `TELEMETRY ∩ MAPPED` / `TELEMETRY - MAPPED` / `MAPPED - TELEMETRY` | 185 / 215 / 0 |
| `REGISTERED ∩ TELEMETRY ∩ MAPPED` | 185 |
| Mapping UID in neither registered nor telemetry | 0 |

Thus `MAPPED` is an observed subset of the 319 UID intersection; it does not
explain population differences or establish an operational fleet.

## `device_list` registration model

| Exact column | Type / nullable | Observed facts |
|---|---|---|
| `device_uid` | `int NULL` | 339 rows, distinct UIDs, and no nulls; unique constraint `UQ_device_list_device_uid`. |
| `cell_number` | `nvarchar(25) NULL` | 339 distinct non-null values. It is contact data and is deliberately omitted from samples and repository output. |

The table is a heap with its UID unique constraint. It has no timestamp,
status, activation, transformer, or communication column. Database evidence
therefore supports only: a registered device is a row in this UID directory.
`device_status` has the same 339 UIDs (symmetric difference zero), but no
foreign key declares that relationship.

## `trfr_list` mapping model

| Exact column | Type / nullable | Observed facts |
|---|---|---|
| `id` | `int NOT NULL` | Clustered surrogate primary key; 185 distinct, no nulls. |
| `trfr` | `nvarchar(20) NOT NULL` | 185 distinct, no nulls. |
| `device_uid` | `int NOT NULL` | 185 distinct, no nulls. |

All 185 rows have unique UID and code: observed one-to-one data, not a
business uniqueness constraint or FK. It has no timestamps/descriptive
fields, so it is not authoritative by database evidence alone. Telemetry has
1,732 distinct transformer labels and 2,072 distinct UID/transformer pairs.
Only 183 current mapping pairs occur exactly in telemetry; 29042/`EMV35` and
29598/`TEST29598` do not. This could be history or a quality issue.

## Representative non-sensitive records

| Category | UID | Necessary factual fields |
|---|---:|---|
| registered + telemetry + mapped | 29501 | Mapping/status code `PINS144`; latest telemetry 2026-09-17 01:57; startup 2026-08-26 00:08:46; status/comms null. |
| registered + telemetry + unmapped | 29006 | No mapping/status code; latest telemetry 2017-10-20 05:41; startup 2017-10-20 08:36:29. |
| registered + no telemetry | 29504 | No mapping/status code; observed status timestamp/comms fields null. |
| telemetry-only | 29002 | No registration/status/mapping row; latest telemetry 2021-02-11 07:25. |
| mapped unusual pair | 29598 | Mapping/status code `TEST29598`, `last_comms_ok=0`, latest telemetry 2021-12-30 01:41; current pair absent from telemetry. |

## Status and communication model

`device_status` is keyed by UID and has exact columns `device_uid int NOT
NULL`, `trfr nvarchar(40) NULL`, `last_status nvarchar(80) NULL`,
`last_status_timestamp datetime2 NULL`, `last_comms_ok bit NULL`,
`last_powerdown_timestamp datetime2 NULL`, and `last_startup_timestamp
datetime2 NULL`.

| Database fact | Observed result |
|---|---|
| status transformer | 154 null, 185 non-null |
| last status | 236 null; 103 `High Temp.` |
| last status time | 236 null; non-null 2021-02-03 19:31:00 through 2026-08-17 10:31:14 |
| last comms flag | 207 null; 130 true; 2 false |
| powerdown/startup time | 324/13 null; non-null ranges 2018-04-29..2025-03-03 and 2017-08-22..2026-08-26 |
| `comms_alarm` | 132 UID rows; columns UID, transformer, nullable last-status time (2 null), non-null `no_data_recorded`: 130 false, 2 true |

Event/message source labels: alarm `High Temp.` (3,346 rows), powerdown
`Powerdown` (719), sensor errors `Sensor Error` (1,177), and startup log
`Check-in` (332,079), `Online` (58,060), `Battery Low` (7,674). These logs
carry UID, transformer, timestamps, temperature, max flag, battery voltage,
status and firmware; startup/powerdown also carry measurement period. No
`dbo` table/column with “activation” was found.

Possible application interpretation: label and display such values as source
facts with timestamps/provenance only. Do not infer online/offline,
freshness, activation, acknowledgement, or thresholds: the DB provides no
timing/semantic rule for that.

## Narrow repository extension

`RTLTemperatureRepository` now has `get_registered_devices()` (UID only,
excluding sensitive cellular data) and `get_transformer_mappings()` (UID plus
source `trfr`). Both are deterministic, parameterized SELECT reads. It does
not expose `get_canonical_fleet`, a hierarchy claim, or status interpretation.

## Client decisions remaining

1. Which population/list is canonical and how should the 81 telemetry-only
   and 20 registered/no-telemetry UIDs appear?
2. Is `trfr_list` authoritative, including the two current pair differences
   and historical/multiple telemetry labels?
3. What operational meaning and timing, if any, do comms/status/message facts
   convey?
4. Timezone and temperature validity/deduplication remain separate open
   questions; this audit does not decide them.
