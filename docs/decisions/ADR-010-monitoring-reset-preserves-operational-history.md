# ADR-010: A monitoring reset replaces measurements and preserves operational history

Status: Approved
Date: 2026-08-30
Evidence: live `information_schema` FK inventory (below);
`db/seed_plant_monitoring.py:48-54` (`_reset_data`, the defect);
`db/seed_plant_monitoring.py:202-205, 224-227, 257-260` (all three hierarchy
inserts are already `ON CONFLICT DO NOTHING`);
`db/hierarchy.py:83-87` (`build_hierarchy` output is stable by construction)
Implemented-by: `29f5290`
Fixes: SEED-RESET-1 (`docs/context/KNOWN_DEFECTS.md`)

## Context

`seed_plant_monitoring --reset` could not complete. `_reset_data` deleted in
this order:

```
readings -> devices -> transformers -> plants
```

and called it "FK-safe order". That was true when it was written. The DB-1..4
and ROLE-3 work then added four more tables referencing `devices`, none of
them cleared first, so on any database that had registered an RTL, assigned a
technician, or run the event seed, `--reset` failed on a foreign-key
violation.

Because it is the documented way back from every other seed, its failure
removed the rollback story for all of them — which is what blocked the CC-1
mixed-freshness browser verification.

### The complete dependency picture, from the live schema

Every foreign key in `plant_monitoring`, `delete_rule` included. Nothing
cascades; every one is `NO ACTION`:

| Child | Column | Parent |
|---|---|---|
| `readings` | `device_id` | `devices` |
| `device_events` | `device_id` | `devices` |
| `rtl_active_state` | `device_id` | `devices` |
| `rtl_programming_requests` | `device_id` | `devices` |
| `user_device_assignments` | `device_id` | `devices` |
| `devices` | `transformer_id` | `transformers` |
| `device_events` | `transformer_id` | `transformers` |
| `rtl_programming_requests` | `transformer_id` | `transformers` |
| `transformers` | `plant_id` | `plants` |
| `audit_log` | `user_id` | `users` |
| `message_forwarding` | `user_id` | `users` |
| `rtl_programming_requests` | `requested_by` | `users` |
| `user_device_assignments` | `user_id` / `assigned_by` | `users` |

## Decision

### D1 — A reset replaces MEASUREMENTS, not the hierarchy

`--reset` deletes `readings` and nothing else.

This is not a compromise to dodge the foreign keys; it is what the seed
always meant. Deleting the hierarchy was never necessary, and the code
already proves it: all three hierarchy inserts are
`ON CONFLICT (…) DO NOTHING` (`:202`, `:224`, `:257`), and `build_hierarchy`
documents its own output as "stable regardless of input ordering"
(`db/hierarchy.py:85-87`). The same 30/71/120 rows with the same ids are
produced on every run, so re-inserting over an existing hierarchy is already
a no-op.

Removing the deletes therefore makes the command **strictly less
destructive and strictly more likely to succeed**, with no behaviour lost.
The reserved identifier `plant-01-t1-d1` keeps its row, and every
`device_id` that events, assignments, active state and programming requests
point at stays valid throughout.

### D2 — What a reset preserves, stated per table

The monitoring seed owns *measurements*. It does not own the record of what
people and devices did. Named individually, because "everything else" is not
a contract:

| Table | On `--reset` | Why |
|---|---|---|
| `readings` | **REPLACED** | the synthetic measurements; the seed's own output |
| `plants` / `transformers` / `devices` | **PRESERVED** (reconciled) | deterministic and idempotent; deleting them is what broke |
| `device_events` | **PRESERVED** | append-only by contract (INGEST-D3); a reseed of telemetry is not a reason to forget that an RTL powered down |
| `user_device_assignments` | **PRESERVED** | who is responsible for what is an administrative fact, not a measurement |
| `rtl_active_state` | **PRESERVED** | activation is a real device state change (ACT-D1..D5), not synthetic data |
| `rtl_programming_requests` | **PRESERVED** | a request someone made |
| `audit_log` | **PRESERVED** | an audit log that a dev command can silently empty is not an audit log |
| `users` | **PRESERVED** | never the monitoring seed's business |

### D3 — The destructive teardown exists, is separate, and says so

A genuine "give me an empty database" operation is a real need, and hiding
it inside `--reset` is what caused this defect. It becomes its own flag,
`--purge`, which:

- deletes in the FK-safe order derived from the table above,
- names every domain it is about to destroy, with row counts, before doing
  anything,
- refuses to run without an explicit second acknowledgement, and
- is never invoked by `--reset`.

### D4 — No `CASCADE`, ever

Not on the constraints, not on the deletes. `CASCADE` would make `--reset`
succeed while silently destroying audit and assignment history that no other
command can rebuild — the same defect wearing the fix's clothes, and harder
to notice because the error message disappears.

### D5 — The freshness demo becomes reversible, not merely repeatable

`db/seed_freshness_demo.py` must remove readings to create staleness and
absence (they cannot be inserted — ADR-009 D3). It therefore **captures the
exact rows it will delete before deleting them**, and `--restore` puts them
back.

- Capture is written and read back before a single row is deleted. A crash
  between the two leaves the database untouched.
- Restore inserts with `ON CONFLICT DO NOTHING`, which the
  `UNIQUE (device_id, metric, reading_ts)` constraint makes exactly
  idempotent — so a half-finished apply or a repeated restore both converge
  on the original state instead of duplicating rows.
- `--apply` refuses when a capture already exists, so the pristine copy can
  never be overwritten by a second run.

That turns the CC-1 acceptance sequence into: capture → apply → verify →
restore → prove restored, with no rebuild of anything.

## Consequences

- `--reset` stops being a rebuild and starts being what its name implies.
  A developer wanting the old teardown behaviour uses `--purge`, and finds
  out exactly what it destroys first.
- The blocker on CC-1's mixed-freshness verification is removed without
  making any seed more destructive.
- `_reset_data`'s "FK-safe order" comment goes away with the code. A comment
  asserting an ordering is safe rots the moment a table is added; the
  ordering now lives in one place with a test that walks the live schema.
