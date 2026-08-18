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
            html.H1("User Administration"),
            html.P(
                "Manage application users and access.",
                className="page__subtitle",
            ),
            # Prototype notice
            html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Prototype. "),
                    html.Span(
                        "User management is not connected to a production "
                        "identity system. Changes are not persisted."
                    ),
                ],
            ),
            # Toolbar — search, status filter, add user button
            html.Div(
                className="user-admin-toolbar",
                children=[
                    dcc.Input(
                        id="user-admin-search",
                        type="text",
                        placeholder="Search users...",
                        className="user-admin-toolbar__search",
                        debounce=True,
                    ),
                    html.Div(
                        className="user-admin-toolbar__filters",
                        children=[
                            html.Label(
                                "Status:",
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
                    html.Button(
                        "Add User",
                        id="user-admin-add-btn",
                        n_clicks=0,
                        className="user-admin-toolbar__add-btn",
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
                state_column_id="status",
            ),
            # User form drawer (opens on Add/Edit)
            user_form_drawer(),
        ],
    )