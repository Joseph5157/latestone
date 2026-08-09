"""Metric snapshot strip — 8-tile multi-metric overview."""
from __future__ import annotations

from dash import dcc, html

from config.metrics import MetricConfig, format_value, ordered_metrics
from components.freshness_badge import freshness_badge
from routes import device_href
from services.monitoring_service import DeltaResult, MetricView


def direction_text(metric: MetricConfig, change: DeltaResult) -> str:
    """Signed change against the period start, or an em dash when unknown.

    The arrow carries the direction and the number carries the magnitude, so a
    fall reads "▼ 0.31 kV" rather than "▼ -0.31 kV" — one sign, not two.

    A cumulative meter whose delta is indeterminate shows the dash rather than a
    negative, which would read as generation.
    """
    if not change.is_known or change.value is None:
        return "—"
    if change.value > 0:
        return f"▲ +{format_value(metric, change.value)}"
    if change.value < 0:
        return f"▼ {format_value(metric, abs(change.value))}"
    return format_value(metric, change.value)


def snapshot_tile(
    snapshot: MetricView,
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
                    # Always rendered, em dash when unknown, so every tile keeps
                    # one height — the strip feeds the §6.8 chart-top budget and
                    # a stepping row would push the chart down.
                    html.Div(
                        direction_text(metric, snapshot.change),
                        className="snapshot-tile__direction",
                    ),
                    freshness_badge(snapshot.freshness),
                    html.Div(className="snapshot-tile__condition"),
                ],
            )
        ],
    )


def metric_snapshot_strip(
    snapshots: list[MetricView],
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
