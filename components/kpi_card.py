"""Reusable KPI card component.

This is the ONLY component that branches on aggregation, and it branches
once — on MetricConfig.aggregation, never on a metric key.
"""
from __future__ import annotations

from datetime import timedelta

from dash import html

from components.freshness_badge import format_last_reading
from config.metrics import Aggregation, format_value
from services.monitoring_service import DeltaStatus, MetricView


def kpi_card(
    label: str,
    value: str,
    secondary: str | None = None,
    card_id: str | None = None,
    accent: bool = False,
):
    """Label, value, and one compact line of real context.

    There is deliberately no `state` parameter. The spec sketches one for a
    future threshold layer, but adding it now invites a fabricated `Normal`
    against values nobody has validated — and no client electrical thresholds
    exist. `MonitoringCondition` stays UNKNOWN until they do.

    `secondary` is always rendered, empty when there is nothing to say, so the
    row keeps a single height instead of stepping.
    """
    classes = "kpi-card kpi-card--accent" if accent else "kpi-card"
    extra_props = {"id": card_id} if card_id is not None else {}
    return html.Div(
        className=classes,
        children=[
            html.Div(label, className="kpi-card__label"),
            html.Div(value, className="kpi-card__value"),
            html.Div(secondary or "", className="kpi-card__secondary"),
        ],
        **extra_props,
    )


def _at(timestamp, dated: bool = False, timezone_label: str | None = "UTC") -> str:
    """When an extreme occurred: `at 13:30 UTC`, or `at 22 Jul 13:30 UTC`.

    Time alone is ambiguous the moment the period spans more than a day — over
    30 days "at 01:30 UTC" names 30 different instants. The caller decides based
    on the span of the data actually shown, not on the selected period, so a
    custom range gets it right too.
    """
    if not timestamp:
        return ""
    fmt = "%d %b %H:%M" if dated else "%H:%M"
    suffix = f" {timezone_label}" if timezone_label else ""
    return f"at {timestamp.strftime(fmt)}{suffix}"


def _spans_more_than_a_day(series) -> bool:
    if len(series) < 2:
        return False
    return (series[-1].timestamp - series[0].timestamp) > timedelta(hours=24)


def kpi_row(
    view: MetricView,
    period_label: str | None = None,
    timestamp_timezone_label: str | None = "UTC",
):
    """KPI cards for one metric.

    This is the ONLY component that branches on aggregation, and it branches
    once — on MetricConfig.aggregation, never on a metric key.

    Secondary lines carry context derived from the data actually shown — when an
    extreme occurred, how many samples the period holds, the freshness of the
    latest reading. None of it is a threshold judgement.
    """
    metric = view.metric
    dated = _spans_more_than_a_day(view.series)

    current_secondary = format_last_reading(
        view.last_updated, view.age, timezone_label=timestamp_timezone_label
    )
    cards = [
        kpi_card(
            "Current",
            format_value(metric, view.current),
            secondary=current_secondary,
            accent=True,
        )
    ]

    if metric.aggregation is Aggregation.DELTA:
        # A cumulative meter's period change is only a number while the meter is
        # monotonic. The two ways it can be unknown get different explanations:
        # "the meter reset" and "we have too few readings" are not the same
        # thing, and one em dash for both tells the operator nothing.
        status = view.period_change_status
        if status is DeltaStatus.DISCONTINUITY:
            value_text = format_value(metric, None)
            secondary = "Meter discontinuity in this period"
        elif status is DeltaStatus.INSUFFICIENT_DATA:
            value_text = format_value(metric, None)
            secondary = "Not enough readings in this period"
        else:
            value_text = format_value(metric, view.period_change)
            secondary = period_label or ""
        cards.append(kpi_card("Period Change", value_text, secondary=secondary))
    else:
        cards.append(
            kpi_card("Minimum", format_value(metric, view.minimum),
                     secondary=_at(view.min_at, dated, timestamp_timezone_label))
        )
        cards.append(
            kpi_card("Maximum", format_value(metric, view.maximum),
                     secondary=_at(view.max_at, dated, timestamp_timezone_label))
        )
        count = view.sample_count
        cards.append(
            kpi_card("Average", format_value(metric, view.average),
                     secondary=f"{count} readings" if count else "")
        )

    return html.Div(className="kpi-row", children=cards)
