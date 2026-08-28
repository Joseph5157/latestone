"""The shared card surface and its header anatomy.

Five surfaces had implemented the same idea independently and disagreed on
it: `fleet-condition__card` (8px radius, a 3%-alpha shadow, 16px padding),
`needs-attention` and `unassigned-rtls` (8px, no shadow, 12/16px),
`asset-navigator` (6px, 16px) and `kpi-card` (6px, 8/16px). Only the border
and background already agreed. The surface now lives in one CSS rule driven
by a single `--card-spacing`, so a sixth card cannot invent a sixth
treatment.

Only the header is a component: the body of a card is whatever the calling
component already renders, and wrapping that in a generic container would
buy nothing while adding a div to every tree. What the header buys is the
action slot — Fleet Overview had nowhere to put a card-level action, so
"View full fleet" lived inside a bespoke summary row in Needs Attention.
"""
from __future__ import annotations

from dash import html


def card_header(
    title: str,
    description: str | None = None,
    *,
    action=None,
    heading=html.H3,
) -> html.Div:
    """Title, optional description, optional action pinned top-right.

    `heading` is the caller's choice rather than a fixed level: a card is a
    surface, not a position in the document outline, and the page owns that.
    """
    children = [html.Div(title, className="card__title") if heading is None
                else heading(title, className="card__title")]
    if description:
        children.append(html.P(description, className="card__description"))
    if action is not None:
        children.append(html.Div(action, className="card__action"))
    return html.Div(className="card__header", children=children)
