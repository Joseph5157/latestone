# ADR-009: Priority Investigation ranks on freshness only, and a STALE age is the OLDEST metric's timestamp

Status: Superseded
Superseded-by: ADR-024 (the panel this governed was removed in SWITCH-OVER-1, 2026-09-19)
Date: 2026-08-30
Evidence: `services/monitoring_service.py:298` (`device_last_updated`),
`services/monitoring_service.py:388-394` (it is a MAX over metric rows),
`services/monitoring_service.py:239-247` (`severity_rank`),
`components/command_center/situation_summary.py:119-121` (the existing
citation of this hazard), ADR-002
Implemented-by: `ce5d4ac`
Extends: ADR-002 (does not supersede it — the no-age rule for NO_DATA is
restated here unchanged, and the STALE rule below is the case ADR-002 did
not need to answer)

## Context

CC-1 Phase 10 answers the last question in the investigation chain: **which
exact RTLs should the operator open first?** The three panels before it
narrow by volume (how much), by location (where), and by transformer (which
concentration). None of them names a device.

The risk this ADR exists to bound is that a per-RTL ranked list is one
design decision away from being an alarm queue — and an alarm queue is
precisely what this application cannot honestly render, because events have
no closure contract (ADR-001).

## Decision

### D1 — The population is the attention population, unchanged

Priority Investigation ranks `STALE + NO_DATA` and nothing else, read from
the same `FleetHealth` the Situation Summary already rendered. FRESH RTLs
never enter it.

No event participates in membership **or** in ordering. A recent
`power_down` or `battery_low` occurrence does not boost a device one place.
The reason is ADR-002's, applied one level down: an event proves something
happened at a moment, not that the device is in that condition now, so
letting occurrence reorder a *current-state* queue would smuggle back the
third attention bucket ADR-002 removed.

### D2 — The order, and why each key is the one it is

1. **NO_DATA before STALE** — via `monitoring_service.severity_rank`, not a
   private copy. That function is public for exactly this reason and says
   so: "a presentation layer sorting by its own private copy is how the two
   would eventually disagree."
2. **Within NO_DATA — hierarchy, then device.** Plant name, then
   transformer code, then device id, each compared case-insensitively with
   the raw id as the final key. This is `_affected_locations`' rule one
   level down, and the case-folding is there for the same reason it was
   there: real fleet data ranked `GRAVELINES` above `Grand Coulee`, which
   reads as a bug to anyone scanning a list alphabetically.
3. **Within STALE — oldest lagging metric first**, i.e. ascending
   `device_oldest_metric_updated` (D3). The longest-silent feed is the one
   to open first.
4. **`device_id` as the final key, always.** Ordering must be fully
   determined; two devices matching on every prior key still order the same
   way on every render.

### D3 — A STALE age comes from the OLDEST metric, never `device_last_updated`

This is the load-bearing correction in this phase, and it was found by
reading the code rather than the plan.

`FleetHealth.device_last_updated` is a **max** over the device's metric rows
(`services/monitoring_service.py:388-394`: "any one metric's newest sample
is the device's newest delivery"). ADR-002 already warns that it "describes
whichever metric IS reporting", and `situation_summary.py:119-121` already
cites that warning.

So on a device that is STALE because one of its eight metrics stopped while
the other seven keep reporting, `device_last_updated` holds the **freshest**
metric's timestamp. A row built on it would render

    STALE · Latest available monitored data 2m ago

which is not false and is completely useless — and, worse, it would make
the D2 ordering key sort on the wrong number, silently ranking a nine-hour
outage below a forty-minute one.

**Therefore:** `FleetHealth` gains one derived field,
`device_oldest_metric_updated`, built from the same rows in the same pass —
no second query, no second freshness calculation. It is the **min** over the
device's metric timestamps, and it is populated **only when every one of
that device's metric rows carries a timestamp**.

That last clause is the whole point, and it is enforced in the data rather
than left to each caller to remember:

> An age exists exactly when every metric has a timestamp.

A device with a never-reported metric is `NO_DATA` and its
`device_oldest_metric_updated` is `None` — so there is no number available
to fabricate a duration from, whatever a future caller intends. The `None`
is not a missing value to be filled in later; it is the honest answer.

### D4 — The copy names what it measures

    NO_DATA: "At least one monitored metric has no reading."
    STALE:   "Oldest monitored metric last reported 3h 41m ago"

The NO_DATA sentence is `situation_summary.NO_DATA_EXPLANATION`, reused
rather than retyped, so the Communication card and these rows cannot drift.

The STALE sentence deliberately does **not** say "latest available
monitored data". That phrase describes a max, and the number is a min; on a
mixed-metric device the words and the figure would disagree, and only
someone who opened the device page would find out.

It also does **not name the lagging metric**, and that is a decision rather
than an omission. `device_oldest_metric_updated` carries a timestamp, not
the identity of the metric that produced it. Naming one would mean the
component inferring it — and an inferred name is a claim the snapshot
cannot support, because several metrics can tie on the same oldest
timestamp and picking one to print would be arbitrary in a way the operator
cannot see.

So the generic wording above is the contract until the model carries the
identity. If a future phase wants "Voltage last reported 3h 41m ago", the
order of work is fixed: **the field first, the sentence second.** Guard
tests assert that no metric name reaches the copy and that `PriorityRTL`
exposes no metric field to infer one from, so the two cannot be done out of
order.

### D5 — Eight rows, and no footer link

The panel shows at most **8** RTLs. It is one cell of a fixed cockpit, and
the ranking's purpose is to name a first move, not to enumerate a
population the Situation Summary already counted.

There is **no** "View all affected RTLs →" footer. The only deeper
destination that exists is `/command-center/locations`, which is the ranked
**plant** list (ADR-003 — Location is Plant), not an RTL list. Linking it
would promise a population the page does not show. An approximate
destination is worse than none, so the footer is omitted until a page
exists that means exactly this.

## Consequences

- One new field on `FleetHealth`, derived in `fleet_health_from_rows` from
  rows already fetched. No new repository read, and ADR-008's approved read
  set is unchanged — Phase 10 adds no read path at all.
- Hierarchy labels come from `hierarchy_service.list_device_paths`, the
  batched lookup ADR-008 already approved for Phase 9. **One call per
  render, covering the whole attention population — not only the eight rows
  that survive the cap.** This differs from Phase 9's "visible rows only"
  usage and the difference is forced: the NO_DATA order is by plant *name*,
  so the names are what decide which eight rows are visible. Asking for
  eight would mean ranking before knowing the keys.

  It remains one query and stays bounded — the attention population cannot
  exceed the caller's own scope, and in the worst case (every RTL blind) it
  is the scope size. The N+1 shape ADR-008 exists to prevent is untouched;
  what changed is the row count of a single `IN (...)`, not the number of
  round trips.
- A device whose label lookup fails keeps its stable id and stays in the
  list. Dropping it would hide a device that is, by definition, one the
  operator was told to investigate first.
- `command_center_service` produces presentation-ready priority rows; the
  component renders them and reproduces no freshness ranking of its own
  (AGENTS.md rule 8, and the reason `CommandCenterSnapshot` exists).

## What this ADR does not decide

- Whether Priority Investigation should ever gain an acknowledge/assign
  action. It should not while ADR-001 stands, but that is ADR-001's ruling,
  not a new one here.
- The freshness demo seed's composition. It is required to *verify* this
  phase in a browser and is tracked by the gate, but what it seeds is a
  fixture decision, not an architectural one.
