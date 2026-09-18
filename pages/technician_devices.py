"""Technician Devices page — layout only, no queries.

A Technician's own operate-equipment surface (ADR-016): the assigned
devices `my_rtls_panel` already lists on Overview, plus a "Manage" action
column reaching the SAME `device_manage_drawer()` the Administrator's
`/admin/devices` mounts. Deliberately its own page at its own route
(`/devices`, `routes.py::parse_pathname`), not a role branch inside
`admin_devices` — assignment and registration never appear here, and never
will; that boundary is `services/authorization.py`'s `ROUTE_POLICY` and
ADR-016, not something this layout enforces on its own.
"""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.device_manage_drawer import device_manage_drawer
from components.entity_table import entity_table

TABLE_ID = "technician-devices-table"
EMPTY_ID = "technician-devices-empty"

#: Same columns and "RTL" vocabulary as `components.my_rtls.MY_RTLS_COLUMNS`
#: (the technician-facing convention — `pages.device_admin`'s own table says
#: "Device" instead, matching its administrator-facing table), plus one
#: column neither has: "Manage", reaching the shared `device_manage_drawer()`.
#: No Status, Technician or Assign column — a Technician already knows these
#: are their own devices, and assignment is never offered here (ADR-016).
TECHNICIAN_DEVICE_COLUMNS = [
    {"name": "RTL", "id": "device"},
    {"name": "Plant", "id": "plant"},
    {"name": "Transformer", "id": "transformer"},
    {"name": "Data", "id": "freshness"},
    {"name": "Manage", "id": "manage", "presentation": "markdown"},
]


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--technician-devices",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Devices", None)]),
            ),
            html.H1("Devices"),
            html.P(
                "The RTLs assigned to you.",
                className="page__subtitle",
            ),
            html.Div(id="technician-devices-error", className="listing-error"),
            html.P(id="technician-devices-summary", className="page__meta"),
            entity_table(
                table_id=TABLE_ID,
                # `callbacks/technician_devices.py` imports this SAME list
                # (unlike pages/plants_overview.py's PLANT_COLUMNS, which is
                # deliberately duplicated because that callback lives ahead
                # of its page in the dependency direction) — first paint and
                # every re-render share one definition, so they cannot drift.
                columns=TECHNICIAN_DEVICE_COLUMNS,
                rows=[],
                link_column_id="device",
                state_column_id="freshness",
                responsive=True,
                filter_action="none",
            ),
            html.Div(id=EMPTY_ID),
            # Same drawer `pages/device_admin.py` and `pages/device_dashboard.py`
            # mount — not a copy, not a technician variant (ADR-016).
            device_manage_drawer(),
        ],
    )
