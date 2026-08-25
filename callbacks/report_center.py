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

from config.metrics import get_metric
from config.reports import get_report, REPORTS
from components.entity_table import entity_table
from services import hierarchy_service
from services.device_scope import DeviceScope, scope_from_session
from services.report_service import (
    InstalledRtlsRow,
    ReportError,
    installed_rtls_rows,
    rtl_alarms_30d_rows,
)

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


def _plant_options(scope: DeviceScope) -> list[dict]:
    return [
        {"label": p.name, "value": p.plant_id}
        for p in hierarchy_service.list_plants(scope=scope)
    ]


def _transformer_options(plant_id: str, scope: DeviceScope) -> list[dict]:
    if not plant_id:
        return []
    return [
        {"label": t.transformer_code, "value": t.transformer_id}
        for t in hierarchy_service.list_transformers(plant_id, scope=scope)
    ]


def _device_options(transformer_id: str, scope: DeviceScope) -> list[dict]:
    if not transformer_id:
        return []
    return [
        {"label": d.device_code, "value": d.device_id}
        for d in hierarchy_service.list_devices(transformer_id, scope=scope)
    ]


def _scope_label(
    scope: str,
    plant_id: str = "",
    transformer_id: str = "",
    device_id: str = "",
    *,
    device_scope: DeviceScope = None,
) -> str:
    """Build human-readable scope label.

    `scope` here is the report's *asset scope* selection ("fleet"/"plant"/
    "transformer"/"device") — an unrelated string that predates ROLE-3 and is
    not renamed to avoid a churny diff. `device_scope` is the caller's
    `DeviceScope`, required whenever this needs to list transformers.
    """
    if scope == "fleet":
        return "Entire Fleet"
    if scope == "plant" and plant_id:
        plant = hierarchy_service.get_plant_or_none(plant_id)
        return f"Plant: {plant.name if plant else plant_id}"
    if scope == "transformer" and transformer_id:
        transformer = next(
            (
                t for t in hierarchy_service.list_transformers(plant_id, scope=device_scope)
                if t.transformer_id == transformer_id
            ),
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

    if report.key == "installed_rtls":
        # REPORT-2: this report is data-backed. The honesty notice now
        # states what is real and what is still missing, rather than a
        # blanket "no backend yet".
        return html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.P(html.Strong("Installed RTL data is sourced from the current application database. ")),
                html.P(
                    "OU, Zone, Sector, CNC and Feeder Name are unavailable "
                    "until the client asset-hierarchy mapping is confirmed. "
                    "They are shown as placeholders in the generated report."
                ),
            ],
        )

    if report.key == "rtl_alarms_30d":
        # REPORT-3: alarm rows come from persisted application events.
        # Same honesty convention as REPORT-2 — no file-generation claims.
        return html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.P(html.Strong("Alarm data is sourced from persisted device events. ")),
                html.P(
                    "The report covers the last 30 days (fixed by the report "
                    "definition). OU, Zone, Sector, CNC and Feeder are "
                    "unavailable until the client asset-hierarchy mapping is "
                    "confirmed; they are shown as placeholders."
                ),
            ],
        )

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


def _build_installed_rtls_table(rows: list[InstalledRtlsRow]) -> html.Div:
    """Render Installed RTLs as the real data table (REPORT-2).

    Presentation-only mapping from domain rows to table cells:
    R2-D2 — a None taxonomy field becomes "—"; the service layer never
    emits placeholder text, so a future exporter can still tell
    "unmapped" apart from report data. Timestamps and temperatures keep
    their raw typed values in `InstalledRtlsRow` and are formatted here.
    """
    decimals = get_metric("temperature").precision
    data = [
        {
            "ou": row.ou or "—",
            "zone": row.zone or "—",
            "sector": row.sector or "—",
            "cnc": row.cnc or "—",
            "feeder_name": row.feeder_name or "—",
            "transformer": row.transformer,
            "uid": row.uid,
            "last_recorded_at": (
                row.last_recorded_at.strftime("%Y-%m-%d %H:%M UTC")
                if row.last_recorded_at else "—"
            ),
            "last_temperature": (
                f"{row.last_temperature:.{decimals}f}"
                if row.last_temperature is not None else "—"
            ),
            "rtl_status": row.rtl_status,
        }
        for row in rows
    ]
    columns = [
        {"name": name, "id": cid}
        for cid, name in [
            ("ou", "OU"),
            ("zone", "Zone"),
            ("sector", "Sector"),
            ("cnc", "CNC"),
            ("feeder_name", "Feeder Name"),
            ("transformer", "Transformer"),
            ("uid", "UID"),
            ("last_recorded_at", "Timestamp of Last Recorded Data"),
            ("last_temperature", "Last Recorded Temperature (°C)"),
            ("rtl_status", "RTL Status"),
        ]
    ]
    return entity_table("installed-rtls-report-table", columns, data)


