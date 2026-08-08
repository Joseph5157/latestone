"""
Centralized metric metadata.

Single source of truth for metric presentation (label, unit, precision,
chart type, display order) and for KPI/aggregation semantics. Services
dispatch on `aggregation`; components read presentation fields only.
Nothing outside this module may branch on a specific metric key.

DEVELOPMENT DISPLAY UNITS. Every unit below is a development display unit
chosen so the dashboard reads plausibly. Actual client units and metric
definitions must be mapped here when the real database/schema is available.

No warning/critical thresholds are defined. Thresholds are deliberately
absent until confirmed by the client.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Aggregation(str, Enum):
    """How a metric's period KPIs are computed."""

    STATISTICS = "statistics"  # Current / Minimum / Maximum / Average
    DELTA = "delta"            # Current meter value / Period change = last - first


@dataclass(frozen=True)
class MetricConfig:
    key: str
    label: str
    unit: str          # development display unit; "" for dimensionless
    precision: int     # decimal places for display
    chart_type: str
    display_order: int
    aggregation: Aggregation


METRICS: tuple[MetricConfig, ...] = (
    MetricConfig("temperature", "Temperature", "°C", 1, "line", 1, Aggregation.STATISTICS),
    MetricConfig("voltage", "Voltage", "kV", 2, "line", 2, Aggregation.STATISTICS),
    MetricConfig("current", "Current", "A", 1, "line", 3, Aggregation.STATISTICS),
    MetricConfig("active_power", "Active Power", "MW", 2, "line", 4, Aggregation.STATISTICS),
    MetricConfig("reactive_power", "Reactive Power", "MVAr", 2, "line", 5, Aggregation.STATISTICS),
    MetricConfig("power_factor", "Power Factor", "", 3, "line", 6, Aggregation.STATISTICS),
    MetricConfig("frequency", "Frequency", "Hz", 2, "line", 7, Aggregation.STATISTICS),
    # Cumulative meter: period KPI is last - first, never average/min/max.
    MetricConfig("energy", "Energy", "MWh", 1, "line", 8, Aggregation.DELTA),
)

METRIC_KEYS: tuple[str, ...] = tuple(m.key for m in METRICS)
DEFAULT_METRIC_KEY: str = METRICS[0].key

_BY_KEY: dict[str, MetricConfig] = {m.key: m for m in METRICS}


def get_metric(key: str) -> MetricConfig | None:
    return _BY_KEY.get(key)


def ordered_metrics() -> list[MetricConfig]:
    return sorted(METRICS, key=lambda m: m.display_order)


def format_value(metric: MetricConfig, value: float | None) -> str:
    """Format a value for display, or an em dash when absent."""
    if value is None:
        return "—"
    rendered = f"{value:.{metric.precision}f}"
    return f"{rendered} {metric.unit}" if metric.unit else rendered
