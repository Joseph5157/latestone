"""Device Registration page — layout only, no queries.

Frontend-only workflow for registering a new device. This is a prototype
form: the submit action does not persist to any database. The success
message explicitly states this.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--device-register",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    ("Devices", "/admin/devices"),
                    ("Register", None),
                ]),
            ),
            html.H1("Register Device"),
            html.P(
                "Add a new device to the monitoring hierarchy.",
                className="page__subtitle",
            ),
            # Prototype notice
            html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Prototype workflow. "),
                    html.Span(
                        "This form does not persist data to the production "
                        "database. It demonstrates the registration UX for "
                        "client review."
                    ),
                ],
            ),
            # Registration form
            html.Div(
                id="device-register-form",
                className="device-register-form",
                children=[
                    # Device Code
                    html.Div(
                        className="device-register-form__field",
                        children=[
                            html.Label(
                                "Device Code",
                                htmlFor="device-register-code",
                                className="device-register-form__label",
                            ),
                            dcc.Input(
                                id="device-register-code",
                                type="text",
                                placeholder="e.g. 29017",
                                className="device-register-form__input",
                                maxLength=10,
                            ),
                            html.P(
                                id="device-register-code-error",
                                className="device-register-form__error",
                            ),
                        ],
                    ),
                    # Plant selector (cascade trigger)
                    html.Div(
                        className="device-register-form__field",
                        children=[
                            html.Label(
                                "Plant",
                                htmlFor="device-register-plant",
                                className="device-register-form__label",
                            ),
                            dcc.Dropdown(
                                id="device-register-plant",
                                options=[],
                                placeholder="Select plant...",
                                searchable=True,
                                className="device-register-form__dropdown",
                            ),
                            html.P(
                                id="device-register-plant-error",
                                className="device-register-form__error",
                            ),
                        ],
                    ),
                    # Transformer selector (cascade from plant)
                    html.Div(
                        className="device-register-form__field",
                        children=[
                            html.Label(
                                "Transformer",
                                htmlFor="device-register-transformer",
                                className="device-register-form__label",
                            ),
                            dcc.Dropdown(
                                id="device-register-transformer",
                                options=[],
                                placeholder="Select transformer...",
                                searchable=True,
                                disabled=True,
                                className="device-register-form__dropdown",
                            ),
                            html.P(
                                id="device-register-transformer-error",
                                className="device-register-form__error",
                            ),
                        ],
                    ),
                    # Status
                    html.Div(
                        className="device-register-form__field",
                        children=[
                            html.Label(
                                "Status",
                                htmlFor="device-register-status",
                                className="device-register-form__label",
                            ),
                            dcc.Dropdown(
                                id="device-register-status",
                                options=[
                                    {"label": "Active", "value": "active"},
                                    {"label": "Inactive", "value": "inactive"},
                                ],
                                value="active",
                                clearable=False,
                                className="device-register-form__dropdown",
                            ),
                        ],
                    ),
                    # Form actions
                    html.Div(
                        className="device-register-form__actions",
                        children=[
                            html.Button(
                                "Review",
                                id="device-register-review-btn",
                                n_clicks=0,
                                className="device-register-form__btn device-register-form__btn--primary",
                            ),
                            dcc.Link(
                                "Cancel",
                                href="/admin/devices",
                                className="device-register-form__btn device-register-form__btn--secondary",
                            ),
                        ],
                    ),
                ],
            ),
            # Review state (hidden initially)
            html.Div(
                id="device-register-review",
                className="device-register-form",
                style={"display": "none"},
                children=[
                    html.H2("Review Registration"),
                    html.Div(id="device-register-review-summary"),
                    html.Div(
                        className="device-register-form__actions",
                        children=[
                            html.Button(
                                "Submit (Prototype)",
                                id="device-register-submit-btn",
                                n_clicks=0,
                                className="device-register-form__btn device-register-form__btn--primary",
                            ),
                            html.Button(
                                "Edit",
                                id="device-register-edit-btn",
                                n_clicks=0,
                                className="device-register-form__btn device-register-form__btn--secondary",
                            ),
                        ],
                    ),
                ],
            ),
            # Success state (hidden initially)
            html.Div(
                id="device-register-success",
                className="device-register-form",
                style={"display": "none"},
                children=[
                    html.Div(
                        className="status-panel status-panel--success",
                        children=[
                            html.H3("Device Registered (Prototype)"),
                            html.P(
                                "The device has been registered in the "
                                "frontend session. No data was persisted to "
                                "the production database."
                            ),
                            html.Div(id="device-register-success-detail"),
                        ],
                    ),
                    dcc.Link(
                        "Back to Device Management",
                        href="/admin/devices",
                        className="device-register-form__btn device-register-form__btn--primary",
                    ),
                ],
            ),
        ],
    )
