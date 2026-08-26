"""Assignment drawer — modal for assigning a technician to an RTL device.

Displayed when the user clicks the "Assign" action in the device admin table,
or opened via an `?assign=` deep link from the Fleet Overview's Unassigned
RTLs panel.

Technician assignment is persisted (DB-3) via services/prototype_assignments.py,
backed by plant_monitoring.user_device_assignments. Technician *options* come
from the shared prototype user store, services/prototype_users.py.

There is deliberately NO asset (device -> transformer) section: moving a
device between transformers is the registration/hierarchy workflow, and the
former mock cascade never wrote to devices.transformer_id — presenting it as
an assignment implied an operation that does not exist (ENT-5 decision D1).
"""
from __future__ import annotations

from dash import dcc, html

ASSIGN_DRAWER_ID = "assign-device-drawer"
ASSIGN_DEVICE_ID = "assign-device-hidden-id"
ASSIGN_TECHNICIAN_ID = "assign-technician"
ASSIGN_CONFIRM_BTN = "assign-confirm-btn"
ASSIGN_CANCEL_BTN = "assign-cancel-btn"
ASSIGN_CLOSE_BTN = "assign-close-btn"
ASSIGN_RESULT_ID = "assign-result"


def assign_device_drawer() -> html.Div:
    """Hidden modal/drawer that opens on assign action.

    The drawer contains:
    - header (eyebrow / title / description) with an accessible close button
    - device info (read-only)
    - Technician Assignment section: technician dropdown (from prototype users)
    - boundary notice
    - cancel / confirm actions and a result slot

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
                            html.Div(
                                children=[
                                    html.Div(
                                        "Device Management",
                                        className="assign-drawer__eyebrow",
                                    ),
                                    html.H2("Assign Device"),
                                    html.P(
                                        "Assign a technician responsible "
                                        "for this RTL device.",
                                        className="assign-drawer__description",
                                    ),
                                ],
                            ),
                            html.Button(
                                "\u00d7",
                                id=ASSIGN_CANCEL_BTN,
                                className="assign-drawer__close",
                                n_clicks=0,
                                title="Close assignment form",
                                **{"aria-label": "Close assignment form"},
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
                                    html.Span("Transformer:", className="assign-drawer__label"),
                                    html.Span(id="assign-drawer-current-transformer", className="assign-drawer__value"),
                                ],
                            ),
                            html.Div(
                                className="assign-drawer__row",
                                children=[
                                    html.Span("Plant:", className="assign-drawer__label"),
                                    html.Span(id="assign-drawer-current-plant", className="assign-drawer__value"),
                                ],
                            ),
                        ],
                    ),
                    # Technician Assignment
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
                    # Boundary notice — technician assignment persists (DB-3);
                    # the disclosure names what is NOT connected.
                    html.Div(
                        className="status-panel status-panel--inactive",
                        children=[
                            html.Strong("Assignment is stored and audited. "),
                            html.Span(
                                "The technician assignment is saved in this "
                                "application's database. No identity-system "
                                "or hierarchy change is made, and no message "
                                "is sent to the device."
                            ),
                        ],
                    ),
                    # Result slot — every confirm renders exactly one outcome
                    # here (success / failure / refusal); the drawer stays
                    # open so the operator keeps their context.
                    html.Div(id=ASSIGN_RESULT_ID),
                    # Actions
                    html.Div(
                        className="assign-drawer__actions",
                        children=[
                            html.Button(
                                "Cancel",
                                id=ASSIGN_CLOSE_BTN,
                                n_clicks=0,
                                className="assign-drawer__btn assign-drawer__btn--secondary",
                            ),
                            html.Button(
                                "Confirm Assignment",
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
