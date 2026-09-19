"""The redesigned Fleet Overview's data (FO-NEW-1).

"Where is everything and how hot is it?" (redesign D1, D6). One snapshot per
render, built from reads that already exist:

- `hierarchy_service.list_plants` — the plants in scope, for their names;
- `temperature_condition_service.device_temperatures` — every in-scope RTL's
  latest temperature and its condition (ADR-023), with its transformer;
- `repo.max_temperature_report_rows` — the 30-day maximum per transformer,
  the same read the Maximum Temperature report (C-15) uses.

No alarm counts and no electrical metrics (D2, D8): those belong to the
Command Center and the Device page. Scope is resolved once by the caller and
passed in (ADR-004); every read here is narrowed by it.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from repositories import plant_monitoring_repository as repo
from services.device_scope import DeviceScope
from services.hierarchy_service import list_plants
from services.temperature_condition_service import (
    TEMPERATURE_METRIC,
    DeviceTemperature,
    TemperatureCondition,
    TemperatureLimits,
    current_limits,
    device_temperatures,
    hottest,
)

MAX_WINDOW = timedelta(days=30)

#: Conditions that count as "has a temperature problem".
HOT = frozenset({TemperatureCondition.WARNING, TemperatureCondition.CRITICAL})

#: Worst first, for picking a plant's or transformer's headline condition.
_SEVERITY = (
    TemperatureCondition.CRITICAL,
    TemperatureCondition.WARNING,
    TemperatureCondition.NO_RECENT_DATA,
    TemperatureCondition.LIMITS_NOT_SET,
    TemperatureCondition.NORMAL,
)


@dataclass(frozen=True)
class TransformerView:
    transformer_id: str
    transformer_code: str
    max_30d: float | None
    max_30d_at: datetime | None
    max_30d_device_code: str | None
    loggers: tuple[DeviceTemperature, ...]


@dataclass(frozen=True)
class ConditionCounts:
    normal: int = 0
    hot: int = 0
    no_recent_data: int = 0
    limits_not_set: int = 0


@dataclass(frozen=True)
class PlantView:
    plant_id: str
    name: str
    country: str | None
    transformers: tuple[TransformerView, ...]
    hottest: DeviceTemperature | None
    counts: ConditionCounts

    @property
    def logger_count(self) -> int:
        return sum(len(t.loggers) for t in self.transformers)


@dataclass(frozen=True)
class FleetOverview:
    generated_at: datetime
    limits: TemperatureLimits | None
    plants: tuple[PlantView, ...]

    @property
    def transformer_count(self) -> int:
        return sum(len(p.transformers) for p in self.plants)

    @property
    def logger_count(self) -> int:
        return sum(p.logger_count for p in self.plants)


def worst_condition(temps) -> TemperatureCondition | None:
    present = {t.condition for t in temps}
    return next((c for c in _SEVERITY if c in present), None)


def condition_counts(temps) -> ConditionCounts:
    temps = list(temps)
    return ConditionCounts(
        normal=sum(t.condition is TemperatureCondition.NORMAL for t in temps),
        hot=sum(t.condition in HOT for t in temps),
        no_recent_data=sum(t.condition is TemperatureCondition.NO_RECENT_DATA for t in temps),
        limits_not_set=sum(t.condition is TemperatureCondition.LIMITS_NOT_SET for t in temps),
    )


def build_overview(plants, temps, maxima, *, now, limits) -> FleetOverview:
    """Pure assembly. Plants with no in-scope RTL are left out.

    Plants are ordered by name so a plant is always where the reader last saw
    it; the hottest temperature is on every row for a quick scan.
    """
    code_of = {t.device_id: t.device_code for t in temps}
    peak = {m.transformer_id: m for m in maxima}
    by_plant: dict[str, dict[str, list[DeviceTemperature]]] = defaultdict(lambda: defaultdict(list))
    for t in temps:
        by_plant[t.plant_id][t.transformer_id].append(t)

    views = []
    for plant in plants:
        tree = by_plant.get(plant.plant_id)
        if not tree:
            continue
        transformers = []
        for transformer_id, loggers in tree.items():
            m = peak.get(transformer_id)
            transformers.append(TransformerView(
                transformer_id=transformer_id,
                transformer_code=loggers[0].transformer_code,
                max_30d=m.max_temperature if m else None,
                max_30d_at=m.max_reading_at if m else None,
                max_30d_device_code=code_of.get(m.device_id) if m and m.device_id else None,
                loggers=tuple(sorted(loggers, key=lambda t: t.device_code)),
            ))
        transformers.sort(key=lambda t: t.transformer_code)
        everyone = [t for tv in transformers for t in tv.loggers]
        top = hottest(everyone, 1)
        views.append(PlantView(
            plant_id=plant.plant_id,
            name=plant.name,
            country=plant.country,
            transformers=tuple(transformers),
            hottest=top[0] if top else None,
            counts=condition_counts(everyone),
        ))
    views.sort(key=lambda p: (p.name.lower(), p.plant_id))
    return FleetOverview(generated_at=now, limits=limits, plants=tuple(views))


def get_fleet_overview(scope: DeviceScope, *, now: datetime | None = None) -> FleetOverview:
    now = now or datetime.now(timezone.utc)
    temps = device_temperatures(scope, now=now)
    maxima = repo.max_temperature_report_rows(
        temperature_metric=TEMPERATURE_METRIC,
        since=now - MAX_WINDOW,
        until=now,
        allowed_device_ids=scope.device_ids,
    )
    return build_overview(
        list_plants(scope=scope), temps, maxima, now=now, limits=current_limits()
    )


# --------------------------------------------------------------------------
# Filter and sort (POLISH-1). Pure: they narrow and order a snapshot the
# caller already has, so a filter change never means a second definition of
# "hot" or "no recent data".
# --------------------------------------------------------------------------

FILTER_ALL = "all"
FILTER_HOT = "hot"
FILTER_NO_DATA = "no_recent_data"
FILTER_NORMAL = "normal"
SORT_NAME = "name"
SORT_HOTTEST = "hottest"

_FILTERS = {
    FILTER_ALL: lambda p: True,
    FILTER_HOT: lambda p: p.counts.hot > 0,
    FILTER_NO_DATA: lambda p: p.counts.no_recent_data > 0,
    FILTER_NORMAL: lambda p: p.counts.normal == p.logger_count,
}


def available_filters(view: FleetOverview) -> tuple[str, ...]:
    """Hot and Normal need limits: without them no RTL can be either."""
    if view.limits is None:
        return (FILTER_ALL, FILTER_NO_DATA)
    return (FILTER_ALL, FILTER_HOT, FILTER_NO_DATA, FILTER_NORMAL)


def filter_counts(view: FleetOverview) -> dict[str, int]:
    """Plants matching each available filter."""
    return {
        key: sum(1 for p in view.plants if _FILTERS[key](p))
        for key in available_filters(view)
    }


def filter_and_sort(view: FleetOverview, filter_key: str, sort_key: str) -> tuple[PlantView, ...]:
    """The plants to show. An unknown or unavailable filter shows all."""
    if filter_key not in available_filters(view):
        filter_key = FILTER_ALL
    plants = [p for p in view.plants if _FILTERS[filter_key](p)]
    if sort_key == SORT_HOTTEST:
        # Plants with no recent reading go last, still in name order.
        plants.sort(key=lambda p: (p.hottest is None, -(p.hottest.value if p.hottest else 0)))
    return tuple(plants)


# --------------------------------------------------------------------------
# Stat cards (STATS-CARDS-1). Derived from the one snapshot; counts are RTLs,
# not plants, so they never compete with the filter chips' plant counts.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class FleetStats:
    hottest: DeviceTemperature | None
    hottest_plant: str | None
    warning: int
    critical: int
    peak_value: float | None
    peak_at: datetime | None
    peak_device_code: str | None
    peak_plant: str | None
    reporting: int
    total: int


def fleet_stats(view: FleetOverview) -> FleetStats:
    loggers = [(p, t) for p in view.plants for tv in p.transformers for t in tv.loggers]
    top = hottest([t for _p, t in loggers], 1)
    plant_of = {t.device_id: p.name for p, t in loggers}
    peaks = [(p, tv) for p in view.plants for tv in p.transformers if tv.max_30d is not None]
    peak_plant, peak = max(peaks, key=lambda pt: pt[1].max_30d, default=(None, None))
    return FleetStats(
        hottest=top[0] if top else None,
        hottest_plant=plant_of.get(top[0].device_id) if top else None,
        warning=sum(t.condition is TemperatureCondition.WARNING for _p, t in loggers),
        critical=sum(t.condition is TemperatureCondition.CRITICAL for _p, t in loggers),
        peak_value=peak.max_30d if peak else None,
        peak_at=peak.max_30d_at if peak else None,
        peak_device_code=peak.max_30d_device_code if peak else None,
        peak_plant=peak_plant.name if peak_plant else None,
        # Same rule as the Command Center's "N of M RTLs reporting".
        reporting=sum(t.condition is not TemperatureCondition.NO_RECENT_DATA for _p, t in loggers),
        total=len(loggers),
    )


def rtl_condition_counts(view: FleetOverview) -> dict[TemperatureCondition, int]:
    """RTLs per temperature condition across the snapshot (CLICK-FILTER-1's
    stacked bar). Worst first; conditions with no RTL are left out."""
    counts: dict[TemperatureCondition, int] = {}
    for p in view.plants:
        for tv in p.transformers:
            for t in tv.loggers:
                counts[t.condition] = counts.get(t.condition, 0) + 1
    return {c: counts[c] for c in _SEVERITY if counts.get(c)}
