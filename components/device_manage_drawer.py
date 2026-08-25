"""Device management drawer — single workflow for Program RTL, Message Forwarding, Deactivate.

Opened from the "Manage" action in the device admin table. Contains three
sub-actions as tab-like sections. All are persisted (Program RTL records a
pending programming request per OPS-PROG-1, Message Forwarding stores a
per-user preference per OPS-FWD-1, Deactivate transitions rtl_active_state
per OPS-DEACT-1); none communicates with the RTL Master — no SMS is sent,
no backend command is issued to hardware.
"""
from __future__ import annotations

from dash import dcc, html

MANAGE_DRAWER_ID = "device-manage-drawer"
MANAGE_DEVICE_ID = "manage-device-hidden-id"
MANAGE_ACTION_STORE_ID = "manage-action-store"
MANAGE_CLOSE_BTN = "manage-close-btn"
MANAGE_BACK_BTN = "manage-back-btn"

# Program RTL
PROGRAM_RTL_UID_ID = "program-rtl-uid"
PROGRAM_RTL_TRANSFORMER_ID = "program-rtl-transformer"
PROGRAM_RTL_MSISDN_ID = "program-rtl-msisdn"
PROGRAM_RTL_CONFIRM_BTN = "program-rtl-confirm-btn"
PROGRAM_RTL_RESULT_ID = "program-rtl-result"

# Message Forwarding
MSG_FWD_TOGGLE_ID = "msg-fwd-toggle"
MSG_FWD_CONFIRM_BTN = "msg-fwd-confirm-btn"
MSG_FWD_RESULT_ID = "msg-fwd-result"

# Deactivate RTL
DEACTIVATE_CONFIRM_BTN = "deactivate-confirm-btn"
DEACTIVATE_RESULT_ID = "deactivate-result"


