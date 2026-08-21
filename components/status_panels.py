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


def forbidden_panel() -> html.Div:
    """Shown when a signed-in operator opens a route their role may not have.

    Deliberately NOT the not-found panel. An authorization failure and a bad
    URL are different facts, and telling someone a page does not exist when it
    does exist and they are simply not entitled to it is a lie the operator
    will act on — they will retype the URL, or report a broken link.

    Says nothing about the policy: no role name, no route, nothing echoed back
    from the URL. It states the outcome and offers the way back to a page every
    role may open.

    This panel is the visible half of an application-level control. The router
    refuses the route; it is not a server-side authorization boundary — see
    docs/CODE_AUDIT.md, "Security posture".
    """
    return html.Div(
        className="status-panel status-panel--forbidden",
        children=[
            html.H3("No access"),
            html.P("Your account does not have access to this page."),
            dcc.Link("Back to Fleet Overview", href="/plants"),
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
