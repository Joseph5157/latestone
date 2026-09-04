# ADR-018: SimulatorTransport is a deterministic test contract, not the Eskom protocol

Status: Approved
Date: 2026-09-04
Evidence: `alembic/versions/009_rtl_command_lifecycle.py`;
`config/commands.py` (`ALLOWED_TRANSITIONS`, `TERMINAL_STATES`,
`FAILURE_CODE_*`); `services/rtl_command_service.py` (`mark_sent`,
`mark_acknowledged`, `mark_succeeded`, `mark_failed`, `mark_timed_out`);
`services/device_transport.py` (`DeviceTransport`, `TransportOutcome`);
`services/simulator_transport.py`; `services/rtl_command_dispatch_service.py`
(`dispatch_command`); `tests/test_migration_rtl_command_lifecycle.py`;
`tests/test_rtl_command_service_lifecycle.py`;
`tests/test_rtl_command_dispatch.py`
Implemented-by: not yet
Supersedes: nothing — extends ADR-017 without changing what
`rtl_programming_requests` or `rtl_commands`'s creation-time contract mean.

## Context

ADR-017 (RTL-IF-1) gave `rtl_commands` a state column with no CHECK
constraint and left every row `QUEUED` forever — deliberately, because no
transport existed to move it. RTL-IF-2 is the first tranche that actually
moves a command through a lifecycle, but still with **no real transport**:
no MQTT, no SMS, no Eskom protocol client. Building the lifecycle machinery
(state transitions, timestamps, a dispatcher, a transport abstraction)
against a deterministic simulator, before any production adapter exists,
lets the machinery be tested exhaustively without a single network call.

## Decision

**Four new pieces, each with a narrow job:**

1. **The lifecycle** (`config/commands.py`): `QUEUED -> SENT ->
   ACKNOWLEDGED -> SUCCEEDED`, with `SENT -> FAILED` and `SENT ->
   TIMED_OUT` as the two alternate terminal outcomes.
   `ALLOWED_TRANSITIONS` is the single source of truth for what is legal;
   every terminal state's entry is the empty set, which is the entire
   mechanism preventing a terminal state from moving again — there is no
   separate "is this terminal" check to drift out of sync with the map.
   `ACKNOWLEDGED -> FAILED` was considered and **not** added: nothing in
   this tranche's completion model reaches it (SimulatorTransport's FAILURE
   outcome goes `SENT -> FAILED` directly, never through `ACKNOWLEDGED`),
   and RTL-IF-2's own instructions were explicit that an edge needs a
   concrete justification, not just plausibility.

2. **The schema** (`alembic/versions/009_rtl_command_lifecycle.py`):
   `sent_at`/`acknowledged_at`/`completed_at`/`failure_code`/
   `failure_detail`, all nullable, plus four CHECK constraints that hold
   regardless of which state-string vocabulary is in use — a timestamp
   requires its predecessor timestamp, and `failure_code` requires
   `completed_at`. `state`/`command_type` still carry **no** CHECK
   (ADR-017's decision, unchanged): the six-state vocabulary lives in
   `config/commands.py` and is enforced by `rtl_command_service`, not the
   database, so a future transport tranche can still extend it without a
   migration.

3. **The transition boundary** (`services/rtl_command_service.py`): the
   only code path allowed to write `rtl_commands.state`. Every transition
   does one conditional `UPDATE ... WHERE state = :expected_state`
   (`repositories.plant_monitoring_repository.update_command_state`) inside
   one transaction — not a read-then-write with a race window. A caller
   attempting an illegal move (including any move out of a terminal state,
   or two concurrent dispatches of the same command) is refused with
   `CommandTransitionError` before or instead of a database write, never
   partially applied.

4. **The transport contract and its one implementation**
   (`services/device_transport.py`, `services/simulator_transport.py`,
   `services/rtl_command_dispatch_service.py`): `DeviceTransport.send()`
   receives a `CommandRecord` and its referenced `ProgrammingRequestRecord`
   — never a database session, never Flask/session identity.
   Authorization already happened before the command existed (at the
   action guard, before `rtl_programming_service.record_request` ever
   ran); a transport has no authorization role. `SimulatorTransport`
   returns a fixed, pre-configured outcome (`SUCCESS`/`FAILURE`/`TIMEOUT`)
   synchronously — no network, no sleep, no thread, no background loop.
   `dispatch_command()` is called explicitly, by tests today and by a
   future worker/scheduler that does not exist yet — **never**
   automatically, and never from `callbacks/device_manage.py` or
   `rtl_programming_service.record_request`. The Program RTL action still
   stops at `command = QUEUED`.

## What "ACKNOWLEDGED" does not mean

`ACKNOWLEDGED` is a `SimulatorTransport` fixture state meaning "the
configured send() call reported success and the dispatcher advanced one
step." It is **not** evidence that a physical RTL received or acted on
anything, and it does not yet correspond to any documented Eskom protocol
acknowledgement. A future production adapter that implements
`DeviceTransport` for a real device defines its own mapping onto (or
extension of) this lifecycle; RTL-IF-2 does not pre-commit to what a real
ACK looks like, how long a real timeout is, or what a real failure code
means. `SIMULATED_FAILURE`/`SIMULATED_TIMEOUT` (`config/commands.py`) are
named as simulated on purpose, so nothing downstream can mistake them for
a provider error code.

## What this does not claim

No physical RTL is programmed by any test in this tranche. `rtl_commands`
rows reaching `SUCCEEDED` describe the simulator's own internal test
contract completing, nothing about device state. `rtl_programming_requests`
remains the immutable operator-intent record — unchanged, unread by the
transition/dispatch layer for anything but resolving `device_id`/context,
and verified unchanged after every simulated outcome
(`tests/test_rtl_command_dispatch.py`,
`tests/test_rtl_command_service_lifecycle.py`).

No new audit event exists for any lifecycle transition. `RTL_PROGRAM_REQUESTED`
still records the operator's action exactly once; a durable transport-
transition history/audit trail (if the client ever needs to see "when was
this ACKed") is explicitly deferred to a later tranche that has a real
transport to describe, rather than invented now against a simulator.

No retry, no `CANCELLED` state, no command_attempts, no worker, no
scheduler, no automatic dispatch. `dispatch_command()` is dumb on purpose:
it does exactly what its caller tells it to, once, and nothing decides to
call it but a human running a test (or, later, a worker this tranche does
not build).
