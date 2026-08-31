# CC-04 Communication

## Purpose
Answer: `How much of the monitored fleet is currently invisible to us?`

This card keeps its position in the Command Center mockup. Only its contents
change: it presents truthful No Data visibility, not an invented duration
breakdown.

## Content for CC-1
- `No Data RTLs` count
- percentage of monitored RTLs
- explanatory copy: **"At least one monitored metric has no reading."**
- optionally, the number of affected Plants, if derived from the same
  `FleetHealth` object rather than a second query

## Why there are no age buckets in CC-1
Freshness is evaluated **per (device, metric)** and the RTL takes the worst
state. An RTL is therefore `NO_DATA` when *any one* monitored metric has never
reported — even while its other metrics are delivering fresh readings.

Two consequences:

1. `>24h` / `>48h` / `>72h` buckets would read as "No Data duration", and the
   backend cannot derive that. There is no per-metric missing-since fact.
2. `device_last_updated` must not be used to fake it. It is the newest
   timestamp across *any* metric, so a `NO_DATA` RTL can carry a recent one.
   That timestamp says nothing about how long the missing metric has been
   absent.

Do **not** label these RTLs `Never reported`. The RTL may well have readings
for its other metrics.

## Future contract
> No Data duration is not currently derivable. A future metric-level
> missing-since / closure contract would be required before age buckets can be
> shown.

## Stale age
If a duration visualization is wanted later, **Stale age** is the honest
candidate: stale readings have timestamps. It is deliberately out of scope for
CC-1 unless the planning pass proves a useful aggregation.

## Guardrail
Do not turn No Data into a stronger connectivity claim than current monitoring
semantics support. No Data is monitoring blindness, not proof of equipment
failure and not a measured outage duration.
