"""Assignment drawer — modal for reassigning a device to a different transformer
and/or assigning a technician.

Displayed when the user clicks the "Assign" action in the device admin table.
This is a prototype component: the assign action uses mock in-memory adapters
and does not persist to any database.

The drawer has two explicit sections:
1. Asset Assignment — Plant → Transformer (existing functionality)
2. Technician Assignment — Assigned Technician (new from Functional Spec)
"""
from __future__ import annotations

from dash import dcc, html

ASSIGN_DRAWER_ID = "assign-device-drawer"
ASSIGN_DEVICE_ID = "assign-device-hidden-id"
ASSIGN_PLANT_ID = "assign-plant"
ASSIGN_TRANSFORMER_ID = "assign-transformer"
ASSIGN_TECHNICIAN_ID = "assign-technician"
ASSIGN_CONFIRM_BTN = "assign-confirm-btn"
ASSIGN_CANCEL_BTN = "assign-cancel-btn"


def assign_device_drawer() -> html.Div:
    """Hidden modal/drawer that opens on assign action.

    The drawer contains:
    - device info (read-only)
    - Asset Assignment section: plant dropdown → transformer cascade
    - Technician Assignment section: technician dropdown (from prototype users)
    - confirm / cancel actions

    Options are populated by callback on open; the drawer starts hidden.
    """
    return html.Div(
        id=ASSIGN_DRAWER_ID,
        className="assign-drawer",
        style={"display": "none"},
        children=[
            html.Div(
                className="assign-drawer__overlay",
                id="assign-drawer-overlay",
            ),
            html.Div(
                className="assign-drawer__panel",
                children=[
                    html.Div(
                        className="assign-drawer__header",
                        children=[
                            html.H2("Assign Device"),
                            html.Button(
                                "\u00d7",
                                id=ASSIGN_CANCEL_BTN,
                                className="assign-drawer__close",
                                n_clicks=0,
                            ),
                        ],
                    ),
                    # Hidden field to track which device is being assigned
                    dcc.Store(id=ASSIGN_DEVICE_ID, storage_type="memory"),
                    # Device info (read-only)
                    html.Div(
                        className="assign-drawer__device-info",
                        children=[
                            html.Div(
                                className="assign-drawer__row",
                                children=[
                                    html.Span("Device:", className="assign-drawer__label"),
                                    html.Span(id="assign-drawer-device-code", className="assign-drawer__value"),
                                ],
                            ),
                            html.Div(
                                className="assign-drawer__row",
                                children=[
                                    html.Span("Current Transformer:", className="assign-drawer__label"),
                                    html.Span(id="assign-drawer-current-transformer", className="assign-drawer__value"),
                                ],
                            ),
                            html.Div(
                                className="assign-drawer__row",
                                children=[
                                    html.Span("Current Plant:", className="assign-drawer__label"),
                                    html.Span(id="assign-drawer-current-plant", className="assign-drawer__value"),
                                ],
                            ),
                        ],
                    ),
                    # Section 1: Asset Assignment
                    html.Hr(className="assign-drawer__divider"),
                    html.H3("Asset Assignment", className="assign-drawer__section-title"),
                    html.P(
                        "Reassign this device to a different plant/transformer.",
                        className="assign-drawer__section-desc",
                    ),
                    html.Div(
                        className="assign-drawer__fields",
                        children=[
                            html.Div(
                                className="assign-drawer__field",
                                children=[
                                    html.Label(
                                        "Plant",
                                        htmlFor=ASSIGN_PLANT_ID,
                                        className="assign-drawer__field-label",
                                    ),
                                    dcc.Dropdown(
                                        id=ASSIGN_PLANT_ID,
                                        options=[],
                                        placeholder="Select plant...",
                                        searchable=True,
                                        className="assign-drawer__dropdown",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="assign-drawer__field",
                                children=[
                                    html.Label(
                                        "Transformer",
                                        htmlFor=ASSIGN_TRANSFORMER_ID,
                                        className="assign-drawer__field-label",
                                    ),
                                    dcc.Dropdown(
                                        id=ASSIGN_TRANSFORMER_ID,
                                        options=[],
                                        placeholder="Select transformer...",
                                        searchable=True,
                                        disabled=True,
                                        className="assign-drawer__dropdown",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Section 2: Technician Assignment
                    html.Hr(className="assign-drawer__divider"),
                    html.H3("Technician Assignment", className="assign-drawer__section-title"),
                    html.P(
                        "Assign a technician to this RTL device. Only active "
                        "technicians appear in the list.",
                        className="assign-drawer__section-desc",
                    ),
                    html.Div(
                        className="assign-drawer__fields",
                        children=[
                            html.Div(
                                className="assign-drawer__field",
                                children=[
                                    html.Label(
                                        "Assigned Technician",
                                        htmlFor=ASSIGN_TECHNICIAN_ID,
                                        className="assign-drawer__field-label",
                                    ),
                                    dcc.Dropdown(
                                        id=ASSIGN_TECHNICIAN_ID,
                                        options=[],
                                        placeholder="Select technician...",
                                        searchable=True,
                                        clearable=True,
                                        className="assign-drawer__dropdown",
                                    ),
                                    html.P(
                                        id="assign-technician-empty",
                                        className="assign-drawer__empty-state",
                                        style={"display": "none"},
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Prototype notice
                    html.Div(
                        className="status-panel status-panel--inactive",
                        children=[
                            html.Strong("Prototype. "),
                            html.Span(
                                "This action does not persist to the "
                                "production database or identity system."
                            ),
                        ],
                    ),
                    # Actions
                    html.Div(
                        className="assign-drawer__actions",
                        children=[
                            html.Button(
                                "Confirm Assignment (Prototype)",
                                id=ASSIGN_CONFIRM_BTN,
                                n_clicks=0,
                                className="assign-drawer__btn assign-drawer__btn--primary",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
