"""Device management drawer — single workflow for Program RTL, Message Forwarding, Deactivate.

Opened from the "Manage" action in the device admin table. Contains three
sub-actions as tab-like sections. All are persisted (Program RTL records a
programming request per OPS-PROG-1, Message Forwarding stores a per-user
preference per OPS-FWD-1, Deactivate transitions rtl_active_state per
OPS-DEACT-1); none communicates with the RTL Master — no SMS is sent, no
backend command is issued to hardware.

That last sentence stays true with RTL-PROG-SIM-1's simulation section
below, which appears only when the development simulator is explicitly
enabled: it moves the request's own recorded status through the existing
command lifecycle against a deterministic in-process transport (ADR-018).
No MQTT, SMS, HTTP or Eskom communication occurs there either, and its
copy says so on screen.
"""
from __future__ import annotations

from dash import dcc, html

from services.rtl_programming_simulation_service import (
    SIMULATION_OUTCOME_LABELS,
    SIMULATION_OUTCOMES,
    is_simulation_enabled,
)

MANAGE_DRAWER_ID = "device-manage-drawer"
MANAGE_DEVICE_ID = "manage-device-hidden-id"
MANAGE_ACTION_STORE_ID = "manage-action-store"
MANAGE_CLOSE_BTN = "manage-close-btn"
MANAGE_BACK_BTN = "manage-back-btn"

# Program RTL
PROGRAM_RTL_UID_ID = "program-rtl-uid"
PROGRAM_RTL_TRANSFORMER_ID = "program-rtl-transformer"
PROGRAM_RTL_MSISDN_ID = "program-rtl-msisdn"
PROGRAM_RTL_MSISDN_ERROR_ID = "program-rtl-msisdn-error"
PROGRAM_RTL_CONFIRM_BTN = "program-rtl-confirm-btn"
PROGRAM_RTL_RESULT_ID = "program-rtl-result"

#: The request id the drawer last recorded, so a follow-up action in this
#: same drawer knows which request the operator is looking at. Always
#: present (a hidden store costs nothing and keeps `confirm_program_rtl`'s
#: output shape identical in every environment) — but **browser-owned and
#: therefore untrusted**: any callback consuming it must authorize against
#: the device first and then prove the request actually belongs to that
#: device (see callbacks/rtl_programming_simulation.py).
PROGRAM_RTL_LAST_REQUEST_ID = "program-rtl-last-request-id"

# Program RTL — development/demo simulation (RTL-PROG-SIM-1). These ids
# exist in the layout ONLY when the simulator is explicitly enabled for a
# non-production environment; the callback that uses them is likewise only
# registered then, so neither half is reachable by default.
PROGRAM_RTL_SIM_SECTION_ID = "program-rtl-sim-section"
PROGRAM_RTL_SIM_OUTCOME_ID = "program-rtl-sim-outcome"
PROGRAM_RTL_SIM_BTN = "program-rtl-sim-btn"
PROGRAM_RTL_SIM_RESULT_ID = "program-rtl-sim-result"

#: The one sentence that must accompany every simulation control, so no
#: screen can imply a physical RTL was contacted.
SIMULATION_NOTICE = (
    "Development simulation — no physical RTL, MQTT, SMS or Eskom "
    "communication occurs."
)


