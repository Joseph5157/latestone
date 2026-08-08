"""Reusable KPI card component.

This is the ONLY component that branches on aggregation, and it branches
once — on MetricConfig.aggregation, never on a metric key.
"""
from __future__ import annotations

from dash import html

from config.metrics import Aggregation, format_value
from services.monitoring_service import MetricView


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


def kpi_row(view: MetricView):
    """KPI cards for one metric.

    This is the ONLY component that branches on aggregation, and it branches
    once — on MetricConfig.aggregation, never on a metric key.
    """
    metric = view.metric
    cards = [kpi_card("Current", format_value(metric, view.current), accent=True)]

    if metric.aggregation is Aggregation.DELTA:
        cards.append(kpi_card("Period Change", format_value(metric, view.period_change)))
    else:
        cards.append(kpi_card("Minimum", format_value(metric, view.minimum)))
        cards.append(kpi_card("Maximum", format_value(metric, view.maximum)))
        cards.append(kpi_card("Average", format_value(metric, view.average)))

    return html.Div(className="kpi-row", children=cards)
