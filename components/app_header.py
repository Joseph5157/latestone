"""App header — brand, breadcrumb slot, hierarchy selector slot, freshness, logout."""
from __future__ import annotations

from dash import html

from components.freshness_badge import freshness_badge, FRESHNESS_LABELS
from services.monitoring_service import Freshness


def app_header(
    breadcrumb_children=None,
    freshness: Freshness | None = None,
    selector_children=None,
) -> html.Header:
    children = [
        html.Div("Powerplant Dashboard", className="header__brand"),
    ]

    if breadcrumb_children is not None:
        children.append(
            html.Div(breadcrumb_children, className="header__breadcrumb")
        )

    if selector_children is not None:
        children.append(
            html.Div(selector_children, className="header__selector")
        )

    if freshness is not None:
        children.append(
            html.Div(
                [
                    html.Span("Data: ", className="header__freshness-label"),
                    freshness_badge(freshness, component_id="header-freshness"),
                ],
                className="header__freshness",
            )
        )

    children.append(
        html.Div(
            html.A("Logout", href="/logout", className="header__logout"),
            className="header__logout-wrapper",
        )
    )

    return html.Header(children=children, className="app-header")
