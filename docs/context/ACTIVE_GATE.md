# Active Gate

Status: **CLOSED / COMMITTED LOCALLY / NOT YET PUSHED**
Date: 2026-09-04
Gate: RTL-IF-1 — Protocol-neutral command contract and persistence
Branch: `main`, baseline `662a605446bc7d78fc838704ce7340cb31800a6b`
Commit/push permission: **GRANTED and exercised for this commit.** RTL-IF-1
was implemented against explicit "DO NOT COMMIT OR PUSH" instructions and
left `READY FOR REVIEW / NOT COMMITTED`. It was then independently verified
by Codex (RTL-IF-1V — migration, transaction atomicity, request/command
integrity, device_id duplication invariant, programming provenance, command
contract, authorization, audit, reset/seed, tests, architecture boundary —
all PASS, no blockers), and this session's own RTL-IF-1-CLOSE task
explicitly authorizes commit and push. Pushing happens as its own step —
see the commit-SHA record below, updated after Step 4 verifies the remote.

## Purpose

Introduce the first protocol-neutral seam between an authorized RTL
programming request and a future device transport:

```
authorized Program RTL
        v
rtl_programming_requests   (operator-intent record, immutable — OPS-PROG-1)
        v
rtl_commands                (this gate)
        v
future transport            (not this tranche)
        v
future simulator / Eskom adapter (not this tranche)
```

No real transport in this tranche. See `docs/decisions/ADR-017-rtl-commands-are-the-protocol-neutral-transport-seam.md`
for the full decision record.

## What changed

- **`alembic/versions/008_rtl_commands.py`** — new `rtl_commands` table:
  `command_id`, `request_id` (FK -> `rtl_programming_requests`, UNIQUE —
  one command per request), `device_id` (FK -> `devices`), `command_type`,
  `state` (default `QUEUED`), `created_at`, `updated_at`. No CHECK
  constraint on `command_type`/`state` (deliberate — see ADR-017). Indexes
  for request lookup (the unique constraint), device/history lookup
  (`ix_rtl_commands_device_ts`), and future state/dispatch lookup
  (`ix_rtl_commands_state`).
- **`config/commands.py`** (new) — `COMMAND_TYPE_PROGRAM_RTL`,
  `STATE_QUEUED` vocabulary constants, mirroring `config/audit.py`'s style.
- **`repositories/plant_monitoring_repository.py`** — `CommandRecord`
  dataclass, `create_command()` (resolves `device_id` from the referenced
  request row, never from caller input), `get_command_for_request()`.
  `rtl_commands.device_id` duplicates `rtl_programming_requests.device_id`
  by design (query convenience — a caller resolves everything from the
  command alone rather than joining back to the request for device
  identity). That duplication's consistency is a **repository write-path
  invariant** — `create_command()`'s `SELECT ... FROM rtl_programming_requests`
  is the only way a `device_id` reaches the column — **not** a database
  CHECK/trigger/generated-column constraint across the two tables. No
  cross-table DB constraint enforces it; nothing else in this codebase
  writes to `rtl_commands.device_id`.
- **`services/rtl_programming_service.py`** — `record_request()` now
  creates one `rtl_commands` row inside the same transaction as the
  request insert and its audit write. A failed command insert rolls the
  request and audit back with it (no second transaction). No new audit
  event: `RTL_PROGRAM_REQUESTED` still records the operator's action once.
- **`services/rtl_command_service.py`** (new) — the minimum read API:
  `get_command_for_request(request_id)`. No command-management UI.
- **`db/seed_plant_monitoring.py`** — `rtl_commands` classified into
  `RESET_PRESERVES`, `PURGE_ORDER` (before its two parents), and
  `PURGE_DESTROYS_IRRECOVERABLY`, per ADR-010's D2 contract ("every table
  named individually").
- **`docs/decisions/ADR-017-...md`** (new) — the decision record.
- **`docs/decisions/ADR-010-...md`** — addendum noting the `rtl_commands`
  classification (ADR-010's own decision, D1-D4, is unchanged).
- **`docs/context/DECISION_INDEX.md`** — ADR-017 row added.
- Tests: `tests/test_migration_rtl_commands.py` (new),
  `tests/test_rtl_commands.py` (new), `tests/test_rtl_programming.py`
  (FK-safe wipe order updated — `rtl_commands` now exists and references
  `rtl_programming_requests`), `tests/test_migration_foundation.py`
  (`EXPECTED_UPGRADE_TABLES` includes `rtl_commands`),
  `tests/test_seed_reset_contract.py` (`KNOWN_TABLES` and purge-order
  assertions extended).

## Explicitly NOT implemented (out of scope, per the task)

SimulatorTransport, MQTT, RabbitMQ, SMS/email, workers, scheduler, retries,
command_attempts, SENT/ACK handling, success/failure transport transitions,
desired/reported state, 18:30 forwarding, monitoring use of
`rtl_active_state`, alarm redesign, UI redesign. No new runtime
dependencies were installed. The visible programming UI in
`callbacks/device_manage.py` is unchanged; `rtl_programming_requests` was
not modified into a transport record and is not updated later in this
tranche.

## Verification

- Focused: `tests/test_migration_rtl_commands.py` +
  `tests/test_migration_foundation.py` — 19 passed.
  `tests/test_rtl_commands.py` + `tests/test_rtl_programming.py` — 38
  passed. `tests/test_seed_reset_contract.py` — 21 passed.
- `python -m pytest -m db -q` — all passed, exit 0, no failures (Windows
  Git Bash swallows this pytest install's final summary line; exit code 0
  plus an unbroken dot sequence with no `F`/`E` markers across every
  progress chunk is the evidence available this session).
- `python -m pytest -m "not db" -q` — all passed, exit 0, same evidence
  shape as above.
- `python -m pytest -q` (full suite) — all passed, exit 0, same evidence
  shape as above.
- `python scripts/build_context_pack.py --check` — CLEAN, at both open and
  close of this gate.
- `git diff --check` — clean, no whitespace errors.
- `git status --short` — matches the file list above plus untouched
  `debug.log`; no unexpected changes.

## Codex RTL-IF-1V independent verification

Result: **VERIFIED**, no blockers — migration PASS; transaction atomicity
PASS; request/command integrity PASS; device_id duplication ACCEPTABLE WITH
DOCUMENTED INVARIANT (see the note under "What changed" above); programming
provenance PASS; command contract PASS; authorization PASS; audit PASS;
reset/seed PASS; tests PASS; architecture boundary PASS.

This gate does not overstate what was built: no physical RTL was
programmed, no command was sent, no transport exists. `rtl_commands` rows
stay `QUEUED` until a future transport tranche gives them a consumer.

## Known ambiguity

None encountered. No authority conflict between `AGENTS.md`,
`SOURCE_AUTHORITY.md`, `PROJECT_LEDGER.md`, or the RTL-related source files
inspected (`callbacks/device_manage.py`,
`services/rtl_programming_service.py`, `services/audit_service.py`,
`repositories/plant_monitoring_repository.py`,
`alembic/versions/005_rtl_operational_state.py`, `config/audit.py`).

## Next queued gate

None queued. This gate is implemented, independently verified (Codex
RTL-IF-1V), and committed locally as part of this same closure task. It is
**not yet pushed** at the point this paragraph was written (Step 2 of
RTL-IF-1-CLOSE, before the Step 3 commit exists) — the commit SHA and push
verification are recorded in the Step 5 finalization pass over this file,
never claimed here in advance of the push actually happening.
