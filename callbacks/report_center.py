"""Report Center callbacks — form handling, preview, prototype generation.

All operations are frontend-only. Report types are confirmed by the RTL
Functional Specification (§11). Report generation creates a clearly labeled
prototype result; no files are produced or delivered. Recent reports table
uses mock data explicitly marked as demo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from dash import Input, Output, State, dcc, no_update, html

from config.metrics import get_metric
from config.reports import get_report, REPORTS
from components.entity_table import entity_table
from services import hierarchy_service
from services.hierarchy_service import entity_in_scope
from services.action_guard import require_capability
from services.auth_service import current_identity
from services.authorization import AuthorizationError, EXPORT_DATA
from services.device_scope import DeviceScope, current_device_scope
from services.report_export import (
    EXPORT_FORMAT_LABEL,
    EXPORTABLE_REPORTS,
    installed_rtls_document,
    render_export,
    rtl_alarms_document,
)
from services.report_service import (
    InstalledRtlsRow,
    MaxTemperatureRow,
    RtlAlarms30dRow,
    ReportError,
    installed_rtls_rows,
    max_temperature_rows,
    resolve_max_temperature_period,
    rtl_alarms_30d_rows,
)

# Reused rather than re-derived: this is the same "calendar date ->
# closed-day query bound" parsing the device dashboard's custom range
# already fixed a real bug in (see callbacks/device.py's docstring).
# Maximum Temperature's custom range must resolve the same way or its
# displayed period would silently disagree with what was actually queried.
from callbacks.device import _parse_picker_date

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
    device_scope: DeviceScope,
) -> str:
    """Build human-readable scope label.

    `scope` here is the report's *asset scope* selection ("fleet"/"plant"/
    "transformer"/"device") — an unrelated string that predates ROLE-3 and is
    not renamed to avoid a churny diff. `device_scope` is the CURRENT trusted
    caller's `DeviceScope` and is now required (no default): every branch
    below resolves a NAME from a browser-supplied id, which is exactly the
    kind of read `entity_in_scope` exists to gate first.

    AUTH-HARDEN-1R (blocker 3). `plant_id`/`transformer_id`/`device_id` are
    untrusted REQUESTED filters, not proof of anything. Report ROWS were
    already correctly scoped (`installed_rtls_rows`/`rtl_alarms_30d_rows`
    both take `device_scope` and filter with it) — this function's labels
    were not: a Technician could type an arbitrary plant/transformer/device
    id into the report form and this would happily resolve and display its
    real name, which is a metadata leak even though no ROW data followed it.
    Both callers of this function (preview and CSV export) share it, so
    fixing it once fixes both paths.

    Out of scope reads the same as "not found": the raw id is echoed back
    rather than a resolved name, so this deliberately does not confirm
    whether the requested asset exists.
    """
    if scope == "fleet":
        return "Entire Fleet"
    if scope == "plant" and plant_id:
        plant = (
            hierarchy_service.get_plant_or_none(plant_id)
            if entity_in_scope(device_scope, plant_id=plant_id)
            else None
        )
        return f"Plant: {plant.name if plant else plant_id}"
    if scope == "transformer" and transformer_id:
        # Already scope-filtered: list_transformers queries with
        # allowed_device_ids=device_scope.device_ids, so an out-of-scope
        # transformer_id is simply absent from this list — `transformer`
        # stays None for it, same as a nonexistent one.
        transformer = next(
            (
                t for t in hierarchy_service.list_transformers(plant_id, scope=device_scope)
                if t.transformer_id == transformer_id
            ),
            None
        )
        # The plant's name is resolved ONLY once the transformer lookup above
        # has already proven it in scope — never independently, which is what
        # let a forged plant_id resolve a real name regardless of the
        # transformer requested alongside it.
        plant = (
            hierarchy_service.get_plant_or_none(plant_id)
            if transformer and plant_id else None
        )
        return f"Transformer: {transformer.transformer_code if transformer else transformer_id} ({plant.name if plant else plant_id})"
    if scope == "device" and device_id:
        device = (
            hierarchy_service.get_device_context(device_id)
            if entity_in_scope(device_scope, device_id=device_id)
            else None
        )
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

    if report.key == "max_temperature":
        # REPORT-MAXTEMP-1: per-transformer peak temperature, sourced from
        # persisted readings. Same honesty convention as REPORT-2/REPORT-3.
        return html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.P(html.Strong(
                    "Maximum Temperature data is sourced from persisted "
                    "temperature readings, one row per transformer. "
                )),
                html.P(
                    "Default period is a rolling 30 days; a custom date "
                    "range is also available (development baseline C-15, "
                    "pending client confirmation). OU, Zone, Sector, CNC "
                    "and Feeder Name are unavailable until the client "
                    "asset-hierarchy mapping is confirmed; they are shown "
                    "as placeholders. Date Installed reflects the specific "
                    "device that recorded the maximum and is blank when "
                    "that device has no installation date on record."
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
    return entity_table(
        "installed-rtls-report-table", columns, data, responsive=True
    )


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


def _format_alarm_at(value: datetime) -> str:
    """UTC-normalized "%Y-%m-%d %H:%M UTC" rendering for alarm previews.

    Mirrors report_export._utc so the preview and the CSV export always
    describe the same instant: timezone-aware values are converted to UTC
    before formatting; naive values (no tzinfo to convert from) format
    as-is, exactly as the exporter treats them.
    """
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M UTC")


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
            "alarm_at": _format_alarm_at(row.alarm_at),
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
    return entity_table(
        "rtl-alarms-30d-report-table", columns, data, responsive=True
    )


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


def _format_report_date(value: datetime | None) -> str:
    """Date-only ("%Y-%m-%d") rendering, UTC-normalized like
    ``_format_alarm_at`` — but a date, not a date+time, matching the
    "Date Installed"/"Date of Maximum Temperature" column names literally.
    """
    if value is None:
        return "—"
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%d")


def _format_report_period(start: datetime, end: datetime) -> str:
    """The resolved [start, end] window, always UTC, always both bounds —
    the one place this is rendered, so the preview header and any future
    export describe the exact window that was actually queried."""
    return f"{_format_report_date(start)} to {_format_report_date(end)} UTC"


def _build_max_temperature_table(rows: list[MaxTemperatureRow]) -> html.Div:
    """Render Maximum Temperature as the real data table (REPORT-MAXTEMP-1).

    Presentation-only mapping: None taxonomy fields become "—" (R2-D2);
    ``date_installed``/``max_temperature_at`` are dates only, per the column
    contract's literal names; ``max_temperature`` is None exactly when the
    transformer had no in-window, in-scope reading (a legitimate empty row).
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
            "date_installed": _format_report_date(row.date_installed),
            "max_temperature_at": _format_report_date(row.max_temperature_at),
            "max_temperature": (
                f"{row.max_temperature:.{decimals}f}"
                if row.max_temperature is not None else "—"
            ),
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
            ("date_installed", "Date Installed"),
            ("max_temperature_at", "Date of Maximum Temperature"),
            ("max_temperature", "Maximum Temperature (°C)"),
        ]
    ]
    return entity_table(
        "max-temperature-report-table", columns, data, responsive=True
    )