def _build_installed_rtls_report(
    asset_scope: str, plant_id, transformer_id, device_id, device_scope: DeviceScope
) -> html.Div:
    """Gather → service → format. Errors surface as friendly panels."""
    try:
        rows = installed_rtls_rows(
            plant_id=plant_id if asset_scope in ("plant", "transformer", "device") else None,
            transformer_id=transformer_id if asset_scope in ("transformer", "device") else None,
            device_id=device_id if asset_scope == "device" else None,
            device_scope=device_scope,
        )
    except ReportError:
        return html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.H4("Report unavailable"),
                html.P(
                    "The Installed RTLs report could not be loaded. "
                    "Please try again."
                ),
            ],
        )

    return html.Div(
        children=[
            html.H4(f"Installed RTLs — {len(rows)} device(s)"),
            _build_installed_rtls_table(rows),
        ],
    )


def _build_rtl_alarms_table(rows: list[RtlAlarms30dRow]) -> html.Div:
    """Render RTL Alarms (30 Days) as the real data table (REPORT-3).

    Presentation-only mapping: None taxonomy fields become "—" (R2-D2);
    battery/temperature render "—" when the device did not send a value
    (EVT-D4 — display payload, never a classification input). Alarm labels
    arrive already resolved through the shared semantics layer.
    """
    decimals = get_metric("temperature").precision
    data = [
        {
            "ou": row.ou or "—",
            "zone": row.zone or "—",
            "sector": row.sector or "—",
            "cnc": row.cnc or "—",
            "feeder": row.feeder_name or "—",
            "transformer": row.transformer or "—",
            "uid": row.uid or "—",
            "battery_voltage": (
                f"{row.battery_voltage:.2f}"
                if row.battery_voltage is not None else "—"
            ),
            "alarm_at": row.alarm_at.strftime("%Y-%m-%d %H:%M UTC"),
            "temperature": (
                f"{row.temperature:.{decimals}f}"
                if row.temperature is not None else "—"
            ),
            "alarm_label": row.alarm_label,
            "firmware_version": row.firmware_version or "—",
        }
        for row in rows
    ]
    columns = [
        {"name": name, "id": cid}
        for cid, name in [
            ("ou", "OU"),
            ("zone", "Zone"),
            ("sector", "Sector"),
            ("cnc", "CNC"),
            ("feeder", "Feeder"),
            ("transformer", "Transformer"),
            ("uid", "UID"),
            ("battery_voltage", "Battery(V)"),
            ("alarm_at", "Alarm Date & Time"),
            ("temperature", "Temperature (°C)"),
            ("alarm_label", "Alarm"),
            ("firmware_version", "Firmware"),
        ]
    ]
    return entity_table("rtl-alarms-30d-report-table", columns, data)


def _build_rtl_alarms_report(
    asset_scope: str, plant_id, transformer_id, device_id, device_scope: DeviceScope
) -> html.Div:
    """Gather → service → format for RTL Alarms (30 Days). A zero-row
    result is a legitimate empty report, not an error (R3-D8)."""
    try:
        rows = rtl_alarms_30d_rows(
            plant_id=plant_id if asset_scope in ("plant", "transformer", "device") else None,
            transformer_id=transformer_id if asset_scope in ("transformer", "device") else None,
            device_id=device_id if asset_scope == "device" else None,
            device_scope=device_scope,
        )
    except ReportError:
        return html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.H4("Report unavailable"),
                html.P(
                    "The RTL Alarms (30 Days) report could not be loaded. "
                    "Please try again."
                ),
            ],
        )

    return html.Div(
        children=[
            html.H4(f"RTL Alarms (30 Days) — {len(rows)} alarm event(s)"),
            _build_rtl_alarms_table(rows),
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
        State("auth-store", "data"),
    )
    def populate_report_plants(_, auth_data):
        try:
            return _plant_options(scope_from_session(auth_data))
        except Exception:
            logger.exception("Failed to populate report plant options")
            return []

    @app.callback(
        Output("report-transformer", "options"),
        Output("report-transformer", "disabled"),
        Input("report-plant", "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def populate_report_transformers(plant_id, auth_data):
        try:
            options = _transformer_options(plant_id, scope_from_session(auth_data))
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
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def generate_report(
        n_clicks, report_key, asset_scope, plant_id, transformer_id, device_id,
        period, custom_start, custom_end, auth_data,
    ):
        if not n_clicks:
            return no_update, no_update

        report = get_report(report_key)
        report_label = report.label if report else "Unknown"

        # REPORT-2: Installed RTLs is the first data-backed report.
        # REPORT-3: RTL Alarms (30 Days) is the second — real event rows,
        # still no file generation (R3-D8). Everything else keeps its
        # explicit prototype panels (R2-D5).
        if report and report.key == "installed_rtls":
            result = _build_installed_rtls_report(
                asset_scope, plant_id, transformer_id, device_id,
                scope_from_session(auth_data),
            )
            return {"display": "block"}, result

        if report and report.key == "rtl_alarms_30d":
            result = _build_rtl_alarms_report(
                asset_scope, plant_id, transformer_id, device_id,
                scope_from_session(auth_data),
            )
            return {"display": "block"}, result

        # Build scope description
        scope_desc = _scope_label(
            asset_scope, plant_id, transformer_id, device_id,
            device_scope=scope_from_session(auth_data),
        )

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
