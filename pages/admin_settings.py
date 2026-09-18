"""Administrator Settings page — layout only.

Each slot is filled by its own panel callback, which answers to this route
and re-verifies its own capability before any query or write.
"""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb
from components.freshness_threshold_panel import PANEL_ID as FRESHNESS_PANEL_ID
from components.temperature_threshold_panel import PANEL_ID as TEMPERATURE_PANEL_ID
from components.vibration_contract_panel import PANEL_ID as VIBRATION_PANEL_ID


def _section(eyebrow: str, title: str, description: str, panel_id: str) -> html.Section:
    return html.Section(
        className="admin-settings__section",
        children=[
            html.Div(
                className="admin-section-heading",
                children=[
                    html.Div(
                        children=[
                            html.Div(eyebrow, className="admin-section-heading__eyebrow"),
                            html.H2(title),
                        ],
                    ),
                    html.P(description),
                ],
            ),
            html.Div(id=panel_id, className="fleet-administration"),
        ],
    )


def layout() -> html.Div:
    return html.Div(
        className="page page--monitoring page--admin-settings",
        children=[
            app_header(breadcrumb_children=breadcrumb([("Settings", None)])),
            html.Header(
                className="admin-page-heading",
                children=[
                    html.Div("Administration", className="admin-page-heading__eyebrow"),
                    html.H1("Settings"),
                    html.P(
                        "Fleet-wide configuration. Every change is recorded in the Audit Log.",
                        className="admin-page-heading__description",
                    ),
                ],
            ),
            _section(
                "Monitoring",
                "Data freshness",
                "Changes what counts as Stale across every dashboard.",
                FRESHNESS_PANEL_ID,
            ),
            _section(
                "Configuration only",
                "Temperature and vibration",
                "Recorded for the client's confirmation. These values do not yet "
                "change any device's monitoring status.",
                TEMPERATURE_PANEL_ID,
            ),
            html.Div(id=VIBRATION_PANEL_ID, className="fleet-administration"),
        ],
    )
