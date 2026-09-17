"""Report Center page — layout only, no queries.

Frontend shell for report generation, CSV/PDF/XLSX export, and history.
Report types are confirmed by the RTL Functional Specification (§11).
XLSX matches the Functional Specification's own "Export to Excel" UI
(FS-EXPORT-1); CSV/PDF remain additional development-convenience formats
(C-04 baseline). The client-approved production delivery MECHANISM
remains unresolved (REQ-1A §16) regardless of format; all three reports —
Installed RTLs, RTL Alarms (30 Days), and Maximum Temperature — are
data-backed and exportable as of REPORT-EXPORT-1/FS-EXPORT-1.
"""
from __future__ import annotations

from dash import dcc, html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.entity_table import entity_table
from config.reports import report_options
from services.report_export import EXPORT_FORMAT_LABEL


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--report-center",
        children=[
            app_header(
                breadcrumb_children=breadcrumb([("Report Center", None)]),
            ),
            html.H1("Report Center"),
            html.P(
                "Generate and view monitoring reports.",
                className="page__subtitle",
            ),
            # Honesty notice — single-sourced from EXPORT_FORMAT_LABEL
            # (services/report_export.py) so this banner and the post-
            # export status panel can never drift apart about which
            # formats exist or their status (R4-D1).
            html.Div(
                className="status-panel status-panel--inactive",
                children=[
                    html.Strong("Export format note. "),
                    html.Span(
                        EXPORT_FORMAT_LABEL + " No files are emailed or "
                        "delivered elsewhere — every export is a direct "
                        "browser download."
                    ),
                ],
            ),
            # Section A — Generate Report
            html.Section(
                className="report-section",
                children=[
                    html.H2("Generate Report"),
                    html.Div(
                        className="report-form",
                        children=[
                            # Report Type
                            html.Div(
                                className="report-form__field",
                                children=[
                                    html.Label(
                                        "Report Type",
                                        htmlFor="report-type",
                                        className="report-form__label",
                                    ),
                                    dcc.Dropdown(
                                        id="report-type",
                                        options=report_options(),
                                        value=None,
                                        clearable=False,
                                        placeholder="Select a report type...",
                                        className="report-form__dropdown",
                                    ),
                                ],
                            ),
                            # Report Definition Status
                            html.Div(
                                id="report-definition-status",
                                className="report-form__status",
                                style={"display": "none"},
                            ),
                            # Report Layout Preview — wrapped in dcc.Loading so
                            # preview/result work shows the shared spinner
                            # affordance while form controls stay usable.
                            dcc.Loading(
                                html.Div(
                                    id="report-preview",
                                    className="report-preview",
                                    style={"display": "none"},
                                ),
                                className="report-loading",
                            ),
                            # Asset Scope
                            html.Div(
                                className="report-form__field",
                                children=[
                                    html.Label(
                                        "Asset Scope",
                                        htmlFor="report-asset-scope",
                                        className="report-form__label",
                                    ),
                                    dcc.Dropdown(
                                        id="report-asset-scope",
                                        options=[
                                            {"label": "Entire Fleet", "value": "fleet"},
                                            {"label": "Plant", "value": "plant"},
                                            {"label": "Transformer", "value": "transformer"},
                                            {"label": "Device", "value": "device"},
                                        ],
                                        value="fleet",
                                        clearable=False,
                                        className="report-form__dropdown",
                                    ),
                                ],
                            ),
                            # Plant Selector (visible when scope = plant/transformer/device)
                            html.Div(
                                id="report-plant-container",
                                className="report-form__field",
                                style={"display": "none"},
                                children=[
                                    html.Label(
                                        "Plant",
                                        htmlFor="report-plant",
                                        className="report-form__label",
                                    ),
                                    dcc.Dropdown(
                                        id="report-plant",
                                        options=[],
                                        placeholder="Select plant...",
                                        searchable=True,
                                        className="report-form__dropdown",
                                    ),
                                ],
                            ),
                            # Transformer Selector (visible when scope = transformer/device)
                            html.Div(
                                id="report-transformer-container",
                                className="report-form__field",
                                style={"display": "none"},
                                children=[
                                    html.Label(
                                        "Transformer",
                                        htmlFor="report-transformer",
                                        className="report-form__label",
                                    ),
                                    dcc.Dropdown(
                                        id="report-transformer",
                                        options=[],
                                        placeholder="Select transformer...",
                                        searchable=True,
                                        disabled=True,
                                        className="report-form__dropdown",
                                    ),
                                ],
                            ),
                            # Device Selector (visible when scope = device)
                            html.Div(
                                id="report-device-container",
                                className="report-form__field",
                                style={"display": "none"},
                                children=[
                                    html.Label(
                                        "Device",
                                        htmlFor="report-device",
                                        className="report-form__label",
                                    ),
                                    dcc.Dropdown(
                                        id="report-device",
                                        options=[],
                                        placeholder="Select device...",
                                        searchable=True,
                                        disabled=True,
                                        className="report-form__dropdown",
                                    ),
                                ],
                            ),
                            # Date Range
                            html.Div(
                                id="report-period-container",
                                className="report-form__field",
                                # RadioItems groups several controls under one
                                # label — the group role names the whole set,
                                # including the conditional custom-range
                                # picker it reveals, rather than any one radio.
                                role="group",
                                **{"aria-labelledby": "report-period-label"},
                                children=[
                                    html.Label(
                                        "Date Range",
                                        id="report-period-label",
                                        className="report-form__label",
                                    ),
                                    dcc.RadioItems(
                                        id="report-period",
                                        options=[
                                            {"label": " 24h", "value": "24h"},
                                            {"label": " 7d", "value": "7d"},
                                            {"label": " 30d", "value": "30d"},
                                            {"label": " Custom", "value": "custom"},
                                        ],
                                        value="30d",
                                        inline=True,
                                        className="report-form__radio",
                                    ),
                                    html.Div(
                                        id="report-custom-range-container",
                                        style={"display": "none", "marginTop": "8px"},
                                        children=[
                                            dcc.DatePickerRange(
                                                id="report-custom-date-range",
                                                display_format="YYYY-MM-DD",
                                                start_date=None,
                                                end_date=None,
                                            ),
                                        ],
                                    ),
                                    # Fixed period notice (for RTL Alarms 30 Days)
                                    html.Div(
                                        id="report-period-notice",
                                        style={"display": "none", "marginTop": "4px"},
                                    ),
                                ],
                            ),
                            # Actions: preview (Generate) and export (Download)
                            # are deliberately separate actions (R4-D2).
                            html.Div(
                                className="report-form__actions",
                                children=[
                                    html.Button(
                                        "Generate Preview",
                                        id="report-generate-btn",
                                        n_clicks=0,
                                        disabled=True,
                                        className="report-form__btn report-form__btn--primary",
                                    ),
                                    # Format choice sits right next to the
                                    # Download button it controls — CSV, PDF
                                    # or native XLSX (FS-EXPORT-1; XLSX is
                                    # what the Functional Specification's own
                                    # "Export to Excel" UI calls for; CSV/PDF
                                    # remain development-convenience formats,
                                    # C-04).
                                    html.Label(
                                        "Export format",
                                        htmlFor="report-export-format",
                                        className="report-form__label",
                                        style={"marginLeft": "8px"},
                                    ),
                                    dcc.RadioItems(
                                        id="report-export-format",
                                        options=[
                                            {"label": " CSV", "value": "csv"},
                                            {"label": " PDF", "value": "pdf"},
                                            {"label": " XLSX", "value": "xlsx"},
                                        ],
                                        value="csv",
                                        inline=True,
                                        className="report-form__radio",
                                    ),
                                    html.Button(
                                        "Download",
                                        id="report-download-btn",
                                        n_clicks=0,
                                        disabled=True,
                                        className="report-form__btn",
                                    ),
                                    dcc.Download(id="report-download"),
                                    html.Div(
                                        id="report-export-status",
                                        style={"display": "none",
                                               "marginTop": "4px"},
                                    ),
                                ],
                            ),
                            # Generation result — own loading wrapper so a
                            # data-backed report fetch never blocks the page.
                            dcc.Loading(
                                html.Div(
                                    id="report-generation-result",
                                    className="report-generation-result",
                                    style={"display": "none", "marginTop": "16px"},
                                ),
                                className="report-loading",
                            ),
                        ],
                    ),
                ],
            ),
            # Section B — Recent Reports
            html.Section(
                className="report-section",
                children=[
                    html.H2("Recent Reports"),
                    html.Div(
                        className="status-panel status-panel--inactive",
                        children=[
                            html.Strong("Demo data. "),
                            html.Span(
                                "Recent reports below are mock entries for UI demonstration only."
                            ),
                        ],
                    ),
                    # Error slot
                    html.Div(id="recent-reports-error", className="listing-error"),
                    # Recent reports table
                    # Recent reports table — responsive card presentation
                    # below 768px; "Demo" status renders muted/italic (not
                    # freshness green) since these are mock entries.
                    entity_table(
                        table_id="recent-reports-table",
                        columns=[
                            {"name": "Report", "id": "report"},
                            {"name": "Scope", "id": "scope"},
                            {"name": "Requested", "id": "requested"},
                            {"name": "Status", "id": "status"},
                        ],
                        rows=[],
                        link_column_id="report",
                        state_column_id="status",
                        responsive=True,
                        extra_style_data_conditional=[
                            {
                                "if": {"column_id": "status"},
                                "color": "var(--color-muted)",
                                "fontStyle": "italic",
                            },
                        ],
                    ),
                ],
            ),
        ],
    )
