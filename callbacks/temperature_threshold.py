"""THRESH-CONFIG-1 admin control — the C-01 global temperature threshold
configuration panel.

Deliberately self-contained, same shape as
`callbacks/forwarding_schedule.py`: a separate `@app.callback` with its own
single Output, sharing only the `page-context` Input. It does NOT extend
`administration_section`'s single-query render path — this feature has no
reason to join the "one AdminOverviewSummary" invariant that pipeline is
built around.

No alarm/event evaluation lives here or anywhere else in this gate — see
services/temperature_threshold_service.py's module docstring.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, callback_context, no_update

from components.status_panels import action_refused_notice
from components.temperature_threshold_panel import (
    CLEAR_BTN_ID,
    CRITICAL_INPUT_ID,
    PANEL_ID,
    SET_BTN_ID,
    WARNING_INPUT_ID,
    temperature_threshold_panel,
)
from services import temperature_threshold_service as service
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_TEMPERATURE_THRESHOLD

logger = logging.getLogger(__name__)


def _render(error: str | None = None):
    state = service.get_current_threshold_config()
    return temperature_threshold_panel(state, error=error)


def register(app) -> None:
    """Register the temperature threshold configuration panel's callbacks."""

    @app.callback(
        Output(PANEL_ID, "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def _render_panel(context):
        # AUTH-HARDEN-1R shape: authorize before any query, and fire no
        # query at all for a denied role — same reasoning as
        # callbacks.forwarding_schedule._render_panel.
        if not context or context.get("route") != "admin_settings":
            return no_update

        try:
            require_capability(current_identity(), MANAGE_TEMPERATURE_THRESHOLD)
        except AuthorizationError:
            return None

        try:
            return _render()
        except Exception:
            logger.exception("Temperature threshold panel unavailable")
            return None

    @app.callback(
        Output(PANEL_ID, "children", allow_duplicate=True),
        Input(SET_BTN_ID, "n_clicks"),
        Input(CLEAR_BTN_ID, "n_clicks"),
        State(WARNING_INPUT_ID, "value"),
        State(CRITICAL_INPUT_ID, "value"),
        prevent_initial_call=True,
    )
    def _handle_action(_set_clicks, _clear_clicks, raw_warning, raw_critical):
        triggered = callback_context.triggered
        trigger_id = triggered[0]["prop_id"].split(".")[0] if triggered else None
        if trigger_id not in (SET_BTN_ID, CLEAR_BTN_ID):
            return no_update
        # Dash fires this when the panel is (re)inserted, with n_clicks=0;
        # only a real click may reach validation or a write.
        if not triggered[0].get("value"):
            return no_update

        user = current_identity()
        try:
            require_capability(user, MANAGE_TEMPERATURE_THRESHOLD)
        except AuthorizationError:
            return action_refused_notice()

        try:
            if trigger_id == SET_BTN_ID:
                warning_c = service.parse_temperature(raw_warning, field_label="Warning")
                critical_c = service.parse_temperature(raw_critical, field_label="Critical")
                service.set_threshold_config(
                    warning_c=warning_c, critical_c=critical_c,
                    actor_user_id=user.user_id,
                )
            else:
                service.clear_threshold_config(actor_user_id=user.user_id)
            return _render()
        except service.ThresholdConfigError as exc:
            return _render(error=str(exc))
        except Exception:
            logger.exception("Temperature threshold action failed")
            return _render(
                error="The temperature threshold could not be saved. Please try again."
            )
