"""RTL command type, state and failure-code vocabulary (RTL-IF-1, RTL-IF-2).

Constants only — no logic, mirroring `config/audit.py`. Unlike
`rtl_programming_requests.status` (a CHECK-constrained, fully-known
five-value lifecycle since migration 005), `rtl_commands.command_type` and
`rtl_commands.state` carry no CHECK constraint (migration 008) — the
lifecycle below is enforced entirely by
`services/rtl_command_service.py`'s transition map against this module, not
by the database. A future transport tranche extends this module (new
states, new failure codes) rather than writing a migration merely to grow
an enum.
"""
from __future__ import annotations

#: The only command type either tranche writes. A programming request always
#: produces exactly one PROGRAM_RTL command (RTL-IF-1); future tranches may
#: add further types (e.g. a deactivation or forwarding command) as those
#: features grow their own transport story.
COMMAND_TYPE_PROGRAM_RTL = "PROGRAM_RTL"

#: Lifecycle states (RTL-IF-2). QUEUED is the only state RTL-IF-1 ever
#: wrote; the rest exist for the deterministic SimulatorTransport dispatcher
#: this tranche adds — see services/rtl_command_dispatch_service.py.
STATE_QUEUED = "QUEUED"
STATE_SENT = "SENT"
STATE_ACKNOWLEDGED = "ACKNOWLEDGED"
STATE_SUCCEEDED = "SUCCEEDED"
STATE_FAILED = "FAILED"
STATE_TIMED_OUT = "TIMED_OUT"

#: Terminal states never transition further (services/rtl_command_service.py
#: enforces this by giving each an empty entry in ALLOWED_TRANSITIONS below —
#: not by a separate check, so there is exactly one place this fact lives).
TERMINAL_STATES = frozenset({STATE_SUCCEEDED, STATE_FAILED, STATE_TIMED_OUT})

#: The complete legal transition graph (RTL-IF-2 section 1). Deliberately
#: minimal: no CANCELLED, no retry, no ACKNOWLEDGED -> FAILED — the
#: SimulatorTransport's FAILURE outcome never reaches ACKNOWLEDGED (it goes
#: SENT -> FAILED directly), so that edge has no justification yet. Extend
#: this map, not a schema migration, when a future transport needs a new
#: state or edge.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATE_QUEUED: frozenset({STATE_SENT}),
    STATE_SENT: frozenset({STATE_ACKNOWLEDGED, STATE_FAILED, STATE_TIMED_OUT}),
    STATE_ACKNOWLEDGED: frozenset({STATE_SUCCEEDED}),
    STATE_SUCCEEDED: frozenset(),
    STATE_FAILED: frozenset(),
    STATE_TIMED_OUT: frozenset(),
}

#: Normalized internal failure codes (RTL-IF-2 section 7). Never a
#: provider-specific error code — SimulatorTransport is not the Eskom
#: protocol, and a future production adapter defines its own mapping onto
#: (or extension of) this vocabulary, not a reuse of an Eskom wire code.
FAILURE_CODE_SIMULATED_FAILURE = "SIMULATED_FAILURE"
FAILURE_CODE_SIMULATED_TIMEOUT = "SIMULATED_TIMEOUT"
