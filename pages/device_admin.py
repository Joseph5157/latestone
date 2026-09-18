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
    # The former single "actions" column's 18%, split between the two
    # columns that replaced it (FIX-1C). The total still accounts for the
    # whole table: short of 100% and dash_table hands the remainder to one
    # column, which is the void these shares exist to prevent.
    "assign": "9%",
    "manage": "9%",
}


DATA_FILTER_OPTIONS = [
    {"label": "All", "value": "all"},
    {"label": "Fresh", "value": "fresh"},
    {"label": "Stale", "value": "stale"},
    {"label": "No data", "value": "no_data"},
]

#: Values are `callbacks.device_admin.last_reading_band` results.
READING_FILTER_OPTIONS = [
    {"label": "All", "value": "all"},
    {"label": "Under 1 hour", "value": "lt1h"},
    {"label": "1–24 hours", "value": "1to24h"},
    {"label": "Over 24 hours", "value": "gt24h"},
    {"label": "No readings", "value": "none"},
]


def _column_filter(label: str, dropdown: dcc.Dropdown) -> html.Div:
    """One labelled column filter (DEVICE-FILTERS-1).

    dcc.Dropdown renders a div, which a <label for> cannot reach, so the
    label names a role="group" around it, as the Status filter does.
    """
    label_id = f"{dropdown.id}-label"
    return html.Div(
        className="device-admin-filters__item",
        children=[
            html.Label(label, id=label_id, className="device-admin-filters__label"),
            html.Div(
                role="group",
                **{"aria-labelledby": label_id},
                children=[dropdown],
            ),
        ],
    )


def _column_filters() -> html.Div:
    return html.Div(
        className="device-admin-filters",
        children=[
            _column_filter("Plant", dcc.Dropdown(
                id="device-admin-plant-filter",
                options=[],
                placeholder="All plants",
                searchable=True,
                className="device-admin-toolbar__dropdown",
            )),
            _column_filter("Transformer", dcc.Dropdown(
                id="device-admin-transformer-filter",
                options=[],
                placeholder="All transformers",
                searchable=True,
                disabled=True,
                className="device-admin-toolbar__dropdown",
            )),
            _column_filter("Data", dcc.Dropdown(
                id="device-admin-data-filter",
                options=DATA_FILTER_OPTIONS,
                value="all",
                clearable=False,
                searchable=False,
                className="device-admin-toolbar__dropdown",
            )),
            _column_filter("Technician", dcc.Dropdown(
                id="device-admin-technician-filter",
                options=[{"label": "All", "value": "all"}],
                value="all",
                clearable=False,
                searchable=True,
                className="device-admin-toolbar__dropdown",
            )),
            _column_filter("Last reading", dcc.Dropdown(
                id="device-admin-reading-filter",
                options=READING_FILTER_OPTIONS,
                value="all",
                clearable=False,
                searchable=False,
                className="device-admin-toolbar__dropdown",
            )),
            html.Button(
                "Clear filters",
                id="device-admin-clear-filters",
                n_clicks=0,
                className="device-admin-filters__clear",
            ),
        ],
    )


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
                    html.Label(
                        "Search devices",
                        htmlFor="device-admin-search",
                        className="visually-hidden",
                    ),
                    dcc.Input(
                        id="device-admin-search",
                        # Controlled from first paint: Clear filters sets
                        # this value, and React warns when an input switches
                        # from uncontrolled to controlled.
                        value="",
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
            # Column filters (DEVICE-FILTERS-1). The native filter row stays
            # off: this row is the table's only filter surface besides Search
            # and Status above.
            _column_filters(),
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
                    # One column per action (FIX-1C). Must stay identical to
                    # DEVICE_ADMIN_COLUMNS in callbacks/device_admin.py: this
                    # is the first paint, that is what replaces it on the
                    # callback's first fire, and a difference reshuffles the
                    # table under the operator.
                    {"name": "Assign", "id": "assign", "presentation": "markdown"},
                    {"name": "Manage", "id": "manage", "presentation": "markdown"},
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