def device_manage_drawer() -> html.Div:
    """Hidden modal/drawer with three device management prototype actions.

    Layout:
    - Device info header (read-only)
    - Action selector: Program RTL | Message Forwarding | Deactivate RTL
    - Action-specific content panels
    - Prototype notice
    - Back / Close buttons
    """
    return html.Div(
        id=MANAGE_DRAWER_ID,
        className="manage-drawer",
        style={"display": "none"},
        children=[
            html.Div(
                className="manage-drawer__overlay",
                id="manage-drawer-overlay",
            ),
            html.Div(
                className="manage-drawer__panel",
                children=[
                    # Header
                    html.Div(
                        className="manage-drawer__header",
                        children=[
                            html.H2("Device Management"),
                            html.Button(
                                "\u00d7",
                                id=MANAGE_CLOSE_BTN,
                                className="manage-drawer__close",
                                n_clicks=0,
                            ),
                        ],
                    ),
                    # Hidden stores
                    dcc.Store(id=MANAGE_DEVICE_ID, storage_type="memory"),
                    dcc.Store(id=MANAGE_ACTION_STORE_ID, storage_type="memory", data="menu"),
                    # Device info
                    html.Div(
                        className="manage-drawer__device-info",
                        children=[
                            html.Div(
                                className="manage-drawer__row",
                                children=[
                                    html.Span("Device:", className="manage-drawer__label"),
                                    html.Span(id="manage-drawer-device-code", className="manage-drawer__value"),
                                ],
                            ),
                            html.Div(
                                className="manage-drawer__row",
                                children=[
                                    html.Span("Transformer:", className="manage-drawer__label"),
                                    html.Span(id="manage-drawer-transformer", className="manage-drawer__value"),
                                ],
                            ),
                            html.Div(
                                className="manage-drawer__row",
                                children=[
                                    html.Span("Plant:", className="manage-drawer__label"),
                                    html.Span(id="manage-drawer-plant", className="manage-drawer__value"),
                                ],
                            ),
                        ],
                    ),
                    html.Hr(className="manage-drawer__divider"),
                    # Action menu (shown when action="menu")
                    html.Div(
                        id="manage-action-menu",
                        className="manage-drawer__menu",
                        children=[
                            html.H3("Select Action"),
                            html.Button(
                                "Program RTL",
                                id="manage-menu-program",
                                className="manage-drawer__menu-btn",
                                n_clicks=0,
                            ),
                            html.P(
                                "Upload settings to this RTL device.",
                                className="manage-drawer__menu-desc",
                            ),
                            html.Button(
                                "Message Forwarding",
                                id="manage-menu-forwarding",
                                className="manage-drawer__menu-btn",
                                n_clicks=0,
                            ),
                            html.P(
                                "Enable or disable startup/check-in message forwarding.",
                                className="manage-drawer__menu-desc",
                            ),
                            html.Button(
                                "Deactivate RTL",
                                id="manage-menu-deactivate",
                                className="manage-drawer__menu-btn manage-drawer__menu-btn--danger",
                                n_clicks=0,
                            ),
                            html.P(
                                "Remove this RTL from the active monitoring list.",
                                className="manage-drawer__menu-desc",
                            ),
                        ],
                    ),
                    # Program RTL panel (shown when action="program")
                    html.Div(
                        id="manage-program-panel",
                        className="manage-drawer__action-panel",
                        style={"display": "none"},
                        children=[
                            html.H3("Program RTL"),
                            html.P(
                                "Record a programming request for this RTL "
                                "device. The field marked with * is required.",
                                className="manage-drawer__section-desc",
                            ),
                            html.Div(
                                className="manage-drawer__fields",
                                children=[
                                    html.Div(
                                        className="manage-drawer__field",
                                        children=[
                                            html.Label(
                                                "RTL UID *",
                                                className="manage-drawer__field-label",
                                            ),
                                            dcc.Input(
                                                id=PROGRAM_RTL_UID_ID,
                                                type="text",
                                                readOnly=True,
                                                className="manage-drawer__input",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="manage-drawer__field",
                                        children=[
                                            html.Label(
                                                "Transformer Name *",
                                                className="manage-drawer__field-label",
                                            ),
                                            dcc.Input(
                                                id=PROGRAM_RTL_TRANSFORMER_ID,
                                                type="text",
                                                readOnly=True,
                                                className="manage-drawer__input",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="manage-drawer__field",
                                        children=[
                                            html.Label(
                                                "RTL Master MSISDN *",
                                                className="manage-drawer__field-label",
                                            ),
                                            dcc.Input(
                                                id=PROGRAM_RTL_MSISDN_ID,
                                                type="text",
                                                maxLength=20,
                                                placeholder="Enter the RTL Master MSISDN",
                                                className="manage-drawer__input",
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="status-panel status-panel--inactive",
                                children=[
                                    html.Strong("Requests are recorded, not sent. "),
                                    html.Span(
                                        "The programming request is stored in "
                                        "this application. No command is yet "
                                        "sent to the RTL Master and delivery "
                                        "requires future backend integration."
                                    ),
                                ],
                            ),
                            html.Div(
                                className="manage-drawer__actions",
                                children=[
                                    html.Button(
                                        "Back",
                                        id=MANAGE_BACK_BTN,
                                        className="manage-drawer__btn manage-drawer__btn--secondary",
                                        n_clicks=0,
                                    ),
                                    html.Button(
                                        "Record Program Request",
                                        id=PROGRAM_RTL_CONFIRM_BTN,
                                        className="manage-drawer__btn manage-drawer__btn--primary",
                                        n_clicks=0,
                                    ),
                                ],
                            ),
                            html.Div(id=PROGRAM_RTL_RESULT_ID),
                        ],
                    ),
                    # Message Forwarding panel (shown when action="forwarding")
                    html.Div(
                        id="manage-forwarding-panel",
                        className="manage-drawer__action-panel",
                        style={"display": "none"},
                        children=[
                            html.H3("Message Forwarding"),
                            html.P(
                                "Enable or disable forwarding of startup/check-in "
                                "messages to the installation phone number.",
                                className="manage-drawer__section-desc",
                            ),
                            html.Div(
                                className="manage-drawer__field",
                                children=[
                                    html.Label(
                                        "Forwarding State",
                                        className="manage-drawer__field-label",
                                    ),
                                    dcc.Dropdown(
                                        id=MSG_FWD_TOGGLE_ID,
                                        options=[
                                            {"label": "Enabled", "value": "enabled"},
                                            {"label": "Disabled", "value": "disabled"},
                                        ],
                                        value="disabled",
                                        clearable=False,
                                        className="manage-drawer__dropdown",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="status-panel status-panel--inactive",
                                children=[
                                    html.Strong("Preference is stored for your account. "),
                                    html.Span(
                                        "Message delivery integration and the "
                                        "documented 18:30 automatic disable are "
                                        "not yet connected."
                                    ),
                                ],
                            ),
                            html.Div(
                                className="manage-drawer__actions",
                                children=[
                                    html.Button(
                                        "Back",
                                        id="manage-forwarding-back-btn",
                                        className="manage-drawer__btn manage-drawer__btn--secondary",
                                        n_clicks=0,
                                    ),
                                    html.Button(
                                        "Apply",
                                        id=MSG_FWD_CONFIRM_BTN,
                                        className="manage-drawer__btn manage-drawer__btn--primary",
                                        n_clicks=0,
                                    ),
                                ],
                            ),
                            html.Div(id=MSG_FWD_RESULT_ID),
                        ],
                    ),
                    # Deactivate RTL panel (shown when action="deactivate")
                    html.Div(
                        id="manage-deactivate-panel",
                        className="manage-drawer__action-panel",
                        style={"display": "none"},
                        children=[
                            html.H3("Deactivate RTL"),
                            html.Div(
                                className="manage-drawer__confirm-box",
                                children=[
                                    html.P(
                                        "This removes the RTL from the "
                                        "active list recorded in this "
                                        "application.",
                                    ),
                                    html.P(
                                        "Administrative device status and "
                                        "technician assignments are not "
                                        "changed.",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="status-panel status-panel--inactive",
                                children=[
                                    html.Strong("Active-list state is local. "),
                                    html.Span(
                                        "Deactivation updates this "
                                        "application's record. No command is "
                                        "yet sent to the RTL Master."
                                    ),
                                ],
                            ),
                            html.Div(
                                className="manage-drawer__actions",
                                children=[
                                    html.Button(
                                        "Back",
                                        id="manage-deactivate-back-btn",
                                        className="manage-drawer__btn manage-drawer__btn--secondary",
                                        n_clicks=0,
                                    ),
                                    html.Button(
                                        "Deactivate RTL",
                                        id=DEACTIVATE_CONFIRM_BTN,
                                        className="manage-drawer__btn manage-drawer__btn--danger",
                                        n_clicks=0,
                                    ),
                                ],
                            ),
                            html.Div(id=DEACTIVATE_RESULT_ID),
                        ],
                    ),
                ],
            ),
        ],
    )
