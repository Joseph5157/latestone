"""Device Registration page — layout only, no queries.

Registers a new device into plant_monitoring.devices (DB-4). Only device
identity/hierarchy placement (device code, transformer, status) is
collected here; operational metadata (MSISDN, hardware/firmware version,
install date) is out of scope until a commissioning workflow exists.

REGISTER-UX-1: the form sits beside a live summary card on wide screens,
and the device code follows the shared 5-digit UID rule (ADR-022).
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.field import field

#: The code hint before anything is typed. The live hint callback returns
#: this same string for an empty value, so first paint and callback agree.
CODE_HINT_EMPTY = "Required · 5 digits, e.g. 29017."

_NOT_ENTERED = "Not entered"
_NOT_SELECTED = "Not selected"


def summary_body(
    code: str | None,
    plant_label: str | None,
    transformer_label: str | None,
    status: str | None,
) -> html.Dl:
    """The summary card's rows: what the operator has entered so far.

    Echoes the form only. It makes no claim that the code is free or valid;
    Review is where that is checked.
    """
    code_text = code.strip() if isinstance(code, str) and code.strip() else None
    rows = [
        ("RTL UID / Device Code", code_text, _NOT_ENTERED),
        ("Plant", plant_label, _NOT_SELECTED),
        ("Transformer", transformer_label, _NOT_SELECTED),
        ("Status", (status or "active").capitalize(), _NOT_SELECTED),
    ]
    children = []
    for label, value, placeholder in rows:
        children.append(html.Dt(label, className="device-register-summary__label"))
        children.append(
            html.Dd(
                value or placeholder,
                className=(
                    "device-register-summary__value"
                    if value
                    else "device-register-summary__value device-register-summary__value--empty"
                ),
            )
        )
    return html.Dl(children, className="device-register-summary__rows")


def _summary_card() -> html.Aside:
    return html.Aside(
        id="device-register-summary",
        className="device-register-summary",
        **{"aria-labelledby": "device-register-summary-title"},
        children=[
            html.Div("Summary", className="admin-section-heading__eyebrow"),
            html.H2("Registration summary", id="device-register-summary-title"),
            html.Div(
                id="device-register-summary-body",
                children=summary_body(None, None, None, "active"),
            ),
            html.Div(
                className="device-register-summary__next",
                children=[
                    html.H3("What happens next"),
                    html.Ul([
                        html.Li(
                            "The device starts unassigned. You can assign a "
                            "technician as soon as it is registered."
                        ),
                        html.Li(
                            "It shows No Data until the RTL sends its first reading."
                        ),
                        html.Li("RTL programming is a separate step."),
                    ]),
                ],
            ),
        ],
    )


def _form() -> html.Div:
    return html.Div(
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
            # A real <input>, so the label's `for` genuinely reaches it. No
            # browser `required`: Dash draws `input.dash-input:invalid` with a
            # red outline, so an empty required input looked like an error
            # before the operator had done anything. The page validates the
            # field itself; the asterisk still marks it required.
            field(
                "RTL UID / Device Code",
                dcc.Input(
                    id="device-register-code",
                    # Controlled from first paint: "Register another" sets
                    # this value, and React warns when an input switches
                    # from uncontrolled to controlled.
                    value="",
                    type="text",
                    inputMode="numeric",
                    autoComplete="off",
                    placeholder="e.g. 29017",
                    className="device-register-form__input",
                    maxLength=5,
                ),
                control_id="device-register-code",
                error_id="device-register-code-error",
                required=True,
                # Live guidance (MOBBIN-UX-6), in its own slot so typing
                # never rewrites the role="alert" error on every keystroke.
                hint=CODE_HINT_EMPTY,
                hint_id="device-register-code-hint",
            ),
            # Cascade trigger. labelable=False: a <label for> cannot
            # target the div dcc.Dropdown renders, so the label names a
            # group around it instead of pointing at nothing.
            field(
                "Plant",
                dcc.Dropdown(
                    id="device-register-plant",
                    options=[],
                    placeholder="Select plant...",
                    searchable=True,
                    className="device-register-form__dropdown",
                ),
                control_id="device-register-plant",
                error_id="device-register-plant-error",
                required=True,
                labelable=False,
            ),
            field(
                "Transformer",
                dcc.Dropdown(
                    id="device-register-transformer",
                    options=[],
                    placeholder="Select transformer...",
                    searchable=True,
                    disabled=True,
                    className="device-register-form__dropdown",
                ),
                control_id="device-register-transformer",
                description="Choose a plant first to load its transformers.",
                error_id="device-register-transformer-error",
                required=True,
                labelable=False,
            ),
            field(
                "Status",
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
                control_id="device-register-status",
                labelable=False,
            ),
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
    )


def _review() -> html.Div:
    return html.Div(
        id="device-register-review",
        className="device-register-form",
        style={"display": "none"},
        children=[
            html.Div(
                className="device-register-form__heading",
                children=[
                    html.Div("Confirm", className="admin-section-heading__eyebrow"),
                    html.H2("Review Registration"),
                    html.P(
                        "You are about to create this application device record.",
                        className="device-register-review__description",
                    ),
                ],
            ),
            html.Div(id="device-register-review-summary"),
            html.Div(id="device-register-error", style={"display": "none"}),
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
        ],
    )


def _success() -> html.Div:
    return html.Div(
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
            html.Div(
                className="device-register-form__actions device-register-success__actions",
                children=[
                    # Assign / Open links for the new device, filled on submit.
                    html.Div(
                        id="device-register-success-actions",
                        className="device-register-success__links",
                    ),
                    html.Button(
                        "Register another",
                        id="device-register-another-btn",
                        n_clicks=0,
                        className="device-register-form__btn device-register-form__btn--secondary",
                    ),
                    dcc.Link(
                        "Back to Device Management",
                        href="/admin/devices",
                        className="device-register-form__btn device-register-form__btn--secondary",
                    ),
                ],
            ),
        ],
    )


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
            # Form, review and success take turns in the main column; the
            # summary card sits beside them and stacks below on narrow screens.
            html.Div(
                className="device-register-layout",
                children=[
                    html.Div(
                        className="device-register-layout__main",
                        children=[_form(), _review(), _success()],
                    ),
                    _summary_card(),
                ],
            ),
        ],
    )
