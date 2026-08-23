"""User Administration page — layout only, no queries.

Frontend prototype for user management. Does not persist to any identity
system. Role assignment is explicitly disabled pending client role model.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from components.user_form_drawer import user_form_drawer


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--user-admin",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("User Administration", None)]),
            ),
            html.Header(
                className="admin-page-heading",
                children=[
                    html.Div(
                        children=[
                            html.Div("Administration", className="admin-page-heading__eyebrow"),
                            html.H1("User Administration"),
                            html.P(
                                "Manage application users, roles, and account status.",
                                className="admin-page-heading__description",
                            ),
                        ],
                    ),
                    html.Button(
                        "Add User",
                        id="user-admin-add-btn",
                        n_clicks=0,
                        className="user-admin-toolbar__add-btn",
                    ),
                ],
            ),
            # Environment and integration notice
            html.Div(
                className="admin-boundary-note",
                children=[
                    html.Strong("Demo environment. "),
                    html.Span(
                        "User accounts, roles, and status changes are stored in "
                        "the local application database. Production "
                        "identity-provider integration is not yet connected."
                    ),
                ],
            ),
            html.Div(
                className="admin-section-heading",
                children=[
                    html.Div(
                        children=[
                            html.Div("Inventory", className="admin-section-heading__eyebrow"),
                            html.H2("Application users"),
                        ],
                    ),
                    html.P("Search by user or identifier, then filter by lifecycle status."),
                ],
            ),
            # Toolbar — search and status filter. Add User is the page action.
            html.Div(
                className="user-admin-toolbar",
                children=[
                    html.Div(
                        className="user-admin-toolbar__control user-admin-toolbar__control--search",
                        children=[
                            html.Label("Search", htmlFor="user-admin-search"),
                            dcc.Input(
                                id="user-admin-search", type="text",
                                placeholder="User or identifier…",
                                className="user-admin-toolbar__search", debounce=True,
                            ),
                        ],
                    ),
                    html.Div(
                        className="user-admin-toolbar__control user-admin-toolbar__filters",
                        children=[
                            html.Label(
                                "Account status",
                                htmlFor="user-admin-status-filter",
                                className="user-admin-toolbar__label",
                            ),
                            dcc.Dropdown(
                                id="user-admin-status-filter",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "Active", "value": "active"},
                                    {"label": "Inactive", "value": "inactive"},
                                ],
                                value="all",
                                clearable=False,
                                className="user-admin-toolbar__dropdown",
                            ),
                        ],
                    ),
                ],
            ),
            # Error slot
            html.Div(id="user-admin-error", className="listing-error"),
            # Summary line
            html.P(id="user-admin-summary", className="page__meta"),
            # User table
            entity_table(
                table_id="user-admin-table",
                columns=[
                    {"name": "User", "id": "username"},
                    {"name": "Identifier", "id": "identifier"},
                    {"name": "Role", "id": "role"},
                    {"name": "Status", "id": "status"},
                    {"name": "Actions", "id": "actions", "presentation": "markdown"},
                ],
                rows=[],
                link_column_id="username",
                administrative_state_column_id="status",
                responsive=True,
                markdown_link_target="_self",
            ),
            # User form drawer (opens on Add/Edit)
            user_form_drawer(),
        ],
    )
