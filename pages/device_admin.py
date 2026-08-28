"""Device Management page — layout only, no queries."""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.assign_device_drawer import assign_device_drawer
from components.breadcrumb import breadcrumb
from components.device_manage_drawer import device_manage_drawer
from components.entity_table import entity_table


#: Proportional shares summing to 100%, so slack becomes even breathing room
#: across the row. Leaving one column unconstrained instead handed it every
#: spare pixel: Plant rendered at 1,320px for 143px of text. Plant still takes
#: the largest share — it holds the longest values in the fleet — but bounded.
#: Slot for the "no rows" message. It stands in for the rows, so it sits
#: directly under the table rather than beside the summary line.
EMPTY_ID = "device-admin-empty"

DEVICE_ADMIN_COLUMN_WIDTHS = {
    "device": "8%",
    "plant": "20%",
    "transformer": "9%",
    "status": "9%",
    "freshness": "11%",
    "last_reading": "11%",
    "technician": "14%",
    "actions": "18%",
}


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
                                id="device-admin-status-filter-label",
                                className="device-admin-toolbar__label",
                            ),
                            # dcc.Dropdown renders a div; <label for> cannot
                            # reach it, so the label names a group instead.
                            html.Div(
                                role="group",
                                **{"aria-labelledby": "device-admin-status-filter-label"},
                                children=[
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
                    {"name": "Last reading", "id": "last_reading"},
                    {"name": "Technician", "id": "technician"},
                    {"name": "Actions", "id": "actions", "presentation": "markdown"},
                ],
                rows=[],
                link_column_id="device",
                state_column_id="freshness",
                administrative_state_column_id="status",
                responsive=True,
                # The toolbar above is this page's filter surface; the native
                # row underneath the header would be a second one.
                filter_action="none",
                column_widths=DEVICE_ADMIN_COLUMN_WIDTHS,
            ),
            html.Div(id=EMPTY_ID),
            # Assignment drawer (opens on Assign action)
            assign_device_drawer(),
            # Device management drawer (opens on Manage action)
            device_manage_drawer(),
        ],
    )
