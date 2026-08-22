"""Report Center callbacks — form handling, preview, prototype generation.

All operations are frontend-only. Report types are confirmed by the RTL
Functional Specification (§11). Report generation creates a clearly labeled
prototype result; no files are produced or delivered. Recent reports table
uses mock data explicitly marked as demo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dash import Input, Output, State, no_update, html

from config.reports import get_report, REPORTS
from services import hierarchy_service
from services.device_scope import DeviceScope, scope_from_session

logger = logging.getLogger(__name__)

# In-memory mock recent reports (prototype only)
_mock_recent_reports: list[dict] = []


def _seed_mock_reports() -> None:
    """Seed demo reports using confirmed report names only."""
    if not _mock_recent_reports:
        now = datetime.now(timezone.utc)
        _mock_recent_reports.extend([
            {
                "id": "demo-1",
                "report": "RTL Alarms (30 Days)",
                "scope": "Fleet",
                "requested": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M UTC"),
                "status": "Demo",
                "_state": "fresh",
                "_severity": 0,
            },
            {
                "id": "demo-2",
                "report": "Installed RTLs",
                "scope": "Plant: Itaipu",
                "requested": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M UTC"),
                "status": "Demo",
                "_state": "fresh",
                "_severity": 0,
            },
            {
                "id": "demo-3",
                "report": "Maximum Temperature",
                "scope": "Fleet",
                "requested": (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M UTC"),
                "status": "Demo",
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


def _device_options(transformer_id: str, scope: DeviceScope) -> list[dict]:
    if not transformer_id:
        return []
    return [
        {"label": d.device_code, "value": d.device_id}
        for d in hierarchy_service.list_devices(transformer_id, scope=scope)
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


def _build_preview(report_key: str) -> html.Div:
    """Build the Report Layout Preview for a selected report."""
    report = get_report(report_key)
    if not report:
        return html.Div(style={"display": "none"})

    column_items = [html.Li(col) for col in report.columns]

    return html.Div(
        className="report-preview__content",
        children=[
            html.H4("Report Layout Preview"),
            html.P(report.label, className="report-preview__title"),
            html.P(report.description, className="report-preview__desc"),
            html.Ul(column_items, className="report-preview__columns"),
        ],
    )


def _build_definition_status(report_key: str) -> html.Div:
    """Build data availability honesty notice for a selected report."""
    report = get_report(report_key)
    if not report:
        return html.Div(style={"display": "none"})

    return html.Div(
        className="status-panel status-panel--inactive",
        children=[
            html.P(
                html.Strong("Report definition confirmed. "),
            ),
            html.P(
                "Production data mapping incomplete. "
                "The columns above reflect the client-confirmed report layout. "
                "Actual data availability depends on the backend report service."
            ),
        ],
    )


def register(app) -> None:
    """Register report center callbacks on the Dash app."""

    # Seed mock reports
    _seed_mock_reports()

    # ---- Report type → preview + status + date-range behavior ----

    @app.callback(
        Output("report-preview", "style"),
        Output("report-preview", "children"),
        Output("report-definition-status", "style"),
        Output("report-definition-status", "children"),
        Output("report-generate-btn", "disabled"),
        Output("report-period-container", "style"),
        Output("report-period", "value"),
        Output("report-period", "options"),
        Output("report-period-notice", "style"),
        Output("report-period-notice", "children"),
        Input("report-type", "value"),
        prevent_initial_call=True,
    )
    def on_report_type_change(report_key):
        if not report_key:
            return (
                {"display": "none"}, no_update,
                {"display": "none"}, no_update,
                True,
                {"display": "block"}, no_update, no_update,
                {"display": "none"}, no_update,
            )

        report = get_report(report_key)
        if not report:
            return (
                {"display": "none"}, no_update,
                {"display": "none"}, no_update,
                True,
                {"display": "block"}, no_update, no_update,
                {"display": "none"}, no_update,
            )

        preview = _build_preview(report_key)
        status = _build_definition_status(report_key)

        # Date-range behavior
        if report.date_range_fixed == "30d":
            # RTL Alarms (30 Days) — locked to 30 days
            period_options = [
                {"label": " 30d (fixed)", "value": "30d", "disabled": True},
            ]
            notice_style = {"display": "block", "marginTop": "4px"}
            notice = html.Em(
                "This report is defined as a 30-day period. "
                "Date range selection is locked.",
                className="report-form__note",
            )
            return (
                {"display": "block"}, preview,
                {"display": "block"}, status,
                False,
                {"display": "block"}, "30d", period_options,
                notice_style, notice,
            )
        elif report.key == "installed_rtls":
            # Installed RTLs — current-state report, no date range
            return (
                {"display": "block"}, preview,
                {"display": "block"}, status,
                False,
                {"display": "none"}, no_update, no_update,
                {"display": "none"}, no_update,
            )
        else:
            # Maximum Temperature — period not defined by spec
            notice_style = {"display": "block", "marginTop": "4px"}
            notice = html.Em(
                "The Functional Specification does not define a reporting period for this report.",
                className="report-form__note",
            )
            return (
                {"display": "block"}, preview,
                {"display": "block"}, status,
                False,
                {"display": "none"}, no_update, no_update,
                notice_style, notice,
            )

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
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_report_devices(transformer_id, auth_data):
        try:
            options = _device_options(transformer_id, scope_from_session(auth_data))
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
    def generate_report(n_clicks, report_key, asset_scope, plant_id, transformer_id, device_id, period, custom_start, custom_end):
        if not n_clicks:
            return no_update, no_update

        report = get_report(report_key)
        report_label = report.label if report else "Unknown"

        # Build scope description
        scope_desc = _scope_label(asset_scope, plant_id, transformer_id, device_id)

        # Build period description
        if report and report.date_range_fixed == "30d":
            period_desc = "Last 30 days (fixed by report definition)"
        elif period is None:
            period_desc = "Not applicable (current-state report)"
        elif period == "custom" and custom_start and custom_end:
            period_desc = f"Custom: {custom_start} to {custom_end} UTC"
        else:
            period_labels = {"24h": "Last 24 hours", "7d": "Last 7 days", "30d": "Last 30 days"}
            period_desc = period_labels.get(period, period)

        # Prototype result
        result = html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.H4("Prototype Only"),
                html.P("No report file was generated or delivered."),
                html.Div(
                    className="report-prototype-detail",
                    children=[
                        html.P(html.Strong("Report: "), report_label),
                        html.P(html.Strong("Scope: "), scope_desc),
                        html.P(html.Strong("Period: "), period_desc),
                    ],
                ),
            ],
        )

        return {"display": "block"}, result
