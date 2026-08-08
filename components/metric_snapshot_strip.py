"""Metric snapshot strip — 8-tile multi-metric overview."""
from __future__ import annotations

from dash import dcc, html

from config.metrics import format_value, ordered_metrics
from components.freshness_badge import freshness_badge
from routes import device_href
from services.monitoring_service import MetricSnapshot


def snapshot_tile(
    snapshot: MetricSnapshot,
    is_active: bool,
    device_id: str,
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> html.Div:
    """Single metric tile with value and freshness indicator.

    The link carries the active period through `device_href`; building it by
    hand here previously dropped it, so switching metric from a 7d/30d/custom
    view silently snapped the dashboard back to 24h.
    """
    metric = snapshot.metric
    active_class = "snapshot-tile--active" if is_active else ""
    href = device_href(
        device_id,
        metric_key=metric.key,
        period=period,
        start=custom_start,
        end=custom_end,
    )

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
    period: str | None = None,
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> html.Div:
    """8-tile strip in display order, marking the active metric."""
    tiles = [
        snapshot_tile(
            s, s.metric.key == active_metric_key, device_id,
            period=period, custom_start=custom_start, custom_end=custom_end,
        )
        for s in snapshots
    ]
    return html.Div(children=tiles, className="metric-snapshot-strip")
