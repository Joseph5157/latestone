"""Device Management callbacks — Manage drawer workflow, Program RTL, Message Forwarding, Deactivate.

All three drawer actions are persisted as of OPS-DEACT-1: Message
Forwarding per-user (OPS-FWD-1), Program RTL as a pending programming
request (OPS-PROG-1), Deactivate as an active-list transition in
rtl_active_state (OPS-DEACT-1). None of them communicates with the RTL
Master — no SMS transport, no command delivery, no scheduler.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.status_panels import action_refused_notice
from services import (
    message_forwarding_service,
    rtl_deactivation_service,
    rtl_programming_service,
)
from services.action_guard import may_action, require_action
from services.auth_service import current_identity
from services.authorization import (
    AuthorizationError,
    DEACTIVATE_RTL,
    PROGRAM_RTL,
    TOGGLE_MESSAGE_FORWARDING,
)
from components.device_operations import (
    OPEN_OPERATIONS_BTN,
    OPERATIONS_ID,
    device_operations_panel,
)
from components.device_manage_drawer import (
    MANAGE_DRAWER_ID,
    MANAGE_DEVICE_ID,
    MANAGE_ACTION_STORE_ID,
    MANAGE_CLOSE_BTN,
    MANAGE_BACK_BTN,
    PROGRAM_RTL_UID_ID,
    PROGRAM_RTL_TRANSFORMER_ID,
    PROGRAM_RTL_MSISDN_ID,
    PROGRAM_RTL_MSISDN_ERROR_ID,
    PROGRAM_RTL_CONFIRM_BTN,
    PROGRAM_RTL_RESULT_ID,
    PROGRAM_RTL_LAST_REQUEST_ID,
    MSG_FWD_TOGGLE_ID,
    MSG_FWD_CONFIRM_BTN,
    MSG_FWD_RESULT_ID,
    DEACTIVATE_CONFIRM_BTN,
    DEACTIVATE_RESULT_ID,
)

logger = logging.getLogger(__name__)

#: The two drawer openers' "I am not the callback for this click" reply, one
#: `no_update` per declared Output. Named and counted in one place because the
#: four hand-written `(no_update,) * 11` tuples it replaces were all one short
#: of the twelve Outputs, and nothing in the code said what the number was
#: supposed to be. A test asserts this length against each opener's own Output
#: list, so the three cannot drift apart.
_MANAGE_DRAWER_OUTPUTS = 12
_DECLINED = (no_update,) * _MANAGE_DRAWER_OUTPUTS

#: The three actions this drawer performs, in the order the drawer lists them.
#: `manage_assignment` is deliberately absent and must stay so: assignment is
#: what GRANTS technician authority, so a technician who could manage it could
#: grant it to themselves (services/authorization.py, ACTION_POLICY).
_OPERATIONAL_ACTIONS = (PROGRAM_RTL, TOGGLE_MESSAGE_FORWARDING, DEACTIVATE_RTL)


def device_operations_children(user, device_id: str):
    """The device page's operational section for `user`, or None.

    ROLE-4B. Returns None — not a disabled panel — when the persona has no
    authorized action here, so a general user's device page is exactly the page
    it was before this gate and an out-of-scope RTL offers a technician nothing.

    Asks `may_action` rather than comparing roles. The policy lives in
    `ACTION_POLICY`; a role comparison here would be a second copy of it that no
    policy test would catch drifting. The markup lives in
    `components/device_operations.py` — this decides, it does not draw.

    **This hides, it does not protect.** The confirm callbacks below call
    `require_action` regardless, so a fabricated click on a control that was
    never rendered is still refused.
    """
    if not device_id:
        return None
    if not any(
        may_action(user, action, device_id=device_id)
        for action in _OPERATIONAL_ACTIONS
    ):
        return None
    return device_operations_panel(device_id)


def register(app) -> None:
    """Register device management callbacks on the Dash app."""

    # --- ROLE-4B: the device page's operational surface ---
    @app.callback(
        Output(OPERATIONS_ID, "children"),
        Input("page-context", "data"),
        Input("auth-store", "data"),
    )
    def render_device_operations(page_context, auth_data):
        """Fill the device page's operations section for this persona.

        Keyed on `page-context` because that is where the router already put
        the resolved device (`callbacks/routing.py`, `build_device_context`) —
        re-resolving the URL here would be a second router.

        Renders nothing off a device route. `/admin/devices` keeps its own
        entry point through the table's Manage column, and the two never
        collide because the router mounts one page at a time.
        """
        context = page_context or {}
        if context.get("route") != "device":
            return None
        return device_operations_children(
            current_identity(), context.get("device_id", "")
        )

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
        Input(OPEN_OPERATIONS_BTN, "n_clicks"),
        State("page-context", "data"),
        prevent_initial_call=True,
    )
    def open_manage_drawer_from_device(n_clicks, page_context):
        """Open the same drawer from the device page.

        A second opener rather than a widened first one: `open_manage_drawer`
        is driven by the admin table's `active_cell` and reads the clicked
        ROW, which does not exist here. Both write the same outputs, which is
        why these are `allow_duplicate`; they cannot fire together because
        their triggers live on different pages.

        The button is only rendered for a persona `may_action` approved, and
        the confirm callbacks below re-check with `require_action` — so the
        drawer opening is never itself the permission.
        """
        if not n_clicks:
            return _DECLINED

        context = page_context or {}
        device_id = context.get("device_id")
        if context.get("route") != "device" or not device_id:
            return _DECLINED

        device_code = context.get("device_code", "—")
        transformer = context.get("transformer_code", "—")
        return (
            {"display": "block"},          # show drawer
            device_id,                      # store device_id
            "menu",                         # start at action menu
            device_code,                    # device code
            transformer,                    # transformer
            context.get("plant_name", "—"),  # plant
            {"display": "none"},           # program panel hidden
            {"display": "none"},           # forwarding panel hidden
            {"display": "none"},           # deactivate panel hidden
            {"display": "block"},          # menu visible
            device_code,                    # pre-fill UID
            transformer,                    # pre-fill transformer name
        )

    @app.callback(
        Output(MANAGE_DRAWER_ID, "style"),
        Output(MANAGE_DEVICE_ID, "data"),
        Output(MANAGE_ACTION_STORE_ID, "data"),
        Output("manage-drawer-device-code", "children"),
        Output("manage-drawer-transformer", "children"),
        Output("manage-drawer-plant", "children"),
        Output("manage-program-panel", "style"),
        Output("manage-forwarding-panel", "style"),
        Output("manage-deactivate-panel", "style"),
        Output("manage-action-menu", "style"),
        Output(PROGRAM_RTL_UID_ID, "value"),
        Output(PROGRAM_RTL_TRANSFORMER_ID, "value"),
        Input("device-admin-table", "active_cell"),
        State("device-admin-table", "data"),
        prevent_initial_call=True,
    )
    def open_manage_drawer(active_cell, table_data):
        """Open the manage drawer when the Manage column is clicked.

        Keyed on the `manage` column. It previously accepted `"actions"` —
        the same cell `open_assign_drawer` accepted — and then tried to tell
        the two apart by looking for "Manage" in the cell's markdown. That
        could not work: every row's markdown was the same literal string, so
        the check passed on every row and both drawers opened on one click.

        The declines below return `_DECLINED`, sized from this callback's own
        Output list. They used to be 11-tuples against 12 declared Outputs —
        dormant only because the text check above made them nearly
        unreachable, and a Dash output-count error the moment a decline
        actually happened, which is exactly what routing by column makes
        routine.
        """
        if not active_cell or active_cell.get("column_id") != "manage":
            return _DECLINED

        row_id = active_cell.get("row_id")
        if not row_id:
            return _DECLINED

        row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
        if not row:
            return _DECLINED

        return (
            {"display": "block"},           # show drawer
            row_id,                          # store device_id
            "menu",                          # start at action menu
            row.get("device", "—"),          # device code
            row.get("transformer", "—"),     # transformer
            row.get("plant", "—"),           # plant
            {"display": "none"},            # program panel hidden
            {"display": "none"},            # forwarding panel hidden
            {"display": "none"},            # deactivate panel hidden
            {"display": "block"},           # menu visible
            row.get("device", ""),           # pre-fill UID
            row.get("transformer", ""),      # pre-fill transformer name
        )

    @app.callback(
        Output(MANAGE_DRAWER_ID, "style", allow_duplicate=True),
        Input(MANAGE_CLOSE_BTN, "n_clicks"),
        Input("manage-drawer-overlay", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_manage_drawer(close_clicks, overlay_clicks):
        """Close the manage drawer."""
        return {"display": "none"}

    # --- Action menu navigation ---
    @app.callback(
        Output(MANAGE_ACTION_STORE_ID, "data", allow_duplicate=True),
        Output("manage-program-panel", "style", allow_duplicate=True),
        Output("manage-forwarding-panel", "style", allow_duplicate=True),
        Output("manage-deactivate-panel", "style", allow_duplicate=True),
        Output("manage-action-menu", "style", allow_duplicate=True),
        Output(MSG_FWD_TOGGLE_ID, "value", allow_duplicate=True),
        Input("manage-menu-program", "n_clicks"),
        Input("manage-menu-forwarding", "n_clicks"),
        Input("manage-menu-deactivate", "n_clicks"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def navigate_to_action(program_clicks, forwarding_clicks, deactivate_clicks, auth_data):
        """Show the selected action panel, hide the menu.

        FWD-D7: the forwarding control is prefilled from PostgreSQL when its
        panel opens, so what the operator sees is the stored state — never
        callback memory. A read failure leaves the control untouched rather
        than silently displaying a state that may not be true.
        """
        ctx = __import__("dash").callback_context
        if not ctx.triggered:
            return (no_update,) * 6

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "manage-menu-program":
            return "program", {"display": "block"}, {"display": "none"}, {"display": "none"}, {"display": "none"}, no_update
        if trigger_id == "manage-menu-forwarding":
            prefill = no_update
            try:
                user = current_identity()
                if user is not None:
                    state = message_forwarding_service.get_state(user.user_id)
                    prefill = "enabled" if state.enabled else "disabled"
            except Exception:
                logger.exception("Failed to read forwarding state for prefill")
            return "forwarding", {"display": "none"}, {"display": "block"}, {"display": "none"}, {"display": "none"}, prefill
        if trigger_id == "manage-menu-deactivate":
            return "deactivate", {"display": "none"}, {"display": "none"}, {"display": "block"}, {"display": "none"}, no_update

        return (no_update,) * 6

    # --- Back buttons return to menu ---
    @app.callback(
        Output(MANAGE_ACTION_STORE_ID, "data", allow_duplicate=True),
        Output("manage-program-panel", "style", allow_duplicate=True),
        Output("manage-forwarding-panel", "style", allow_duplicate=True),
        Output("manage-deactivate-panel", "style", allow_duplicate=True),
        Output("manage-action-menu", "style", allow_duplicate=True),
        Input(MANAGE_BACK_BTN, "n_clicks"),
        Input("manage-forwarding-back-btn", "n_clicks"),
        Input("manage-deactivate-back-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def back_to_menu(program_back, fwd_back, deact_back):
        """Return to the action menu from any sub-action."""
        return "menu", {"display": "none"}, {"display": "none"}, {"display": "none"}, {"display": "block"}

    # --- Program RTL confirm ---
    @app.callback(
        Output(PROGRAM_RTL_RESULT_ID, "children"),
        Output(PROGRAM_RTL_MSISDN_ERROR_ID, "children"),
        Output(PROGRAM_RTL_LAST_REQUEST_ID, "data"),
        Input(PROGRAM_RTL_CONFIRM_BTN, "n_clicks"),
        State(MANAGE_DEVICE_ID, "data"),
        State(PROGRAM_RTL_UID_ID, "value"),
        State(PROGRAM_RTL_TRANSFORMER_ID, "value"),
        State(PROGRAM_RTL_MSISDN_ID, "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def confirm_program_rtl(n_clicks, device_id, uid, transformer, msisdn, auth_data):
        """Persist one programming request (OPS-PROG-1).

        The guard authorizes before anything is written; the service then
        validates the operator-supplied Master MSISDN (PROG-D1) and stores
        request + audit atomically. There is no prototype fallback: a
        failure renders a friendly panel and nothing was recorded.

        Validation presentation only: the service remains the sole authority
        for the MSISDN rules; this callback maps its safe ProgrammingError
        text into the inline field slot and invents no policy of its own.

        Publishes the recorded request id to `PROGRAM_RTL_LAST_REQUEST_ID`
        so a follow-up action in this drawer knows which request is on
        screen. Recording still EXECUTES nothing: no dispatch, no transport,
        no simulator — the request is left `queued` exactly as
        RTL-PROG-EXEC-1 leaves it.
        """
        if not n_clicks:
            return no_update, no_update, no_update

        user = current_identity()

        # Authorized BEFORE the write below: a refusal that lands after
        # the mutation has already happened is not a refusal.
        try:
            require_action(user, PROGRAM_RTL, device_id=device_id)
        except AuthorizationError:
            return action_refused_notice(), no_update, None

        try:
            record = rtl_programming_service.record_request(
                device_id=device_id,
                master_msisdn=msisdn,
                actor_user_id=user.user_id,
            )
        except rtl_programming_service.ProgrammingError as exc:
            logger.info(
                "Programming request not recorded for device %s: %s",
                device_id, exc,
            )
            return "", str(exc), None

        logger.info(
            "Programming request %s recorded for device %s",
            record.request_id,
            device_id,
        )

        return html.Div(
            className="status-panel status-panel--success",
            children=[
                html.Strong("Programming request recorded. "),
                html.Span(
                    f"Request {record.request_id} for UID "
                    f"{uid or record.device_id} is saved and queued. "
                    "No command has yet been sent to the RTL Master, and "
                    "the physical RTL is not confirmed programmed."
                ),
            ],
        ), "", record.request_id

    # --- Message Forwarding confirm ---
    @app.callback(
        Output(MSG_FWD_RESULT_ID, "children"),
        Input(MSG_FWD_CONFIRM_BTN, "n_clicks"),
        State(MANAGE_DEVICE_ID, "data"),
        State(MSG_FWD_TOGGLE_ID, "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def confirm_message_forwarding(n_clicks, device_id, forwarding_state, auth_data):
        """Persist the ACTING USER's forwarding preference (OPS-FWD-1).

        The device_id authorizes — nothing else. FWD-D1: no device
        dimension is stored; FWD-D8: the confirmation states exactly what
        happened (preference saved) and what has not (delivery or BR016).
        """
        if not n_clicks:
            return no_update

        user = current_identity()

        # Authorized BEFORE the state write below: a refusal that lands after
        # the mutation has already happened is not a refusal.
        try:
            require_action(
                user, TOGGLE_MESSAGE_FORWARDING, device_id=device_id
            )
        except AuthorizationError:
            return action_refused_notice()

        try:
            message_forwarding_service.set_forwarding(
                enabled=(forwarding_state == "enabled"),
                actor_user_id=user.user_id,
            )
        except message_forwarding_service.ForwardingError:
            return html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Not saved. "),
                    html.Span(
                        "The message forwarding preference could not be "
                        "stored. Please try again."
                    ),
                ],
            )

        if forwarding_state == "enabled":
            detail = (
                "Message forwarding enabled for your account. This "
                "preference applies to your account, not specifically to "
                "this RTL. Delivery integration is not yet connected; the "
                "RTL Master owns BR016's daily cutoff."
            )
        else:
            detail = (
                "Message forwarding disabled for your account. This "
                "preference applies to your account, not specifically to "
                "this RTL. The RTL Master owns BR016's daily cutoff."
            )

        logger.info(
            "Message forwarding preference saved (requested=%s)", forwarding_state
        )

        return html.Div(
            className="status-panel status-panel--success",
            children=[
                html.Strong("Preference saved. "),
                html.Span(detail),
            ],
        )

    # --- Deactivate RTL confirm ---
    @app.callback(
        Output(DEACTIVATE_RESULT_ID, "children"),
        Input(DEACTIVATE_CONFIRM_BTN, "n_clicks"),
        State(MANAGE_DEVICE_ID, "data"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def confirm_deactivate_rtl(n_clicks, device_id, auth_data):
        """Persist one active-list deactivation (OPS-DEACT-1).

        The guard authorizes before anything is written; the service then
        classifies the outcome (DEACT-D1/D2/D3) and stores transition +
        audit atomically when a genuine true→false change occurred.
        """
        if not n_clicks:
            return no_update

        user = current_identity()

        # Authorized BEFORE the write below: a refusal that lands after
        # the mutation has already happened is not a refusal.
        try:
            require_action(user, DEACTIVATE_RTL, device_id=device_id)
        except AuthorizationError:
            return action_refused_notice()

        try:
            result = rtl_deactivation_service.deactivate_rtl(
                device_id=device_id,
                actor_user_id=user.user_id,
            )
        except rtl_deactivation_service.DeactivationError as exc:
            return html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Not deactivated. "),
                    html.Span(str(exc)),
                ],
            )

        logger.info(
            "RTL deactivation for device %s resolved as %s",
            device_id,
            result.outcome,
        )

        if result.outcome == rtl_deactivation_service.OUTCOME_DEACTIVATED:
            return html.Div(
                className="status-panel status-panel--success",
                children=[
                    html.Strong("RTL deactivated. "),
                    html.Span(
                        "This RTL has been removed from the active list in "
                        "this application. No command has been sent to the "
                        "RTL Master."
                    ),
                ],
            )
        if (
            result.outcome
            == rtl_deactivation_service.OUTCOME_NOT_ON_ACTIVE_LIST
        ):
            return html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("RTL is not on the active list. "),
                    html.Span(
                        "Nothing was changed because this application has "
                        "no active-list entry for the device."
                    ),
                ],
            )
        return html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.Strong("RTL is already inactive. "),
                html.Span("No change was made."),
            ],
        )
