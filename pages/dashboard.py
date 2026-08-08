"""Dashboard page layout."""
from __future__ import annotations

from dash import dcc, html

from components.kpi_card import kpi_row
from components.period_filter import period_filter
from components.readings_table import readings_table
from components.temperature_chart import temperature_chart
from config.settings import demo_device


def dashboard_header():
    return html.Div(
        className="dashboard-header",
        children=[
            html.Div(
                className="dashboard-header__title",
                children=[
                    html.Span("POWER PLANT MONITORING", className="dashboard-header__brand"),
                ],
            ),
            html.Div(
                className="dashboard-header__meta",
                children=[
                    html.Span(f"Transformer: {demo_device.transformer.upper()}"),
                    html.Span("•", className="dashboard-header__dot"),
                    html.Span(f"Device: {demo_device.device}"),
                    html.Span("•", className="dashboard-header__dot"),
                    html.Span(id="last-data-timestamp", children="Last data: —"),
                ],
            ),
            html.Div(
                className="dashboard-header__actions",
                children=[
                    html.Span(id="connection-state", className="connection-state"),
                    html.Button("Logout", id="logout-button", className="logout-button", n_clicks=0),
                ],
            ),
        ],
    )


def status_badge():
    return html.Div(id="status-badge", className="status-badge status-badge--normal", children="—")


def dashboard_layout():
    return html.Div(
        className="dashboard-page",
        children=[
            dashboard_header(),
            html.Div(
                className="dashboard-controls",
                children=[period_filter()],
            ),
            html.Div(id="kpi-row-container", children=kpi_row("—", "—", "—", "—")),
            html.Div(
                className="chart-section",
                children=[
                    html.Div(
                        className="chart-section__header",
                        children=[
                            html.H3("Temperature Trend", className="chart-section__title"),
                            status_badge(),
                        ],
                    ),
                    dcc.Loading(temperature_chart(), type="circle"),
                ],
            ),
            html.Div(
                className="table-section",
                children=[
                    html.H3("Recent Readings", className="table-section__title"),
                    readings_table(),
                ],
            ),
            dcc.Interval(id="refresh-interval", interval=30 * 60 * 1000, n_intervals=0),
        ],
    )
