"""Report Center callbacks — form handling, asset scope cascade, prototype generation.

All operations are frontend-only. Report generation creates a clearly labeled
prototype result; no files are produced or delivered. Recent reports table
uses mock data explicitly marked as demo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dash import Input, Output, State, no_update, html

from services import hierarchy_service

logger = logging.getLogger(__name__)

# In-memory mock recent reports (prototype only)
_mock_recent_reports: list[dict] = []


def _seed_mock_reports() -> None:
    """Seed demo reports if empty."""
    if not _mock_recent_reports:
        now = datetime.now(timezone.utc)
        _mock_recent_reports.extend([
            {
                "id": "demo-1",
                "report": "Daily Temperature Summary",
                "scope": "Fleet",
                "requested": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M UTC"),
                "status": "Completed",
                "action": "[View](#)",
                "_state": "fresh",
                "_severity": 0,
            },
            {
                "id": "demo-2",
                "report": "Transformer Load Report",
                "scope": "Plant: Itaipu",
                "requested": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M UTC"),
                "status": "Completed",
                "action": "[View](#)",
                "_state": "fresh",
                "_severity": 0,
            },
            {
                "id": "demo-3",
                "report": "Energy Consumption Export",
                "scope": "Device: plant-01-t1-d1",
                "requested": (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M UTC"),
                "status": "Completed",
                "action": "[View](#)",
                "_state": "fresh",
                "_severity": 0,
            },
        ])


def _plant_options() -> list[dict]:
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants()
    ]


def _transformer_options(plant_id: str) -> list[dict]:
    if not plant_id:
        return []
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in hierarchy_service.list_transformers(plant_id)
    ]


def _device_options(transformer_id: str) -> list[dict]:
    if not transformer_id:
        return []
    return [
        {"label": d.device_code, "value": d.device_id}
        for d in hierarchy_service.list_devices(transformer_id)
    ]


def _scope_label(scope: str, plant_id: str = "", transformer_id: str = "", device_id: str = "") -> str:
    """Build human-readable scope label."""
    if scope == "fleet":
        return "Entire Fleet"
    if scope == "plant" and plant_id:
        plant = hierarchy_service.get_plant_or_none(plant_id)
        return f"Plant: {plant.name if plant else plant_id}"
    if scope == "transformer" and transformer_id:
        transformer = next(
            (t for t in hierarchy_service.list_transformers(plant_id) if t.transformer_id == transformer_id),
            None
        )
        plant = hierarchy_service.get_plant_or_none(plant_id) if plant_id else None
        return f"Transformer: {transformer.transformer_code if transformer else transformer_id} ({plant.name if plant else plant_id})"
    if scope == "device" and device_id:
        device = hierarchy_service.get_device_context(device_id)
        return f"Device: {device.device_code if device else device_id}"
    return scope.capitalize()


def register(app) -> None:
    """Register report center callbacks on the Dash app."""

    # Seed mock reports
    _seed_mock_reports()

    # ---- Asset scope cascade ----

    @app.callback(
        Output("report-plant-container", "style"),
        Output("report-transformer-container", "style"),
        Output("report-device-container", "style"),
        Input("report-asset-scope", "value"),
        prevent_initial_call=True,
    )
    def toggle_scope_fields(scope):
        """Show/hide asset scope dropdowns based on selection."""
        if scope == "fleet":
            return {"display": "none"}, {"display": "none"}, {"display": "none"}
        if scope == "plant":
            return {"display": "block"}, {"display": "none"}, {"display": "none"}
        if scope == "transformer":
            return {"display": "block"}, {"display": "block"}, {"display": "none"}
        if scope == "device":
            return {"display": "block"}, {"display": "block"}, {"display": "block"}
        return {"display": "none"}, {"display": "none"}, {"display": "none"}

    @app.callback(
        Output("report-plant", "options"),
        Input("report-plant", "id"),
    )
    def populate_report_plants(_):
        try:
            return _plant_options()
        except Exception:
            logger.exception("Failed to populate report plant options")
            return []

    @app.callback(
        Output("report-transformer", "options"),
        Output("report-transformer", "disabled"),
        Input("report-plant", "value"),
        prevent_initial_call=True,
    )
    def populate_report_transformers(plant_id):
        try:
            options = _transformer_options(plant_id)
            return options, not options
        except Exception:
            logger.exception("Failed to populate report transformers for %r", plant_id)
            return [], True

    @app.callback(
        Output("report-device", "options"),
        Output("report-device", "disabled"),
        Input("report-transformer", "value"),
        prevent_initial_call=True,
    )
    def populate_report_devices(transformer_id):
        try:
            options = _device_options(transformer_id)
            return options, not options
        except Exception:
            logger.exception("Failed to populate report devices for %r", transformer_id)
            return [], True

    # ---- Custom date range visibility ----

    @app.callback(
        Output("report-custom-range-container", "style"),
        Input("report-period", "value"),
        prevent_initial_call=True,
    )
    def toggle_custom_range(period):
        if period == "custom":
            return {"display": "block", "marginTop": "8px"}
        return {"display": "none"}

    # ---- Recent reports table ----

    @app.callback(
        Output("recent-reports-table", "data"),
        Output("recent-reports-table", "columns"),
        Output("recent-reports-error", "children"),
        Input("page-context", "data"),
        prevent_initial_call=True,
    )
    def populate_recent_reports(context):
        if not context or context.get("route") != "reports":
            return no_update, no_update, no_update

        try:
            _seed_mock_reports()
            rows = _mock_recent_reports.copy()
            columns = [
                {"name": "Report", "id": "report"},
                {"name": "Scope", "id": "scope"},
                {"name": "Requested", "id": "requested"},
                {"name": "Status", "id": "status"},
                {"name": "Action", "id": "action", "presentation": "markdown"},
            ]
            return rows, columns, None
        except Exception:
            logger.exception("Failed to load recent reports")
            return [], [], "Error loading recent reports."

    # ---- Prototype generation ----

    @app.callback(
        Output("report-generation-result", "style"),
        Output("report-generation-result", "children"),
        Input("report-generate-btn", "n_clicks"),
        State("report-type", "value"),
        State("report-asset-scope", "value"),
        State("report-plant", "value"),
        State("report-transformer", "value"),
        State("report-device", "value"),
        State("report-period", "value"),
        State("report-custom-date-range", "start_date"),
        State("report-custom-date-range", "end_date"),
        prevent_initial_call=True,
    )
    def generate_report(n_clicks, report_type, asset_scope, plant_id, transformer_id, device_id, period, custom_start, custom_end):
        if not n_clicks:
            return no_update, no_update

        # Build scope description
        scope_desc = _scope_label(asset_scope, plant_id, transformer_id, device_id)

        # Build period description
        if period == "custom" and custom_start and custom_end:
            period_desc = f"Custom: {custom_start} to {custom_end} UTC"
        else:
            period_labels = {"24h": "Last 24 hours", "7d": "Last 7 days", "30d": "Last 30 days"}
            period_desc = period_labels.get(period, period)

        # Prototype result
        result = html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.H4("Report Generated (Prototype)"),
                html.P(f"No actual report was produced or delivered."),
                html.Div(
                    className="report-prototype-detail",
                    children=[
                        html.P(f"<strong>Report Type:</strong> {report_type or 'TBD'}"),
                        html.P(f"<strong>Asset Scope:</strong> {scope_desc}"),
                        html.P(f"<strong>Date Range:</strong> {period_desc}"),
                    ],
                ),
            ],
        )

        return {"display": "block"}, result