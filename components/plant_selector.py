"""Plant/location selector control for the multi-plant monitoring demo."""
from __future__ import annotations

from dash import dcc, html

from services.monitoring_service import Plant


def plant_options(plants: list[Plant]) -> list[dict]:
    return [
        {"label": f"{p.name} ({p.country})", "value": p.plant_id}
        for p in plants
    ]


def plant_selector(plants: list[Plant]):
    options = plant_options(plants)
    default_value = options[0]["value"] if options else None
    return html.Div(
        className="plant-selector",
        children=[
            html.Label("Location", className="plant-selector__label", htmlFor="plant-dropdown"),
            dcc.Dropdown(
                id="plant-dropdown",
                options=options,
                value=default_value,
                clearable=False,
                searchable=True,
                className="plant-selector__dropdown",
            ),
        ],
    )
