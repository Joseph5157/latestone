"""User Administration page — layout only, no queries.

ADR-033: application-managed accounts (local authentication). Administrators
create accounts, link them to client persons, issue one-time setup/reset
links, and disable/re-enable them. Persisted in the application database.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from components.user_form_drawer import user_form_drawer

#: Values are the stored roles (`services.prototype_users.CONFIRMED_ROLES`);
#: labels match the table's Role column.
ROLE_FILTER_OPTIONS = [
    {"label": "All", "value": "all"},
    {"label": "Administrator", "value": "administrator"},
    {"label": "Technician", "value": "technician"},
    {"label": "General User", "value": "general"},
]


#: The one definition of the table columns, shared with the populate callback.
USER_TABLE_COLUMNS = [
    {"name": "User", "id": "username"},
    {"name": "Name", "id": "full_name"},
    {"name": "Identifier", "id": "identifier"},
    {"name": "Role", "id": "role"},
    {"name": "Status", "id": "status"},
    {"name": "Client person", "id": "client_person"},
    {"name": "Actions", "id": "actions", "presentation": "markdown"},
]


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
                    html.Strong("Application-managed sign-in. "),
                    html.Span(
                        "Accounts, roles and status are stored in the application "
                        "database and users sign in with their own password. There "
                        "is no external identity provider. Setup and reset links "
                        "are handed over by an Administrator; no email or SMS is sent."
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
                    html.P("Search by user or identifier, then filter by role or account status."),
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
                    # Role (USER-FILTERS-1). dcc.Dropdown renders a div,
                    # which a <label for> cannot reach, so the label names a
                    # group around it instead.
                    html.Div(
                        className="user-admin-toolbar__control user-admin-toolbar__filters",
                        children=[
                            html.Label(
                                "Role",
                                id="user-admin-role-filter-label",
                                className="user-admin-toolbar__label",
                            ),
                            html.Div(
                                role="group",
                                **{"aria-labelledby": "user-admin-role-filter-label"},
                                children=[
                                    dcc.Dropdown(
                                        id="user-admin-role-filter",
                                        options=ROLE_FILTER_OPTIONS,
                                        value="all",
                                        clearable=False,
                                        searchable=False,
                                        className="user-admin-toolbar__dropdown",
                                    ),
                                ],
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
                                    {"label": "Pending activation", "value": "pending_activation"},
                                    {"label": "Disabled", "value": "disabled"},
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
                columns=USER_TABLE_COLUMNS,
                rows=[],
                link_column_id="username",
                administrative_state_column_id="status",
                responsive=True,
                markdown_link_target="_self",
                # The toolbar above is this page's filter surface; the native
                # row underneath the header would be a second one, and it
                # rendered badly (USER-FILTERS-1).
                filter_action="none",
            ),
            # User form drawer (opens on Add/Edit)
            user_form_drawer(),
        ],
    )
