# ADR-017: rtl_commands is the protocol-neutral seam between a programming request and future transport

Status: Approved
Date: 2026-09-04
Evidence: `alembic/versions/008_rtl_commands.py`;
`repositories/plant_monitoring_repository.py` (`CommandRecord`,
`create_command`, `get_command_for_request`);
`services/rtl_programming_service.py` (`record_request` now creates one
command in the same transaction as the request insert and its audit row);
`config/commands.py`; `services/rtl_command_service.py`;
`tests/test_migration_rtl_commands.py`; `tests/test_rtl_commands.py`
Implemented-by: `831ea2b3ea612921d9fb44813924aeea43922fb0` (`feat(integration): add protocol-neutral RTL command foundation`)
Supersedes: nothing — extends OPS-PROG-1 without changing what
`rtl_programming_requests` means.

## Context

`rtl_programming_requests` (OPS-PROG-1, migration 005) already persists
honestly: "request recorded ≠ programmed" (PROG-D7), and it is append-only
by design (PROG-D3) so it can serve as intent/provenance. But nothing in the
schema represented "this request is now something a transport layer could
act on." A future MQTT/SMS/Eskom adapter would have had nowhere to attach
dispatch state without either mutating the immutable request row (breaking
PROG-D3) or inventing its own ad hoc bridge table with no established
pattern to follow.

## Decision

**`rtl_commands` is the one seam between an authorized programming request
and a future transport:**

```
authorized Program RTL
        v
rtl_programming_requests   (operator-intent record, immutable — OPS-PROG-1)
        v
rtl_commands                (this ADR)
        v
future transport            (not this tranche)
        v
future simulator / Eskom adapter (not this tranche)
```

One command per request, enforced by `uq_rtl_commands_request_id` — not
merely by service-layer discipline. Created atomically inside
`rtl_programming_service.record_request`'s existing transaction, alongside
the request insert and its audit row: a failed command insert rolls the
request (and audit) back with it, the same AUD-1/FWD-D5 atomicity pattern
already governing forwarding, programming and deactivation.

The command references the request rather than duplicating its payload:
`device_id` is resolved from the referenced request row at insert time (the
same pattern `create_programming_request` already uses to resolve
`transformer_id` from `devices`), so it cannot name a device the request
didn't. `master_msisdn`, `requested_by`, `request_method` and every other
operator-supplied field stay solely on the request — a future transport
resolves everything it needs from the command plus its referenced request,
never from a second copy.

## Why no CHECK constraint on command_type or state

`rtl_programming_requests.status` carries a CHECK constraint (migration
005) because its five-value lifecycle (`pending`/`queued`/`sent`/
`successful`/`failed`) was already fully known when that migration was
written. `rtl_commands.command_type`/`state` deliberately do not: this
tranche's own vocabulary is a single value each (`PROGRAM_RTL`, `QUEUED` —
`config/commands.py`), and a future transport tranche will need to add
`SENT`/`ACK`/`FAILED` states — and, eventually, other command types — without
a schema migration merely to extend an enum. This follows
`device_events.event_type`'s precedent (migration 006, open `VARCHAR`) over
migration 005's closed `CHECK`; the difference is deliberate, not
inconsistency: 005's vocabulary was complete at the time, this one is not.

## What this does not claim

No transport exists. Every `rtl_commands` row stays `QUEUED` until a future
RTL-IF tranche gives it a state machine and a consumer. Recording a command
is not evidence of dispatch, exactly as recording a request was never
evidence of programming — PROG-D7 is unchanged, still true, still enforced
by the same UI copy in `callbacks/device_manage.py`.

No new audit event exists for command creation. `RTL_PROGRAM_REQUESTED`
(the existing human-actor audit entry) still records the operator's action
once; the command row is an internal artifact of accepting that request, not
a second user-visible event. A future SENT/ACK/FAILED transition can define
its own audit/history design when that transport work exists — inventing
one now, for a state machine that does not yet run, would be speculative.

## Extends ADR-010's reset/purge contract

`rtl_commands` joins `RESET_PRESERVES` (it is operational history, not
synthetic measurement — a command someone's request produced) and
`PURGE_ORDER` (deleted before both its parents, `devices` and
`rtl_programming_requests`) and `PURGE_DESTROYS_IRRECOVERABLY` (nothing
rebuilds a lost command record). See `db/seed_plant_monitoring.py` and
`tests/test_seed_reset_contract.py::TestPurgeOrderAgainstTheLiveSchema`,
which walks the live FK graph and would fail here if `rtl_commands` had
been left unclassified — precisely the SEED-RESET-1 failure mode ADR-010
exists to prevent for every new table.
