"""Multi-plant monitoring dashboard page (demo).

Shows synthetic temperature readings across 30 real power plant
locations (see db/seed_data/plants.json), reading from the consolidated
monitoring.readings table. Companion to the single-device dashboard in
pages/dashboard.py, which continues to mirror the client's current
production shape unchanged.
"""
from __future__ import annotations

from dash import dcc, html

from components.kpi_card import kpi_row
from components.period_filter import period_filter
from components.plant_selector import plant_selector
from components.readings_table import readings_table
from components.temperature_chart import temperature_chart
from services.monitoring_service import list_plants

ID_PREFIX = "plants-"


def plants_dashboard_header():
    return html.Div(
        className="dashboard-header",
        children=[
            html.Div(
                className="dashboard-header__title",
                children=[
                    html.Span("MULTI-PLANT MONITORING (DEMO)", className="dashboard-header__brand"),
                ],
            ),
            html.Div(
                className="dashboard-header__meta",
                children=[
                    html.Span(id=f"{ID_PREFIX}device-meta", children="Transformer: — • Device: —"),
                    html.Span("•", className="dashboard-header__dot"),
                    html.Span(id=f"{ID_PREFIX}last-data-timestamp", children="Last data: —"),
                ],
            ),
            html.Div(
                className="dashboard-header__actions",
                children=[
                    html.Span(id=f"{ID_PREFIX}connection-state", className="connection-state"),
                    html.Button("Logout", id="logout-button", className="logout-button", n_clicks=0),
                ],
            ),
        ],
    )


def plants_status_badge():
    return html.Div(
        id=f"{ID_PREFIX}status-badge",
        className="status-badge status-badge--normal",
        children="—",
    )


def plants_dashboard_layout():
    plants = list_plants()
    return html.Div(
        className="dashboard-page",
        children=[
            plants_dashboard_header(),
            html.Div(
                className="dashboard-controls",
                children=[plant_selector(plants), period_filter(id_prefix=ID_PREFIX)],
            ),
            html.Div(
                id=f"{ID_PREFIX}kpi-row-container",
                children=kpi_row("—", "—", "—", "—"),
            ),
            html.Div(
                className="chart-section",
                children=[
                    html.Div(
                        className="chart-section__header",
                        children=[
                            html.H3("Temperature Trend", className="chart-section__title"),
                            plants_status_badge(),
                        ],
                    ),
                    dcc.Loading(temperature_chart(id_prefix=ID_PREFIX), type="circle"),
                ],
            ),
            html.Div(
                className="table-section",
                children=[
                    html.H3("Recent Readings", className="table-section__title"),
                    readings_table(id_prefix=ID_PREFIX),
                ],
            ),
            dcc.Interval(
                id=f"{ID_PREFIX}refresh-interval", interval=30 * 60 * 1000, n_intervals=0
            ),
        ],
    )
