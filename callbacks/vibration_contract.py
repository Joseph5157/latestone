"""VIB-CONFIG-1 admin control — the C-02 vibration contract answer panel.

Deliberately self-contained, same shape as
`callbacks/temperature_threshold.py`: a separate `@app.callback` with its
own single Output, sharing only the `page-context` Input. It does NOT
extend `administration_section`'s single-query render path.

No vibration runtime activation lives here or anywhere else in this gate
— see services/vibration_contract_service.py's module docstring.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, callback_context, no_update

from components.status_panels import action_refused_notice
from components.vibration_contract_panel import (
    ANSWER_INPUT_ID,
    CLEAR_BTN_ID,
    PANEL_ID,
    QUESTION_SELECT_ID,
    SET_BTN_ID,
    vibration_contract_panel,
)
from services import vibration_contract_service as service
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_VIBRATION_CONTRACT

logger = logging.getLogger(__name__)


def _render(error: str | None = None):
    answers = service.get_all_answers()
    return vibration_contract_panel(answers, error=error)


def register(app) -> None:
    """Register the vibration contract answer panel's callbacks."""

    @app.callback(
        Output(PANEL_ID, "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def _render_panel(context):
        # AUTH-HARDEN-1R shape: authorize before any query, and fire no
        # query at all for a denied role — same reasoning as
        # callbacks.temperature_threshold._render_panel.
        if not context or context.get("route") != "admin_settings":
            return no_update

        try:
            require_capability(current_identity(), MANAGE_VIBRATION_CONTRACT)
        except AuthorizationError:
            return None

        try:
            return _render()
        except Exception:
            logger.exception("Vibration contract panel unavailable")
            return None

    @app.callback(
        Output(PANEL_ID, "children", allow_duplicate=True),
        Input(SET_BTN_ID, "n_clicks"),
        Input(CLEAR_BTN_ID, "n_clicks"),
        State(QUESTION_SELECT_ID, "value"),
        State(ANSWER_INPUT_ID, "value"),
        prevent_initial_call=True,
    )
    def _handle_action(_set_clicks, _clear_clicks, question_key, raw_answer):
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
            require_capability(user, MANAGE_VIBRATION_CONTRACT)
        except AuthorizationError:
            return action_refused_notice()

        if not question_key:
            return _render(error="Select a question first.")

        try:
            if trigger_id == SET_BTN_ID:
                service.set_answer(
                    question_key=question_key, answer_text=raw_answer,
                    actor_user_id=user.user_id,
                )
            else:
                service.clear_answer(
                    question_key=question_key, actor_user_id=user.user_id,
                )
            return _render()
        except service.VibrationContractError as exc:
            return _render(error=str(exc))
        except Exception:
            logger.exception("Vibration contract answer action failed")
            return _render(
                error="The answer could not be saved. Please try again."
            )
