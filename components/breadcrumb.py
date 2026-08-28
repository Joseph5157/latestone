"""Breadcrumb navigation.

Structure carries the meaning here, not just the styling. An ordered list is
what tells assistive technology this is a sequence and how far along it you
are; a run of spans reads as four unrelated labels. The separators are
decoration and are hidden, the current step is marked rather than merely
coloured, and the landmark is named because the application renders a second
`<nav>` (the sidebar) on every page.
"""
from __future__ import annotations

from dash import dcc, html


def breadcrumb(items: list[tuple[str, str | None]]) -> html.Nav:
    """Render a breadcrumb trail.

    items: list of (label, href) tuples. href=None means the current page.

    Long labels truncate with an ellipsis rather than wrapping: plant names
    reach "Itaipu Binacional Dam (Paraguay part)", and a trail that rewraps
    onto two lines moves the page header under it. `title` keeps the full
    name reachable on hover for a label that has been cut.
    """
    steps = []
    for i, (label, href) in enumerate(items):
        children = []
        if i > 0:
            # Decoration, not content: without this the deepest trail
            # announces three angle quotation marks between its four labels.
            children.append(
                html.Span("›", className="breadcrumb__sep", **{"aria-hidden": "true"})
            )
        if href is not None:
            children.append(
                dcc.Link(label, href=href, className="breadcrumb__link", title=label)
            )
        else:
            # The current step is not a link — a link to the page you are on
            # is a dead control — and says so to assistive technology.
            children.append(
                html.Span(
                    label,
                    className="breadcrumb__current",
                    title=label,
                    **{"aria-current": "page"},
                )
            )
        steps.append(html.Li(children, className="breadcrumb__item"))

    return html.Nav(
        html.Ol(steps, className="breadcrumb__list"),
        className="breadcrumb",
        **{"aria-label": "Breadcrumb"},
    )
