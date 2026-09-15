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

from dataclasses import dataclass

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


@dataclass(frozen=True)
class DispatchPolicy:
    """Protocol-neutral dispatch policy for a future transport worker.

    ``DeviceTransport`` reports timeout as an outcome; this object records
    the policy a caller wants the eventual adapter/worker to apply without
    embedding a wire timeout or retry interpretation here.  Retries are
    deliberately disabled by the safe default and must be explicitly opted
    into by a later, client-approved policy.
    """

    timeout_seconds: float = 30.0
    max_retries: int = 0
    retry_delay_seconds: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.timeout_seconds, bool) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int):
            raise ValueError("max_retries must be a non-negative integer")
        if self.max_retries < 0:
            raise ValueError("max_retries must be a non-negative integer")
        if isinstance(self.retry_delay_seconds, bool) or self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must be non-negative")

    @property
    def retries_enabled(self) -> bool:
        return self.max_retries > 0


DEFAULT_DISPATCH_POLICY = DispatchPolicy()

#: `rtl_programming_requests.status` vocabulary (migration 005's CHECK
#: constraint: 'pending', 'queued', 'sent', 'successful', 'failed').
#: RTL-PROG-EXEC-1 is the first tranche that writes any of these besides
#: 'pending' — see REQUEST_STATUS_FOR_COMMAND_STATE below, the seam this
#: gate adds between the two lifecycles. Named here, alongside the command
#: vocabulary rather than in a separate module, because the projection is
#: inherently a pairing of both.
REQUEST_STATUS_PENDING = "pending"
REQUEST_STATUS_QUEUED = "queued"
REQUEST_STATUS_SENT = "sent"
REQUEST_STATUS_SUCCESSFUL = "successful"
REQUEST_STATUS_FAILED = "failed"

#: Every `rtl_commands.state` this module defines maps to exactly one
#: `rtl_programming_requests.status` (RTL-PROG-EXEC-1). SENT and
#: ACKNOWLEDGED both project to "sent" — from the operator's point of view
#: both mean "handed to transport, not yet resolved"; ACKNOWLEDGED's own
#: meaning (ADR-018: "the configured send() call reported success and the
#: dispatcher advanced one step") is not something the request lifecycle
#: distinguishes. FAILED and TIMED_OUT both project to "failed" — the
#: request's four-state completion model (migration 005) has no separate
#: timeout status, and inventing one would be a schema change this gate
#: does not make. "pending" is deliberately absent from this map: it is
#: the request's insert-time default, never a projection target.
REQUEST_STATUS_FOR_COMMAND_STATE: dict[str, str] = {
    STATE_QUEUED: REQUEST_STATUS_QUEUED,
    STATE_SENT: REQUEST_STATUS_SENT,
    STATE_ACKNOWLEDGED: REQUEST_STATUS_SENT,
    STATE_SUCCEEDED: REQUEST_STATUS_SUCCESSFUL,
    STATE_FAILED: REQUEST_STATUS_FAILED,
    STATE_TIMED_OUT: REQUEST_STATUS_FAILED,
}
