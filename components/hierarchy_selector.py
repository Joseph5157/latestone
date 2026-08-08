"""Hierarchy selector — cascading Plant -> Transformer -> Device dropdowns."""
from __future__ import annotations

from dash import dcc, html


def hierarchy_selector(
    plants: list[dict],
    transformers: list[dict],
    devices: list[dict],
    plant_id: str | None = None,
    transformer_id: str | None = None,
    device_id: str | None = None,
) -> html.Div:
    """Three searchable dropdowns; transformer/device disabled until parent selected."""
    return html.Div(
        className="hierarchy-selector",
        children=[
            dcc.Dropdown(
                id="hier-plant",
                options=plants,
                value=plant_id,
                placeholder="Select plant...",
                clearable=False,
                searchable=True,
            ),
            dcc.Dropdown(
                id="hier-transformer",
                options=transformers,
                value=transformer_id,
                placeholder="Select transformer...",
                clearable=False,
                searchable=True,
                disabled=plant_id is None,
            ),
            dcc.Dropdown(
                id="hier-device",
                options=devices,
                value=device_id,
                placeholder="Select device...",
                clearable=False,
                searchable=True,
                disabled=transformer_id is None,
            ),
        ],
    )
