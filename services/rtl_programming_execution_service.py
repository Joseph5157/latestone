"""Programming-request execution (RTL-PROG-EXEC-1).

    operator's programming request         (rtl_programming_service, RTL-IF-1)
            v
    its existing QUEUED command             (rtl_commands, ADR-017)
            v
    execute_request()                       (this module — explicit caller only)
            v
    rtl_command_dispatch_service.dispatch_command()   (RTL-IF-2, ADR-018)
            v
    DeviceTransport.send()                  (services/device_transport.py)
            v
    command lifecycle transition(s)         (services/rtl_command_service.py)
            v
    request status projection               (RTL-PROG-EXEC-1, same transaction
                                              as each command transition)

This module resolves "which command belongs to this request" and hands it
to the dispatcher; it invents nothing about transport, timing, or retries —
every one of those decisions already belongs to
`services/rtl_command_dispatch_service.py`/`services/device_transport.py`
(RTL-IF-2) or is explicitly out of scope for this gate.

Protocol-neutral by construction: ``transport`` is caller-injected and
typed only as `services.device_transport.DeviceTransport`. This module
never imports, names, or constructs `services.simulator_transport.
SimulatorTransport` — picking a transport (simulator today, a real
production adapter later) is the caller's decision, not this module's. No
callback, page, or scheduler calls this today; nothing here is wired into
`callbacks/device_manage.py`'s Program RTL action, which still stops at
``command = QUEUED`` exactly as RTL-IF-2 left it. **No automatic
execution, no retry**: a caller invokes ``execute_request`` once, on
purpose, exactly as `dispatch_command` is itself explicit-caller-only.
"""
from __future__ import annotations

from repositories.plant_monitoring_repository import CommandRecord
from services import rtl_command_dispatch_service, rtl_command_service
from services.device_transport import DeviceTransport
from services.rtl_command_dispatch_service import CommandNotDispatchableError


class ProgrammingExecutionError(Exception):
    """A programming request could not be executed through its command:
    no command exists for the request, or the command is not currently
    dispatchable (already in flight or terminal)."""


def execute_request(request_id: int, transport: DeviceTransport) -> CommandRecord:
    """Execute ``request_id``'s existing command through ``transport``.

    Resolves the request's one corresponding command
    (``uq_rtl_commands_request_id``, ADR-017) and dispatches it. Raises
    ``ProgrammingExecutionError`` — never a bare ``AttributeError`` or
    ``CommandNotDispatchableError`` — when no command exists for the
    request (should not happen while `rtl_programming_service.
    record_request` keeps creating one atomically with every request, but
    is checked rather than assumed) or when the command is not currently
    QUEUED (`rtl_command_dispatch_service.CommandNotDispatchableError`,
    wrapped so this module's callers only need to catch one exception
    type).
    """
    command = rtl_command_service.get_command_for_request(request_id)
    if command is None:
        raise ProgrammingExecutionError(
            f"No command exists for programming request {request_id!r}."
        )

    try:
        return rtl_command_dispatch_service.dispatch_command(
            command.command_id, transport
        )
    except CommandNotDispatchableError as exc:
        raise ProgrammingExecutionError(str(exc)) from exc


__all__ = ["ProgrammingExecutionError", "execute_request"]
