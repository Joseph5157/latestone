"""Metric snapshot strip — 8-tile multi-metric overview."""
from __future__ import annotations

from dash import dcc, html

from config.metrics import format_value, ordered_metrics
from components.freshness_badge import freshness_badge
from services.monitoring_service import MetricSnapshot


def snapshot_tile(snapshot: MetricSnapshot, is_active: bool, device_id: str) -> html.Div:
    """Single metric tile with value and freshness indicator."""
    metric = snapshot.metric
    active_class = "snapshot-tile--active" if is_active else ""
    href = f"/devices/{device_id}?metric={metric.key}"

    return html.Div(
        className=f"snapshot-tile {active_class}",
        children=[
            dcc.Link(
                href=href,
                children=[
                    html.Div(metric.label, className="snapshot-tile__label"),
                    html.Div(
                        format_value(metric, snapshot.current),
                        className="snapshot-tile__value",
                    ),
                    freshness_badge(snapshot.freshness),
                    html.Div(className="snapshot-tile__condition"),
                ],
            )
        ],
    )


def metric_snapshot_strip(
    snapshots: list[MetricSnapshot],
    active_metric_key: str,
    device_id: str,
) -> html.Div:
    """8-tile strip in display order, marking the active metric."""
    tiles = [
        snapshot_tile(s, s.metric.key == active_metric_key, device_id)
        for s in snapshots
    ]
    return html.Div(children=tiles, className="metric-snapshot-strip")
