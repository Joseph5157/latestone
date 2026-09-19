"""Temperature condition per RTL against Administrator-configured limits
(TEMP-CONDITION-1, ADR-023).

The one place that answers "what is this RTL's temperature condition now?".
Pages read `device_temperatures()`; none compares a temperature against a
limit itself.

    latest temperature  --+
    stored limits        --+--> classify() --> TemperatureCondition
    freshness threshold --+

The limits are whatever an Administrator stored through
`temperature_threshold_service` (migration 011). They are NOT Eskom-confirmed
values, so every surface that shows a condition carries `LIMIT_SOURCE_NOTE`.
Nothing is persisted and no event is raised: high temperature is a derived
condition here, not an alarm (`event_semantics` still has no
`high_temperature` entry, ADR-001).

Order of the rules matters and is deliberate:

1. No reading, or a reading older than the freshness threshold
   -> NO_RECENT_DATA. An old reading says nothing about now, so it is never
   Normal — and never Critical either, however hot it was.
2. No limits configured -> LIMITS_NOT_SET, never Normal.
3. Otherwise compare with `>=` at each limit, in `Decimal`, the stored
   column's own type, so a float can never land on the wrong side of a
   limit it displays as equal to.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Iterable

from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope
from services.freshness_threshold_service import effective_stale_after_minutes
from services.temperature_threshold_service import get_current_threshold_config

TEMPERATURE_METRIC = "temperature"

#: Shown beside any temperature condition (ADR-023).
LIMIT_SOURCE_NOTE = "Limits set by an administrator"


class TemperatureCondition(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    NORMAL = "normal"
    NO_RECENT_DATA = "no_recent_data"
    LIMITS_NOT_SET = "limits_not_set"


CONDITION_LABELS: dict[TemperatureCondition, str] = {
    TemperatureCondition.CRITICAL: "Critical",
    TemperatureCondition.WARNING: "Warning",
    TemperatureCondition.NORMAL: "Normal",
    TemperatureCondition.NO_RECENT_DATA: "No recent data",
    TemperatureCondition.LIMITS_NOT_SET: "Limits not set",
}


@dataclass(frozen=True)
class TemperatureLimits:
    warning_c: Decimal
    critical_c: Decimal


@dataclass(frozen=True)
class DeviceTemperature:
    """One RTL's latest temperature and its condition, with its place in the tree."""

    plant_id: str
    transformer_id: str
    transformer_code: str
    device_id: str
    device_code: str
    value: float | None
    reading_ts: datetime | None
    condition: TemperatureCondition


def classify(
    value: float | None,
    reading_ts: datetime | None,
    *,
    now: datetime,
    limits: TemperatureLimits | None,
    stale_after: timedelta,
) -> TemperatureCondition:
    """Pure. See the module docstring for the rule order."""
    if value is None or reading_ts is None or now - reading_ts > stale_after:
        return TemperatureCondition.NO_RECENT_DATA
    if limits is None:
        return TemperatureCondition.LIMITS_NOT_SET
    reading = Decimal(str(value))
    if reading >= limits.critical_c:
        return TemperatureCondition.CRITICAL
    if reading >= limits.warning_c:
        return TemperatureCondition.WARNING
    return TemperatureCondition.NORMAL


def current_limits() -> TemperatureLimits | None:
    """The stored limit pair, or None when an Administrator has set none."""
    state = get_current_threshold_config()
    if state is None:
        return None
    return TemperatureLimits(warning_c=state.warning_c, critical_c=state.critical_c)


def device_temperatures(
    scope: DeviceScope, *, now: datetime | None = None
) -> list[DeviceTemperature]:
    """Every active RTL in `scope` with its latest temperature and condition.

    Three reads, once per call: limits, freshness threshold, and one
    fleet-wide bounded-seek temperature read (ADR-014). Resolve `scope` once
    per render and pass it in (ADR-004).
    """
    now = now or datetime.now(timezone.utc)
    limits = current_limits()
    stale_after = timedelta(minutes=effective_stale_after_minutes())
    rows = repo.latest_metric_readings(
        TEMPERATURE_METRIC, fleet=True, allowed_device_ids=scope.device_ids
    )
    return [
        DeviceTemperature(
            plant_id=r.plant_id,
            transformer_id=r.transformer_id,
            transformer_code=r.transformer_code,
            device_id=r.device_id,
            device_code=r.device_code,
            value=r.value,
            reading_ts=r.reading_ts,
            condition=classify(
                r.value, r.reading_ts, now=now, limits=limits, stale_after=stale_after
            ),
        )
        for r in rows
    ]


def hottest(temps: Iterable[DeviceTemperature], n: int) -> list[DeviceTemperature]:
    """Up to `n` RTLs with a recent reading, highest temperature first.

    RTLs with no recent data are left out: their last value describes the
    past, and "hottest right now" is a claim about now.
    """
    recent = [
        t for t in temps
        if t.value is not None and t.condition is not TemperatureCondition.NO_RECENT_DATA
    ]
    return sorted(recent, key=lambda t: (-t.value, t.device_id))[:n]
