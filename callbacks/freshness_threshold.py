"""FRESHNESS-CONFIG-1 admin control — the global freshness threshold panel.

Same self-contained shape as `callbacks/temperature_threshold.py`: its own
Output, sharing only the `page-context` Input, authorizing before any query
or write.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, callback_context, no_update

from components.freshness_threshold_panel import (
    CLEAR_BTN_ID,
    MINUTES_INPUT_ID,
    PANEL_ID,
    SET_BTN_ID,
    freshness_threshold_panel,
)
from components.status_panels import action_refused_notice
from services import freshness_threshold_service as service
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_FRESHNESS_THRESHOLD

logger = logging.getLogger(__name__)


def _render(error: str | None = None):
    return freshness_threshold_panel(
        service.get_current_config(),
        default_minutes=service.default_stale_after_minutes(),
        error=error,
    )


def register(app) -> None:
    """Register the freshness threshold panel's callbacks."""

    @app.callback(
        Output(PANEL_ID, "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def _render_panel(context):
        if not context or context.get("route") != "admin_settings":
            return no_update
        try:
            require_capability(current_identity(), MANAGE_FRESHNESS_THRESHOLD)
        except AuthorizationError:
            return None
        try:
            return _render()
        except Exception:
            logger.exception("Freshness threshold panel unavailable")
            return None

    @app.callback(
        Output(PANEL_ID, "children", allow_duplicate=True),
        Input(SET_BTN_ID, "n_clicks"),
        Input(CLEAR_BTN_ID, "n_clicks"),
        State(MINUTES_INPUT_ID, "value"),
        prevent_initial_call=True,
    )
    def _handle_action(_set_clicks, _clear_clicks, raw_minutes):
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
            require_capability(user, MANAGE_FRESHNESS_THRESHOLD)
        except AuthorizationError:
            return action_refused_notice()

        try:
            if trigger_id == SET_BTN_ID:
                service.set_config(
                    stale_after_minutes=service.parse_minutes(raw_minutes),
                    actor_user_id=user.user_id,
                )
            else:
                service.clear_config(actor_user_id=user.user_id)
            return _render()
        except service.FreshnessThresholdError as exc:
            return _render(error=str(exc))
        except Exception:
            logger.exception("Freshness threshold action failed")
            return _render(error="The freshness threshold could not be saved. Please try again.")
