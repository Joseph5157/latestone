"""Temperature-only UI adapter for an explicitly supplied raw RTL UID."""
from __future__ import annotations

from datetime import datetime, timedelta

from config.metrics import get_metric
from repositories.rtl_temperature_repository import RTLTemperatureRepository, RTLTemperatureRepositoryError
from services.monitoring_service import DeltaResult, DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading


class RTLTemperatureUnavailable(RuntimeError):
    """RTL cannot supply this requested temperature view; never use PG fallback."""


def get_temperature_view(device_uid: int, period: str, custom_start: datetime | None = None, custom_end: datetime | None = None) -> MetricView:
    """Fetch raw latest then a bounded raw history, preserving naive source time."""
    try:
        latest = RTLTemperatureRepository().get_latest_temperature(device_uid)
        if latest is None or latest.reading_time is None:
            return _empty()
        end = custom_end.replace(tzinfo=None) if custom_end else latest.reading_time
        spans = {"24h": timedelta(days=1), "7d": timedelta(days=7), "30d": timedelta(days=30)}
        start = custom_start.replace(tzinfo=None) if custom_start else end - spans.get(period, timedelta(days=1))
        rows = RTLTemperatureRepository().get_temperature_range(device_uid, start, end)
    except RTLTemperatureRepositoryError as exc:
        raise RTLTemperatureUnavailable("RTL temperature source is unavailable") from exc
    series = [Reading(r.reading_time, float(r.temperature)) for r in rows if r.reading_time is not None]
    if not series:
        return _empty(last_updated=latest.reading_time, start=start, end=end)
    values = [r.value for r in series]
    return MetricView(get_metric("temperature"), float(latest.temperature), min(values), max(values), sum(values) / len(values), None, DeltaStatus.INSUFFICIENT_DATA, series, latest.reading_time, Freshness.NO_DATA, MonitoringCondition.UNKNOWN, True, DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA), start, end)


def _empty(last_updated=None, start=None, end=None) -> MetricView:
    return MetricView(get_metric("temperature"), None, None, None, None, None, DeltaStatus.INSUFFICIENT_DATA, [], last_updated, Freshness.NO_DATA, MonitoringCondition.UNKNOWN, False, DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA), start, end)
