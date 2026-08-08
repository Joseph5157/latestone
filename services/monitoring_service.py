"""
Monitoring service (multi-plant demo).

Mirrors services/temperature_service.py's period/KPI logic but reads from
the consolidated monitoring.readings table via monitoring_repository.
Reuses Reading/Kpis/Period/Status/get_status from temperature_service
rather than redefining them - the KPI math and warning-threshold rule are
identical, only the data source differs. Because the consolidated schema
stores real timestamptz/numeric columns, there is no varchar parsing step
here (contrast with temperature_service.parse_reading).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from repositories.monitoring_repository import (
    Plant,
    RawReading,
    get_all_readings,
    get_latest_reading,
    get_recent_readings,
    list_plants,
)
from services.temperature_service import (
    Kpis,
    Period,
    Reading,
    Status,
    get_status,
)


def _period_start(period: Period, now: datetime) -> datetime | None:
    if period == Period.LAST_24H:
        return now - timedelta(hours=24)
    if period == Period.LAST_7D:
        return now - timedelta(days=7)
    if period == Period.LAST_30D:
        return now - timedelta(days=30)
    return None  # CUSTOM handled separately by caller

__all__ = [
    "Plant",
    "Reading",
    "Kpis",
    "Period",
    "Status",
    "get_status",
    "list_plants",
    "get_trend_series",
    "get_kpis",
    "get_recent_readings_typed",
]


def _to_reading(raw: RawReading) -> Reading:
    return Reading(timestamp=raw.timestamp, temperature_c=raw.value)


def get_trend_series(
    plant_id: str,
    period: Period,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> list[Reading]:
    """Return the parsed, time-ordered series for the selected plant/period."""
    all_readings = [_to_reading(r) for r in get_all_readings(plant_id)]
    if not all_readings:
        return []

    if period == Period.CUSTOM:
        start = custom_start
        end = custom_end
    else:
        latest_ts = max(r.timestamp for r in all_readings)
        start = _period_start(period, latest_ts)
        end = latest_ts

    if start is None:
        return all_readings

    if start.tzinfo is None and all_readings[0].timestamp.tzinfo is not None:
        start = start.replace(tzinfo=all_readings[0].timestamp.tzinfo)
    if end is not None and end.tzinfo is None and all_readings[0].timestamp.tzinfo is not None:
        end = end.replace(tzinfo=all_readings[0].timestamp.tzinfo)

    return [r for r in all_readings if start <= r.timestamp <= (end or start)]


def get_kpis(
    plant_id: str,
    period: Period,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> Kpis:
    """Compute KPI cards for the selected plant/period.

    'Current' is always the latest available reading overall (not bounded
    by the period), matching the single-device demo's behaviour.
    """
    latest_raw = get_latest_reading(plant_id)
    latest = _to_reading(latest_raw) if latest_raw else None

    series = get_trend_series(plant_id, period, custom_start, custom_end)

    if not series:
        return Kpis(
            current=latest.temperature_c if latest else None,
            minimum=None,
            maximum=None,
            average=None,
            status=get_status(latest.temperature_c if latest else None),
            last_updated=latest.timestamp if latest else None,
        )

    temps = [r.temperature_c for r in series]
    current = latest.temperature_c if latest else temps[-1]

    return Kpis(
        current=current,
        minimum=min(temps),
        maximum=max(temps),
        average=sum(temps) / len(temps),
        status=get_status(current),
        last_updated=latest.timestamp if latest else series[-1].timestamp,
    )


def get_recent_readings_typed(plant_id: str, limit: int = 50) -> list[Reading]:
    return [_to_reading(r) for r in get_recent_readings(plant_id, limit=limit)]
