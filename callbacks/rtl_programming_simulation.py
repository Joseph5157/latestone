"""Development/demo-only simulated programming execution callback
(RTL-PROG-SIM-1).

`register()` is a NO-OP unless
`services.rtl_programming_simulation_service.is_simulation_enabled()` — so in
production, and in any environment that has not explicitly opted in, this
callback does not exist at all. That pairs with
`components/device_manage_drawer.py`, which likewise renders the simulation
controls only then: no control, no callback, nothing to fabricate a click
against.

The simulation is never automatic. It runs on one explicit button press,
against a request the operator has already recorded, and performs exactly one
attempt — no retry, no polling, no worker.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, html, no_update

from components.status_panels import action_refused_notice
from components.device_manage_drawer import (
    MANAGE_DEVICE_ID,
    PROGRAM_RTL_LAST_REQUEST_ID,
    PROGRAM_RTL_SIM_BTN,
    PROGRAM_RTL_SIM_OUTCOME_ID,
    PROGRAM_RTL_SIM_RESULT_ID,
    SIMULATION_NOTICE,
)
from repositories import plant_monitoring_repository as repo
from services import rtl_programming_simulation_service as simulation
from services.action_guard import require_action
from services.auth_service import current_identity
from services.authorization import AuthorizationError, PROGRAM_RTL
from services.rtl_programming_execution_service import ProgrammingExecutionError

logger = logging.getLogger(__name__)

#: One message for "that request is not this device's request", covering both
#: a request that does not exist and one belonging to another device.
#: Deliberately identical for both cases: a distinct "no such request" reply
#: would turn this control into an oracle for which request ids exist, which
#: a browser-supplied id must never be able to ask.
_UNKNOWN_REQUEST_MESSAGE = (
    "No recorded programming request for this RTL was found to simulate. "
    "Record a programming request first."
)


def _notice(class_name: str, strong: str, detail: str) -> html.Div:
    return html.Div(
        className=class_name,
        children=[html.Strong(strong), html.Span(detail)],
    )


def _refused(detail: str) -> html.Div:
    return _notice("status-panel status-panel--inactive", "Not simulated. ", detail)


def register(app) -> None:
    """Register the simulation callback — only when simulation is enabled."""
    if not simulation.is_simulation_enabled():
        logger.debug(
            "RTL programming simulator disabled; simulation callback not "
            "registered."
        )
        return

    @app.callback(
        Output(PROGRAM_RTL_SIM_RESULT_ID, "children"),
        Input(PROGRAM_RTL_SIM_BTN, "n_clicks"),
        State(MANAGE_DEVICE_ID, "data"),
        State(PROGRAM_RTL_LAST_REQUEST_ID, "data"),
        State(PROGRAM_RTL_SIM_OUTCOME_ID, "value"),
        prevent_initial_call=True,
    )
    def simulate_program_rtl_execution(n_clicks, device_id, request_id, outcome):
        """Run this drawer's recorded request through a simulated transport.

        Order is the whole security story, and it is deliberate:

        1. **Authorize against the DEVICE first** (`require_action`,
           PROGRAM_RTL — Administrator any RTL, Technician assigned only,
           General never). Hiding the control is not protection: this runs
           whether or not the control was ever rendered for this persona.
           Nothing is read from the database about the request until this
           passes, so an unauthorized caller learns nothing at all.
        2. **Then prove the browser-supplied `request_id` belongs to that
           same device.** Both the store and the device id arrive from the
           browser and neither is trusted; the device id is what was
           authorized, so the request must be shown to be that device's own
           before anything executes. A mismatch is refused with the same
           message an unknown id gets, so this cannot be used to probe which
           request ids exist.
        3. Only then simulate — which itself re-checks that simulation is
           enabled and non-production before a transport is constructed.

        A repeated press is refused by the EXISTING command lifecycle
        (`dispatch_command` will not re-dispatch a command that is not
        QUEUED), surfaced here as a friendly notice — this callback adds no
        retry and no second opinion about what is dispatchable.
        """
        if not n_clicks:
            return no_update

        user = current_identity()

        try:
            require_action(user, PROGRAM_RTL, device_id=device_id)
        except AuthorizationError:
            return action_refused_notice()

        # A drawer with no device, or a store holding anything but a real
        # request id, is refused before the lookup — there is nothing an
        # ownership check could even compare against. `bool` is excluded
        # explicitly because it is an `int` subclass, so `True` would
        # otherwise be accepted as request id 1.
        if not device_id:
            return _refused(_UNKNOWN_REQUEST_MESSAGE)
        if not isinstance(request_id, int) or isinstance(request_id, bool):
            return _refused(_UNKNOWN_REQUEST_MESSAGE)

        # The store is browser-owned: prove the request is this device's own
        # before executing anything. `get_programming_request` is reached
        # only after authorization above, so this read cannot be used by an
        # unauthorized caller.
        request = repo.get_programming_request(request_id)
        if request is None or request.device_id != device_id:
            logger.warning(
                "Refusing simulated execution: request %r does not belong to "
                "device %r",
                request_id,
                device_id,
            )
            return _refused(_UNKNOWN_REQUEST_MESSAGE)

        try:
            command = simulation.simulate_request_execution(
                request_id=request_id, outcome=outcome
            )
        except simulation.SimulationOutcomeError:
            return _refused("Select a simulated outcome first.")
        except simulation.SimulationDisabledError:
            # Unreachable while this callback is only registered when
            # enabled — kept so a configuration change mid-process fails
            # closed rather than raising into the browser.
            return _refused(
                "Simulated execution is not enabled in this environment."
            )
        except ProgrammingExecutionError as exc:
            logger.info(
                "Simulated execution refused for request %s: %s", request_id, exc
            )
            return _refused(
                "This request has already been executed and cannot be run "
                "again. Record a new programming request to simulate another "
                "execution."
            )

        updated = repo.get_programming_request(request_id)
        status = updated.status if updated else "unknown"
        failure = command.failure_code

        detail = (
            f"Request {request_id} is now {status}. "
            f"Simulated command state: {command.state}"
            + (f" ({failure})." if failure else ".")
            + f" {SIMULATION_NOTICE} This is not evidence that the physical "
            "RTL was programmed."
        )
        return _notice(
            "status-panel status-panel--inactive",
            "Simulated execution complete. ",
            detail,
        )


__all__ = ["register"]
