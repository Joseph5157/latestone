"""Equipment context strip — compact device identity display."""
from __future__ import annotations

from dash import html


def equipment_context(
    plant_name: str,
    transformer_code: str,
    device_code: str,
    admin_status: str,
    last_updated_text: str,
) -> html.Div:
    """Compact strip showing device identity and administrative status."""
    items = [
        ("Plant", plant_name),
        ("Transformer", transformer_code),
        ("Device", device_code),
        ("Status", admin_status),
        ("Last data", last_updated_text),
    ]
    return html.Div(
        className="equipment-context",
        children=[
            html.Div(
                className="equipment-context__item",
                children=[
                    html.Span(label, className="equipment-context__label"),
                    html.Span(value, className="equipment-context__value"),
                ],
            )
            for label, value in items
        ],
    )
