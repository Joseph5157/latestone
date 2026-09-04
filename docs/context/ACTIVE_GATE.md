# Active Gate

Status: **CLOSED / COMMITTED LOCALLY / NOT YET PUSHED**
Date: 2026-09-04
Gate: RTL-IF-2 — SimulatorTransport + command lifecycle
Branch: `main`, baseline `bb9085b07b1e40b84ef78f695944a4787a8079df`
Commit/push permission: **GRANTED and exercised.** RTL-IF-2 was implemented
against explicit "DO NOT COMMIT OR PUSH" instructions and left
`READY FOR REVIEW / NOT COMMITTED`. It was then independently verified by
Codex (RTL-IF-2V — diff scope, migration 009, state machine, timestamp
integrity, dispatch transaction, transport contract, programming
provenance, authorization, audit, test quality, architecture boundary all
PASS; concurrent dispatch CONCURRENCY SAFE — the conditional QUEUED→SENT
update prevents duplicate transport calls; transport exception ACCEPTABLE
WITH DOCUMENTED RECOVERY REQUIREMENT — a transport exception leaves the
command coherently SENT, recovery/retry intentionally deferred; no
blockers), and this session's own RTL-IF-2-CLOSE task explicitly
authorized the commit and push recorded below (Verification section).

## Purpose

Add the first deterministic device-command execution path on top of
RTL-IF-1's `rtl_commands`, with no real external integration:

```
authorized PROGRAM RTL
        v
programming request
        v
rtl_commands = QUEUED           (RTL-IF-1)
        v
dispatch_command()              (explicit caller only — this gate)
        v
SimulatorTransport               (this gate — a test contract, not Eskom)
        v
SENT -> ACKNOWLEDGED -> SUCCEEDED
     \-> FAILED
     \-> TIMED_OUT
```

See `docs/decisions/ADR-018-simulator-transport-is-not-the-eskom-protocol.md`
for the full decision record.

## What changed

