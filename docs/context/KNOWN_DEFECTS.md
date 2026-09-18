# Known Defects

Status: Approved
Date: 2026-08-30
Last updated: 2026-09-18 — ADMIN-PANEL-LOAD-ERROR-1 added and resolved

Defects found during gated work that were deliberately **not** fixed in the
tranche that found them. Each carries the evidence that established it and
the gate it must be fixed before.

This is not a backlog of ideas. A row belongs here only when the behaviour
is confirmed broken against the code (`SOURCE_AUTHORITY.md` rung 2), and it
leaves when a commit fixes it — not when someone decides it is unimportant.

| Id | Defect | Found | Fix before |
|---|---|---|---|
| ~~SEED-RESET-1~~ | `seed_plant_monitoring --reset` cannot complete: FK dependents of `devices` are not cleared first | CC-1 Phase 10 (2026-08-30) | **RESOLVED 2026-08-30** — ADR-010 |
| ~~ADMIN-PANEL-LOAD-ERROR-1~~ | Temperature Threshold panel shows "Warning is required." on page load before any click; Vibration Contract panel has the same code path | FRESHNESS-CONFIG-1 browser check (2026-09-18) | **RESOLVED 2026-09-18** — SETTINGS-PAGE-1 |

---

## SEED-RESET-1 — Restore safe monitoring reseed/reset behaviour

**Status:** RESOLVED (ADR-010) · **Found:** CC-1 Phase 10 · **Fixed:**
2026-08-30, in its own commit as required.

### How it was resolved

Not by adding deletes — by removing them. All three hierarchy inserts were
already `ON CONFLICT DO NOTHING` and `build_hierarchy` is deterministic, so
deleting the hierarchy on reset was never necessary. `--reset` now replaces
`readings` only; the destructive teardown moved to an explicit `--purge`
that names what it destroys and refuses without a second acknowledgement.
No `CASCADE`.

Proven on the real database: `--reset` completed with 13 events, 96
assignments and 2 active-state rows referencing `devices` — the exact
condition that used to fail — and preserved every one of them while
restoring readings to 1,383,360. The `db`-marked suite went green in the
same run.

The freshness demo is now reversible (capture -> apply -> restore), which
was the acceptance blocker. See ADR-010 D5.

The original analysis is kept below, because the reasoning is the record.

### The defect

`db/seed_plant_monitoring.py:48-54` (`_reset_data`) deletes in this order:

```
DELETE FROM <schema>.readings
DELETE FROM <schema>.devices
DELETE FROM <schema>.transformers
DELETE FROM <schema>.plants
```

Its docstring says "Delete data in FK-safe order". That was true when it was
written. It is no longer true: the DB-1..DB-4 and ROLE-3 work added four
tables that reference `devices`, and none of them is cleared first.

Confirmed against the live schema, not inferred — `information_schema`
reports these foreign keys onto `devices`:

- `readings.device_id` (handled — deleted first)
- `device_events.device_id` (**not handled**)
- `user_device_assignments.device_id` (**not handled**)
- `rtl_active_state.device_id` (**not handled**)
- `rtl_programming_requests.device_id` (**not handled**)

So on any database that has run `db.seed_events_demo`, `db.seed_admin_demo`,
or registered/activated an RTL, `--reset` fails on a foreign-key violation.

### Why it matters more than it looks

It is the documented way back from every other seed, so its failure removes
the rollback story for all of them. That is what blocked the Phase 10 mixed
Fresh/STALE/NO_DATA browser verification: `db/seed_freshness_demo.py` has to
DELETE readings (staleness cannot be inserted — see ADR-009 D3), and with no
working reseed the change is one-way. The seed was therefore built, tested
and left unapplied.

### Scope when it is fixed

- Inspect every FK dependent of `devices` — from the live schema, not from
  memory of the migrations.
- Define a safe deletion / reseed order.
- Decide **per table** whether a monitoring reset should preserve or
  deliberately clear it. Events, assignments, active state and programming
  requests are not obviously all the same answer: readings are synthetic
  telemetry, an audit row is a record that something happened.
- Add rollback/reseed tests, so the order cannot silently rot again the next
  time a table gains a `device_id`.
- Make visual-demo seeding reversible or disposable, which is what would let
  `seed_freshness_demo` be applied without a one-way commitment.

### Do not

Do not fix it by adding `CASCADE`. That would make a reset silently destroy
audit and assignment history that no other command can rebuild, which is a
worse defect wearing the fix's clothes.

---

## ADMIN-PANEL-LOAD-ERROR-1 — Admin config panels validate before any click

**Status:** RESOLVED (SETTINGS-PAGE-1, 2026-09-18) — both callbacks now
ignore zero-click triggers; regression tests in `tests/test_admin_settings.py`.
**Found:** FRESHNESS-CONFIG-1 browser verification, 2026-09-18.

### The defect

When Fleet Overview loads for an Administrator, the Temperature Threshold
panel immediately shows the validation error "Warning is required." Nobody
has clicked anything.

Cause: the panel is inserted into its slot by a callback. Dash then fires
the panel's Set/Clear action callback (`callbacks/temperature_threshold.py`
`_handle_action`) with `n_clicks=0` for the newly inserted button.
`prevent_initial_call=True` does not stop this for components added after
the first page load. The handler checks only which button triggered it, not
whether it was actually clicked, so it validates the empty form.

`callbacks/vibration_contract.py` `_handle_action` has the identical
trigger check and is expected to behave the same way (not browser-checked).

### The fix (already proven)

`callbacks/freshness_threshold.py` returns `no_update` when the triggering
value is falsy (`n_clicks` 0/None), with a regression test
(`tests/test_freshness_threshold_callback.py::
TestActions::test_panel_insertion_with_zero_clicks_is_not_a_click`). The
same one-line guard and test apply to both affected callbacks. It was left
out of FRESHNESS-CONFIG-1 to keep that gate's scope to the freshness panel.
