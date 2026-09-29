# RTL-INTEGRATION-04 — Real data adapter foundation

Status: implemented 2026-09-29 against baseline `e20d2d1`; uncommitted, awaiting
independent review. This is a data-access foundation, not the Fleet Overview.
`CLIENT-CLARIFICATION-02` has **not** been answered; nothing here decides it.

## Architecture

```text
client RTL SQL Server (READ_ONLY, rtl_app_reader, RTL_DB_*)
  └─ repositories/rtl_temperature_repository.py   raw shape, SELECT only
       └─ services/rtl_source_facts_service.py    factual model, outcomes, provenance
            └─ (future) authorized application services — NOT wired to any UI/route
```

PostgreSQL remains the only application-owned, writeable store. Neither new
module imports `db.engine`, SQLAlchemy, Alembic or the PostgreSQL repository
(pinned by a test). `RTL_DB_*` never reaches PostgreSQL/Alembic paths.

## Repository additions (raw RTL shape)

| API | Meaning |
|---|---|
| `get_latest_temperatures(uids) -> dict[uid, RTLLatestTemperature]` | set-based latest raw reading per requested UID |
| `get_registered_device_uids()` | UIDs with a `device_list` row |
| `get_telemetry_device_uids(uids=None)` | UIDs with any `master_temperature` row; unrestricted = one heap scan |
| `get_mapped_device_uids()` | distinct UIDs with a `trfr_list` row |

Existing `get_registered_devices`, `get_transformer_mappings`,
`get_latest_temperature`, `get_temperature_range` are unchanged.

## Factual device model (`RTLDeviceFacts`)

`device_uid`, `registered_in_device_list`, `has_temperature_telemetry`,
`has_transformer_mapping`, `transformer_mapping_values` (raw `trfr` strings),
`latest_temperature` (raw, source-clock), `provenance`.

`registered_in_device_list=True` means only "a row exists in `device_list`". It
does not mean active, authorized or monitored. No field is named or translated
to Online/Offline/Active/Healthy/Needs Attention. `device_status` fields
(comms/status) are deliberately **not** represented: their meaning is a deferred
client decision.

## Source populations

`get_source_populations()` returns `registered`, `telemetry`, `mapped` as three
separate frozensets. No API chooses "the fleet"; there is no
`get_canonical_/active_/monitored_fleet`. Every multi-device operation
(`get_device_facts`, `get_latest_temperatures`) requires an explicit UID
population. A UID unknown to every table yields a record with all flags False.

## Transformer mapping treatment

Raw `trfr_list` values are exposed per UID as observed facts. They are not called
authoritative, not attached to application transformers, and no app-device ↔ RTL
mapping or PostgreSQL assignment is created.

## Set-based latest-temperature strategy

One query per batch: a `VALUES` request set → `MAX(reading_timestamp)` per UID
(null timestamps excluded) → join back to source rows at that timestamp. This is
RTL-FLEET-02's "aggregate + join", chosen because it was faster than
`ROW_NUMBER` at 400 UIDs (258 vs 410 ms) and because it exposes ties.
Parameterized (one bound parameter per UID), explicit columns, no `SELECT *`,
no temp tables/indexes/views. UIDs are validated as ints in the SQL `int` range,
deduplicated and sorted; empty input opens no connection.

**Query-size limit:** batches of `LATEST_BATCH_SIZE = 500` UIDs (a `VALUES`
constructor caps at 1000 rows; native driver parameters at 2100), sequential on
one connection. All 400 telemetry UIDs = 1 query. Larger requests cost one heap
scan per 500 UIDs. No caching is introduced.

## Duplicate-latest handling

All source rows sharing a UID's latest timestamp are read and represented in
`RTLLatestTemperature`; the application never chooses among conflicting values.

| Case | `temperature` | `tied_latest_row_count` | `tied_source_temperatures` | `has_latest_ambiguity` |
|---|---|---:|---|---|
| A. one row | that value | 1 | (value,) | False |
| B. several rows, identical value | the common source value | n | (value,) | False |
| C. several rows, distinct values | **None** | n | all distinct values, ascending | **True** |

