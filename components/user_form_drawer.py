"""User form drawer — modal for adding/editing a user.

Prototype only: does not persist to any identity system. Role selector is
disabled with explicit 'Client role model required' label.
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


def user_form_drawer() -> html.Div:
    """Hidden modal/drawer that opens on Add User or Edit action.

    Contains:
    - Username (required)
    - Identifier/Email (optional, prototype)
    - Role (disabled — 'Client role model required')
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
                            html.H2(id="user-form-drawer-title"),
                            html.Button(
                                "\u00d7",
                                id=USER_CANCEL_BTN,
                                className="user-form-drawer__close",
                                n_clicks=0,
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
                                        "Username",
                                        htmlFor=USER_USERNAME_ID,
                                        className="user-form-drawer__field-label",
                                    ),
                                    dcc.Input(
                                        id=USER_USERNAME_ID,
                                        type="text",
                                        placeholder="Enter username...",
                                        className="user-form-drawer__input",
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
                                        "Identifier / Email",
                                        htmlFor=USER_IDENTIFIER_ID,
                                        className="user-form-drawer__field-label",
                                    ),
                                    dcc.Input(
                                        id=USER_IDENTIFIER_ID,
                                        type="text",
                                        placeholder="e.g. user@example.com",
                                        className="user-form-drawer__input",
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
                                            {"label": "Client role model required", "value": "tbd", "disabled": True},
                                        ],
                                        value="tbd",
                                        disabled=True,
                                        clearable=False,
                                        className="user-form-drawer__dropdown",
                                    ),
                                    html.P(
                                        "Role assignment pending client role model confirmation.",
                                        className="user-form-drawer__role-note",
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
                        className="status-panel status-panel--inactive",
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