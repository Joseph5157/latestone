"""Placeholder destination page — layout only, no queries, no workflows.

Rendered for routes whose destination is not implemented yet (Device
Administration, Reports, Notifications, User Administration). Phase 1 scope:
a page title, a one-sentence purpose, and the explicit pending message. No
forms, fields, roles, report types or notification behaviours are invented —
later phases design those from client-confirmed scope.
"""
from __future__ import annotations

from dash import html

from components.app_header import app_header
from components.breadcrumb import breadcrumb

PENDING_MESSAGE = "Design/implementation pending client-approved frontend scope."


def placeholder_layout(title: str, purpose: str) -> html.Div:
    """A minimal, honest destination for a route that is not built yet.

    `title` is both the H1 and the breadcrumb's current item: the page has no
    parent in the Fleet hierarchy, so the crumb is deliberately a single,
    non-linked entry rather than a fabricated trail.
    """
    return html.Div(
        className="page page--monitoring page--placeholder",
        children=[
            app_header(breadcrumb_children=breadcrumb([(title, None)])),
            html.H1(title),
            html.P(purpose, className="page__subtitle"),
            html.Div(
                className="status-panel status-panel--placeholder",
                children=[html.P(PENDING_MESSAGE)],
            ),
        ],
    )