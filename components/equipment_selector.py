"""Cross-plant equipment selector — cascading Plant -> Transformer -> Device.

Mounted **once, in the global app layout**, never inside a page layout.

The callbacks in `callbacks/equipment_selector.py` fire on auth and on every
cascade change, so their targets have to exist no matter which route is
rendered. A page-scoped selector is what produced the nonexistent-Output
`ReferenceError` documented as finding 2 in docs/CODE_AUDIT.md. The shell is
therefore always in the DOM and merely hidden on the login route.
"""
from __future__ import annotations

from dash import dcc, html

SHELL_ID = "equipment-selector-shell"
PLANT_ID = "equip-plant"
TRANSFORMER_ID = "equip-transformer"
DEVICE_ID = "equip-device"

HIDDEN_STYLE = {"display": "none"}


def equipment_selector() -> html.Div:
    """The three dropdowns. Options are filled in by callback, never here.

    Rendering starts empty so that no hierarchy query runs while the login
    page is on screen.
    """
    return html.Div(
        className="hierarchy-selector",
        children=[
            dcc.Dropdown(
                id=PLANT_ID,
                options=[],
                placeholder="Plant...",
                searchable=True,
                className="hierarchy-selector__field",
            ),
            dcc.Dropdown(
                id=TRANSFORMER_ID,
                options=[],
                placeholder="Transformer...",
                searchable=True,
                disabled=True,
                className="hierarchy-selector__field",
            ),
            dcc.Dropdown(
                id=DEVICE_ID,
                options=[],
                placeholder="Device...",
                searchable=True,
                disabled=True,
                className="hierarchy-selector__field",
            ),
        ],
    )


def equipment_selector_shell() -> html.Div:
    """Global wrapper whose `style` the auth callback toggles.

    Starts hidden: the first paint is always the login page.
    """
    return html.Div(
        id=SHELL_ID,
        className="equipment-selector-bar",
        style=dict(HIDDEN_STYLE),
        children=[
            html.Span("Jump to equipment", className="equipment-selector-bar__label"),
            equipment_selector(),
        ],
    )
