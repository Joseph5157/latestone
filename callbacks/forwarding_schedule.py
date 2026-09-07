"""C08-AUTO-DISABLE-1 admin control — the BR016 auto-disable override panel.

Deliberately self-contained: a separate `@app.callback` with its own single
Output, sharing only the `page-context` Input that
`callbacks.listings.populate_overview` also listens to. It does NOT extend
that callback or `administration_section`'s single-query render path — this
feature has no reason to join the "one AdminOverviewSummary" invariant that
pipeline is built around, and joining it would mean touching a tested,
carefully-scoped function for an unrelated concern.

The auto-disable ACTION itself (services.forwarding_auto_disable_service.
apply_auto_disable) has no callback here at all — it is invoked only by
scripts/run_forwarding_auto_disable.py, from an external scheduler. This
module is the override CONTROL only.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import Input, Output, State, callback_context, no_update

from components.auto_disable_override_panel import (
    CLEAR_BTN_ID,
    PANEL_ID,
    REASON_INPUT_ID,
    SET_BTN_ID,
    TIME_INPUT_ID,
    auto_disable_override_panel,
)
from components.status_panels import action_refused_notice
from config.forwarding_schedule import TIMEZONE
from services import forwarding_auto_disable_service as service
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, MANAGE_AUTO_DISABLE_OVERRIDE

logger = logging.getLogger(__name__)


def _today_local():
    return datetime.now(timezone.utc).astimezone(TIMEZONE).date()


def _render(error: str | None = None):
    override = service.get_current_override()
    today = _today_local()
    effective_today = override is not None and override.override_date == today
    return auto_disable_override_panel(
        override, effective_today=effective_today, error=error
    )


def register(app) -> None:
    """Register the auto-disable override panel's callbacks."""

    @app.callback(
        Output(PANEL_ID, "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def _render_panel(context):
        # AUTH-HARDEN-1R shape: authorize before any query, and fire no
        # query at all for a denied role — same reasoning as
        # callbacks.listings.administration_section.
        if not context or context.get("route") != "overview":
            return no_update

        try:
            require_capability(current_identity(), MANAGE_AUTO_DISABLE_OVERRIDE)
        except AuthorizationError:
            return None

        try:
            return _render()
        except Exception:
            logger.exception("Auto-disable override panel unavailable")
            return None

    @app.callback(
        Output(PANEL_ID, "children", allow_duplicate=True),
        Input(SET_BTN_ID, "n_clicks"),
        Input(CLEAR_BTN_ID, "n_clicks"),
        State(TIME_INPUT_ID, "value"),
        State(REASON_INPUT_ID, "value"),
        prevent_initial_call=True,
    )
    def _handle_action(_set_clicks, _clear_clicks, raw_time, raw_reason):
        triggered = callback_context.triggered
        trigger_id = triggered[0]["prop_id"].split(".")[0] if triggered else None
        if trigger_id not in (SET_BTN_ID, CLEAR_BTN_ID):
            return no_update

        user = current_identity()
        try:
            require_capability(user, MANAGE_AUTO_DISABLE_OVERRIDE)
        except AuthorizationError:
            return action_refused_notice()

        try:
            if trigger_id == SET_BTN_ID:
                cutoff_time = service.parse_cutoff_time(raw_time)
                service.set_override(
                    cutoff_time=cutoff_time,
                    reason=raw_reason,
                    actor_user_id=user.user_id,
                )
            else:
                service.clear_override(actor_user_id=user.user_id)
            return _render()
        except service.AutoDisableError as exc:
            return _render(error=str(exc))
        except Exception:
            logger.exception("Auto-disable override action failed")
            return _render(
                error="The override could not be saved. Please try again."
            )
