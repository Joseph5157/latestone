"""SimulatorTransport (RTL-IF-2) — a deterministic, in-process stand-in for
a real device transport.

**This is an internal TEST CONTRACT, not the Eskom protocol.** Its outcome
vocabulary (SUCCESS/FAILURE/TIMEOUT), its failure codes
(SIMULATED_FAILURE/SIMULATED_TIMEOUT — config/commands.py), and its
zero-latency, always-synchronous behaviour describe nothing about how a
real RTL Master, MQTT broker, or SMS gateway will actually acknowledge or
reject a command. A future production adapter implements
`services/device_transport.DeviceTransport` on its own terms; it does not
extend or wrap this class.

Distinct from `db/live_simulator.py`: that module is a measurement
generator (appends synthetic sensor readings on a timer) and is unrelated
to command transport — RTL-IF-1P confirmed this and RTL-IF-2 leaves it
untouched.

No network calls, sleeps, threads, background loops, MQTT, SMS, or
filesystem coordination — the configured outcome is returned synchronously,
every time, for every `send()` call on a given instance.
"""
from __future__ import annotations

from config import commands as command_cfg
from services.device_transport import (
    TRANSPORT_RESULT_FAILURE,
    TRANSPORT_RESULT_SUCCESS,
    TRANSPORT_RESULT_TIMEOUT,
    TransportOutcome,
)

#: The three outcomes a SimulatorTransport instance can be configured with.
OUTCOME_SUCCESS = "SUCCESS"
OUTCOME_FAILURE = "FAILURE"
OUTCOME_TIMEOUT = "TIMEOUT"

_VALID_OUTCOMES = frozenset({OUTCOME_SUCCESS, OUTCOME_FAILURE, OUTCOME_TIMEOUT})


class SimulatorTransport:
    """A `DeviceTransport` whose outcome is fixed at construction.

    Every `send()` call on one instance returns the same configured
    outcome, unconditionally — it does not inspect ``command`` or
    ``request`` to decide. Tests construct one instance per scenario
    (`SimulatorTransport(OUTCOME_FAILURE)`, etc.); nothing else in the
    application constructs or wires one automatically.
    """

    def __init__(self, outcome: str = OUTCOME_SUCCESS) -> None:
        if outcome not in _VALID_OUTCOMES:
            raise ValueError(f"Unknown SimulatorTransport outcome: {outcome!r}")
        self._outcome = outcome

    def send(self, command, request) -> TransportOutcome:
        if self._outcome == OUTCOME_SUCCESS:
            return TransportOutcome(result=TRANSPORT_RESULT_SUCCESS)
        if self._outcome == OUTCOME_FAILURE:
            return TransportOutcome(
                result=TRANSPORT_RESULT_FAILURE,
                failure_code=command_cfg.FAILURE_CODE_SIMULATED_FAILURE,
                failure_detail="Simulated transport failure (SimulatorTransport test fixture).",
            )
        return TransportOutcome(
            result=TRANSPORT_RESULT_TIMEOUT,
            failure_code=command_cfg.FAILURE_CODE_SIMULATED_TIMEOUT,
            failure_detail="Simulated transport timeout (SimulatorTransport test fixture).",
        )


__all__ = ["OUTCOME_FAILURE", "OUTCOME_SUCCESS", "OUTCOME_TIMEOUT", "SimulatorTransport"]
