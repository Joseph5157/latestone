"""User form drawer — modal for adding/editing an application account.

ADR-033. Accounts are application-managed (local authentication): an
Administrator creates an account in Pending activation, links a client person
where relevant, and issues a one-time setup/reset link. Account STATUS is
read-only here — it changes only through the lifecycle actions (issue link,
disable, re-enable), never by picking a value, so an account cannot become
Active without a password being set.

The link result renders in `USER_RESULT_ID` and is cleared whenever the drawer
opens or closes; it is never stored client-side.
"""
from __future__ import annotations

from dash import dcc, html

USER_DRAWER_ID = "user-form-drawer"
USER_HIDDEN_ID = "user-form-hidden-id"
USER_USERNAME_ID = "user-form-username"
USER_FULLNAME_ID = "user-form-fullname"
USER_IDENTIFIER_ID = "user-form-identifier"
USER_ROLE_ID = "user-form-role"
USER_PERSON_ID = "user-form-client-person"
USER_STATUS_ID = "user-form-status"
USER_ACTIONS_ID = "user-form-lifecycle"
USER_ISSUE_BTN = "user-form-issue-btn"
USER_DISABLE_BTN = "user-form-disable-btn"
USER_ENABLE_BTN = "user-form-enable-btn"
USER_CONFIRM_BTN = "user-form-confirm-btn"
USER_CANCEL_BTN = "user-form-cancel-btn"
USER_DISMISS_BTN = "user-form-dismiss-btn"
USER_RESULT_ID = "user-form-result"
USER_REFRESH_ID = "user-admin-refresh"

_FIELD = "user-form-drawer__field"
_LABEL = "user-form-drawer__field-label"
_INPUT = "user-form-drawer__input"
_BTN_SECONDARY = "user-form-drawer__btn user-form-drawer__btn--secondary"


def _optional_label(text: str, field_id: str) -> html.Label:
    return html.Label(
        [text, html.Span("Optional", className="field-optional")],
        htmlFor=field_id,
        className=_LABEL,
    )


def user_form_drawer() -> html.Div:
    """Hidden modal/drawer that opens on Add User or Edit action.

    Contains:
    - Username (required), Full name, Identifier/Email (optional)
    - Role (Administrator / Technician / General User)
    - Client person ID (optional, validated against the client persons)
    - Account status (read-only) and lifecycle actions (edit only)
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
                                "×",
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
                    # Bumped after any account change so the table reloads.
                    dcc.Store(id=USER_REFRESH_ID, storage_type="memory", data=0),
                    html.Div(
                        className="user-form-drawer__fields",
                        children=[
                            html.Div(
                                className=_FIELD,
                                children=[
                                    html.Label(
                                        ["Username", html.Span(" *", className="required-marker")],
                                        htmlFor=USER_USERNAME_ID,
                                        className=_LABEL,
                                    ),
                                    dcc.Input(
                                        id=USER_USERNAME_ID,
                                        type="text",
                                        placeholder="Enter username...",
                                        className=_INPUT,
                                        autoComplete="off",
                                    ),
                                    html.P(
                                        id="user-form-username-error",
                                        className="user-form-drawer__error",
                                    ),
                                ],
                            ),
                            html.Div(
                                className=_FIELD,
                                children=[
                                    _optional_label("Full name", USER_FULLNAME_ID),
                                    dcc.Input(
                                        id=USER_FULLNAME_ID,
                                        type="text",
                                        placeholder="Defaults to the username",
                                        className=_INPUT,
                                        autoComplete="off",
                                    ),
                                ],
                            ),
                            html.Div(
                                className=_FIELD,
                                children=[
                                    _optional_label("Identifier / Email", USER_IDENTIFIER_ID),
                                    dcc.Input(
                                        id=USER_IDENTIFIER_ID,
                                        type="text",
                                        placeholder="e.g. user@example.com",
                                        className=_INPUT,
                                        autoComplete="off",
                                    ),
                                ],
                            ),
                            html.Div(
                                className=_FIELD,
                                children=[
                                    html.Label("Role", htmlFor=USER_ROLE_ID, className=_LABEL),
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
                                className=_FIELD,
                                children=[
                                    _optional_label("Client person ID", USER_PERSON_ID),
                                    dcc.Input(
                                        id=USER_PERSON_ID,
                                        type="number",
                                        min=1,
                                        step=1,
                                        placeholder="Client person ID",
                                        className=_INPUT,
                                        autoComplete="off",
                                    ),
                                    html.P(
                                        "Links this account to one client person. A Technician "
                                        "must be linked to a client Technician.",
                                        className="user-form-drawer__role-note",
                                    ),
                                ],
                            ),
                            html.Div(
                                className=_FIELD,
                                children=[
                                    html.Span(
                                        "Account status",
                                        className=_LABEL,
                                        id="user-form-status-label",
                                    ),
                                    html.Div(
                                        id=USER_STATUS_ID,
                                        className="user-form-drawer__status",
                                        **{"aria-labelledby": "user-form-status-label"},
                                    ),
                                ],
                            ),
                            # Lifecycle actions: edit only (hidden on Add).
                            html.Div(
                                id=USER_ACTIONS_ID,
                                className=_FIELD,
                                style={"display": "none"},
                                children=[
                                    html.Span("Account actions", className=_LABEL),
                                    html.Div(
                                        className="user-form-drawer__actions",
                                        children=[
                                            html.Button(
                                                "Issue setup link",
                                                id=USER_ISSUE_BTN,
                                                n_clicks=0,
                                                className=_BTN_SECONDARY,
                                            ),
                                            html.Button(
                                                "Disable account",
                                                id=USER_DISABLE_BTN,
                                                n_clicks=0,
                                                className=_BTN_SECONDARY,
                                            ),
                                            html.Button(
                                                "Re-enable account",
                                                id=USER_ENABLE_BTN,
                                                n_clicks=0,
                                                className=_BTN_SECONDARY,
                                                style={"display": "none"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        className="admin-boundary-note admin-boundary-note--drawer",
                        children=[
                            html.Strong("Administrative provisioning. "),
                            html.Span(
                                "Accounts use this application's own sign-in. A setup "
                                "or reset link is shown once for you to hand over; no "
                                "email or SMS is sent, and passwords are never shown."
                            ),
                        ],
                    ),
                    # Result slot — refusals and the one-time link render here
                    # so a failed action is never a silent no-op; the drawer
                    # stays open.
                    html.Div(id=USER_RESULT_ID),
                    html.Div(
                        className="user-form-drawer__actions",
                        children=[
                            html.Button(
                                "Cancel",
                                id=USER_DISMISS_BTN,
                                n_clicks=0,
                                className=_BTN_SECONDARY,
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
