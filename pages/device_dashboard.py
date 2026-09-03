"""Device dashboard page shell — layout only, no queries.

ROLE-4B mounts the operational surface here. The three actions a technician
holds on an assigned RTL (`program_rtl`, `toggle_message_forwarding`,
`deactivate_rtl`) were only ever rendered by `device_manage_drawer()` on
`/admin/devices`, which `ROUTE_POLICY` reserves for administrators — so the
permission had no reachable path. The SAME drawer is mounted here; nothing was
duplicated and no action was widened.

`assign_device_drawer()` is deliberately NOT mounted. Assignment is what grants
technician authority, so it stays on the administrator page with the rest of
fleet administration.

The section is a container only. What goes in it is decided per persona and per
device by `callbacks.device_manage.render_device_operations`, because this
module has no session and must not acquire one — a layout that inspected a role
would be a second permission table.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.device_manage_drawer import device_manage_drawer
from components.device_operations import OPERATIONS_ID
from components.metric_chart import metric_chart
from components.readings_table import readings_table
from components.status_panels import inactive_notice
from config.metrics import ordered_metrics
from config.settings import monitoring
from services.monitoring_service import Freshness


def _context_item(
    label: str,
    value,
    value_id: str | None = None,
    modifier: str | None = None,
) -> html.Div:
    value_props = {"id": value_id} if value_id else {}
    classes = "equipment-context__item"
    if modifier:
        classes += f" equipment-context__item--{modifier}"
    return html.Div(
        className=classes,
        children=[
            html.Span(label, className="equipment-context__label"),
            html.Span(value, className="equipment-context__value", **value_props),
        ],
    )


def layout(
    plant_name: str = "",
    transformer_code: str = "",
    device_code: str = "",
    metric_key: str | None = None,
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
    plant_id: str = "",
    transformer_id: str = "",
    device_status: str = "",
) -> html.Div:
    metric_options = [{"label": m.label, "value": m.key} for m in ordered_metrics()]
    initial_metric = metric_key or (metric_options[0]["value"] if metric_options else None)
    initial_period = period or "24h"

    # Parent crumbs link only when their ids are known; a crumb with a
    # half-built href is worse than plain text.
    plant_href = f"/plants/{plant_id}" if plant_id else None
    transformer_href = (
        f"/plants/{plant_id}/{transformer_id}" if plant_id and transformer_id else None
    )

    return html.Div(
        className="page page--device-dashboard",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([
                    # Label only — the route stays /plants (spec §3.1).
                    ("Fleet", "/plants"),
                    (plant_name or "Plant", plant_href),
                    (transformer_code or "Transformer", transformer_href),
                    (device_code or "Device", None),
                ]),
                freshness=Freshness.NO_DATA,
            ),
            # Inactive equipment stays reachable by URL; it is marked rather
            # than hidden, so historical readings remain inspectable.
            inactive_notice("device") if device_status == "inactive" else None,
            html.Header(
                className="device-page-heading",
                children=[
                    html.Div("RTL device", className="device-page-heading__eyebrow"),
                    html.H1(device_code or "Device", className="device-page-heading__title"),
                    html.P(
                        "Telemetry and latest-known operational state",
                        className="device-page-heading__description",
                    ),
                ],
            ),
            html.Section(
                className="device-section device-current-state",
                children=[
                    html.Div(
                        className="device-section__heading device-section__heading--inline",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("Current state", className="device-section__eyebrow"),
                                    html.H2("Metric workspace"),
                                ]
                            ),
                            # One instruction line for this interactive region:
                            # selecting a cell promotes that metric to the
                            # chart below.
                            html.P("Select a metric to promote it to the main chart."),
                        ],
                    ),
                    # UI_SPEC 6a: administrative status remains distinct from
                    # data freshness (header badge) and monitoring condition.
                    html.Div(
                        id="equipment-context-container",
                        className="equipment-context",
                        children=[
                            _context_item("Plant", plant_name or "—"),
                            _context_item("Transformer", transformer_code or "—"),
                            _context_item("Device", device_code or "—"),
                            _context_item(
                                "Status", device_status or "—", modifier="administrative"
                            ),
                            _context_item(
                                "Last data (UTC)", "—", value_id="equipment-last-data"
                            ),
                        ],
                    ),
                    html.Div(id="metric-workspace"),
                ],
            ),
            html.Section(
                className="device-section device-telemetry",
                children=[
                    html.Div(
                        className="device-section__heading device-section__heading--inline",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("Telemetry", className="device-section__eyebrow"),
                                    html.H2("Metric history"),
                                ]
                            ),
                            html.P("Select a metric and UTC time range."),
                        ],
                    ),
                    html.Div(
                        className="metric-controls",
                        children=[
                            html.Div(
                                className="metric-control metric-control--metric",
                                children=[
                                    html.Label("Metric", htmlFor="metric-dropdown"),
                                    dcc.Dropdown(
                                        id="metric-dropdown", options=metric_options,
                                        value=initial_metric, clearable=False,
                                        searchable=False, className="metric-dropdown",
                                    ),
                                ],
                            ),
                            html.Fieldset(
                                className="metric-control metric-control--period",
                                children=[
                                    html.Legend("Time range"),
                                    dcc.RadioItems(
                                        id="period-radio",
                                        options=[
                                            {"label": "24h", "value": "24h"},
                                            {"label": "7d", "value": "7d"},
                                            {"label": "30d", "value": "30d"},
                                            {"label": "Custom", "value": "custom"},
                                        ],
                                        value=initial_period, inline=True,
                                        className="period-radio",
                                    ),
                                ],
                            ),
                            html.Div(
                                id="custom-range-container",
                                className="metric-control metric-control--custom",
                                style={
                                    "display": "block" if initial_period == "custom" else "none"
                                },
                                # DatePickerRange renders a composite, not a
                                # native input; <label for> cannot reach it,
                                # so this container (which wraps only the
                                # label and the picker) names the group.
                                role="group",
                                **{"aria-labelledby": "custom-date-range-label"},
                                children=[
                                    html.Label("Custom UTC range", id="custom-date-range-label"),
                                    dcc.DatePickerRange(
                                        id="custom-date-range", display_format="YYYY-MM-DD",
                                        start_date=custom_start, end_date=custom_end,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(id="kpi-row-container"),
                    html.Div(
                        className="device-chart-panel",
                        children=[dcc.Loading(metric_chart("metric-chart"), className="chart-loading")],
                    ),
                ],
            ),
            html.Section(
                className="device-section device-readings",
                children=[
                    html.Div(
                        className="device-section__heading device-section__heading--inline",
                        children=[
                            html.Div(
                                children=[
                                    html.Div("History", className="device-section__eyebrow"),
                                    html.H2("Recent readings"),
                                ]
                            ),
                            html.P("Newest observations first. Timestamps are UTC."),
                        ],
                    ),
                    readings_table("readings-table"),
                ],
            ),
            # ROLE-4B. Empty unless the signed-in persona may perform at
            # least one operational action on THIS device; `require_action`
            # in the confirm callbacks is what actually refuses.
            html.Div(id=OPERATIONS_ID),
            # The same drawer `/admin/devices` opens. Its ids are fixed rather
            # than pattern-matched, which is safe because the router renders
            # exactly one page: the admin page and this one are never mounted
            # together. A test pins that.
            device_manage_drawer(),
            dcc.Interval(
                id="device-refresh-interval",
                interval=monitoring.refresh_interval_seconds * 1000,
            ),
        ],
    )
