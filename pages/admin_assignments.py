"""Assignments page — layout only, no queries.

ADMIN-ASSIGN-1: a technician workload roster (who has how many RTLs) above
the same per-device Assign/Manage table Device Management already offers —
same column set, same shared `assign_device_drawer()`/`device_manage_drawer()`,
never a second copy of that workflow. Replaces the sidebar's former
routeless "Assignments" placeholder (`components/app_sidebar.py`) with a
real page.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.assign_device_drawer import assign_device_drawer
from components.breadcrumb import breadcrumb
from components.column_filter import DATA_FILTER_OPTIONS, column_filter
from components.device_manage_drawer import device_manage_drawer
from components.entity_table import entity_table

WORKLOAD_TABLE_ID = "assignment-workload-table"
TABLE_ID = "assignment-devices-table"
EMPTY_ID = "assignment-devices-empty"

#: ASSIGN-TOOLBAR-1: the RTL table's filter surface, replacing dash_table's
#: native filter row (first-column-only placeholder, case-sensitive match,
#: filter cells on the Assign/Manage action columns). Same controls and same
#: `filter_device_rows` as Device Management, minus the filters that page
#: needs for fleet housekeeping (Status, Transformer, Last reading).
SEARCH_ID = "assignment-search"
PLANT_FILTER_ID = "assignment-plant-filter"
DATA_FILTER_ID = "assignment-data-filter"
TECHNICIAN_FILTER_ID = "assignment-technician-filter"
CLEAR_FILTERS_ID = "assignment-clear-filters"
DEVICE_SUMMARY_ID = "assignment-devices-summary"

#: Technician | count of assigned RTLs, sorted most-loaded first by the
#: callback — this is the page's one new piece of information Device
#: Management does not already show (a roster, not a per-device fact).
WORKLOAD_COLUMNS = [
    {"name": "Technician", "id": "technician"},
    {"name": "Assigned RTLs", "id": "count", "type": "numeric"},
]

#: Same shape as `callbacks.admin_assignments.DEVICE_TABLE_COLUMNS`
#: (itself `callbacks.device_admin.DEVICE_ADMIN_COLUMNS`) — deliberately
#: duplicated by value rather than imported, matching
#: `pages/device_admin.py`'s own convention (a page composing components
#: must not depend on a callbacks module; the callback replaces this on
#: first fire, and a test asserts the two stay identical).
DEVICE_TABLE_COLUMNS = [
    {"name": "Device", "id": "device"},
    {"name": "Plant", "id": "plant"},
    {"name": "Transformer", "id": "transformer"},
    {"name": "Status", "id": "status"},
    {"name": "Data", "id": "freshness"},
    {"name": "Last reading", "id": "last_reading"},
    {"name": "Technician", "id": "technician"},
    {"name": "Assign", "id": "assign", "presentation": "markdown"},
    {"name": "Manage", "id": "manage", "presentation": "markdown"},
]

#: Same proportional shares as `pages.device_admin.DEVICE_ADMIN_COLUMN_WIDTHS`
#: — the same nine columns, so the same widths apply.
DEVICE_TABLE_COLUMN_WIDTHS = {
    "device": "8%",
    "plant": "20%",
    "transformer": "9%",
    "status": "9%",
    "freshness": "11%",
    "last_reading": "11%",
    "technician": "14%",
    "assign": "9%",
    "manage": "9%",
}


def _device_filters() -> html.Div:
    return html.Div(
        className="device-admin-filters",
        children=[
            column_filter("Plant", dcc.Dropdown(
                id=PLANT_FILTER_ID,
                options=[],
                placeholder="All plants",
                searchable=True,
                className="device-admin-toolbar__dropdown",
            )),
            column_filter("Data", dcc.Dropdown(
                id=DATA_FILTER_ID,
                options=DATA_FILTER_OPTIONS,
                value="all",
                clearable=False,
                searchable=False,
                className="device-admin-toolbar__dropdown",
            )),
            column_filter("Technician", dcc.Dropdown(
                id=TECHNICIAN_FILTER_ID,
                options=[{"label": "All", "value": "all"}],
                value="all",
                clearable=False,
                searchable=True,
                className="device-admin-toolbar__dropdown",
            )),
            html.Button(
                "Clear filters",
                id=CLEAR_FILTERS_ID,
                n_clicks=0,
                className="device-admin-filters__clear",
            ),
        ],
    )


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--admin-assignments",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Assignments", None)]),
            ),
            html.H1("Assignments"),
            html.P(
                "Technician workload and RTL assignment.",
                className="page__subtitle",
            ),
            html.Div(id="admin-assignments-error", className="listing-error"),
            # Filled by the callback with admin_summary_cards() — the SAME
            # three-card component the Fleet Overview's Administration
            # section renders, from the SAME AdminOverviewSummary shape.
            html.Div(id="admin-assignments-summary"),
            html.H2("Technician Workload", className="fleet-inventory__title"),
            entity_table(
                table_id=WORKLOAD_TABLE_ID,
                columns=WORKLOAD_COLUMNS,
                rows=[],
                filter_action="none",
            ),
            html.H2("RTL Assignments", className="fleet-inventory__title"),
            html.Div(
                className="device-admin-toolbar",
                children=[
                    html.Label(
                        "Search RTLs",
                        htmlFor=SEARCH_ID,
                        className="visually-hidden",
                    ),
                    dcc.Input(
                        id=SEARCH_ID,
                        # Controlled from first paint: Clear filters sets it.
                        value="",
                        type="text",
                        placeholder="Search device, plant, transformer, technician...",
                        className="device-admin-toolbar__search",
                        debounce=True,
                    ),
                ],
            ),
            _device_filters(),
            html.P(id=DEVICE_SUMMARY_ID, className="page__meta"),
            entity_table(
                table_id=TABLE_ID,
                columns=DEVICE_TABLE_COLUMNS,
                rows=[],
                link_column_id="device",
                state_column_id="freshness",
                administrative_state_column_id="status",
                responsive=True,
                # The toolbar above is this table's filter surface.
                filter_action="none",
                # TABLE-SORT-TEXT-1: same reason as device_admin.py — Data
                # and Last reading render text that is not its own sort
                # order; `callbacks/admin_assignments.py` sorts `data` itself.
                sort_action="custom",
                column_widths=DEVICE_TABLE_COLUMN_WIDTHS,
            ),
            html.Div(id=EMPTY_ID),
            # Same drawers `pages/device_admin.py` mounts — not copies
            # (ADR-016's "shared surface" principle extended to Assign too).
            assign_device_drawer(),
            device_manage_drawer(),
        ],
    )
