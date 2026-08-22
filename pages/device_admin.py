"""Device Management page — layout only, no queries."""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.assign_device_drawer import assign_device_drawer
from components.breadcrumb import breadcrumb
from components.device_manage_drawer import device_manage_drawer
from components.entity_table import entity_table


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--device-admin",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Devices", None)]),
            ),
            html.H1("Device Management"),
            html.P(
                "Manage the devices this application monitors.",
                className="page__subtitle",
            ),
            # Toolbar — search, status filter, register button
            html.Div(
                className="device-admin-toolbar",
                children=[
                    dcc.Input(
                        id="device-admin-search",
                        type="text",
                        placeholder="Search devices...",
                        className="device-admin-toolbar__search",
                        debounce=True,
                    ),
                    html.Div(
                        className="device-admin-toolbar__filters",
                        children=[
                            html.Label(
                                "Status:",
                                className="device-admin-toolbar__label",
                            ),
                            dcc.Dropdown(
                                id="device-admin-status-filter",
                                options=[
                                    {"label": "All", "value": "all"},
                                    {"label": "Active", "value": "active"},
                                    {"label": "Inactive", "value": "inactive"},
                                ],
                                value="all",
                                clearable=False,
                                className="device-admin-toolbar__dropdown",
                            ),
                        ],
                    ),
                    html.Button(
                        "Register Device",
                        id="device-admin-register-btn",
                        n_clicks=0,
                        className="device-admin-toolbar__register-btn",
                    ),
                ],
            ),
            # Error slot
            html.Div(id="device-admin-error", className="listing-error"),
            # Summary line
            html.P(id="device-admin-summary", className="page__meta"),
            # Device table
            entity_table(
                table_id="device-admin-table",
                columns=[
                    {"name": "Device", "id": "device"},
                    {"name": "Plant", "id": "plant"},
                    {"name": "Transformer", "id": "transformer"},
                    {"name": "Status", "id": "status"},
                    {"name": "Data", "id": "freshness"},
                    {"name": "Actions", "id": "actions", "presentation": "markdown"},
                ],
                rows=[],
                link_column_id="device",
                state_column_id="freshness",
                administrative_state_column_id="status",
                responsive=True,
            ),
            # Assignment drawer (opens on Assign action)
            assign_device_drawer(),
            # Device management drawer (opens on Manage action)
            device_manage_drawer(),
        ],
    )
