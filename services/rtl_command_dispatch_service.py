"""Explicit command dispatch (RTL-IF-2).

    accepted programming request
            v
    rtl_commands = QUEUED   (rtl_programming_service.record_request, RTL-IF-1)
            v
    dispatch_command()      (this module — explicit caller only)
            v
    DeviceTransport.send()  (services/device_transport.py)
            v
    lifecycle transition(s) (services/rtl_command_service.py)

**No automatic dispatch.** `dispatch_command()` is called by tests today
and, in a future tranche, by a worker/scheduler that does not exist yet —
never by a callback, never by `rtl_programming_service.record_request`
itself. The existing Program RTL action in
`callbacks/device_manage.py`/`services/rtl_programming_service.py` still
stops at `command = QUEUED`; nothing in this module is wired to it.
"""
from __future__ import annotations

from config import commands as command_cfg
from repositories.plant_monitoring_repository import CommandRecord
from repositories import plant_monitoring_repository as repo
from services import rtl_command_service
from services.device_transport import (
    TRANSPORT_RESULT_FAILURE,
    TRANSPORT_RESULT_SUCCESS,
    TRANSPORT_RESULT_TIMEOUT,
    DeviceTransport,
    is_transport_configured,
)


class CommandNotDispatchableError(Exception):
    """Refused to dispatch: unknown command, or not currently QUEUED.

    A terminal or already-in-flight command (SENT/ACKNOWLEDGED/SUCCEEDED/
    FAILED/TIMED_OUT) is refused loudly here rather than silently
    re-dispatched — RTL-IF-2 section 1/6's "do not silently re-dispatch
    completed commands", generalized to every non-QUEUED state, since
    re-running a command already in flight is exactly as wrong as re-running
    one already finished.
    """


class ProductionTransportNotConfiguredError(CommandNotDispatchableError):
    """No production transport was supplied; command remains QUEUED."""


def dispatch_command(
    command_id: int,
    transport: DeviceTransport | None = None,
    *,
    policy: command_cfg.DispatchPolicy = command_cfg.DEFAULT_DISPATCH_POLICY,
) -> CommandRecord:
    """Dispatch one QUEUED command through ``transport`` to a terminal
    (or SENT-and-unresolved, if the transport itself raises) state.

    1. Loads the command and confirms it is dispatchable (state QUEUED).
    2. Resolves the protocol-neutral programming request it references.
    3. Marks the command SENT (its own DB transaction).
    4. Invokes ``transport.send(command, request)``.
    5. Maps the outcome onto the correct lifecycle transition(s), each its
       own DB transaction — SUCCESS is ACKNOWLEDGED then SUCCEEDED; FAILURE
       is FAILED; TIMEOUT is TIMED_OUT.

    If ``transport.send()`` raises, the command is left exactly at SENT —
    a genuine, non-terminal, non-corrupted resting state (it really was
    sent; the outcome is merely unknown to this call). The exception
    propagates unchanged: a transport is documented not to raise for a
    modeled delivery failure, so a raise here is a real bug, not something
    to paper over with a guessed lifecycle transition.
    """
    if not is_transport_configured(transport):
        raise ProductionTransportNotConfiguredError(
            "No device transport is configured; command remains queued."
        )
    if not isinstance(policy, command_cfg.DispatchPolicy):
        raise ValueError("policy must be a DispatchPolicy")
    if policy.retries_enabled:
        raise CommandNotDispatchableError(
            "Retries are not enabled until a client-approved command policy exists."
        )

    command = rtl_command_service.get_command(command_id)
    if command is None:
        raise CommandNotDispatchableError(f"Unknown command_id: {command_id!r}")
    if command.state != command_cfg.STATE_QUEUED:
        raise CommandNotDispatchableError(
            f"Command {command_id} is {command.state!r}, not QUEUED; "
            "refusing to dispatch."
        )

    request = repo.get_programming_request(command.request_id)
    if request is None:
        # Cannot happen while rtl_commands.request_id keeps its FK to
        # rtl_programming_requests — guarded explicitly rather than left to
        # surface as an obscure AttributeError further down.
        raise CommandNotDispatchableError(
            f"Command {command_id} references unknown request_id "
            f"{command.request_id!r}."
        )

    command = rtl_command_service.mark_sent(command_id)

    outcome = transport.send(command, request)

    if outcome.result == TRANSPORT_RESULT_SUCCESS:
        rtl_command_service.mark_acknowledged(command_id)
        return rtl_command_service.mark_succeeded(command_id)
    if outcome.result == TRANSPORT_RESULT_FAILURE:
        return rtl_command_service.mark_failed(
            command_id,
            failure_code=outcome.failure_code,
            failure_detail=outcome.failure_detail,
        )
    if outcome.result == TRANSPORT_RESULT_TIMEOUT:
        return rtl_command_service.mark_timed_out(
            command_id,
            failure_code=outcome.failure_code,
            failure_detail=outcome.failure_detail,
        )
    raise CommandNotDispatchableError(
        f"Unknown transport result for command {command_id}: "
        f"{outcome.result!r}."
    )


__all__ = [
    "CommandNotDispatchableError",
    "ProductionTransportNotConfiguredError",
    "dispatch_command",
]
