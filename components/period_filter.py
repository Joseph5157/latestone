"""Time period filter control (24h / 7d / 30d / custom)."""
from __future__ import annotations

from dash import dcc, html

PERIOD_OPTIONS = [
    {"label": "24 Hours", "value": "24h"},
    {"label": "7 Days", "value": "7d"},
    {"label": "30 Days", "value": "30d"},
    {"label": "Custom", "value": "custom"},
]


def period_filter(id_prefix: str = ""):
    return html.Div(
        className="period-filter",
        children=[
            dcc.RadioItems(
                id=f"{id_prefix}period-radio",
                options=PERIOD_OPTIONS,
                value="24h",
                className="period-filter__options",
                inputClassName="period-filter__input",
                labelClassName="period-filter__label",
            ),
            html.Div(
                id=f"{id_prefix}custom-range-container",
                className="period-filter__custom",
                style={"display": "none"},
                children=[
                    dcc.DatePickerRange(
                        id=f"{id_prefix}custom-date-range",
                        display_format="YYYY-MM-DD",
                    ),
                ],
            ),
        ],
    )
