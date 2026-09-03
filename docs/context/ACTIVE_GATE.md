# Active Gate

Status: Complete — reviewed, accepted, committed and pushed
Date: 2026-09-03
Gate: DB-ORDER-1 — diagnose and remove the DB test-order sensitivity
Branch: `main`, baseline `c4896e9`
Commit/push permission: GRANTED by the operator at DB-ORDER-1-CLOSE, after
review, for exactly the six reviewed files onto `main`. The gate was
implemented under an explicit "do not commit, do not push" and held for that
review; the push is the final action of this closure.

## Purpose

`test_batched_latest_returns_all_eight_metrics` had been intermittently red
across three separate gates, each time passing in isolation and failing only
after some other work had run. It was recorded as order sensitivity and
queued rather than repaired opportunistically inside FIX-1.

Find what actually varies, fix it at the layer that owns it, and make the
result independent of execution order.

## Evidence at gate open

- `python scripts/build_context_pack.py --check` — CLEAN, wrote nothing.
- `main` at `c4896e9`, tracked tree clean, untracked `debug.log` present.
- DB suite in isolation: **487 passed** — the same count CC-1 recorded
  (`CC1_ACCEPTANCE.md:17`), so no DB test had been added since.
- Three prior records of the same failure, none of which agreed on a cause:
  `docs/CODE_AUDIT.md:349-355` (cold connection), FIX-1's close record in
  `5901945` (order-dependent after a targeted subset), and CLIENT-SYNC-1's
  in `c4896e9` (warm vs cold database).

## What it turned out to be

Not leaked test state. Nothing survives between tests; what varies is the
**database's buffer cache**, and test order only correlates with it.

`readings` is 1,682 MB against 128 MB of `shared_buffers`. The query behind
that test read **11,528 index rows and 463 buffers to return 8 values**, so
whether those pages were resident decided its cost:

| cache state | buffers | execution |
|---|---|---|
| resident | `hit=463 read=0` | 2.6 ms |
| evicted | `hit=3 read=460` | 31.9 ms |

Same code, same plan, same process — a 12× swing from cache residency alone.

The shape is also the one the repository's own contract rules out
(`plant_monitoring_repository.py:559-568`), and the budget it kept crossing
exists specifically to catch it (`test_plant_monitoring_repository.py:28-34`:
"a query whose cost grows with history rather than device count must fail
here rather than in production"). So the test was right and the production
query was wrong — ownership category G, a genuine defect that ordering
merely exposed.

Recorded as **ADR-014**.

## In scope

- `repositories/plant_monitoring_repository.py` —
  `get_latest_readings_for_device` resolves each metric by bounded index
  seeks (recursive loose index scan for the metric domain, then one
  `CROSS JOIN LATERAL (... ORDER BY reading_ts DESC LIMIT 1)` per metric).
  17 rows and 86 buffers where it previously read 11,528 and 463.
- `tests/test_plant_monitoring_repository.py` — `TestBatchedLatestQueryShape`,
  which asserts rows examined from the plan of the statement the repository
  actually issued, instead of a wall clock that measures the machine's cache.

## Explicitly out of scope — and not touched

- ROLE-4A..4D and any credential, role-policy or authorization change.
- Technician action UI, General/Viewer seeding, browser verification.
- Route policy, Command Center design, reporting, notifications.
- Schema redesign — the fix needed none; the existing
  `ix_readings_device_metric_ts` already supports the bounded shape.
- The wall-clock tests in `TestLatestReadings`, deliberately left as they
  are (see ADR-014, "The guard changes instrument").
- The untracked `debug.log`.

## Relevant files

- `repositories/plant_monitoring_repository.py`
- `tests/test_plant_monitoring_repository.py`
- `docs/decisions/ADR-014-latest-reads-are-bounded-seeks.md`
- `docs/context/DECISION_INDEX.md`
- `docs/context/CURRENT_STATE.md` (generated only)

## Verification

- Regression seen failing first: **11,528 rows** to return 8, and **2,882**
  to return 2. After the fix: 17 and 11.
- Equivalence: all **120 devices** compared against the previous query —
  **0 mismatches** — plus the metric-filtered path and the unknown-device,
  unknown-metric and empty-list cases.
- Focused: repository module **56 passed**; service/analytics/period/route/
  register consumers **142 passed**.
- Order independence: the affected module before and after the heavy
  reading-sweep DB modules, on a cold cache — **121 passed** both directions.
- DB suite in isolation, cold cache: **489 passed** (487 + the 2 new).
- Full project suite: **2,993 passed** (2,991 + 2).
- The wall-clock test's margin moved from 5.27 ms to **2.65 ms** against its
  80 ms budget; the historical failures were 84.5 ms and 91 ms.
- `git diff --check` — clean.

## Known limitation, stated plainly

The **wall-clock symptom** could not be reproduced on this machine: it has
enough RAM to hold all 1,682 MB in the host page cache, so even a restarted
container and a full eviction sweep left the test at 5.37 ms. The *cause*
was proven directly instead, by plan and buffer inspection, which is
independent of any machine's cache — and the regression is written on that
same basis so it cannot go quiet on a fast machine.

## Outcome

DB-ORDER-1 is **CLOSED**. The reviewed change was committed as a single
commit on `main` covering the two implementation files and the four context
records, and pushed to `origin/main` with local and remote SHAs verified to
match. The untracked `debug.log` was neither staged nor committed.

Verified at closure: `git diff --check` clean, `git diff --cached --check`
clean, staged set exactly the six reviewed files, and the context pack CLEAN
both before staging and after the commit.

### One bookkeeping item, deliberately left open

`ADR-014`'s `Implemented-by` reads `not yet recorded as a sha`, because the
closure was specified as a single commit and an ADR cannot cite the commit
that carries it. `scripts/build_context_pack.py:208` requires that field to
either begin "not yet" or name a reachable commit, so a forward reference
would have failed the pack. Backfill the sha in a follow-up context commit,
the way FIX-1 did in `5901945` — the same two-step this repository already
uses to record provenance.

## Next queued gate — do not start

**ROLE-4 — credentialed personas and their surfaces.** Sub-gates, in order:

- **ROLE-4A** — credentialed personas. This is the next gate.
- **ROLE-4B** — Technician operational surface.
- **ROLE-4C** — General/Viewer persona.
- **ROLE-4D** — browser acceptance for all three roles.

ROLE-4A carries a debt CC-1 acceptance recorded and never cleared: EVT-D5 was
verified by substituting the authorization identity in the session store, not
by a credentialed sign-in, and "a credentialed technician login has no demo
credential" (`CC1_ACCEPTANCE.md`, "Deferred, explicitly", item 1).

None of ROLE-4 was started during DB-ORDER-1. PCB remains paused at
`PCB-9-CLOSE`.
