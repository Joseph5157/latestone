"""Temperature attribution card — the hottest latest-available temperature
beneath one Plant or Transformer, attributed to the device that recorded it.

Attribution only, never a threshold judgement — no Warning/Critical/Alert
wording exists here or anywhere upstream. See config.metrics.
ATTRIBUTION_METRIC_KEY and services.monitoring_service.hottest_temperature
for why temperature is the one metric this exists for and why a stale
reading is still eligible to be "hottest".
"""
from __future__ import annotations

from dash import dcc, html

from components.freshness_badge import UTC_FORMAT, freshness_badge
from config.metrics import format_value
from routes import device_href
from services.monitoring_service import TemperatureAttribution

LABEL = "Hottest Device"


def _format_absolute(ts) -> str:
    """Absolute UTC only — deliberately not `freshness_badge.format_last_reading`,
    which also needs an `age` timedelta. `TemperatureAttribution` carries
    `reading_ts` alone: computing age here would mean the component deciding
    freshness math (`now - reading_ts`), which belongs to the service
    (`monitoring_service.reading_age`), not the presentation layer. Same
    `UTC_FORMAT` as `format_last_reading` uses, so the two absolute-timestamp
    renderings on a page cannot drift apart in style.
    """
    if ts is None:
        return "No readings"
    return f"{ts.strftime(UTC_FORMAT)} UTC"


def _coverage_text(view: TemperatureAttribution) -> str:
    if view.total_devices == 0:
        return "No active devices"
    return f"{view.reporting_count} of {view.total_devices} devices reporting"


def temperature_attribution(
    view: TemperatureAttribution, *, show_transformer: bool = True
) -> html.Div:
    """Hottest-device attribution card.

    `show_transformer` hides the transformer identity line for a Transformer
    page, whose header already names the transformer being viewed; a Plant
    page keeps it, since a plant spans several transformers. One component
    with a small presentation option, rather than two near-identical
    components for Plant vs Transformer.

    A stale selected reading renders exactly like a fresh one plus its badge
    — it is last-known data, not no data, so nothing here dims or hides the
    card for it.
    """
    if not view.has_data:
        return html.Div(
            className="temperature-attribution temperature-attribution--empty",
            children=[
                html.Div(LABEL, className="temperature-attribution__label"),
                html.Div(
                    "No temperature data available",
                    className="temperature-attribution__empty-message",
                ),
                html.Div(_coverage_text(view), className="temperature-attribution__coverage"),
            ],
        )

    identity_parts = [f"Device {view.device_code}"]
    if show_transformer:
        identity_parts.append(f"Transformer {view.transformer_code}")

    return html.Div(
        className="temperature-attribution",
        children=[
            html.Div(LABEL, className="temperature-attribution__label"),
            html.Div(
                format_value(view.metric, view.value),
                className="temperature-attribution__value",
            ),
            dcc.Link(
                " · ".join(identity_parts),
                className="temperature-attribution__identity",
                href=device_href(view.device_id),
            ),
            freshness_badge(view.freshness),
            html.Div(_coverage_text(view), className="temperature-attribution__coverage"),
            html.Div(
                _format_absolute(view.reading_ts),
                className="temperature-attribution__timestamp",
            ),
        ],
    )
