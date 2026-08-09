"""Device dashboard page shell — layout only, no queries."""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.metric_chart import metric_chart
from components.readings_table import readings_table
from components.status_panels import inactive_notice
from config.metrics import ordered_metrics
from config.settings import monitoring
from services.monitoring_service import Freshness


def _context_item(label: str, value, value_id: str | None = None) -> html.Div:
    value_props = {"id": value_id} if value_id else {}
    return html.Div(
        className="equipment-context__item",
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
                    ("Plants", "/plants"),
                    (plant_name or "Plant", plant_href),
                    (transformer_code or "Transformer", transformer_href),
                    (device_code or "Device", None),
                ]),
                freshness=Freshness.NO_DATA,
            ),
            # Inactive equipment stays reachable by URL; it is marked rather
            # than hidden, so historical readings remain inspectable.
            inactive_notice("device") if device_status == "inactive" else None,
            # UI_SPEC 6a: Plant | Transformer | Device | Status. `Status` is the
            # administrative state from DevicePath — deliberately not merged
            # with data freshness (header badge) or monitoring condition.
            html.Div(
                id="equipment-context-container",
                className="equipment-context",
                children=[
                    _context_item("Plant", plant_name or "—"),
                    _context_item("Transformer", transformer_code or "—"),
                    _context_item("Device", device_code or "—"),
                    _context_item("Status", device_status or "—"),
                    _context_item("Last data (UTC)", "—", value_id="equipment-last-data"),
                ],
            ),
            html.Div(id="snapshot-strip"),
            html.Div(
                className="metric-controls",
                children=[
                    dcc.Dropdown(
                        id="metric-dropdown",
                        options=metric_options,
                        value=initial_metric,
                        clearable=False,
                        searchable=False,
                        className="metric-dropdown",
                    ),
                    dcc.RadioItems(
                        id="period-radio",
                        options=[
                            {"label": " 24h", "value": "24h"},
                            {"label": " 7d", "value": "7d"},
                            {"label": " 30d", "value": "30d"},
                            {"label": " Custom", "value": "custom"},
                        ],
                        value=initial_period,
                        inline=True,
                        className="period-radio",
                    ),
                    html.Div(
                        id="custom-range-container",
                        style={"display": "block" if initial_period == "custom" else "none"},
                        children=[
                            dcc.DatePickerRange(
                                id="custom-date-range",
                                display_format="YYYY-MM-DD",
                                start_date=custom_start,
                                end_date=custom_end,
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(id="kpi-row-container"),
            dcc.Loading(
                metric_chart("metric-chart"),
                className="chart-loading",
            ),
            # Below the primary chart, so eight more figures cannot push it
            # past the §6.8 budget.
            html.H2("Quick Trends", className="section-heading"),
            html.Div(id="trend-grid"),
            readings_table("readings-table"),
            dcc.Interval(
                id="device-refresh-interval",
                interval=monitoring.refresh_interval_seconds * 1000,
            ),
        ],
    )
