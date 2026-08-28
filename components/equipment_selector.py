"""Cross-plant equipment selector — cascading Plant -> Transformer -> Device.

Mounted **once, in the global app layout**, never inside a page layout.

The callbacks in `callbacks/equipment_selector.py` fire on auth and on every
cascade change, so their targets have to exist no matter which route is
rendered. A page-scoped selector is what produced the nonexistent-Output
`ReferenceError` documented as finding 2 in docs/CODE_AUDIT.md. The shell is
therefore always in the DOM and merely hidden on the login route.

Layer 1 (Global Shell): presented as the vertical "Asset Navigator" panel
docked in the app shell's right-hand utility column (see
`components/app_shell.py`) rather than the former full-width bar above it.
Only the surrounding markup/labels and CSS changed — `SHELL_ID`, the three
field ids and every callback in `callbacks/equipment_selector.py` are
untouched, so the cascade and cross-plant navigation behave exactly as
before.
"""
from __future__ import annotations

from dash import dcc, html

SHELL_ID = "equipment-selector-shell"
PLANT_ID = "equip-plant"
TRANSFORMER_ID = "equip-transformer"
DEVICE_ID = "equip-device"

HIDDEN_STYLE = {"display": "none"}


def _field_group(label: str, dropdown: dcc.Dropdown) -> html.Div:
    return html.Div(
        className="hierarchy-selector__group",
        children=[
            html.Span(label, className="hierarchy-selector__group-label"),
            dropdown,
        ],
    )


def equipment_selector() -> html.Div:
    """The three dropdowns, each under its own label. Options are filled in
    by callback, never here.

    Rendering starts empty so that no hierarchy query runs while the login
    page is on screen.
    """
    return html.Div(
        className="hierarchy-selector",
        children=[
            _field_group(
                "Plant",
                dcc.Dropdown(
                    id=PLANT_ID,
                    options=[],
                    placeholder="Plant...",
                    searchable=True,
                    className="hierarchy-selector__field",
                ),
            ),
            _field_group(
                "Transformer",
                dcc.Dropdown(
                    id=TRANSFORMER_ID,
                    options=[],
                    placeholder="Transformer...",
                    searchable=True,
                    disabled=True,
                    className="hierarchy-selector__field",
                ),
            ),
            # Labelled "RTL Device" per the approved Asset Navigator copy —
            # the id, options and cascade behaviour are still the plain
            # device selector `callbacks/equipment_selector.py` drives.
            _field_group(
                "RTL Device",
                dcc.Dropdown(
                    id=DEVICE_ID,
                    options=[],
                    placeholder="Device...",
                    searchable=True,
                    disabled=True,
                    className="hierarchy-selector__field",
                ),
            ),
        ],
    )


def equipment_selector_shell() -> html.Div:
    """Global wrapper whose `style` the auth callback toggles.

    Starts hidden: the first paint is always the login page.
    """
    return html.Div(
        id=SHELL_ID,
        className="asset-navigator",
        style=dict(HIDDEN_STYLE),
        children=[
            html.H2("Asset Navigator", className="asset-navigator__title"),
            equipment_selector(),
        ],
    )
