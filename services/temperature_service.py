"""
Temperature service.

Owns:
- Conversion of raw varchar timestamp/temperature strings into typed values.
- KPI calculations (current/min/max/average) for a selected period.
- Warning/status determination against the configurable demo threshold.

The UI layer calls this module only; it never talks to the repository or
parses raw strings itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from config.settings import demo_device, warning_settings
from repositories.temperature_repository import (
    InvalidIdentifierError,
    RawReading,
    UnknownDeviceError,
    get_all_readings,
    get_latest_reading,
    get_recent_readings,
)

# Documented assumption - see db/seed.py and DATABASE.md.
TIMESTAMP_FORMAT = "%y/%m/%d,%H:%M"


class Status(str, Enum):
    NORMAL = "Normal"
    WARNING = "Warning"
    NO_DATA = "No data"


class TemperatureParseError(ValueError):
    """Raised when a stored value cannot be converted to a typed reading."""


@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    temperature_c: float


@dataclass(frozen=True)
class Kpis:
    current: float | None
    minimum: float | None
    maximum: float | None
    average: float | None
    status: Status
    last_updated: datetime | None


class Period(str, Enum):
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"
    CUSTOM = "custom"


def parse_reading(raw: RawReading) -> Reading | None:
    """Convert a raw reading to typed values.

    Returns None (rather than raising) for malformed individual rows, so a
    single bad row doesn't take down the whole chart/table - callers should
    log/skip these rather than crash the UI.
    """
    try:
        ts = datetime.strptime(raw.timestamp_raw.strip(), TIMESTAMP_FORMAT)
    except (ValueError, AttributeError):
        return None

    try:
        temp = float(raw.temperature_raw.strip())
    except (ValueError, AttributeError):
        return None

    return Reading(timestamp=ts, temperature_c=temp)


def _parse_all(raws: list[RawReading]) -> list[Reading]:
    parsed = [parse_reading(r) for r in raws]
    return [r for r in parsed if r is not None]


def _period_start(period: Period, now: datetime) -> datetime | None:
    if period == Period.LAST_24H:
        return now - timedelta(hours=24)
    if period == Period.LAST_7D:
        return now - timedelta(days=7)
    if period == Period.LAST_30D:
        return now - timedelta(days=30)
    return None  # CUSTOM handled separately by caller


def get_status(temperature_c: float | None) -> Status:
    if temperature_c is None:
        return Status.NO_DATA
    if temperature_c > warning_settings.threshold_celsius:
        return Status.WARNING
    return Status.NORMAL


def get_trend_series(
    period: Period,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> list[Reading]:
    """Return the parsed, time-ordered series for the selected period."""
    all_readings = _parse_all(
        get_all_readings(demo_device.transformer, demo_device.device)
    )
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

    return [r for r in all_readings if start <= r.timestamp <= (end or start)]


def get_kpis(
    period: Period,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> Kpis:
    """Compute KPI cards for the selected period.

    'Current' is always the latest available reading overall (not bounded
    by the period), per UI_SPEC.md. Min/max/average apply to the period.
    """
    latest_raw = get_latest_reading(demo_device.transformer, demo_device.device)
    latest = parse_reading(latest_raw) if latest_raw else None

    series = get_trend_series(period, custom_start, custom_end)

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


def get_recent_readings_typed(limit: int = 50) -> list[Reading]:
    raws = get_recent_readings(demo_device.transformer, demo_device.device, limit=limit)
    return _parse_all(raws)
