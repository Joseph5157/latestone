"""Device dashboard callback — single callback owns the whole dashboard body."""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from dash import Input, Output, State, no_update

from components.freshness_badge import freshness_badge
from components.kpi_card import kpi_row
from components.metric_chart import build_metric_figure
from components.metric_snapshot_strip import metric_snapshot_strip
from components.readings_table import build_table_rows
from components.status_panels import error_panel
from routes import device_href
from services import monitoring_service as svc
from services.monitoring_service import Period

logger = logging.getLogger(__name__)


def _parse_picker_date(value: str | None, *, is_end: bool = False) -> datetime | None:
    """Convert a `dcc.DatePickerRange` value into a query bound.

    The picker yields a calendar date ("2026-08-06"), not an instant. Parsing
    that literally gives midnight, which would exclude the whole of the chosen
    end day — selecting Aug 3 to Aug 6 silently dropped 47 of 192 readings and
    skewed every period KPI. An end date therefore means the *end* of that day.
    """
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if is_end and parsed.time() == time.min:
        parsed = parsed + timedelta(days=1) - timedelta(microseconds=1)
    return parsed


def register(app) -> None:
    """Register device dashboard callbacks on the Dash app."""

    @app.callback(
        Output("snapshot-strip", "children"),
        Output("kpi-row-container", "children"),
        Output("metric-chart", "figure"),
        Output("readings-table", "data"),
        Output("readings-table", "columns"),
        Output("header-freshness", "children"),
        Output("equipment-last-data", "children"),
        Input("page-context", "data"),
        Input("metric-dropdown", "value"),
        Input("period-radio", "value"),
        Input("custom-date-range", "start_date"),
        Input("custom-date-range", "end_date"),
        Input("device-refresh-interval", "n_intervals"),
        prevent_initial_call=True,
    )
    def refresh_device_dashboard(context, metric_key, period_value, custom_start, custom_end, _n):
        if not context or context.get("route") != "device":
            return [no_update] * 7

        device_id = context.get("device_id")
        if not device_id:
            return [no_update] * 7

        try:
            # 1. Snapshot strip — one batched query
            snapshots = svc.get_device_snapshot(device_id)

            # 2. Resolve period
            try:
                period = Period(period_value)
            except ValueError:
                period = Period.LAST_24H

            # 3. Parse custom dates
            start = None
            end = None
            if period is Period.CUSTOM:
                start = _parse_picker_date(custom_start)
                end = _parse_picker_date(custom_end, is_end=True)

            # 4. Get metric view
            view = svc.get_metric_view(device_id, metric_key, period, start, end)

            if view is None:
                return [no_update] * 7

            # 5. Build outputs
            strip = metric_snapshot_strip(
                snapshots, metric_key, device_id,
                period=period_value, custom_start=custom_start, custom_end=custom_end,
            )
            kpis = kpi_row(view)
            fig = build_metric_figure(view.metric, view.series)

            # Readings table (newest first)
            sorted_series = sorted(view.series, key=lambda r: r.timestamp, reverse=True)
            table_data = build_table_rows(view.metric, sorted_series)
            table_columns = [
                {"name": "Timestamp", "id": "timestamp"},
                {"name": view.metric.label, "id": "value"},
            ]

            freshness = freshness_badge(view.freshness)
            last_data = (
                view.last_updated.strftime("%Y-%m-%d %H:%M") if view.last_updated else "\u2014"
            )

            return strip, kpis, fig, table_data, table_columns, freshness, last_data

        except Exception:
            # Logged in full so programming errors are diagnosable; the UI panel
            # stays generic and never exposes internals.
            logger.exception(
                "Device dashboard refresh failed for device_id=%r metric=%r period=%r",
                device_id, metric_key, period_value,
            )
            err = error_panel()
            return err, err, {}, [], [], err, "\u2014"

    # Sync metric/period into URL for shareability

    @app.callback(
        Output("url", "search"),
        Input("metric-dropdown", "value"),
        Input("period-radio", "value"),
        Input("custom-date-range", "start_date"),
        Input("custom-date-range", "end_date"),
        State("page-context", "data"),
        prevent_initial_call=True,
    )
    def sync_query_string(metric_key, period_value, custom_start, custom_end, context):
        if not context or context.get("route") != "device":
            return no_update
        # Custom bounds are carried in the URL too; without them a shared
        # "period=custom" link opens on an empty dashboard.
        href = device_href(
            context.get("device_id", ""),
            metric_key=metric_key,
            period=period_value,
            start=custom_start,
            end=custom_end,
        )
        _, _, query = href.partition("?")
        return f"?{query}" if query else ""

    # Note: dropdown/radio are initialized from page-context by device_dashboard.layout()
    # on each route render, so no separate url.search -> dropdown callback is needed
    # (that would create a cycle with sync_query_string above).

    # Toggle custom range picker visibility

    @app.callback(
        Output("custom-range-container", "style"),
        Input("period-radio", "value"),
    )
    def toggle_custom_range(period_value):
        if period_value == "custom":
            return {"display": "block"}
        return {"display": "none"}
