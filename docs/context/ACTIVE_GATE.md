# Active Gate

Status: Approved
Date: 2026-08-30
Gate: SEED-RESET-1 — restore safe monitoring reseed/reset behaviour
Precondition: CC-1 feature implementation complete (`b8315c8`, `41d9de6`);
all nine CC-1 ADRs implemented.
Flow: FK INVENTORY (complete) -> DECIDE (complete, ADR-010) -> IMPLEMENT ->
TEST -> COMMIT -> **FULL STOP**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
as its OWN commit, separate from CC-1 acceptance. Push NOT GRANTED.

## Task

This is a defect gate, not a feature gate. The goal is NOT "make the reset
command stop throwing a foreign-key error". It is:

> Make monitoring demo/reseed operations safe, deterministic, and explicit
> about which persisted domains they preserve or reset.

## What the inventory found

Every foreign key in the schema, read from `information_schema`, is
`NO ACTION` — nothing cascades. Five tables reference `devices`:
`readings`, `device_events`, `rtl_active_state`,
`rtl_programming_requests`, `user_device_assignments`. `_reset_data`
cleared only the first before deleting `devices`.

The decisive find: **deleting the hierarchy was never necessary.** All three
hierarchy inserts are already `ON CONFLICT DO NOTHING`
(`db/seed_plant_monitoring.py:202, 224, 257`) and `build_hierarchy` is
documented as stable regardless of input ordering (`db/hierarchy.py:85-87`).
So the fix removes deletes rather than adding them, and is strictly less
destructive than what is there now.

## The contract — ADR-010

- **D1** `--reset` replaces `readings` only; the hierarchy reconciles itself.
- **D2** Preservation is stated PER TABLE, not as "everything else":
  events, assignments, active state, programming requests, audit log and
  users are all preserved. Only measurements are replaced.
- **D3** The destructive teardown becomes its own `--purge` flag: FK-safe
  order, names each domain and row count first, refuses without an explicit
  acknowledgement, never invoked by `--reset`.
- **D4** No `CASCADE`. It would make the command succeed while silently
  destroying history nothing can rebuild.
- **D5** The freshness demo becomes REVERSIBLE: capture the exact rows
  before deleting, `--restore` puts them back, `ON CONFLICT DO NOTHING`
  makes both apply and restore converge rather than duplicate.

## Required tests

- reset/reseed hits no FK violation
- no implicit or explicit `CASCADE` anywhere in the seeds
- preservation/reset behaviour is explicit for EVERY dependent table
- the FK-safe purge order is derived from the live schema, not hand-written
- the freshness demo is deterministic for a fixed `now`
- applying it twice is refused, not silently doubled
- restore returns the affected readings EXACTLY
- unrelated RTL readings unchanged
- unrelated events unchanged
- assignments unchanged
- active state unchanged
- programming requests unchanged
- a failure partway through leaves no ambiguous half-seeded state

## Non-goals

- No CC-1 acceptance work in this commit (mixed-freshness verification,
  EVT-D5 browser check, Recent Events footer copy, Affected Locations
  height). Those are the NEXT gate and land separately.
- No new Command Center feature work.
- No schema migration: the capture is a developer-tool artifact, not a
  domain table Alembic should own.
- No push.

## Then, and separately: CC-1 acceptance

Once this defect is closed the acceptance tranche runs: mixed freshness
visual verification, EVT-D5 both roles in the browser, the footer copy
change, an explicit decision on Affected Locations height, the full
1440/1366/1024 x dark/light matrix, and a final CC-1 acceptance record.
