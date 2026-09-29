
# Read-only RTL temperature access

## Purpose

`repositories/rtl_temperature_repository.py` is the only application boundary
for the local restored client `RTL` SQL Server database. It is independent of
the PostgreSQL engine, PostgreSQL sessions, Alembic, seeders, and
`plant_monitoring_repository.py`.

```text
Power application
  ├─ PostgreSQL repository ─ application-owned state and all writes
  └─ RTLTemperatureRepository ─ SELECT only
       └─ SQL Server RTL.dbo.master_temperature
```

It uses only `RTL_DB_HOST`, `RTL_DB_PORT`, `RTL_DB_NAME`, `RTL_DB_USER`, and
`RTL_DB_PASSWORD`, and the least-privilege `rtl_app_reader` login. The only
extra runtime dependency is `pymssql==2.3.5`.

## API and source contract

```python
get_latest_temperature(device_uid) -> RTLTemperatureReading | None
get_temperature_range(device_uid, start_time, end_time) -> list[RTLTemperatureReading]
get_registered_devices() -> list[RTLRegisteredDevice]
get_transformer_mappings() -> list[RTLTransformerMapping]
```

`RTLTemperatureReading` deliberately exposes only raw supported facts:
`device_uid: int`, `reading_time: datetime | None`, and
`temperature: Decimal`.

The database source is `dbo.master_temperature(device_uid,
reading_timestamp, temperature)`. The reader does not map UID to transformer,
plant, site, or application device. It does not convert timestamps, filter
temperatures, discard old dates, or deduplicate rows.

A latest read excludes null timestamps because no latest instant can be
determined; a bounded range naturally excludes null timestamps because they
cannot be within a range. This is stated behaviour, not a clean-up rule.
Range results are ordered by `reading_timestamp ASC, temperature ASC`; latest
uses `reading_timestamp DESC, temperature DESC`. Exact duplicates are returned
individually. Rows equal in all three exposed fields are indistinguishable by
this narrow contract.

The `temperature DESC` tie-break of the single-UID latest read is a technical
ordering, not an approved business rule; conflicting same-timestamp readings must
be addressed before relying on it (see RTL-INTEGRATION-04 adapter document).

All queries are parameterized. There is no arbitrary SQL API and no write,
migration, schema, or seed path.

`get_registered_devices()` selects only the registered UID, intentionally not
the source cellular-contact field. `get_transformer_mappings()` selects only
the observed UID and `trfr` code. Both methods use deterministic ordering and
are factual source directories, not a canonical fleet or authoritative
hierarchy decision.

## Local validation

On the local restored copy, test UID `29743` returned a five-row bounded
24-hour history:

| Fact | Observed value |
|---|---|
| Latest timestamp | `2026-09-17 03:39:00` |
| Latest temperature | `16.00` |
| Latest-query timings (three warm calls) | 106.7 ms, 102.6 ms, 121.4 ms |
| Bounded 24-hour range timings (three warm calls) | 174.4 ms, 162.3 ms, 140.1 ms |
| Rows in the bounded 24-hour range | 5 |

`master_temperature` is a heap with no audited user index. These local timings
are acceptable for this narrow proof only, not a fleet-scale performance
guarantee. Any future wider-query integration must bound windows and inspect
real query plans; it must not add indexes to RTL.

The reader account was rechecked: an `UPDATE ... WHERE 1 = 0` was denied,
database updateability is `READ_ONLY`, and the audited counts remained:

| Check | Before / after |
|---|---:|
| `master_temperature` rows | 2,456,901 / 2,456,901 |
| distinct telemetry UIDs | 400 / 400 |
| `device_list` rows | 339 / 339 |
| `trfr_list` rows | 185 / 185 |

## Unresolved business questions

This gate does not resolve any MAP-04 decisions:

1. The canonical monitored UID population.
2. Whether `trfr_list` is authoritative for device-to-transformer association.
3. The timezone represented by RTL timestamps.
4. The client-approved validity and deduplication policy.

No dashboard, hierarchy, alarm, technician, command, or PostgreSQL reading
path is wired to this reader in this gate.

## RTL-UI-03 vertical slice

The existing device dashboard may request real temperature only when its route
context carries an explicit `rtl_uid` populated for an Administrator. This is
a deliberately temporary safe/test path because no approved raw-UID-to-app
device authorization mapping exists. Temperature latest/history calls remain
on this repository; failure is rendered as unavailable and never falls back to
synthetic PostgreSQL temperature data. Raw `datetime2` timestamps are shown
without timezone conversion or timezone claim.

## RTL-INTEGRATION-04 adapter foundation

The repository also offers `get_latest_temperatures(uids)` (set-based, batched at
500 UIDs; identical latest-timestamp duplicates expose the common value, conflicting
ones leave `temperature=None` with `has_latest_ambiguity=True` and the source
values preserved — the application never picks one), `get_registered_device_uids()`,
`get_telemetry_device_uids(uids=None)` and `get_mapped_device_uids()`.
`services/rtl_source_facts_service.py` layers factual, provenance-tagged results
(`DATA`/`PARTIAL`/`NO_DATA`/`UNAVAILABLE`) on top; it is not wired to any UI and
is not an authorization layer. See
`docs/audit/rtl-integration-04/RTL_REAL_DATA_ADAPTER.md`. The four unresolved
business questions above remain unresolved.
