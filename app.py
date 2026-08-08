"""
Application entry point.

Callbacks stay thin: gather inputs -> call service -> format outputs.
No SQL, no raw string parsing, and no KPI math happens in this file.
"""
from __future__ import annotations

from datetime import datetime

import dash
from dash import Input, Output, State, dcc, html, no_update

from components.kpi_card import kpi_row
from components.readings_table import build_table_rows
from components.temperature_chart import build_temperature_figure
from config.settings import dash_settings, demo_device
from db.engine import check_connection
from pages.dashboard import dashboard_layout
from pages.login import login_layout
from pages.plants_dashboard import plants_dashboard_layout
from services.auth_service import verify_credentials
from services.temperature_service import Period, get_kpis, get_trend_series
from services import monitoring_service

app = dash.Dash(__name__, suppress_callback_exceptions=True, title="Power Plant Monitoring")
server = app.server

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        # Memory storage only: session intentionally resets on browser refresh
        # for this demo (see project decision log).
        dcc.Store(id="auth-store", storage_type="memory", data={"authenticated": False}),
        html.Div(id="page-content"),
    ]
)


# ---------------------------------------------------------------------------
# Routing / auth gate
# ---------------------------------------------------------------------------
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    State("auth-store", "data"),
)
def render_page(pathname, auth_data):
    if auth_data and auth_data.get("authenticated"):
        if pathname == "/plants":
            return plants_dashboard_layout()
        return dashboard_layout()
    return login_layout()


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------
@app.callback(
    Output("login-password", "type"),
    Output("toggle-password-btn", "children"),
    Input("toggle-password-btn", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_password_visibility(n_clicks):
    if n_clicks % 2 == 1:
        return "text", "Hide"
    return "password", "Show"


@app.callback(
    Output("auth-store", "data"),
    Output("login-error", "children"),
    Output("url", "pathname"),
    Input("login-button", "n_clicks"),
    Input("login-password", "n_submit"),
    State("login-username", "value"),
    State("login-password", "value"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def handle_login(_n_clicks, _n_submit, username, password, requested_path):
    if verify_credentials(username or "", password or ""):
        destination = requested_path if requested_path == "/plants" else "/dashboard"
        return {"authenticated": True}, "", destination
    return {"authenticated": False}, "Invalid username or password.", no_update


@app.callback(
    Output("auth-store", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("logout-button", "n_clicks"),
    prevent_initial_call=True,
)
def handle_logout(n_clicks):
    if n_clicks:
        return {"authenticated": False}, "/"
    return no_update, no_update


# ---------------------------------------------------------------------------
# Dashboard: period filter -> KPIs + chart + table (single thin callback)
# ---------------------------------------------------------------------------
@app.callback(
    Output("custom-range-container", "style"),
    Input("period-radio", "value"),
)
def toggle_custom_range(period_value):
    if period_value == "custom":
        return {"display": "block"}
    return {"display": "none"}


@app.callback(
    Output("kpi-row-container", "children"),
    Output("temperature-chart", "figure"),
    Output("readings-table", "data"),
    Output("status-badge", "children"),
    Output("status-badge", "className"),
    Output("last-data-timestamp", "children"),
    Output("connection-state", "children"),
    Input("period-radio", "value"),
    Input("custom-date-range", "start_date"),
    Input("custom-date-range", "end_date"),
    Input("refresh-interval", "n_intervals"),
)
def update_dashboard(period_value, custom_start, custom_end, _n_intervals):
    if not check_connection():
        empty_fig = build_temperature_figure([])
        return (
            kpi_row("—", "—", "—", "—"),
            empty_fig,
            [],
            "No data",
            "status-badge status-badge--no-data",
            "Last data: —",
            "Database unavailable",
        )

    period = Period(period_value) if period_value in {p.value for p in Period} else Period.LAST_24H

    start_dt = datetime.fromisoformat(custom_start) if (period == Period.CUSTOM and custom_start) else None
    end_dt = datetime.fromisoformat(custom_end) if (period == Period.CUSTOM and custom_end) else None

    kpis = get_kpis(period, custom_start=start_dt, custom_end=end_dt)
    series = get_trend_series(period, custom_start=start_dt, custom_end=end_dt)
    fig = build_temperature_figure(series)

    # Recent readings table follows the same period filter (per project decision).
    period_readings = sorted(series, key=lambda r: r.timestamp, reverse=True)
    table_rows = build_table_rows(period_readings)

    unit = demo_device.unit
    kpi_children = kpi_row(
        current=f"{kpis.current:.1f} {unit}" if kpis.current is not None else "—",
        minimum=f"{kpis.minimum:.1f} {unit}" if kpis.minimum is not None else "—",
        maximum=f"{kpis.maximum:.1f} {unit}" if kpis.maximum is not None else "—",
        average=f"{kpis.average:.1f} {unit}" if kpis.average is not None else "—",
    )

    status_class_map = {
        "Normal": "status-badge status-badge--normal",
        "Warning": "status-badge status-badge--warning",
        "No data": "status-badge status-badge--no-data",
    }
    status_text = kpis.status.value
    status_class = status_class_map.get(status_text, "status-badge status-badge--no-data")

    last_updated_text = (
        f"Last data: {kpis.last_updated.strftime('%Y-%m-%d %H:%M')}"
        if kpis.last_updated
        else "Last data: —"
    )

    return (
        kpi_children,
        fig,
        table_rows,
        status_text,
        status_class,
        last_updated_text,
        "Connected",
    )


# ---------------------------------------------------------------------------
# Multi-plant demo dashboard: location + period filter -> KPIs + chart + table
# ---------------------------------------------------------------------------
@app.callback(
    Output("plants-custom-range-container", "style"),
    Input("plants-period-radio", "value"),
)
def toggle_plants_custom_range(period_value):
    if period_value == "custom":
        return {"display": "block"}
    return {"display": "none"}


@app.callback(
    Output("plants-kpi-row-container", "children"),
    Output("plants-temperature-chart", "figure"),
    Output("plants-readings-table", "data"),
    Output("plants-status-badge", "children"),
    Output("plants-status-badge", "className"),
    Output("plants-last-data-timestamp", "children"),
    Output("plants-connection-state", "children"),
    Output("plants-device-meta", "children"),
    Input("plant-dropdown", "value"),
    Input("plants-period-radio", "value"),
    Input("plants-custom-date-range", "start_date"),
    Input("plants-custom-date-range", "end_date"),
    Input("plants-refresh-interval", "n_intervals"),
)
def update_plants_dashboard(plant_id, period_value, custom_start, custom_end, _n_intervals):
    if not plant_id or not check_connection():
        empty_fig = build_temperature_figure([])
        return (
            kpi_row("—", "—", "—", "—"),
            empty_fig,
            [],
            "No data",
            "status-badge status-badge--no-data",
            "Last data: —",
            "Database unavailable",
            "Transformer: — • Device: —",
        )

    period = Period(period_value) if period_value in {p.value for p in Period} else Period.LAST_24H

    start_dt = datetime.fromisoformat(custom_start) if (period == Period.CUSTOM and custom_start) else None
    end_dt = datetime.fromisoformat(custom_end) if (period == Period.CUSTOM and custom_end) else None

    plant = next((p for p in monitoring_service.list_plants() if p.plant_id == plant_id), None)
    unit = "°C"

    kpis = monitoring_service.get_kpis(plant_id, period, custom_start=start_dt, custom_end=end_dt)
    series = monitoring_service.get_trend_series(plant_id, period, custom_start=start_dt, custom_end=end_dt)
    fig = build_temperature_figure(series)

    period_readings = sorted(series, key=lambda r: r.timestamp, reverse=True)
    table_rows = build_table_rows(period_readings)

    kpi_children = kpi_row(
        current=f"{kpis.current:.1f} {unit}" if kpis.current is not None else "—",
        minimum=f"{kpis.minimum:.1f} {unit}" if kpis.minimum is not None else "—",
        maximum=f"{kpis.maximum:.1f} {unit}" if kpis.maximum is not None else "—",
        average=f"{kpis.average:.1f} {unit}" if kpis.average is not None else "—",
    )

    status_class_map = {
        "Normal": "status-badge status-badge--normal",
        "Warning": "status-badge status-badge--warning",
        "No data": "status-badge status-badge--no-data",
    }
    status_text = kpis.status.value
    status_class = status_class_map.get(status_text, "status-badge status-badge--no-data")

    last_updated_text = (
        f"Last data: {kpis.last_updated.strftime('%Y-%m-%d %H:%M')}"
        if kpis.last_updated
        else "Last data: —"
    )

    device_meta_text = (
        f"Transformer: {plant.transformer.upper()} • Device: {plant.device}"
        if plant
        else "Transformer: — • Device: —"
    )

    return (
        kpi_children,
        fig,
        table_rows,
        status_text,
        status_class,
        last_updated_text,
        "Connected",
        device_meta_text,
    )


if __name__ == "__main__":
    app.run(
        debug=dash_settings.debug,
        host=dash_settings.host,
        port=dash_settings.port,
    )
