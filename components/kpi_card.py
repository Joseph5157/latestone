"""Reusable KPI card component."""
from __future__ import annotations

from dash import html


def kpi_card(label: str, value: str, card_id: str | None = None, accent: bool = False):
    classes = "kpi-card kpi-card--accent" if accent else "kpi-card"
    extra_props = {"id": card_id} if card_id is not None else {}
    return html.Div(
        className=classes,
        children=[
            html.Div(label, className="kpi-card__label"),
            html.Div(value, className="kpi-card__value"),
        ],
        **extra_props,
    )


def kpi_row(current: str, minimum: str, maximum: str, average: str):
    return html.Div(
        className="kpi-row",
        children=[
            kpi_card("Current Temperature", current, accent=True),
            kpi_card("Minimum", minimum),
            kpi_card("Maximum", maximum),
            kpi_card("Average", average),
        ],
    )
