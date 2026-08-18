"""Device Management callbacks — Manage drawer workflow, Program RTL, Message Forwarding, Deactivate.

All operations are prototype-only. No SMS is sent, no backend command is issued,
no production state is changed.
"""
from __future__ import annotations

import logging

from dash import Input, Output, State, no_update, html

from components.device_manage_drawer import (
    MANAGE_DRAWER_ID,
    MANAGE_DEVICE_ID,
    MANAGE_ACTION_STORE_ID,
    MANAGE_CLOSE_BTN,
    MANAGE_BACK_BTN,
    PROGRAM_RTL_UID_ID,
    PROGRAM_RTL_TRANSFORMER_ID,
    PROGRAM_RTL_MSISDN_ID,
    PROGRAM_RTL_CONFIRM_BTN,
    PROGRAM_RTL_RESULT_ID,
    MSG_FWD_TOGGLE_ID,
    MSG_FWD_CONFIRM_BTN,
    MSG_FWD_RESULT_ID,
    DEACTIVATE_CONFIRM_BTN,
    DEACTIVATE_RESULT_ID,
)

logger = logging.getLogger(__name__)

# In-memory prototype state for device management actions
# device_id -> {"forwarding": "enabled"|"disabled"}
_mock_device_state: dict[str, dict] = {}


def get_mock_device_state(device_id: str) -> dict:
    """Get prototype state for a device (for testing)."""
    return _mock_device_state.get(device_id, {"forwarding": "disabled"})


def clear_mock_device_state() -> None:
    """Reset mock device state (for testing)."""
    _mock_device_state.clear()


def register(app) -> None:
    """Register device management callbacks on the Dash app."""

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
        """Open the manage drawer when Manage is clicked."""
        if not active_cell or active_cell.get("column_id") != "actions":
            return (no_update,) * 11

        row_id = active_cell.get("row_id")
        if not row_id:
            return (no_update,) * 11

        row = next((r for r in (table_data or []) if r.get("id") == row_id), None)
        if not row:
            return (no_update,) * 11

        # Check if this is a Manage action (not View or Assign)
        actions_text = row.get("actions", "")
        if "Manage" not in actions_text:
            return (no_update,) * 11

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
        Input("manage-menu-program", "n_clicks"),
        Input("manage-menu-forwarding", "n_clicks"),
        Input("manage-menu-deactivate", "n_clicks"),
        prevent_initial_call=True,
    )
    def navigate_to_action(program_clicks, forwarding_clicks, deactivate_clicks):
        """Show the selected action panel, hide the menu."""
        ctx = __import__("dash").callback_context
        if not ctx.triggered:
            return (no_update,) * 5

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        if trigger_id == "manage-menu-program":
            return "program", {"display": "block"}, {"display": "none"}, {"display": "none"}, {"display": "none"}
        if trigger_id == "manage-menu-forwarding":
            return "forwarding", {"display": "none"}, {"display": "block"}, {"display": "none"}, {"display": "none"}
        if trigger_id == "manage-menu-deactivate":
            return "deactivate", {"display": "none"}, {"display": "none"}, {"display": "block"}, {"display": "none"}

        return (no_update,) * 5

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
        Input(PROGRAM_RTL_CONFIRM_BTN, "n_clicks"),
        State(PROGRAM_RTL_UID_ID, "value"),
        State(PROGRAM_RTL_TRANSFORMER_ID, "value"),
        State(PROGRAM_RTL_MSISDN_ID, "value"),
        prevent_initial_call=True,
    )
    def confirm_program_rtl(n_clicks, uid, transformer, msisdn):
        """Prototype confirm — no real SMS or command sent."""
        if not n_clicks:
            return no_update

        logger.info("Prototype Program RTL: uid=%s, transformer=%s", uid, transformer)

        return html.Div(
            className="status-panel status-panel--success",
            children=[
                html.Strong("Prototype: Command queued. "),
                html.Span(
                    f"Settings for UID {uid or '—'} would be uploaded to "
                    f"transformer {transformer or '—'}. "
                    "No production command was sent."
                ),
            ],
        )

    # --- Message Forwarding confirm ---
    @app.callback(
        Output(MSG_FWD_RESULT_ID, "children"),
        Input(MSG_FWD_CONFIRM_BTN, "n_clicks"),
        State(MANAGE_DEVICE_ID, "data"),
        State(MSG_FWD_TOGGLE_ID, "value"),
        prevent_initial_call=True,
    )
    def confirm_message_forwarding(n_clicks, device_id, forwarding_state):
        """Prototype confirm — no real forwarding state changed."""
        if not n_clicks:
            return no_update

        # Store prototype state
        if device_id:
            if device_id not in _mock_device_state:
                _mock_device_state[device_id] = {"forwarding": "disabled"}
            _mock_device_state[device_id]["forwarding"] = forwarding_state

        label = "Enabled" if forwarding_state == "enabled" else "Disabled"
        logger.info("Prototype Message Forwarding: device=%s, state=%s", device_id, forwarding_state)

        return html.Div(
            className="status-panel status-panel--success",
            children=[
                html.Strong("Prototype: Forwarding state updated. "),
                html.Span(
                    f"Message forwarding would be {label.lower()} for this "
                    "device. Production message forwarding was not changed."
                ),
            ],
        )

    # --- Deactivate RTL confirm ---
    @app.callback(
        Output(DEACTIVATE_RESULT_ID, "children"),
        Input(DEACTIVATE_CONFIRM_BTN, "n_clicks"),
        State(MANAGE_DEVICE_ID, "data"),
        prevent_initial_call=True,
    )
    def confirm_deactivate_rtl(n_clicks, device_id):
        """Prototype confirm — no real active-list mutation."""
        if not n_clicks:
            return no_update

        logger.info("Prototype Deactivate RTL: device=%s", device_id)

        return html.Div(
            className="status-panel status-panel--success",
            children=[
                html.Strong("Prototype: RTL deactivation requested. "),
                html.Span(
                    f"UID {device_id or '—'} would be removed from the "
                    "active monitoring list. Production active-list state "
                    "was not changed."
                ),
            ],
        )