def _resolve_max_temperature_window(
    period: str | None, custom_start, custom_end
) -> tuple[datetime, datetime]:
    """Shared by the preview and (eventually) export: same parsing, same
    default, so the two paths can never disagree about what window a given
    form state means (R4-D7's principle, applied one level up)."""
    since = until = None
    if period == "custom":
        since = _parse_picker_date(custom_start)
        until = _parse_picker_date(custom_end, is_end=True)
    return resolve_max_temperature_period(since, until)


def _build_max_temperature_report(
    asset_scope: str, plant_id, transformer_id, device_id, device_scope: DeviceScope,
    period: str | None, custom_start, custom_end,
) -> html.Div:
    """Gather → service → format. A zero-row result is a legitimate empty
    report, not an error, matching R3-D8's convention."""
    since, until = _resolve_max_temperature_window(period, custom_start, custom_end)
    try:
        rows = max_temperature_rows(
            plant_id=plant_id if asset_scope in ("plant", "transformer", "device") else None,
            transformer_id=transformer_id if asset_scope in ("transformer", "device") else None,
            device_id=device_id if asset_scope == "device" else None,
            device_scope=device_scope,
            since=since,
            until=until,
        )
    except ReportError:
        return html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.H4("Report unavailable"),
                html.P(
                    "The Maximum Temperature report could not be loaded. "
                    "Please try again."
                ),
            ],
        )

    return html.Div(
        children=[
            html.H4(f"Maximum Temperature — {len(rows)} transformer(s)"),
            html.P(
                html.Strong("Period used: "), _format_report_period(since, until),
            ),
            _build_max_temperature_table(rows),
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
        elif report.key == "max_temperature":
            # Maximum Temperature (REPORT-MAXTEMP-1 / C-15) — rolling
            # 30-day default, plus a custom range. Only these two options:
            # 24h/7d belong to other reports' periods, not this one's
            # confirmed baseline.
            period_options = [
                {"label": " 30d (default)", "value": "30d"},
                {"label": " Custom", "value": "custom"},
            ]
            notice_style = {"display": "block", "marginTop": "4px"}
            notice = html.Em(
                "Default period is a rolling 30 days (development baseline "
                "C-15, pending client confirmation). Choose Custom for a "
                "specific date range.",
                className="report-form__note",
            )
            return (
                {"display": "block"}, preview,
                {"display": "block"}, status,
                False,
                {"display": "block"}, "30d", period_options,
                notice_style, notice,
            )
        else:
            return (
                {"display": "block"}, preview,
                {"display": "block"}, status,
                False,
                {"display": "none"}, no_update, no_update,
                {"display": "none"}, no_update,
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
            return _plant_options(current_device_scope())
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
            options = _transformer_options(plant_id, current_device_scope())
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
            options = _device_options(transformer_id, current_device_scope())
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
                current_device_scope(),
            )
            return {"display": "block"}, result

        if report and report.key == "rtl_alarms_30d":
            result = _build_rtl_alarms_report(
                asset_scope, plant_id, transformer_id, device_id,
                current_device_scope(),
            )
            return {"display": "block"}, result

        # REPORT-MAXTEMP-1: the third data-backed report — real per-
        # transformer rows, no file generation yet (PDF/CSV is a separate
        # gate, REPORT-EXPORT-1).
        if report and report.key == "max_temperature":
            result = _build_max_temperature_report(
                asset_scope, plant_id, transformer_id, device_id,
                current_device_scope(),
                period, custom_start, custom_end,
            )
            return {"display": "block"}, result

        # Build scope description
        scope_desc = _scope_label(
            asset_scope, plant_id, transformer_id, device_id,
            device_scope=current_device_scope(),
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

    # ---- CSV export (REPORT-4) — separate action from Generate (R4-D2) ----

    def _gather_export_rows(report_key, asset_scope, plant_id, transformer_id,
                            device_id, device_scope):
        """Rebuild the report through the SAME service functions and
        parameters the preview uses (R4-D7) — the exporter never invents
        query semantics of its own."""
        if report_key == "installed_rtls":
            return installed_rtls_rows(
                plant_id=plant_id if asset_scope in ("plant", "transformer", "device") else None,
                transformer_id=transformer_id if asset_scope in ("transformer", "device") else None,
                device_id=device_id if asset_scope == "device" else None,
                device_scope=device_scope,
            )
        if report_key == "rtl_alarms_30d":
            return rtl_alarms_30d_rows(
                plant_id=plant_id if asset_scope in ("plant", "transformer", "device") else None,
                transformer_id=transformer_id if asset_scope in ("transformer", "device") else None,
                device_id=device_id if asset_scope == "device" else None,
                device_scope=device_scope,
            )
        raise ReportError(f"{report_key!r} is not an exportable report.")

    @app.callback(
        Output("report-download-btn", "disabled"),
        Input("report-type", "value"),
        prevent_initial_call=True,
    )
    def toggle_download_button(report_key):
        """Download exists only for data-backed reports (R4-D9): REP-03
        never exposes one."""
        return report_key not in EXPORTABLE_REPORTS

    @app.callback(
        Output("report-download", "data"),
        Output("report-export-status", "children"),
        Output("report-export-status", "style"),
        Input("report-download-btn", "n_clicks"),
        State("report-type", "value"),
        State("report-asset-scope", "value"),
        State("report-plant", "value"),
        State("report-transformer", "value"),
        State("report-device", "value"),
        State("auth-store", "data"),
        prevent_initial_call=True,
    )
    def download_report_csv(
        n_clicks, report_key, asset_scope, plant_id, transformer_id,
        device_id, auth_data,
    ):
        if not n_clicks or not report_key:
            return no_update, no_update, no_update

        # ADR-013 (supersedes R4-D3's wording): the guard runs before any
        # rows are fetched, which R4-D3 got right — but as a CAPABILITY.
        # Export names no device: the report below spans a plant, a
        # transformer, one device or none. Scope is not this guard's job and
        # never was; `current_device_scope()` threads the CURRENT trusted
        # caller's DeviceScope into row construction a few lines down, and
        # the repository ANDs `allowed_device_ids` into the query.
        user = current_identity()
        try:
            require_capability(user, EXPORT_DATA)
        except AuthorizationError:
            logger.warning(
                "Refused export attempt for %r by %r",
                report_key, getattr(user, "username", None),
            )
            return (
                no_update,
                html.Div(className="status-panel status-panel--inactive",
                         children="You are not permitted to export reports."),
                {"display": "block"},
            )

        try:
            scope = current_device_scope()
            rows = _gather_export_rows(
                report_key, asset_scope, plant_id, transformer_id,
                device_id, scope,
            )
            now = datetime.now(timezone.utc)
            scope_desc = _scope_label(
                asset_scope, plant_id, transformer_id, device_id,
                device_scope=scope,
            )
            if report_key == "installed_rtls":
                document = installed_rtls_document(rows, scope_label=scope_desc, now=now)
            elif report_key == "rtl_alarms_30d":
                document = rtl_alarms_document(rows, scope_label=scope_desc, now=now)
            else:
                raise ReportError(f"{report_key!r} is not an exportable report.")

            content, mime, filename = render_export(report_key, document)
        except ReportError:
            logger.exception("Failed to build %s export", report_key)
            return (
                no_update,
                html.Div(className="status-panel status-panel--inactive",
                         children="The export could not be generated. Please try again."),
                {"display": "block"},
            )

        status = html.Div(
            className="status-panel status-panel--inactive",
            children=[
                html.P(html.Strong(f"Exported {len(document.rows)} row(s). ")),
                html.P(EXPORT_FORMAT_LABEL),
            ],
        )
        return dcc.send_bytes(content.encode("utf-8"), filename), status, {
            "display": "block",
        }
