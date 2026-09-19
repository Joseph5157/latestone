"""The redesigned Command Center's callbacks (CC-NEW-1, CC-ACTIONS-1).

One interval tick = one `attention_service` snapshot = one render of every
panel (ADR-005). Failure handling matches the old page: a failed first load
shows the error state; a failed refresh keeps the last good panels on screen
and says the data is stale, never blanking correct information.

Actions reuse existing flows, never copies (redesign D7):

- Acknowledge -> `attention_service.acknowledge_problem` -> `require_action`
  + `alarm_acknowledgement_service` (the Notification Center's path). The
  browser names only the RTL and the problem kind, never event ids.
- Manage -> opens the shared `device_manage_drawer()`; its confirm callbacks
  in `callbacks/device_manage.py` do the work and re-check authority.

Buttons are rendered from `may_action`; that hides, it does not protect.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from dash import ALL, Input, Output, State, ctx, html, no_update

from components import attention as ui
from components.command_center import refresh
from components.command_center.primitives import scope_indicator_text
from components.device_manage_drawer import (
    MANAGE_ACTION_STORE_ID,
    MANAGE_DEVICE_ID,
    MANAGE_DRAWER_ID,
    PROGRAM_RTL_TRANSFORMER_ID,
    PROGRAM_RTL_UID_ID,
)
from components.status_panels import action_refused_notice, error_panel
from pages import command_center_new as page
from services.action_guard import may_action
from services.alarm_acknowledgement_service import AlarmAcknowledgementError
from services.attention_service import (
    ProblemKind,
    acknowledge_problem,
    get_attention_snapshot,
)
from services.auth_service import current_identity
from services.authorization import (
    ACKNOWLEDGE_ALARM,
    DEACTIVATE_RTL,
    PROGRAM_RTL,
    TOGGLE_MESSAGE_FORWARDING,
    AuthorizationError,
)
from services.device_scope import current_device_scope
from services.hierarchy_service import list_device_paths

logger = logging.getLogger(__name__)

ROUTE = "command_center_new"
PANEL_OUTPUTS = 6  # scope, status, problems, hottest, activity, trend
#: The drawer's actions; assignment is deliberately not one (ADR-016).
OPERATIONAL_ACTIONS = (PROGRAM_RTL, TOGGLE_MESSAGE_FORWARDING, DEACTIVATE_RTL)
#: Same twelve outputs, in the same order, as callbacks/device_manage.py's
#: openers; a test pins the count against that module.
DRAWER_OUTPUTS = 12
_DRAWER_DECLINED = (no_update,) * DRAWER_OUTPUTS


def _last_success(state) -> datetime | None:
    stamp = (state or {}).get("last_success_at")
    try:
        return datetime.fromisoformat(stamp) if stamp else None
    except (TypeError, ValueError):
        return None


def permitted_devices(problems, user, scope, *, allow=may_action) -> tuple[frozenset, frozenset]:
    """(may_ack, may_manage) device-id sets for the rendered problems.

    `scope` is passed through so no per-row assignment read happens.
    """
    devices = {p.device_id for p in problems}
    may_ack = frozenset(
        d for d in devices if allow(user, ACKNOWLEDGE_ALARM, device_id=d, scope=scope)
    )
    may_manage = frozenset(
        d for d in devices
        if any(allow(user, a, device_id=d, scope=scope) for a in OPERATIONAL_ACTIONS)
    )
    return may_ack, may_manage


def render_panels(snapshot, may_ack=frozenset(), may_manage=frozenset()) -> tuple:
    now = snapshot.generated_at
    return (
        scope_indicator_text(snapshot.total_rtls),
        ui.status_bar(snapshot),
        ui.problem_list(snapshot.problems, now, may_ack=may_ack, may_manage=may_manage),
        ui.hottest_card(snapshot.hottest),
        ui.activity_card(snapshot.activity, now),
        ui.alarm_trend_card(snapshot.daily_alarms),
    )


def populate(
    context, refresh_state, *,
    fetch=get_attention_snapshot, scope_for=current_device_scope,
    identity=current_identity, allow=may_action,
):
    """Body of the populate callback, testable without a Dash runtime."""
    if not context or context.get("route") != ROUTE:
        return (no_update,) * (PANEL_OUTPUTS + 3)
    try:
        fetched_at = datetime.now(timezone.utc)
        scope = scope_for()
        snapshot = fetch(scope, now=fetched_at)
        may_ack, may_manage = permitted_devices(
            snapshot.problems, identity(), scope, allow=allow
        )
        return render_panels(snapshot, may_ack, may_manage) + (
            None,
            refresh.refresh_status(fetched_at, failed=False),
            {"last_success_at": fetched_at.isoformat(), "failed": False},
        )
    except Exception:
        logger.exception("Failed to load the Command Center snapshot")
        last = _last_success(refresh_state)
        if last is None:
            return (no_update,) + ([],) * (PANEL_OUTPUTS - 1) + (
                error_panel(),
                refresh.refresh_status(None, failed=False),
                {"last_success_at": None, "failed": True},
            )
        return (no_update,) * PANEL_OUTPUTS + (
            no_update,
            refresh.refresh_status(last, failed=True),
            {"last_success_at": refresh_state["last_success_at"], "failed": True},
        )


def _notice(message: str) -> html.Div:
    return html.Div(className="status-panel status-panel--inactive", children=html.P(message))


def acknowledge_outputs(
    trigger, clicks, *,
    identity=current_identity, scope_for=current_device_scope, ack=acknowledge_problem,
):
    """(notice, ack-store) for one Acknowledge click.

    Pattern-matching ALL inputs also fire when the list re-renders (every
    poll) with n_clicks 0/None; those are not clicks and do nothing.
    """
    if not clicks or not isinstance(trigger, dict):
        return no_update, no_update
    try:
        kind = ProblemKind(trigger.get("kind"))
    except ValueError:
        return no_update, no_update
    try:
        changed = ack(identity(), scope_for(), trigger.get("device"), kind)
    except AuthorizationError:
        return action_refused_notice(), no_update
    except (AlarmAcknowledgementError, ValueError) as exc:
        return error_panel(str(exc)), no_update
    except Exception:
        logger.exception("Acknowledge from Command Center failed")
        return error_panel(), no_update
    if changed:
        plural = "s" if changed != 1 else ""
        message = f"Acknowledged {changed} alarm{plural}; the problem leaves the list."
    else:
        message = "Nothing left to acknowledge for this problem."
    return _notice(message), {"at": datetime.now(timezone.utc).isoformat()}


def manage_outputs(
    trigger, clicks, *,
    identity=current_identity, scope_for=current_device_scope, allow=may_action,
    paths_for=list_device_paths,
):
    """The shared drawer's twelve outputs for one Manage click."""
    if not clicks or not isinstance(trigger, dict):
        return _DRAWER_DECLINED
    device_id = trigger.get("device")
    user, scope = identity(), scope_for()
    if not device_id or not any(
        allow(user, a, device_id=device_id, scope=scope) for a in OPERATIONAL_ACTIONS
    ):
        return _DRAWER_DECLINED
    paths = paths_for([device_id], scope=scope)
    if not paths:
        return _DRAWER_DECLINED
    path = paths[0]
    return (
        {"display": "block"},       # show drawer
        device_id,                  # drawer's device
        "menu",                     # start at the action menu
        path.device_code,
        path.transformer_code,
        path.plant_name,
        {"display": "none"},        # program panel
        {"display": "none"},        # forwarding panel
        {"display": "none"},        # deactivate panel
        {"display": "block"},       # action menu
        path.device_code,           # pre-fill UID
        path.transformer_code,      # pre-fill transformer name
    )


