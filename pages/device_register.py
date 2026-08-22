"""Device Registration page — layout only, no queries.

Registers a new device into plant_monitoring.devices (DB-4). Only device
identity/hierarchy placement (device code, transformer, status) is
collected here; operational metadata (MSISDN, hardware/firmware version,
install date) is out of scope until a commissioning workflow exists.
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
            html.Header(
                className="admin-page-heading admin-page-heading--registration",
                children=[
                    html.Div("Administration", className="admin-page-heading__eyebrow"),
                    html.H1("Register Device"),
                    html.P(
                        "Create an RTL identity in the monitoring hierarchy.",
                        className="admin-page-heading__description",
                    ),
                ],
            ),
            # Scope notice
            html.Div(
                className="admin-boundary-note device-register-boundary",
                children=[
                    html.Strong("Registers device identity only. "),
                    html.Span(
                        "This adds the device to the monitoring hierarchy. "
                        "Operational metadata (MSISDN, hardware/firmware "
                        "version, install date) and RTL programming are "
                        "handled separately and are not set here."
                    ),
                ],
            ),
            # Registration form
            html.Div(
                id="device-register-form",
                className="device-register-form",
                children=[
                    html.Div(
                        className="device-register-form__heading",
                        children=[
                            html.Div("Registration details", className="admin-section-heading__eyebrow"),
                            html.H2("Device identity and placement"),
                            html.P(
                                [html.Span("*", className="required-marker"), " Required field"],
                                className="device-register-form__required-note",
                            ),
                        ],
                    ),
                    # Device Code
                    html.Div(
                        className="device-register-form__field",
                        children=[
                            html.Label(
                                ["RTL UID / Device Code", html.Span(" *", className="required-marker")],
                                htmlFor="device-register-code",
                                className="device-register-form__label",
                            ),
                            dcc.Input(
                                id="device-register-code",
                                type="text",
                                placeholder="e.g. 29017",
                                className="device-register-form__input",
                                maxLength=10,
                                required=True,
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
                                ["Plant", html.Span(" *", className="required-marker")],
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
                                ["Transformer", html.Span(" *", className="required-marker")],
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
                                "Choose a plant first to load its transformers.",
                                className="device-register-form__helper",
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
                    html.P(
                        "You are about to create this application device record.",
                        className="device-register-review__description",
                    ),
                    html.Div(id="device-register-review-summary"),
                    html.Div(
                        className="device-register-form__actions",
                        children=[
                            html.Button(
                                "Submit",
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
                    html.Div(id="device-register-error", style={"display": "none"}),
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
                            html.H3("Device Registered"),
                            html.P(
                                "The device has been added to the "
                                "monitoring hierarchy."
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
