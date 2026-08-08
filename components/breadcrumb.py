"""Breadcrumb navigation."""
from __future__ import annotations

from dash import dcc, html


def breadcrumb(items: list[tuple[str, str | None]]) -> html.Div:
    """Render a breadcrumb trail.

    items: list of (label, href) tuples. href=None means the current page.
    """
    children = []
    for i, (label, href) in enumerate(items):
        if i > 0:
            children.append(html.Span("\u203a", className="breadcrumb__sep"))
        if href is not None:
            children.append(dcc.Link(label, href=href, className="breadcrumb__link"))
        else:
            children.append(html.Span(label, className="breadcrumb__current"))
    return html.Nav(children=children, className="breadcrumb")