def program_rtl_simulation_controls() -> html.Div:
    """The dev-only simulated-execution controls for the Program RTL panel.

    Rendered only when `is_simulation_enabled()` (RTL-PROG-SIM-1). Nothing
    here simulates on its own: the operator picks an outcome and presses
    "Simulate execution" deliberately, after a request has been recorded —
    recording a request never triggers execution of any kind.
    """
    return html.Div(
        id=PROGRAM_RTL_SIM_SECTION_ID,
        className="manage-drawer__sim-section",
        children=[
            html.Hr(className="manage-drawer__divider"),
            html.H4("Simulate execution (development only)"),
            html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Development simulation. "),
                    html.Span(
                        f"{SIMULATION_NOTICE} A simulated result is not "
                        "evidence that any physical RTL was programmed."
                    ),
                ],
            ),
            html.Div(
                className="manage-drawer__field",
                children=[
                    html.Label(
                        "Simulated outcome",
                        id="program-rtl-sim-outcome-label",
                        className="manage-drawer__field-label",
                    ),
                    # dcc.Dropdown renders a div, so `<label for>` cannot
                    # reach it — same named-group pattern the forwarding
                    # toggle already uses.
                    html.Div(
                        role="group",
                        **{"aria-labelledby": "program-rtl-sim-outcome-label"},
                        children=[
                            dcc.Dropdown(
                                id=PROGRAM_RTL_SIM_OUTCOME_ID,
                                options=[
                                    {
                                        "label": SIMULATION_OUTCOME_LABELS[outcome],
                                        "value": outcome,
                                    }
                                    for outcome in SIMULATION_OUTCOMES
                                ],
                                value=SIMULATION_OUTCOMES[0],
                                clearable=False,
                                className="manage-drawer__dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="manage-drawer__actions",
                children=[
                    html.Button(
                        "Simulate execution",
                        id=PROGRAM_RTL_SIM_BTN,
                        className="manage-drawer__btn manage-drawer__btn--secondary",
                        n_clicks=0,
                    ),
                ],
            ),
            html.Div(id=PROGRAM_RTL_SIM_RESULT_ID),
        ],
    )

# Message Forwarding
MSG_FWD_TOGGLE_ID = "msg-fwd-toggle"
MSG_FWD_CONFIRM_BTN = "msg-fwd-confirm-btn"
MSG_FWD_RESULT_ID = "msg-fwd-result"

# Deactivate RTL
DEACTIVATE_CONFIRM_BTN = "deactivate-confirm-btn"
DEACTIVATE_RESULT_ID = "deactivate-result"


def device_manage_drawer() -> html.Div:
    """Hidden modal/drawer with three device management actions.

    Layout:
    - Header (eyebrow / title / description) with accessible close button
    - Action selector: Program RTL | Message Forwarding | Deactivate RTL
    - Action-specific content panels, each ending in a result slot
    - Honesty notices per action
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
                            html.Div(
                                children=[
                                    html.Div(
                                        "Device Management",
                                        className="manage-drawer__eyebrow",
                                    ),
                                    html.H2("Manage RTL"),
                                    html.P(
                                        "Programming, forwarding and "
                                        "active-list actions for this RTL.",
                                        className="manage-drawer__description",
                                    ),
                                ],
                            ),
                            html.Button(
                                "\u00d7",
                                id=MANAGE_CLOSE_BTN,
                                className="manage-drawer__close",
                                n_clicks=0,
                                title="Close device management",
                                **{"aria-label": "Close device management"},
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
                                "Save a local enable or disable preference for "
                                "your account. It applies to your account, not "
                                "specifically to this RTL; no RTL Master command "
                                "or message delivery occurs here.",
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
                                                htmlFor=PROGRAM_RTL_UID_ID,
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
                                                htmlFor=PROGRAM_RTL_TRANSFORMER_ID,
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
                                                htmlFor=PROGRAM_RTL_MSISDN_ID,
                                                className="manage-drawer__field-label",
                                            ),
                                            dcc.Input(
                                                id=PROGRAM_RTL_MSISDN_ID,
                                                type="text",
                                                maxLength=20,
                                                placeholder="Enter the RTL Master MSISDN",
                                                className="manage-drawer__input",
                                            ),
                                            html.P(
                                                id=PROGRAM_RTL_MSISDN_ERROR_ID,
                                                className="manage-drawer__field-error",
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
                            dcc.Store(
                                id=PROGRAM_RTL_LAST_REQUEST_ID,
                                storage_type="memory",
                            ),
                            html.Div(id=PROGRAM_RTL_RESULT_ID),
                            # RTL-PROG-SIM-1: present only when the
                            # simulator is explicitly enabled for a
                            # non-production environment. When it is not,
                            # these controls do not exist at all — there is
                            # nothing disabled or hidden to re-enable from
                            # the browser.
                            *(
                                [program_rtl_simulation_controls()]
                                if is_simulation_enabled()
                                else []
                            ),
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
                                "Save a local enable or disable preference for "
                                "your account. No RTL Master command or message "
                                "delivery occurs here. BR016's daily cutoff is "
                                "performed by the RTL Master, not this dashboard.",
                                className="manage-drawer__section-desc",
                            ),
                            html.Div(
                                className="manage-drawer__field",
                                children=[
                                    html.Label(
                                        "Forwarding State",
                                        id="msg-fwd-toggle-label",
                                        className="manage-drawer__field-label",
                                    ),
                                    # dcc.Dropdown renders a div, so `<label
                                    # for>` cannot reach it and dcc.* rejects
                                    # arbitrary aria-* props outright — a
                                    # named group is the reachable fix.
                                    html.Div(
                                        role="group",
                                        **{"aria-labelledby": "msg-fwd-toggle-label"},
                                        children=[
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
                                ],
                            ),
                            html.Div(
                                className="status-panel status-panel--inactive",
                                children=[
                                    html.Strong("Preference is stored for your account. "),
                                    html.Span(
                                        "This applies to your account, not "
                                        "specifically to this RTL. Message "
                                        "delivery integration is not yet "
                                        "connected; BR016's 18:30 cutoff is "
                                        "owned by the RTL Master."
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
