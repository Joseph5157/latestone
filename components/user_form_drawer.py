"""User form drawer — modal for adding/editing a user.

Prototype only: does not persist to any identity system. Role selector now uses
confirmed runtime roles from the client Functional Specification.
"""
from __future__ import annotations

from dash import dcc, html

USER_DRAWER_ID = "user-form-drawer"
USER_HIDDEN_ID = "user-form-hidden-id"
USER_USERNAME_ID = "user-form-username"
USER_IDENTIFIER_ID = "user-form-identifier"
USER_ROLE_ID = "user-form-role"
USER_STATUS_ID = "user-form-status"
USER_CONFIRM_BTN = "user-form-confirm-btn"
USER_CANCEL_BTN = "user-form-cancel-btn"
USER_DISMISS_BTN = "user-form-dismiss-btn"


def user_form_drawer() -> html.Div:
    """Hidden modal/drawer that opens on Add User or Edit action.

    Contains:
    - Username (required)
    - Identifier/Email (optional, prototype)
    - Role (Administrator / Technician / General User)
    - Status (Active/Inactive)
    - Confirm / Cancel actions

    The drawer starts hidden and is populated by callback on open.
    """
    return html.Div(
        id=USER_DRAWER_ID,
        className="user-form-drawer",
        style={"display": "none"},
        children=[
            html.Div(
                className="user-form-drawer__overlay",
                id="user-form-drawer-overlay",
            ),
            html.Div(
                className="user-form-drawer__panel",
                children=[
                    html.Div(
                        className="user-form-drawer__header",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("User management", className="user-form-drawer__eyebrow"),
                                    html.H2(id="user-form-drawer-title"),
                                    html.P(
                                        "Set application identity, access role, and lifecycle status.",
                                        className="user-form-drawer__description",
                                    ),
                                ],
                            ),
                            html.Button(
                                "\u00d7",
                                id=USER_CANCEL_BTN,
                                className="user-form-drawer__close",
                                n_clicks=0,
                                title="Close user form",
                                **{"aria-label": "Close user form"},
                            ),
                        ],
                    ),
                    # Hidden field to track which user is being edited (None = new)
                    dcc.Store(id=USER_HIDDEN_ID, storage_type="memory"),
                    # Form fields
                    html.Div(
                        className="user-form-drawer__fields",
                        children=[
                            html.Div(
                                className="user-form-drawer__field",
                                children=[
                                    html.Label(
                                        ["Username", html.Span(" *", className="required-marker")],
                                        htmlFor=USER_USERNAME_ID,
                                        className="user-form-drawer__field-label",
                                    ),
                                    dcc.Input(
                                        id=USER_USERNAME_ID,
                                        type="text",
                                        placeholder="Enter username...",
                                        className="user-form-drawer__input",
                                        autoComplete="off",
                                    ),
                                    html.P(
                                        id="user-form-username-error",
                                        className="user-form-drawer__error",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="user-form-drawer__field",
                                children=[
                                    html.Label(
                                        [
                                            "Identifier / Email",
                                            html.Span("Optional", className="field-optional"),
                                        ],
                                        htmlFor=USER_IDENTIFIER_ID,
                                        className="user-form-drawer__field-label",
                                    ),
                                    dcc.Input(
                                        id=USER_IDENTIFIER_ID,
                                        type="text",
                                        placeholder="e.g. user@example.com",
                                        className="user-form-drawer__input",
                                        autoComplete="off",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="user-form-drawer__field",
                                children=[
                                    html.Label(
                                        "Role",
                                        htmlFor=USER_ROLE_ID,
                                        className="user-form-drawer__field-label",
                                    ),
                                    dcc.Dropdown(
                                        id=USER_ROLE_ID,
                                        options=[
                                            {"label": "Administrator", "value": "administrator"},
                                            {"label": "Technician", "value": "technician"},
                                            {"label": "General User", "value": "general"},
                                        ],
                                        value="general",
                                        clearable=False,
                                        className="user-form-drawer__dropdown",
                                    ),
                                    html.Ul(
                                        className="user-form-drawer__role-note",
                                        children=[
                                            html.Li("Administrator — broader RTL management."),
                                            html.Li("Technician — assigned RTL device work."),
                                            html.Li("General User — view and export access."),
                                        ],
                                    ),
                                ],
                            ),
                            html.Div(
                                className="user-form-drawer__field",
                                children=[
                                    html.Label(
                                        "Status",
                                        htmlFor=USER_STATUS_ID,
                                        className="user-form-drawer__field-label",
                                    ),
                                    dcc.Dropdown(
                                        id=USER_STATUS_ID,
                                        options=[
                                            {"label": "Active", "value": "active"},
                                            {"label": "Inactive", "value": "inactive"},
                                        ],
                                        value="active",
                                        clearable=False,
                                        className="user-form-drawer__dropdown",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Prototype notice
                    html.Div(
                        className="admin-boundary-note admin-boundary-note--drawer",
                        children=[
                            html.Strong("Prototype. "),
                            html.Span(
                                "This action does not persist to the "
                                "production identity system."
                            ),
                        ],
                    ),
                    # Actions
                    html.Div(
                        className="user-form-drawer__actions",
                        children=[
                            html.Button(
                                "Cancel",
                                id=USER_DISMISS_BTN,
                                n_clicks=0,
                                className="user-form-drawer__btn user-form-drawer__btn--secondary",
                            ),
                            html.Button(
                                id=USER_CONFIRM_BTN,
                                n_clicks=0,
                                className="user-form-drawer__btn user-form-drawer__btn--primary",
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