- **`alembic/versions/009_rtl_command_lifecycle.py`** — adds
  `sent_at`/`acknowledged_at`/`completed_at`/`failure_code`(`VARCHAR(30)`)/
  `failure_detail`(`VARCHAR(255)`, bounded — never a raw exception or stack
  trace) to `rtl_commands`, all nullable. Four CHECK constraints hold
  regardless of state vocabulary: a timestamp requires its predecessor
  timestamp (`sent_at`->`created_at`, `acknowledged_at`/`completed_at`->
  `sent_at`), and `failure_code` requires `completed_at`. `state`/
  `command_type` still carry **no** CHECK (ADR-017's decision, unchanged) —
  the six-state vocabulary lives in `config/commands.py`, enforced by the
  service layer, not the database.
- **`config/commands.py`** — adds `STATE_SENT`/`STATE_ACKNOWLEDGED`/
  `STATE_SUCCEEDED`/`STATE_FAILED`/`STATE_TIMED_OUT`, `TERMINAL_STATES`,
  `ALLOWED_TRANSITIONS` (the single source of truth for legal moves — every
  terminal state's entry is empty, which is the entire mechanism
  preventing backward/further movement), and `FAILURE_CODE_SIMULATED_FAILURE`/
  `FAILURE_CODE_SIMULATED_TIMEOUT`. `ACKNOWLEDGED -> FAILED` was
  considered and deliberately **not** added — nothing in this tranche's
  completion model reaches it.
- **`repositories/plant_monitoring_repository.py`** — `CommandRecord`
  extended with the five new fields; `get_command(command_id)`,
  `get_programming_request(request_id)`, and `update_command_state()` (one
  conditional `UPDATE ... WHERE state = :expected_state` — the DB-level
  half of race-safety; the SET clause's timestamp column name is validated
  against a fixed allowlist before interpolation, never caller input).
- **`services/rtl_command_service.py`** — extended with `mark_sent`,
  `mark_acknowledged`, `mark_succeeded`, `mark_failed`, `mark_timed_out`,
  and `CommandTransitionError`. **The only code path allowed to write
  `rtl_commands.state`** — every call validates against
  `config.commands.ALLOWED_TRANSITIONS` before touching the database, then
  performs one conditional UPDATE (one transaction).
- **`services/device_transport.py`** (new) — `DeviceTransport` protocol,
  `TransportOutcome`. Receives a `CommandRecord` + its referenced
  `ProgrammingRequestRecord`; never a DB session, never Flask/session
  identity, no authorization role (authorization already happened before
  the command existed).
- **`services/simulator_transport.py`** (new) — `SimulatorTransport`, a
  deterministic, in-process `DeviceTransport`: SUCCESS/FAILURE/TIMEOUT
  fixed at construction, returned synchronously on every `send()`. No
  network, sleep, thread, background loop, MQTT, SMS, or filesystem
  coordination. Explicitly documented as an internal test contract, not
  the Eskom protocol. `db/live_simulator.py` (the measurement generator)
  is untouched and unrelated.
- **`services/rtl_command_dispatch_service.py`** (new) — `dispatch_command(command_id, transport)`:
  confirms the command is QUEUED (refuses — `CommandNotDispatchableError`
  — for any other state, including terminal ones, rather than silently
  re-dispatching), resolves the referenced request, marks SENT, invokes
  the transport, maps the outcome to the correct transition(s). **Called
  explicitly only** — by tests today, by a future worker that does not
  exist yet. Never wired to a callback; the existing Program RTL action in
  `callbacks/device_manage.py` still stops at `command = QUEUED`.
- **`docs/decisions/ADR-018-...md`** (new) — the decision record.
- **`docs/context/DECISION_INDEX.md`** — ADR-018 row added.
- Tests: `tests/test_migration_rtl_command_lifecycle.py` (new, 11 tests —
  CHECK constraints + an upgrade/downgrade/upgrade round trip),
  `tests/test_rtl_command_service_lifecycle.py` (new, 12 tests — transition
  legality, timestamps, terminal-state integrity, provenance, audit count),
  `tests/test_rtl_command_dispatch.py` (new, 15 tests — full dispatch
  outcomes, re-dispatch refusal, no-network-call proof, transport-exception
  resilience). No existing test file was modified — RTL-IF-1's
  `tests/test_rtl_commands.py`/`tests/test_rtl_programming.py` and the
  authorization suites (`tests/test_action_guard_db.py`,
  `tests/test_technician_operations.py`) pass unmodified.

## Explicitly NOT implemented (out of scope, per the task)

MQTT, RabbitMQ, Paho/Pika, worker, scheduler, retry, command_attempts,
automatic dispatch, browser lifecycle UI, SMS/email, notification
delivery, startup/check-in event simulation, alarm event simulation,
desired/reported state, 18:30 forwarding, active-state monitoring changes.
No `CANCELLED` state, no retry states. No new runtime dependencies were
installed. `db/live_simulator.py` was not modified. No new audit event was
added for any lifecycle transition — `RTL_PROGRAM_REQUESTED` still records
the operator's action exactly once; a durable transport-transition
history/audit trail is explicitly deferred to a later tranche (see
ADR-018).

## Verification

- Focused: `tests/test_migration_rtl_command_lifecycle.py` — 11 passed.
  `tests/test_rtl_command_service_lifecycle.py` — 12 passed.
  `tests/test_rtl_command_dispatch.py` — 15 passed.
- Regression: `tests/test_rtl_commands.py` + `tests/test_rtl_programming.py`
  + `tests/test_migration_rtl_commands.py` + `tests/test_migration_foundation.py`
  + `tests/test_action_guard_db.py` + `tests/test_technician_operations.py`
  — all passed, run together in one invocation.
- `python -m pytest -m db -q` — all passed, exit 0, no failures (Windows
  Git Bash swallows this pytest install's final summary line; exit code 0
  plus an unbroken dot sequence with no `F`/`E` markers across every
  progress chunk is the evidence available this session — same caveat
  recorded at RTL-IF-1's close).
- `python -m pytest -m "not db" -q` — all passed, exit 0, same evidence
  shape as above.
- `python -m pytest -q` (full suite) — all passed, exit 0, same evidence
  shape as above.
- `python scripts/build_context_pack.py --check` — CLEAN, at both open and
  close of this gate.
- `git diff --check` — clean, no whitespace errors.
- `git status --short` — matches the file list above plus untouched
  `debug.log`; no unexpected changes.
- Push verification (RTL-IF-2-CLOSE Step 4): recorded here once `git push
  origin main` and the local/origin/ls-remote SHA match are actually
  performed — not claimed in advance of that step.

## Codex RTL-IF-2V independent verification

Result: **VERIFIED**, no blockers — diff scope PASS; migration 009 PASS;
state machine PASS; timestamp integrity PASS; dispatch transaction PASS;
transport contract PASS; programming provenance PASS; authorization PASS;
audit PASS; test quality PASS; architecture boundary PASS.

Concurrent dispatch: **CONCURRENCY SAFE** — the conditional
`QUEUED -> SENT` database update (`repositories.plant_monitoring_repository.
update_command_state`'s `WHERE state = :expected_state`) prevents two
concurrent `dispatch_command()` calls on the same command from both
reaching `transport.send()`; the loser's UPDATE affects zero rows and
raises `CommandTransitionError`/`CommandNotDispatchableError` instead of
double-dispatching.

Transport exception: **ACCEPTABLE WITH DOCUMENTED RECOVERY REQUIREMENT** —
a transport exception leaves the command coherently `SENT` (verified by
`tests/test_rtl_command_dispatch.py::test_l_transport_exception_leaves_command_at_sent_not_corrupted`).
Recovery/retry from a stuck `SENT` command is intentionally deferred — no
retry, worker, or scheduler exists in this tranche (or any RTL-IF tranche
so far) to resume it automatically; a future tranche owns that.

This gate does not overstate what was built: **no physical RTL is
programmed by anything in this tranche.** `ACKNOWLEDGED`/`SUCCEEDED` are
`SimulatorTransport`'s own internal test-contract semantics — evidence
that the configured, deterministic simulator ran to completion, not
evidence of real device communication. No MQTT, no Eskom protocol, no SMS,
no real transport of any kind exists yet.

## Known ambiguity

None encountered. No authority conflict between `AGENTS.md`,
`SOURCE_AUTHORITY.md`, `PROJECT_LEDGER.md`, ADR-017, or the RTL-IF-1 source
files inspected. One judgment call, not a conflict: whether to add a
database CHECK enumerating the six lifecycle state strings now that the
full vocabulary is known for this tranche. Decided **no** — ADR-017's own
reasoning (a future transport tranche will need to extend the vocabulary
without a migration) applies just as much to RTL-IF-2 as it did when
written, and the task's own framing ("Do not add CANCELLED or retry states
yet") signals this list is still not necessarily final. Legality is
enforced entirely by `config.commands.ALLOWED_TRANSITIONS` and
`rtl_command_service`, documented in ADR-018.

## Next queued gate

None queued. This gate is implemented, independently verified (Codex
RTL-IF-2V), and committed locally as part of this same closure task. It is
**not yet pushed** at the point this paragraph was written (Step 2 of
RTL-IF-2-CLOSE, before the Step 3 commit exists) — the commit SHA and push
verification are recorded in the Step 5 finalization pass over this file,
never claimed here in advance of the push actually happening.
