"""Device dashboard callback — single callback owns the whole dashboard body."""
from __future__ import annotations

from datetime import datetime

from dash import Input, Output, State, callback, no_update, prevent_initial_call
import dash_html_components as html

from components.freshness_badge import freshness_badge
from components.kpi_card import kpi_row
from components.metric_chart import build_metric_figure
from components.metric_snapshot_strip import metric_snapshot_strip
from components.readings_table import build_table_rows
from components.status_panels import error_panel
from config.metrics import METRIC_KEYS
from services import monitoring_service as svc
from services.monitoring_service import Period


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
                if custom_start:
                    start = datetime.fromisoformat(custom_start)
                if custom_end:
                    end = datetime.fromisoformat(custom_end)

            # 4. Get metric view
            view = svc.get_metric_view(device_id, metric_key, period, start, end)

            if view is None:
                return [no_update] * 7

            # 5. Build outputs
            strip = metric_snapshot_strip(snapshots, metric_key, device_id)
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
            err = error_panel()
            return err, err, {}, [], [], err, "\u2014"

    # Sync metric/period into URL for shareability

    @app.callback(
        Output("url", "search"),
        Input("metric-dropdown", "value"),
        Input("period-radio", "value"),
        State("page-context", "data"),
        prevent_initial_call=True,
    )
    def sync_query_string(metric_key, period_value, context):
        if not context or context.get("route") != "device":
            return no_update
        return f"?metric={metric_key}&period={period_value}"

    # Read URL search params to set dropdown values

    @app.callback(
        Output("metric-dropdown", "value"),
        Output("period-radio", "value"),
        Input("url", "search"),
        State("metric-dropdown", "value"),
        prevent_initial_call=True,
    )
    def sync_from_url(search, current_metric):
        from urllib.parse import parse_qs
        from config.metrics import DEFAULT_METRIC_KEY

        if not search:
            return no_update, no_update

        params = parse_qs(search.lstrip("?"))
        metric = params.get("metric", [DEFAULT_METRIC_KEY])[0]
        period = params.get("period", ["24h"])[0]

        if metric not in METRIC_KEYS:
            metric = DEFAULT_METRIC_KEY
        if period not in ("24h", "7d", "30d", "custom"):
            period = "24h"

        # Avoid feedback loop
        if metric == current_metric:
            return no_update, period

        return metric, period

    # Toggle custom range picker visibility

    @app.callback(
        Output("custom-range-container", "style"),
        Input("period-radio", "value"),
    )
    def toggle_custom_range(period_value):
        if period_value == "custom":
            return {"display": "block"}
        return {"display": "none"}
