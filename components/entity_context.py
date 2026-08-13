"""Entity context — static label/value pairs for a Plant or Transformer
header area (Country, Primary fuel, Capacity, Transformer count, ...).

UI-ready values only: this component does not know about `PlantRecord` /
`TransformerRecord` or any repository type — a callback formats whatever it
has into (label, value) pairs before this ever sees them. A sibling of
`pages.device_dashboard`'s page-local `_context_item`/`.equipment-context`,
not a reuse of it: that layout is fixed at five specific fields (Plant,
Transformer, Device, Status, Last data) and its CSS carries positional rules
(`:nth-child(3)`, `:last-child`) tuned to that exact order, which would
misapply to a Plant/Transformer field list of different length and order.
"""
from __future__ import annotations

from dash import html


def _entity_context_item(label: str, value) -> html.Div:
    display = value if value not in (None, "") else "—"
    return html.Div(
        className="entity-context__item",
        children=[
            html.Span(label, className="entity-context__label"),
            html.Span(display, className="entity-context__value"),
        ],
    )


def entity_context(fields: list[tuple[str, object]]) -> html.Div:
    """Row of label/value pairs, in the order given.

    `fields` is already UI-ready. A missing/optional value arrives as `None`
    or `""` and renders as an em dash — the same convention
    `config.metrics.format_value` uses for an absent metric value, so a blank
    field reads consistently wherever it appears on the dashboard.
    """
    return html.Div(
        className="entity-context",
        children=[_entity_context_item(label, value) for label, value in fields],
    )