def register(app) -> None:
    @app.callback(
        Output(page.SCOPE_ID, "children"),
        Output(page.STATUS_SLOT_ID, "children"),
        Output(page.PROBLEMS_ID, "children"),
        Output(page.HOTTEST_ID, "children"),
        Output(page.ACTIVITY_ID, "children"),
        Output(page.TREND_ID, "children"),
        Output(page.ERROR_ID, "children"),
        Output(page.REFRESH_STATUS_ID, "children"),
        Output(page.STORE_ID, "data"),
        Input("page-context", "data"),
        Input(page.INTERVAL_ID, "n_intervals"),
        Input(page.REFRESH_NOW_ID, "n_clicks"),
        Input(page.ACK_STORE_ID, "data"),
        State(page.STORE_ID, "data"),
    )
    def populate_attention(context, _ticks, _clicks, _acked, refresh_state):
        return populate(context, refresh_state)

    @app.callback(
        Output(page.ACTION_RESULT_ID, "children"),
        Output(page.ACK_STORE_ID, "data"),
        Input({"type": ui.ACK_BUTTON, "device": ALL, "kind": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def acknowledge_from_command_center(_clicks):
        value = ctx.triggered[0]["value"] if ctx.triggered else None
        return acknowledge_outputs(ctx.triggered_id, value)

    @app.callback(
        Output(MANAGE_DRAWER_ID, "style", allow_duplicate=True),
        Output(MANAGE_DEVICE_ID, "data", allow_duplicate=True),
        Output(MANAGE_ACTION_STORE_ID, "data", allow_duplicate=True),
        Output("manage-drawer-device-code", "children", allow_duplicate=True),
        Output("manage-drawer-transformer", "children", allow_duplicate=True),
        Output("manage-drawer-plant", "children", allow_duplicate=True),
        Output("manage-program-panel", "style", allow_duplicate=True),
        Output("manage-forwarding-panel", "style", allow_duplicate=True),
        Output("manage-deactivate-panel", "style", allow_duplicate=True),
        Output("manage-action-menu", "style", allow_duplicate=True),
        Output(PROGRAM_RTL_UID_ID, "value", allow_duplicate=True),
        Output(PROGRAM_RTL_TRANSFORMER_ID, "value", allow_duplicate=True),
        Input({"type": ui.MANAGE_BUTTON, "device": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def open_manage_from_command_center(_clicks):
        value = ctx.triggered[0]["value"] if ctx.triggered else None
        return manage_outputs(ctx.triggered_id, value)
