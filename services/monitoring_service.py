"""
Monitoring service — view models, aggregation dispatch and freshness.

Owns the three independent concepts that must never be merged:
- Administrative status (active/inactive) — lives in hierarchy_service
- Data freshness (fresh/stale/no_data) — computed here
- Monitoring condition (normal/warning/critical/unknown) — always UNKNOWN today

Freshness policy comes from config.settings.monitoring, never hard-coded.
This is the only place that branches on MetricConfig.aggregation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from config.metrics import Aggregation, MetricConfig, get_metric, ordered_metrics
from config.settings import monitoring
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import RawReading


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    NO_DATA = "no_data"


class MonitoringCondition(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class Period(str, Enum):
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"
    CUSTOM = "custom"


@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class MetricSnapshot:
    metric: MetricConfig
    current: float | None
    last_updated: datetime | None
    freshness: Freshness
    condition: MonitoringCondition


@dataclass(frozen=True)
class MetricView:
    metric: MetricConfig
    current: float | None
    minimum: float | None
    maximum: float | None
    average: float | None
    period_change: float | None
    series: list[Reading]
    last_updated: datetime | None
    freshness: Freshness
    condition: MonitoringCondition
    has_data: bool


def _now() -> datetime:
    """Indirection so tests can pin the clock."""
    return datetime.now(timezone.utc)


def _align_tz(value: datetime, reference: datetime) -> datetime:
    """Attach the reference's tzinfo to a naive datetime (Dash date pickers
    hand us naive values; stored timestamps are timestamptz)."""
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    return value


def evaluate_freshness(last_updated: datetime | None, now: datetime | None = None) -> Freshness:
    """Data-delivery signal only. NEVER an electrical warning condition."""
    if last_updated is None:
        return Freshness.NO_DATA
    reference = now or _now()
    age = reference - _align_tz(last_updated, reference)
    return (
        Freshness.STALE
        if age > timedelta(minutes=monitoring.stale_after_minutes)
        else Freshness.FRESH
    )


def _current_condition(_view_inputs) -> MonitoringCondition:
    """Placeholder. No client-confirmed thresholds exist, so every metric
    reports UNKNOWN. Wiring this through now means adding real thresholds
    later requires no change to view models, components or callbacks."""
    return MonitoringCondition.UNKNOWN


def _compute_statistics(series: list[Reading]) -> tuple[float | None, float | None, float | None]:
    if not series:
        return None, None, None
    values = [r.value for r in series]
    return min(values), max(values), sum(values) / len(values)


def _compute_delta(series: list[Reading]) -> float | None:
    """Period change for cumulative meters.

    Requires at least TWO readings - a single point has no change. A negative
    result may indicate a counter reset or data-quality condition; it is
    surfaced as-is, with no reset handling at this stage.
    """
    if len(series) < 2:
        return None
    return series[-1].value - series[0].value


def period_start(period: Period, anchor: datetime) -> datetime | None:
    deltas = {
        Period.LAST_24H: timedelta(hours=24),
        Period.LAST_7D: timedelta(days=7),
        Period.LAST_30D: timedelta(days=30),
    }
    delta = deltas.get(period)
    return anchor - delta if delta else None  # CUSTOM handled by the caller


def _build_metric_view(
    metric: MetricConfig,
    latest: RawReading | None,
    series: list[Reading],
    now: datetime,
) -> MetricView:
    minimum = maximum = average = period_change = None
    if metric.aggregation is Aggregation.DELTA:
        period_change = _compute_delta(series)
    else:
        minimum, maximum, average = _compute_statistics(series)

    last_updated = latest.timestamp if latest else None
    return MetricView(
        metric=metric,
        current=latest.value if latest else None,   # latest available, period-independent
        minimum=minimum,
        maximum=maximum,
        average=average,
        period_change=period_change,
        series=series,
        last_updated=last_updated,
        freshness=evaluate_freshness(last_updated, now),
        condition=_current_condition(None),
        has_data=latest is not None,
    )


def _resolve_window(
    period: Period, anchor: datetime | None,
    custom_start: datetime | None, custom_end: datetime | None,
) -> tuple[datetime, datetime] | None:
    """Return the (start, end) window, or None when no window is computable."""
    if period is Period.CUSTOM:
        if custom_start is None or custom_end is None:
            return None
        return custom_start, custom_end
    if anchor is None:
        return None
    start = period_start(period, anchor)
    return (start, anchor) if start else None


def _to_reading(raw: RawReading) -> Reading:
    return Reading(timestamp=raw.timestamp, value=raw.value)


def get_metric_view(
    device_id: str,
    metric_key: str,
    period: Period,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> MetricView | None:
    metric = get_metric(metric_key)
    if metric is None:
        return None

    now = _now()
    latest = repo.get_latest_reading(device_id, metric_key)

    if latest is None:
        return _build_metric_view(metric, None, [], now)

    anchor = _align_tz(latest.timestamp, now)
    window = _resolve_window(period, anchor, custom_start, custom_end)

    if window is None:
        return _build_metric_view(metric, latest, [], now)

    start, end = window
    raw_rows = repo.get_readings_in_range(device_id, metric_key, start, end)
    series = [_to_reading(r) for r in raw_rows]

    return _build_metric_view(metric, latest, series, now)


def get_device_snapshot(device_id: str) -> list[MetricSnapshot]:
    """One batched latest call, one snapshot per metric in display order."""
    now = _now()
    latest_map = repo.get_latest_readings_for_device(device_id)

    snapshots = []
    for metric in ordered_metrics():
        reading = latest_map.get(metric.key)
        snapshots.append(
            MetricSnapshot(
                metric=metric,
                current=reading.value if reading else None,
                last_updated=reading.timestamp if reading else None,
                freshness=evaluate_freshness(reading.timestamp if reading else None, now),
                condition=_current_condition(None),
            )
        )
    return snapshots


def get_device_full_view(
    device_id: str,
    period: Period,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> dict[str, MetricView]:
    """Full view for all metrics: one common dashboard window, per-metric freshness."""
    now = _now()
    latest_map = repo.get_latest_readings_for_device(device_id)

    if not latest_map:
        return {
            m.key: _build_metric_view(m, None, [], now)
            for m in ordered_metrics()
        }

    # Dashboard anchor = latest timestamp across requested metrics
    latest_timestamps = [_align_tz(r.timestamp, now) for r in latest_map.values()]
    anchor = max(latest_timestamps)

    # Resolve one common window
    window = _resolve_window(period, anchor, custom_start, custom_end)

    if window is not None:
        start, end = window
        all_metrics = [m.key for m in ordered_metrics()]
        batched = repo.get_readings_for_device_in_range(device_id, all_metrics, start, end)
    else:
        batched = {}

    views = {}
    for metric in ordered_metrics():
        reading = latest_map.get(metric.key)
        raw_rows = batched.get(metric.key, [])
        series = [_to_reading(r) for r in raw_rows]
        views[metric.key] = _build_metric_view(metric, reading, series, now)

    return views
