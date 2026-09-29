# RTL-FLEET-02 — Fleet query performance

Status: factual local experiment, 2026-09-29; not a production SLA or final
architecture choice.

## Source and method

`dbo.master_temperature` has 2,456,901 rows and 400 distinct telemetry UIDs.
It is a heap: no primary key, unique constraint, or user index was observed.
Tests parameterized a requested-UID `VALUES` set and selected only UID,
timestamp, and temperature. No objects, indexes, views, temp tables,
statistics, schema, or data were created/changed. The source maximum timestamp
was 2026-09-17 08:29:00; it is a factual test anchor only, not timezone policy.

Strategies:

1. Aggregate + join: `MAX(reading_timestamp)` by requested UID, then join to
   source rows at that timestamp. It can return timestamp ties, so it is not a
   duplicate policy.
2. Window: `ROW_NUMBER()` by UID, timestamp DESC, temperature DESC. It returns
   one deterministic exposed row unless duplicate source rows are identical.
3. Bounded aggregate + join: strategy 1 with a timestamp predicate.

No 400-call sequential design was tested. UID samples were deterministic
smallest telemetry UIDs (1/10/50) and all 400 telemetry UIDs.

## Timings

One warm local elapsed-time run per query, including row fetch, milliseconds:

| Strategy | 1 UID | 10 UIDs | 50 UIDs | all 400 UIDs |
|---|---:|---:|---:|---:|
| Aggregate + join | 89.0 (1 row) | 179.6 (10) | 169.8 (50) | 258.1 (400) |
| `ROW_NUMBER` | 57.1 (1 row) | 92.4 (10) | 167.3 (50) | 409.5 (400) |

Aggregate happened to return one row per requested UID in this run, not a tie
guarantee. Window selection is clearer but was slower at all-UID scale.

## Bounded tests, all 400 telemetry UIDs

| Boundary, relative to source maximum | Elapsed ms | UID rows returned | Source fact |
|---|---:|---:|---|
| latest known calendar date (2026-09-17 through maximum) | 232.6 | 13 | 14 source rows on the date, 13 UIDs |
| previous 24 hours | 229.4 | 49 | only UIDs reading in window return |
| previous 7 days | 215.3 | 66 | only UIDs reading in window return |

Bounds reduced returned/aggregated population but did not materially improve
warm elapsed time over unbounded aggregate (258.1 ms). With no UID/time index,
this is consistent with heap scanning; it does not establish a policy.

## Plan/resource evidence

`SHOWPLAN_XML` was denied to `rtl_app_reader` (SQL Server error 262). The
installed `pymssql` driver did not expose consumable `STATISTICS IO/TIME`
messages, so actual operators, logical reads, and server CPU cannot be claimed.
Metadata does establish no index seek route for UID/time predicates: a full
2,456,901-row heap scan is the expected source access per pass. Whether the
aggregate/join second pass is a scan, spool, or another shape cannot honestly
be asserted without plan permission. Local sub-second elapsed results are not
an interactive-concurrency commitment.

## Future candidates; none selected

| Candidate | Benefit | Drawback / RTL impact | Freshness / complexity |
|---|---|---|---|
| Direct set-based RTL | No copy; source current | Heap-load per refresh, no per-UID loop; read-only query load | source-current; low complexity |
| Bounded RTL | Smaller result set | still no seek; omits no-reading UIDs | boundary needs approval; low |
| Application cache | shields repeated reads | invalidation/staleness disclosure; no RTL writes | configurable lag; medium |
| PostgreSQL projection | indexed fleet/history and isolation | ETL, provenance, reconciliation; RTL remains read-only | import lag; high |
| Client reporting projection | owner-optimized source boundary | requires client approval; app must not create it | owner-defined; external dependency |

## Read-only/count verification

Counts before and after: `master_temperature` 2,456,901; telemetry UIDs 400;
`device_list` 339; `trfr_list` 185. `DATABASEPROPERTYEX` reported `READ_ONLY`.
An `UPDATE dbo.device_list ... WHERE 1=0` authorization check was denied with
SQL Server error 229; the predicate could match no row and subsequent counts
were unchanged.