Case B only counts identical rows; it is not deduplication or cleaning. In case
C no highest/lowest/first/average is exposed, so no single temperature can look
like the correct latest value; ascending order is presentation only. The
service passes the result through unchanged. No Eskom duplicate-resolution
policy has been established; CLIENT-CLARIFICATION-02 remains unresolved. Local
data: 0 ties across all 400 UIDs.

Known limitation (deferred): the legacy single-UID `get_latest_temperature`
(RTL-UI-03 dashboard path) still orders same-timestamp readings by `temperature
DESC`. That is a technical ordering, not an approved business rule. Current
local source data has zero ambiguous latest UIDs, so deferral is safe today, but
the behavior must be addressed before relying on that path when conflicting
latest readings exist. It was intentionally not changed in this gate.

## Provenance

Every result and fact record carries `provenance: FactSource`
(currently only `CLIENT_RTL_SQLSERVER`; a PostgreSQL source value is not added until a caller needs one). It is testable data, not required
UI text.

## Failure behaviour

`FactsStatus`: `DATA` (all requested UIDs have a reading), `PARTIAL` (some do;
`uids_without_reading` lists the rest), `NO_DATA` (none, or empty request),
`UNAVAILABLE` (RTL query/connection failure — empty payload, no synthetic
fallback). The service catches only `RTLTemperatureRepositoryError`, so an outage
does not crash unrelated functions, and logs a warning naming the operation and
exception class only (no SQL, credentials, rows or contact data). Malformed UIDs
raise `ValueError` (a caller bug), never a silent empty result.

## Authorization boundary

The service is not wired to any callback, route, component or page (pinned by a
test). Raw RTL UID availability does not authorize viewing; the RTL-UI-03 rule
stands — authorization occurs at the application boundary before an RTL UID is
supplied. No user-facing endpoint accepts arbitrary UIDs.

## Sensitive-data exclusion

The sensitive cellular/contact column of `device_list` is never selected, logged,
serialized or represented. The registered-UID query selects only `device_uid`
(test asserts the exact column list). All queries use explicit columns.

## Limitations

- **Timestamps:** naive source-clock `datetime2` values; no UTC/SAST/IST claim,
  conversion or localisation. Timezone is unresolved.
- **Data quality:** no value filtering, smoothing, range checks, deduplication
  or cleaning. Source rows tied at the latest timestamp are represented
  factually: identical values expose their common source value, conflicting
  values stay ambiguous and preserved, and no value is selected as correct. No
  Eskom duplicate-resolution/data-quality policy has been applied; the policy is
  unresolved.

## Performance evidence (local, warm, 3 runs, ms; regression detection only)

| UIDs | This gate | RTL-FLEET-02 aggregate+join |
|---:|---|---:|
| 1 | 85.4 / 83.8 / 94.6 | 89.0 |
| 10 | 151.4 / 135.7 / 129.8 | 179.6 |
| 50 | 167.3 / 147.0 / 152.8 | 169.8 |
| 400 (all telemetry) | 263.7 / 209.9 / 215.4 | 258.1 |

Consistent with FLEET-02 (heap scan per pass). Unrestricted telemetry-UID
population: ~95 ms. Not an SLA. No 400-query sequence was run.

## Database safety recheck

Before and after integration tests: `Updateability = READ_ONLY`;
`rtl_app_reader` `UPDATE ... WHERE 1=0` denied (error 229); counts unchanged —
`master_temperature` 2,456,901, telemetry UIDs 400, `device_list` 339,
`trfr_list` 185.

## Deferred client decisions (CLIENT-CLARIFICATION-02, still open)

1. Canonical monitored fleet population.
2. Authority of `trfr_list`.
3. Operational status/communications rules.
4. Source timestamp timezone.
5. Temperature anomaly/deduplication policy.
