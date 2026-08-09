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


def inactive_notice(entity_type: str) -> html.Div:
    """Shown when an inactive entity is opened by direct URL.

    Inactive equipment is filtered out of listings and counts, but stays
    reachable so its history can be inspected. This says so, rather than letting
    the page look like live monitoring of something that is no longer running.

    Administrative state only — unrelated to data freshness or monitoring
    condition, which are shown separately.
    """
    return html.Div(
        className="status-panel status-panel--inactive",
        children=[
            html.Strong(f"This {entity_type} is inactive."),
            html.Span(" Any data shown is historical."),
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
