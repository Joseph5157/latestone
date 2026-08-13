"""Metric Health overview — per-metric reporting/freshness beneath one Plant
or Transformer.

Data health only, never a metric-value aggregate: a tile here never shows a
temperature or voltage number, only how many devices are fresh, stale, or
missing for that metric. See services.monitoring_service.MetricHealth /
metric_health_from_rows for why this is a separate axis from the fleet's
per-device Data Health card.
"""
from __future__ import annotations

from dash import html

from components.freshness_badge import freshness_badge
from services.monitoring_service import Freshness, MetricHealth


def _breakdown_text(item: MetricHealth) -> str:
    """"5 stale · 2 fresh", worst state first — but only when the population
    is actually mixed. A single-state population (all fresh, all stale, or
    all no-data) would just repeat the coverage line below it, so it is
    omitted rather than rendered redundantly.
    """
    parts = []
    if item.no_data_count:
        parts.append(f"{item.no_data_count} no data")
    if item.stale_count:
        parts.append(f"{item.stale_count} stale")
    if item.fresh_count:
        parts.append(f"{item.fresh_count} fresh")
    if len(parts) < 2:
        return ""
    return " · ".join(parts)


def _coverage_text(item: MetricHealth) -> str:
    """Reporting coverage, phrased apart from freshness (§ reporting coverage
    is a separate dimension from freshness — a stale device is still
    reporting)."""
    if item.total_devices == 0:
        return "No active devices"
    if item.freshness is Freshness.FRESH:
        return f"All {item.total_devices} devices reporting"
    return f"{item.reporting_count} of {item.total_devices} devices reporting"


def metric_health_tile(item: MetricHealth) -> html.Div:
    return html.Div(
        className="metric-health-tile",
        children=[
            html.Div(item.metric.label, className="metric-health-tile__label"),
            freshness_badge(item.freshness),
            html.Div(_breakdown_text(item), className="metric-health-tile__breakdown"),
            html.Div(_coverage_text(item), className="metric-health-tile__coverage"),
        ],
    )


def metric_health_overview(items: list[MetricHealth]) -> html.Div:
    """One tile per metric, in the order `items` arrives in.

    The service already returns `ordered_metrics()` order — sorting again
    here would risk drifting from it, so this renders `items` as given rather
    than re-deriving an order from the metric registry. No section heading is
    included, matching `metric_snapshot_strip`/`trend_grid`: the page supplies
    its own heading.
    """
    tiles = [metric_health_tile(item) for item in items]
    return html.Div(children=tiles, className="metric-health-overview")
