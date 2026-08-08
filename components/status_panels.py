"""Status panels — not-found, error, and empty-data placeholders."""
from __future__ import annotations

from dash import dcc, html


def not_found_panel(entity_type: str) -> html.Div:
    return html.Div(
        className="status-panel status-panel--not-found",
        children=[
            html.H3("Not found"),
            html.P(f"This {entity_type} was not found."),
            dcc.Link("Back to plants", href="/plants"),
        ],
    )


def error_panel(message: str = "Something went wrong loading this data. Please try again.") -> html.Div:
    return html.Div(
        className="status-panel status-panel--error",
        children=[
            html.H3("Error"),
            html.P(message),
        ],
    )


def empty_data_panel(message: str = "No data available for the selected period") -> html.Div:
    return html.Div(
        className="status-panel status-panel--empty",
        children=[
            html.H3("No data"),
            html.P(message),
        ],
    )
