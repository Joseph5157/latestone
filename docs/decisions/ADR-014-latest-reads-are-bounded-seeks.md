# ADR-014: Every latest-reading read is a bounded seek, at device grain too

Status: Approved
Date: 2026-09-03
Evidence: `repositories/plant_monitoring_repository.py:559-568` (the contract
this extends, stated for `latest_reading_times`);
`repositories/plant_monitoring_repository.py:1071` (`get_latest_readings_for_device`,
the shape it corrects); `tests/test_plant_monitoring_repository.py:28-34`
(why the budgets exist); `tests/test_plant_monitoring_repository.py:311-323`
and `:495-505` (the two sibling guards); `docs/CODE_AUDIT.md:349-355` (the
first record of the intermittent failure)
Implemented-by: not yet recorded as a sha — the code lands in this ADR's
own commit (`fix(db): bound latest-reading query cost`), which cannot cite
itself; backfill the sha the way FIX-1 did in `5901945`
Supersedes: nothing — it extends ADR-008's "reuse the existing read paths"
to the one read path that did not obey the repository's own query contract

## Context

`test_batched_latest_returns_all_eight_metrics` had been intermittently red
since before CC-1. It was investigated three separate times and each time
recorded as order-dependent rather than repaired:

- `docs/CODE_AUDIT.md:349-355` — 84.5 ms against an 80 ms budget once, then
  five consecutive passes. Attributed to a cold connection.
- FIX-1's close record (`5901945`, `ACTIVE_GATE.md:99-105`) — passed alone,
  passed 487/487 on a clean worktree, failed only immediately after a
  targeted DB subset. Recorded as a queued follow-up.
- CLIENT-SYNC-1 (`c4896e9`, `ACTIVE_GATE.md:113-117`) — 91 ms on the first
  full-suite run, then 2,404 passed on a rerun "against the warm database".

All three read the symptom as test-order or process state. It is neither.

## Decision

`get_latest_readings_for_device` resolves each metric by bounded index
seeks, never by `DISTINCT ON` over the device's history.

The repository already states this as a contract, for the fleet-grained
query, at `plant_monitoring_repository.py:559-568`:

> **Query shape is a contract, not an implementation detail.** [...] The
> obvious alternative, `DISTINCT ON (device_id, metric)` over `readings`,
> plans as a full index scan [...] and it degrades with history rather than
> with device count. The client's dataset is larger than ours, so a shape
> that scales with history is the wrong one regardless of how it benchmarks
> today.

`get_latest_readings_for_device` was the one read that did not obey it. Being
device-scoped made it look bounded; it is not. Measured on the seeded
database against the reserved device:

| shape | rows examined | buffers | warm exec | cold exec |
|---|---|---|---|---|
| `DISTINCT ON (metric)` | **11,528** | 463 | 2.6 ms | 31.9 ms |
| bounded seeks | **17** | 86 | 0.2 ms | — |

Eight values, 11,528 index rows read to find them. The cost is a function of
how much history the device has, not of how many metrics were asked for.

## Why this was mistaken for test-order sensitivity

`readings` is 1,682 MB against 128 MB of `shared_buffers` — a 13× over-
subscription, and the index alone is 516 MB. Whether this query's 460 pages
are resident is therefore decided entirely by what ran just before it. Same
code, same plan, same process:

- resident: `Buffers: shared hit=463`, 2.6 ms
- evicted: `Buffers: shared hit=3 read=460`, 31.9 ms

A 12× swing with no test state involved at all. Nothing leaks between tests;
what varies is the database's cache, and test order only correlates with it.
That is why the failure moved whenever anyone looked at it, and why "passed
in isolation" was never evidence the code was sound.

## Consequences

- The device dashboard's snapshot read (`get_device_snapshot`,
  `get_device_full_view`) stops growing with the client's history. At the
  client's 30-minute cadence the old shape's cost compounds indefinitely;
  the new one is flat.
- Correctness is unchanged, and was proven so rather than assumed: all 120
  devices compared against the previous query, 0 mismatches, plus the
  metric-filtered path and the unknown-device / unknown-metric / empty-list
  cases.
- `PostgreSQL 16` has no skip scan, so the metric domain is found by an
  explicit recursive loose index scan. When the client's server reaches a
  version that plans `DISTINCT ON` as a skip scan, the recursion may be
  reconsidered — the *contract* (bounded, history-independent) is the
  decision here, not the recursion that currently implements it.
- Deriving the metric domain from `readings` rather than from
  `config/metrics.py` keeps the repository free of presentation concerns,
  the same reason `latest_reading_times` takes `metrics` as an argument.

## The guard changes instrument

A wall-clock budget cannot express "this query does not scale with history".
It measures the machine's cache, which is what made it flaky, and it only
crossed 80 ms when the pages happened to be evicted — so the defect was
real on every run and *detected* on almost none.

`TestBatchedLatestQueryShape` asserts rows examined instead, read from the
plan of the statement the repository actually issued. That figure is
identical cold and warm, so the guard is order-independent by construction,
and it fails at 11,528 rows whether or not the machine is fast enough to
hide it.

The wall-clock tests in `TestLatestReadings` are deliberately left alone.
They are still a coarse guard, and with the fix they run at 2.65 ms against
their 80 ms budget — a 30× margin, where the historical failures were at
84.5 ms and 91 ms.
