"""App header — brand, breadcrumb slot, freshness, logout.

Deliberately has no equipment-selector slot. The header is rendered *inside*
each page layout, so anything mounted here disappears whenever another route is
active; the selector's callbacks fire on every route and would then target
components that do not exist. The selector therefore lives in the global
app layout instead — see components/equipment_selector.
"""
from __future__ import annotations

from dash import html

from components.freshness_badge import freshness_badge, FRESHNESS_LABELS
from services.monitoring_service import Freshness


def app_header(
    breadcrumb_children=None,
    freshness: Freshness | None = None,
) -> html.Header:
    children = [
        html.Div(
            [
                html.Img(
                    src="/assets/eskom-logo-blue.webp",
                    alt="Eskom",
                    className="header__logo",
                ),
                html.Span("Powerplant Dashboard"),
            ],
            className="header__brand",
        ),
    ]

    if breadcrumb_children is not None:
        children.append(
            html.Div(breadcrumb_children, className="header__breadcrumb")
        )

    if freshness is not None:
        children.append(
            html.Div(
                [
                    html.Span("Data: ", className="header__freshness-label"),
                    # `header-freshness` is a neutral container, not the badge.
                    # It used to be the badge itself while the device callback
                    # wrote a whole new badge into its children — nesting a
                    # badge inside a badge and leaving the outer class stuck at
                    # whatever the layout first rendered.
                    html.Span(
                        freshness_badge(freshness),
                        id="header-freshness",
                        className="header__freshness-slot",
                    ),
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
