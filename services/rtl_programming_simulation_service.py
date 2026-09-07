"""Development/demo-only simulated programming execution (RTL-PROG-SIM-1).

    recorded programming request      (rtl_programming_service, RTL-IF-1)
            v
    simulate_request_execution()      (this module — dev/demo only)
            v
    SimulatorTransport(outcome)       (ADR-018, constructed ONLY here)
            v
    rtl_programming_execution_service.execute_request()   (RTL-PROG-EXEC-1)
            v
    existing command lifecycle + request status projection

**This module is the only place in the application that constructs a
`SimulatorTransport`**, and it does so only after
`require_simulation_enabled()` has passed — which requires both an explicit
`RTL_PROGRAMMING_SIMULATOR_ENABLED` opt-in and a non-production `APP_ENV`
(`config/settings.py`, `resolve_programming_simulator_enabled`). A
production process cannot hold that setting as True (resolution raises
instead), and this module re-checks `IS_PRODUCTION` anyway at call time, so
the boundary holds even if a caller reached this function some other way.

**A simulated outcome is not a device fact.** `SUCCESS`/`FAILURE`/`TIMEOUT`
are `SimulatorTransport`'s own deterministic test vocabulary (ADR-018): no
MQTT, SMS, HTTP or Eskom communication occurs, no payload or ACK contract is
implied, and a request reaching `successful` here is NOT evidence that any
physical RTL was programmed. The UI must say so wherever it exposes this.

**No lifecycle logic lives here.** Legality, concurrency protection,
timestamps, failure normalization and the request-status projection all stay
where RTL-IF-2/RTL-PROG-EXEC-1 put them; this module resolves an outcome to
a transport and delegates. No retry, no scheduler, no worker, no automatic
execution: one explicit call performs one attempt.
"""
from __future__ import annotations

from config import settings
from repositories.plant_monitoring_repository import CommandRecord
from services import rtl_programming_execution_service
from services.simulator_transport import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    OUTCOME_TIMEOUT,
    SimulatorTransport,
)

#: The three deterministic outcomes an operator may simulate — exactly
#: `SimulatorTransport`'s own vocabulary, not an Eskom/device protocol
#: vocabulary. Ordered as the UI offers them.
SIMULATION_OUTCOMES = (OUTCOME_SUCCESS, OUTCOME_FAILURE, OUTCOME_TIMEOUT)

#: Operator-facing labels for those outcomes. Every one says "Simulated" so
#: the selector cannot be read as naming a real device response.
SIMULATION_OUTCOME_LABELS = {
    OUTCOME_SUCCESS: "Simulated success",
    OUTCOME_FAILURE: "Simulated failure",
    OUTCOME_TIMEOUT: "Simulated timeout",
}


class SimulationDisabledError(Exception):
    """Simulated execution was requested while the simulator is not enabled
    for this environment. Raised instead of silently doing nothing, so a
    caller cannot mistake a disabled simulator for a completed simulation."""


class SimulationOutcomeError(Exception):
    """An outcome outside `SIMULATION_OUTCOMES` was requested."""


def is_simulation_enabled() -> bool:
    """Whether simulated programming execution is available right now.

    Read live rather than captured at import so the answer always reflects
    current configuration. Both conditions are checked, not just the
    setting: `IS_PRODUCTION` is re-tested here as defence in depth, since
    this is the predicate the UI and the callback registration both key off.
    """
    return settings.programming_simulator.enabled and not settings.IS_PRODUCTION


def require_simulation_enabled() -> None:
    """Raise `SimulationDisabledError` unless simulation is enabled."""
    if not is_simulation_enabled():
        raise SimulationDisabledError(
            "Simulated RTL programming execution is not enabled in this "
            "environment."
        )


def simulate_request_execution(*, request_id: int, outcome: str) -> CommandRecord:
    """Run ``request_id``'s existing command through a simulated transport.

    Authorization is NOT performed here — it belongs to the caller, at the
    callback boundary, exactly as it does for every other action in this
    application (`services/action_guard.py`), and exactly as ADR-018 already
    specifies for transports. This function assumes the caller has already
    authorized the acting identity against the request's own device.

    Returns the resulting `CommandRecord`; the request's own status is
    projected by `rtl_command_service` inside the same transaction as each
    command transition (RTL-PROG-EXEC-1). Refuses a repeated attempt the
    same way any other execution does — through the existing lifecycle,
    surfaced as `ProgrammingExecutionError`.
    """
    require_simulation_enabled()

    if outcome not in SIMULATION_OUTCOMES:
        raise SimulationOutcomeError(
            f"Unknown simulation outcome: {outcome!r}. Expected one of "
            f"{SIMULATION_OUTCOMES!r}."
        )

    # Constructed only after the enablement/production check above.
    transport = SimulatorTransport(outcome)
    return rtl_programming_execution_service.execute_request(request_id, transport)


__all__ = [
    "SIMULATION_OUTCOMES",
    "SIMULATION_OUTCOME_LABELS",
    "SimulationDisabledError",
    "SimulationOutcomeError",
    "is_simulation_enabled",
    "require_simulation_enabled",
    "simulate_request_execution",
]
