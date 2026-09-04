"""The device transport contract (RTL-IF-2).

`SimulatorTransport` (services/simulator_transport.py) implements this
today; a future production adapter (MQTT/SMS/Eskom) implements the same
contract without changing `services/rtl_command_dispatch_service.py`. This
module intentionally defines only what the dispatcher needs to call and get
an answer back — nothing about *how* a transport delivers a command.

What a transport receives: a protocol-neutral `CommandRecord` plus its
referenced `ProgrammingRequestRecord` (RTL-IF-1's read API, ADR-017) — never
a database session (transports do not manage transactions; the dispatcher
and rtl_command_service own persistence) and never Flask/session identity
(authorization already happened before the command existed, at the action
guard, before `rtl_programming_service.record_request` ever ran — a
transport has no authorization role and nothing to check).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from repositories.plant_monitoring_repository import (
    CommandRecord,
    ProgrammingRequestRecord,
)

#: The three outcomes a transport may report. Not an `rtl_commands.state`
#: value — the dispatcher owns the mapping onto the lifecycle (including
#: the ACKNOWLEDGED intermediate step on SUCCESS), a transport only reports
#: what happened.
TRANSPORT_RESULT_SUCCESS = "SUCCESS"
TRANSPORT_RESULT_FAILURE = "FAILURE"
TRANSPORT_RESULT_TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class TransportOutcome:
    """What `DeviceTransport.send()` reports back to the dispatcher.

    ``failure_code``/``failure_detail`` are only meaningful for FAILURE/
    TIMEOUT; a transport must supply a normalized internal code (never a
    provider-specific one) and a bounded, safe-to-persist detail string
    (never a raw exception or stack trace) — `rtl_commands.failure_detail`
    is `VARCHAR(255)` (migration 009).
    """

    result: str
    failure_code: str | None = None
    failure_detail: str | None = None


class DeviceTransport(Protocol):
    """The smallest send contract a device transport must implement."""

    def send(
        self, command: CommandRecord, request: ProgrammingRequestRecord
    ) -> TransportOutcome:
        """Attempt delivery of ``command`` (whose intent is ``request``)
        and report the outcome. Must not raise for an ordinary delivery
        failure — that is what `TRANSPORT_RESULT_FAILURE`/`_TIMEOUT` are
        for; an exception here is a genuine transport-implementation bug,
        not a modeled outcome."""
        ...


__all__ = [
    "DeviceTransport",
    "TRANSPORT_RESULT_FAILURE",
    "TRANSPORT_RESULT_SUCCESS",
    "TRANSPORT_RESULT_TIMEOUT",
    "TransportOutcome",
]
