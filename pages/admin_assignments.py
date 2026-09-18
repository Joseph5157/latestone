"""Assignments page — layout only, no queries.

ADMIN-ASSIGN-1: a technician workload roster (who has how many RTLs) above
the same per-device Assign/Manage table Device Management already offers —
same column set, same shared `assign_device_drawer()`/`device_manage_drawer()`,
never a second copy of that workflow. Replaces the sidebar's former
routeless "Assignments" placeholder (`components/app_sidebar.py`) with a
real page.
"""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.assign_device_drawer import assign_device_drawer
from components.breadcrumb import breadcrumb
from components.device_manage_drawer import device_manage_drawer
from components.entity_table import entity_table

WORKLOAD_TABLE_ID = "assignment-workload-table"
TABLE_ID = "assignment-devices-table"
EMPTY_ID = "assignment-devices-empty"

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
            entity_table(
                table_id=TABLE_ID,
                columns=DEVICE_TABLE_COLUMNS,
                rows=[],
                link_column_id="device",
                state_column_id="freshness",
                administrative_state_column_id="status",
                responsive=True,
                column_widths=DEVICE_TABLE_COLUMN_WIDTHS,
            ),
            html.Div(id=EMPTY_ID),
            # Same drawers `pages/device_admin.py` mounts — not copies
            # (ADR-016's "shared surface" principle extended to Assign too).
            assign_device_drawer(),
            device_manage_drawer(),
        ],
    )
