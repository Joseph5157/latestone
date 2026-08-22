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

from config.metrics import (
    ATTRIBUTION_METRIC_KEY,
    SOURCE_RESOLUTION_MINUTES,
    Aggregation,
    MetricConfig,
    get_metric,
    ordered_metrics,
)
from config.settings import monitoring
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import DeviceMetricReading, RawReading
from services.device_scope import DeviceScope


class Freshness(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    NO_DATA = "no_data"


#: Worst-of ordering. A rollup reports the least reassuring state present, so a
#: single dead feed cannot hide behind healthy siblings.
_FRESHNESS_SEVERITY = {Freshness.FRESH: 0, Freshness.STALE: 1, Freshness.NO_DATA: 2}

_FRESHNESS_LABELS = {
    Freshness.FRESH: "Fresh",
    Freshness.STALE: "Stale",
    Freshness.NO_DATA: "No data",
}


class DeltaStatus(str, Enum):
    """Why a cumulative-meter delta is, or is not, a number."""

    OK = "ok"
    INSUFFICIENT_DATA = "insufficient_data"
    DISCONTINUITY = "discontinuity"


@dataclass(frozen=True)
class DeltaResult:
    value: float | None
    status: DeltaStatus

    @property
    def is_known(self) -> bool:
        return self.status is DeltaStatus.OK


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


#: Bin widths energy may be aggregated into, coarsest last.
BIN_LADDER: tuple[timedelta, ...] = (
    timedelta(minutes=30), timedelta(hours=1), timedelta(hours=2),
    timedelta(hours=3), timedelta(hours=6), timedelta(hours=12),
    timedelta(days=1), timedelta(days=7),
)

#: Upper bound on bars in one chart. At two grid columns a cell is ~570 px,
#: which gives ~12 px per bar at this count — legible. One target serves the
#: primary chart and the cells alike, so the same metric never shows two
#: different bar widths on one screen.
TARGET_BARS: int = 48


def choose_bin(span: timedelta) -> timedelta:
    """Smallest bin whose bar count fits the target, so density is as high as
    legibility allows.

    Driven by duration, never by period name: a 3-day and a 90-day custom range
    must not share a bin width. Rungs finer than the source resolution are
    excluded rather than clamped, so the floor is a property of the data.
    """
    floor = timedelta(minutes=SOURCE_RESOLUTION_MINUTES)
    usable = [b for b in BIN_LADDER if b >= floor] or [BIN_LADDER[-1]]
    for candidate in usable:
        if span / candidate <= TARGET_BARS:
            return candidate
    return usable[-1]


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
    #: Why `period_change` is or is not a number. A bare None cannot tell
    #: "too few readings" apart from "the meter reset".
    period_change_status: DeltaStatus
    series: list[Reading]
    last_updated: datetime | None
    freshness: Freshness
    condition: MonitoringCondition
    has_data: bool
    #: Change against the start of the selected period, for the tile direction
    #: line. Defaults to unknown so test factories need not restate it; a test
    #: asserts the service always computes it, so production never relies on
    #: the default.
    change: DeltaResult = DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)
    #: The requested window, and the meter value that opens it. Carried on the
    #: view so the chart bins over exactly the window the KPI totals, opened by
    #: the same reading. Two different bases would make the bars stop summing to
    #: the KPI, silently.
    window_start: datetime | None = None
    window_end: datetime | None = None
    prime: Reading | None = None

    #: Presentation-ready KPI context, derived from `series`/`last_updated`
    #: on access rather than stored: kpi_card.py used to compute these itself
    #: by calling `series_context`/`reading_age` directly, which put a data
    #: decision inside a "renders" layer. Properties keep `series_context`/
    #: `reading_age` as the one authoritative implementation and require no
    #: change to any existing `MetricView(...)` construction site — a stored
    #: field would have needed one in every test that builds a view by hand.

    @property
    def min_at(self) -> datetime | None:
        """When `minimum` occurred, for the KPI row's secondary line."""
        return series_context(self.series)["min_at"]

    @property
    def max_at(self) -> datetime | None:
        """When `maximum` occurred, for the KPI row's secondary line."""
        return series_context(self.series)["max_at"]

    @property
    def sample_count(self) -> int:
        """How many readings the Average KPI is drawn from."""
        return series_context(self.series)["count"]

    @property
    def age(self) -> timedelta | None:
        """How old `last_updated` is right now, for the Current KPI's
        "X ago" text. Live clock, same as before this moved here."""
        return reading_age(self.last_updated)


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


@dataclass(frozen=True)
class FreshnessRollup:
    """One level of the metric -> device -> plant -> fleet freshness chain.

    Keeps the counts, not just the winning state: "Stale" alone tells an
    operator nothing about whether one feed or every feed stopped.
    """

    state: Freshness
    counts: dict[Freshness, int]
    total: int

    @property
    def affected(self) -> int:
        """How many children are in the reported state (0 when all are fresh)."""
        if self.state is Freshness.FRESH:
            return 0
        return self.counts.get(self.state, 0)

    def label(self, noun: str = "") -> str:
        """Display text. Fresh needs no qualifier; anything else must say how many."""
        text = _FRESHNESS_LABELS[self.state]
        if self.state is Freshness.FRESH:
            return text
        suffix = f" {noun}" if noun else ""
        return f"{text} · {self.affected} of {self.total}{suffix}"


def severity_rank(state: Freshness) -> int:
    """How alarming a state is: NO_DATA > STALE > FRESH.

    Public because exception-first ordering (§10) is the same domain rule as
    worst-of aggregation, and a presentation layer sorting by its own private
    copy is how the two would eventually disagree.
    """
    return _FRESHNESS_SEVERITY[state]


def aggregate_freshness(states: list[Freshness]) -> FreshnessRollup:
    """Worst-of rollup over one level's children.

    Empty is NO_DATA, never FRESH: a plant with nothing reporting under it has
    produced no evidence of health, and defaulting to green would invent some.
    """
    counts = {state: 0 for state in Freshness}
    for state in states:
        counts[state] += 1

    worst = (
        max(states, key=lambda s: _FRESHNESS_SEVERITY[s])
        if states
        else Freshness.NO_DATA
    )
    return FreshnessRollup(state=worst, counts=counts, total=len(states))


@dataclass(frozen=True)
class FleetHealth:
    """Freshness at every level of the tree, from one query.

    `counts` counts *devices*, not metrics — the Data Health card answers "how
    many devices are reporting", and a device carries eight metrics that would
    otherwise inflate every figure eightfold.

    Plant rollups are worst-of the plant's *devices*, not of its transformers:
    aggregating twice would be a majority rule in disguise, since a transformer
    holding one stale device among six reports STALE with equal weight to one
    holding six.
    """

    devices: dict[str, FreshnessRollup]
    transformers: dict[str, FreshnessRollup]
    plants: dict[str, FreshnessRollup]
    counts: dict[Freshness, int]
    #: transformer_id -> plant_id, so a plant screen can select its own subtree
    #: without a second query or a second definition of the hierarchy.
    _transformer_plant: dict[str, str]
    #: plant_id -> newest reading timestamp seen for that plant (any metric,
    #: any device). Absent plants are None via `.get`. Freshness state and
    #: "how old" are separate questions — the rollups above answer the first,
    #: this answers the second, and both are derived from the same one query so
    #: a stale plant's age can never disagree with its label about which moment
    #: "now" was.
    plant_last_updated: dict[str, datetime | None]

    @property
    def device_count(self) -> int:
        return len(self.devices)

    @property
    def plant_count(self) -> int:
        return len(self.plants)

    def transformers_for_plant(self, plant_id: str) -> dict[str, FreshnessRollup]:
        """This plant's transformer rollups. Unknown plant selects nothing."""
        return {
            tid: rollup
            for tid, rollup in self.transformers.items()
            if self._transformer_plant.get(tid) == plant_id
        }

    def device_counts_for_plant(self, plant_id: str) -> dict[Freshness, int]:
        """Per-state device counts within one plant, for a plant-scoped card.

        Derived from the same object the fleet card uses, so a plant page and
        the fleet page can never report different states for the same device.
        """
        counts = {state: 0 for state in Freshness}
        # A transformer rollup's `counts` already tallies its devices by state,
        # so the plant total is their sum — no second traversal of the rows.
        for rollup in self.transformers_for_plant(plant_id).values():
            for state, n in rollup.counts.items():
                counts[state] += n
        return counts


def fleet_health_from_rows(rows, now: datetime | None = None) -> FleetHealth:
    """Build the whole chain from one `latest_reading_times()` result set.

    Takes rows rather than querying, so the fleet card and the per-plant
    freshness column are served by a single database round trip.
    """
    reference = now or _now()

    device_metric_states: dict[str, list[Freshness]] = {}
    device_plant: dict[str, str] = {}
    device_transformer: dict[str, str] = {}
    transformer_plant: dict[str, str] = {}
    plant_last_updated: dict[str, datetime | None] = {}
    for row in rows:
        device_metric_states.setdefault(row.device_id, []).append(
            evaluate_freshness(row.reading_ts, reference)
        )
        device_plant[row.device_id] = row.plant_id
        transformer_id = getattr(row, "transformer_id", None)
        if transformer_id is not None:
            device_transformer[row.device_id] = transformer_id
            transformer_plant[transformer_id] = row.plant_id

        # A row exists for every (device, metric) pair even when the device
        # never reported (reading_ts is None); those rows say nothing about
        # when the plant last delivered data and are skipped.
        if row.reading_ts is not None:
            current = plant_last_updated.get(row.plant_id)
            if current is None or row.reading_ts > current:
                plant_last_updated[row.plant_id] = row.reading_ts

    devices = {
        device_id: aggregate_freshness(states)
        for device_id, states in device_metric_states.items()
    }

    def _rollup_by(owner: dict[str, str]) -> dict[str, FreshnessRollup]:
        grouped: dict[str, list[Freshness]] = {}
        for device_id, rollup in devices.items():
            if device_id in owner:
                grouped.setdefault(owner[device_id], []).append(rollup.state)
        return {key: aggregate_freshness(states) for key, states in grouped.items()}

    # Both levels aggregate over *devices*. Rolling plants up from transformer
    # states instead would be a majority rule in disguise: a transformer with
    # one stale device among six would weigh the same as one with six.
    transformers = _rollup_by(device_transformer)
    plants = _rollup_by(device_plant)

    counts = {state: 0 for state in Freshness}
    for rollup in devices.values():
        counts[rollup.state] += 1

    return FleetHealth(
        devices=devices,
        transformers=transformers,
        plants=plants,
        counts=counts,
        _transformer_plant=transformer_plant,
        plant_last_updated=plant_last_updated,
    )


def get_fleet_health(now: datetime | None = None, *, scope: DeviceScope) -> FleetHealth:
    """The fleet's freshness, from one query, for one render.

    The Fleet screen's Data Health card and every plant's freshness label are
    derived from the object this returns — call it once per render and pass the
    result down. Calling it per component would issue N queries and, worse,
    let two parts of one screen disagree about which devices are stale.

    Every configured metric is included: a device is only FRESH when all of its
    metrics are, so querying a subset would report a device healthy on the
    strength of one working feed.

    `now` is threaded through so one render evaluates every device against a
    single instant. The Fleet header stamps that same instant, so the page
    cannot claim to have refreshed at a moment different from the one its
    freshness column was computed at.

    Scoped: every figure derived from this describes the caller's visible
    devices only, constrained in SQL before aggregation.
    """
    return fleet_health_from_rows(latest_reading_rows(scope=scope), now)


def latest_reading_rows(*, scope: DeviceScope) -> list[LatestReadingRow]:
    """The one fleet-wide freshness fetch, unaggregated.

    Split out from `get_fleet_health` so a screen needing two different rollups
    of the same facts pays one round trip rather than two. The plant and
    transformer screens need exactly that: device rollups for the Data Health
    card and per-metric rollups for the health grid, which must not be able to
    disagree about which feeds are stale.

    `get_fleet_health` remains the right entry point for a screen that needs
    only device rollups.

    Scoped: constrained in SQL to the caller's visible devices before any
    rollup runs, so fleet health, the health distribution bar, Needs
    Attention and the Notification Center can never disagree with the counts
    the caller is otherwise shown.
    """
    return repo.latest_reading_times(
        [m.key for m in ordered_metrics()], allowed_device_ids=scope.device_ids
    )


@dataclass(frozen=True)
class MetricHealth:
    """One metric's data-health rollup across the devices beneath one Plant
    or Transformer.

    Reporting/freshness only — never a value aggregate. Wraps a
    `FreshnessRollup` the same way `FleetHealth` does at the device level, so
    "worst-of" and the empty-population rule (`aggregate_freshness([])` ->
    NO_DATA) stay defined in exactly one place rather than reimplemented per
    axis.
    """

    metric: MetricConfig
    rollup: FreshnessRollup

    @property
    def freshness(self) -> Freshness:
        return self.rollup.state

    @property
    def fresh_count(self) -> int:
        return self.rollup.counts[Freshness.FRESH]

    @property
    def stale_count(self) -> int:
        return self.rollup.counts[Freshness.STALE]

    @property
    def no_data_count(self) -> int:
        return self.rollup.counts[Freshness.NO_DATA]

    @property
    def reporting_count(self) -> int:
        """Devices that have ever reported this metric, fresh or stale alike."""
        return self.rollup.total - self.no_data_count

    @property
    def total_devices(self) -> int:
        return self.rollup.total


def metric_health_from_rows(
    rows,
    *,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    now: datetime | None = None,
) -> list[MetricHealth]:
    """Per-metric reporting/freshness beneath one Plant or Transformer, from
    an already-fetched `latest_reading_rows()` result.

    Takes rows rather than querying: the fleet-wide fetch already carries
    every active device x every configured metric (`latest_reading_times`'s
    CROSS JOIN), so a Plant or Transformer screen filters the same result set
    it already holds for `fleet_health_from_rows` rather than paying for a
    second round trip. Device population comes from the filtered rows
    themselves — a device that never reported a metric still has a row (NULL
    `reading_ts`, from the repository's LEFT JOIN LATERAL), so grouping by
    device already reflects the correct active population without a separate
    hierarchy call.

    `transformer_id` wins if both scope arguments are given, matching
    `repositories.plant_monitoring_repository.latest_metric_readings`'s
    existing convention.

    Every configured metric is present in the result, in `ordered_metrics()`
    order — including a metric with zero matching rows, or a scope with zero
    matching devices, which reports the pre-existing empty-population rollup
    (`aggregate_freshness([])` -> NO_DATA) rather than being omitted.
    """
    if plant_id is None and transformer_id is None:
        raise ValueError(
            "metric_health_from_rows requires either plant_id or transformer_id"
        )

    reference = now or _now()

    if transformer_id is not None:
        scoped = [r for r in rows if r.transformer_id == transformer_id]
    else:
        scoped = [r for r in rows if r.plant_id == plant_id]

    states_by_metric: dict[str, list[Freshness]] = {m.key: [] for m in ordered_metrics()}
    for row in scoped:
        if row.metric in states_by_metric:
            states_by_metric[row.metric].append(evaluate_freshness(row.reading_ts, reference))

    return [
        MetricHealth(metric=metric, rollup=aggregate_freshness(states_by_metric[metric.key]))
        for metric in ordered_metrics()
    ]


def latest_metric_readings(
    metric: str,
    *,
    plant_id: str | None = None,
    transformer_id: str | None = None,
    scope: DeviceScope,
) -> list[DeviceMetricReading]:
    """The one attribution fetch for one Plant or Transformer render.

    Thin delegation to the repository, mirroring `latest_reading_rows()`: the
    service stays the one place a callback reaches for data, never the
    repository directly, even where there is no aggregation to add on top of
    what the repository already returns.
    """
    return repo.latest_metric_readings(
        metric,
        plant_id=plant_id,
        transformer_id=transformer_id,
        allowed_device_ids=scope.device_ids,
    )


@dataclass(frozen=True)
class TemperatureAttribution:
    """The hottest latest-available temperature beneath one Plant or
    Transformer, attributed to the device that recorded it.

    `has_data` is False exactly when no active device beneath the entity has
    ever reported the attribution metric — every identity/value field is then
    None, so a component can render "No temperature data available" without
    inspecting individual fields or catching an exception.
    """

    metric: MetricConfig
    value: float | None
    reading_ts: datetime | None
    freshness: Freshness
    device_id: str | None
    device_code: str | None
    transformer_id: str | None
    transformer_code: str | None
    reporting_count: int
    total_devices: int
    has_data: bool


def hottest_temperature(
    readings: list[DeviceMetricReading], now: datetime | None = None
) -> TemperatureAttribution:
    """Attribute the maximum latest-available temperature to its device.

    `readings` is one `latest_metric_readings(ATTRIBUTION_METRIC_KEY, ...)`
    result, already scoped to one Plant or Transformer and already
    active-only — the repository call's default. This function does not
    re-filter by status or entity; it only selects and attributes.

    STALE READINGS ARE ELIGIBLE. Freshness and "hottest" are independent
    questions: a device that stopped reporting yesterday at 40C is still the
    hottest known reading today, and silently preferring a cooler FRESH
    device over it would hide the more extreme condition. The selected
    reading's own freshness is reported separately, so a component can still
    show a staleness indicator beside the value.

    Ties (identical maximum value) are broken by (transformer_code,
    device_code) ascending — a fixed, human-stable rule, not the order
    `readings` happens to arrive in. The repository returns rows in this same
    order today, but that ordering is not relied on here.
    """
    metric = get_metric(ATTRIBUTION_METRIC_KEY)
    reference = now or _now()
    total_devices = len(readings)
    reporting = [r for r in readings if r.value is not None]

    if not reporting:
        return TemperatureAttribution(
            metric=metric,
            value=None,
            reading_ts=None,
            freshness=Freshness.NO_DATA,
            device_id=None,
            device_code=None,
            transformer_id=None,
            transformer_code=None,
            reporting_count=0,
            total_devices=total_devices,
            has_data=False,
        )

    max_value = max(r.value for r in reporting)
    hottest = min(
        (r for r in reporting if r.value == max_value),
        key=lambda r: (r.transformer_code, r.device_code),
    )

    return TemperatureAttribution(
        metric=metric,
        value=hottest.value,
        reading_ts=hottest.reading_ts,
        freshness=evaluate_freshness(hottest.reading_ts, reference),
        device_id=hottest.device_id,
        device_code=hottest.device_code,
        transformer_id=hottest.transformer_id,
        transformer_code=hottest.transformer_code,
        reporting_count=len(reporting),
        total_devices=total_devices,
        has_data=True,
    )


def reading_age(last_updated: datetime | None, now: datetime | None = None):
    """How old the newest reading is, or None when there has never been one.

    Time arithmetic lives here rather than in a component: the service already
    owns `_now()` and the naive/aware alignment that this needs. Formatting the
    result for display is a presentation concern and stays in the components.
    """
    if last_updated is None:
        return None
    reference = now or _now()
    return reference - _align_tz(last_updated, reference)


def series_context(series: list[Reading]) -> dict:
    """Real, derived context for the KPI row — never a fabricated condition.

    Returns when the extremes occurred and how many samples the period holds.
    An operator asking "when did it peak?" currently has to read it off the
    chart. Empty keys where a series is too short to answer.
    """
    if not series:
        return {"min_at": None, "max_at": None, "count": 0}
    lo = min(series, key=lambda r: r.value)
    hi = max(series, key=lambda r: r.value)
    return {"min_at": lo.timestamp, "max_at": hi.timestamp, "count": len(series)}


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


def period_delta(series: list[Reading], prime: Reading | None = None) -> DeltaResult:
    """Consumption over a window: last − first, but only while monotonic.

    A decrease means a reset, replacement, rollover or backfill correction. It
    is reported as DISCONTINUITY rather than corrected: no abs(), no assumed
    register width, no summing of positive segments only. The register width is
    unknown, and a wrong constant produces a plausible number that is wrong,
    which is worse than an honest gap.

    `prime` is the last reading at or before the window start, so the first
    interval is not silently dropped.
    """
    values = [r.value for r in series]
    if prime is not None:
        values = [prime.value] + values
    if len(values) < 2:
        return DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)
    for earlier, later in zip(values, values[1:]):
        if later < earlier:
            return DeltaResult(None, DeltaStatus.DISCONTINUITY)
    return DeltaResult(values[-1] - values[0], DeltaStatus.OK)


@dataclass(frozen=True)
class ConsumptionBar:
    """One bar: consumption across [start, end]."""

    start: datetime
    end: datetime
    result: DeltaResult


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _utc_floor(ts: datetime, bin_width: timedelta) -> datetime:
    """Round down to a UTC wall-clock boundary, so a day bar means that UTC day."""
    return _EPOCH + ((ts - _EPOCH) // bin_width) * bin_width


def bin_edges(start: datetime, end: datetime, bin_width: timedelta) -> list[datetime]:
    """Window bounds plus every UTC boundary strictly between them."""
    edges = [start]
    boundary = _utc_floor(start, bin_width) + bin_width
    while boundary < end:
        edges.append(boundary)
        boundary += bin_width
    edges.append(end)
    return edges


def bin_consumption(
    series: list[Reading],
    bin_width: timedelta,
    start: datetime,
    end: datetime,
    prime: Reading | None = None,
) -> list[ConsumptionBar]:
    """Energy consumed in each bin, from the meter value at each boundary.

    `bar(t0, t1) = V(t1) − V(t0)`, where V(t) is the last reading at or before
    t. It is NOT last − first of the readings inside the bin: at 30-minute
    sampling with 30-minute bins each bin holds a single reading, so that
    definition draws only zeros, and at any width it drops the consumption
    between one bin's last reading and the next bin's first.

    A bin whose opening value is unknown, or which no reading closes, is
    INSUFFICIENT_DATA rather than zero — carrying a value forward would assert
    consumption we did not measure.
    """
    pool = [r for r in series if start <= r.timestamp <= end]
    if prime is not None:
        pool = [prime] + pool
    pool.sort(key=lambda r: r.timestamp)

    edges = bin_edges(start, end, bin_width)
    bars: list[ConsumptionBar] = []
    for t0, t1 in zip(edges, edges[1:]):
        opening = [r for r in pool if r.timestamp <= t0]
        inside = [r for r in pool if t0 < r.timestamp <= t1]
        if not opening or not inside:
            bars.append(
                ConsumptionBar(t0, t1, DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA))
            )
            continue
        values = [opening[-1].value] + [r.value for r in inside]
        discontinuous = any(later < earlier for earlier, later in zip(values, values[1:]))
        result = (
            DeltaResult(None, DeltaStatus.DISCONTINUITY)
            if discontinuous
            else DeltaResult(values[-1] - values[0], DeltaStatus.OK)
        )
        bars.append(ConsumptionBar(t0, t1, result))
    return bars


def bin_label(bin_width: timedelta) -> str:
    """How the chart names its bin width, so the quantity is never ambiguous."""
    seconds = int(bin_width.total_seconds())
    if seconds % 86400 == 0:
        return f"{seconds // 86400} d bars"
    if seconds % 3600 == 0:
        return f"{seconds // 3600} h bars"
    return f"{seconds // 60} min bars"


def quick_trend_bars(view: MetricView) -> list[ConsumptionBar]:
    """Consumption bars for a delta metric's Quick Trend cell.

    Returns an empty list for anything that is not a delta metric, or that
    has no series — a statistics metric's Quick Trend cell plots
    `view.series` directly and needs no bars at all, so it is safe for a
    caller to request this for every metric unconditionally.

    Binned over the span of the view's own series, not `window_start`/
    `window_end`: unlike the primary chart's bars (built in
    `callbacks.device.refresh_device_dashboard` from the requested window and
    `view.prime`), a Quick Trend cell carries no Period Change KPI beside it,
    so its bars are not required to sum to a period total. Relocated from
    `components.trend_grid` verbatim — the binning algorithm itself
    (`choose_bin`, `bin_consumption`) is unchanged.
    """
    if view.metric.aggregation is not Aggregation.DELTA or not view.series:
        return []
    start, end = view.series[0].timestamp, view.series[-1].timestamp
    return bin_consumption(view.series, choose_bin(end - start), start, end)


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
    window: tuple[datetime, datetime] | None = None,
    prime: Reading | None = None,
) -> MetricView:
    minimum = maximum = average = period_change = None
    period_change_status = DeltaStatus.OK
    if metric.aggregation is Aggregation.DELTA:
        # The prime opens the window, so the KPI covers the whole requested
        # period rather than starting at the first reading inside it — and the
        # chart's bars, binned over the same window with the same prime, sum to
        # exactly this number.
        delta = period_delta(series, prime=prime)
        period_change = delta.value
        period_change_status = delta.status
    else:
        minimum, maximum, average = _compute_statistics(series)

    # Direction against the start of the selected period. A cumulative meter
    # reuses period_delta, so a discontinuity propagates to the tile too rather
    # than printing a negative there.
    if metric.aggregation is Aggregation.DELTA:
        change = period_delta(series, prime=prime)
    elif len(series) >= 2:
        change = DeltaResult(series[-1].value - series[0].value, DeltaStatus.OK)
    else:
        change = DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)

    last_updated = latest.timestamp if latest else None
    return MetricView(
        metric=metric,
        current=latest.value if latest else None,   # latest available, period-independent
        minimum=minimum,
        maximum=maximum,
        average=average,
        period_change=period_change,
        period_change_status=period_change_status,
        series=series,
        last_updated=last_updated,
        freshness=evaluate_freshness(last_updated, now),
        condition=_current_condition(None),
        has_data=latest is not None,
        change=change,
        window_start=window[0] if window else None,
        window_end=window[1] if window else None,
        prime=prime,
    )


def _resolve_window(
    period: Period, anchor: datetime | None,
    custom_start: datetime | None, custom_end: datetime | None,
) -> tuple[datetime, datetime] | None:
    """Return the (start, end) window, or None when no window is computable.

    Custom bounds are aligned to the anchor's timezone before leaving this
    function. They reach a `TIMESTAMPTZ` comparison, and a naive value there is
    resolved using the database session's `TimeZone` — which would shift the
    operator's selected day on any session that is not UTC.
    """
    if period is Period.CUSTOM:
        if custom_start is None or custom_end is None:
            return None
        if anchor is not None:
            custom_start = _align_tz(custom_start, anchor)
            custom_end = _align_tz(custom_end, anchor)
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

    # Relative periods are anchored to wall-clock now, never to the newest
    # reading. Anchoring to the sample made "Last 24h" on a device that stopped
    # reporting days ago return the 24 hours before *that* reading — a full
    # chart and a full set of KPIs under a label the operator reads as "the
    # last 24 hours". `current` stays tied to the latest reading below, which
    # is what REQUIREMENTS.md actually specifies.
    window = _resolve_window(period, now, custom_start, custom_end)

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

    # One common window, anchored to wall-clock now for the same reason as
    # get_metric_view: a stale device must show an empty "Last 24h", not the
    # 24 hours around its final reading. Per-metric `last_updated` below still
    # reflects each metric's own newest sample.
    window = _resolve_window(period, now, custom_start, custom_end)

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
        # Only a cumulative meter needs the reading that opens the window. One
        # extra indexed seek, and only for the metrics whose arithmetic depends
        # on it.
        prime = None
        if window is not None and metric.aggregation is Aggregation.DELTA:
            raw_prime = repo.get_last_reading_before(device_id, metric.key, window[0])
            prime = _to_reading(raw_prime) if raw_prime else None
        views[metric.key] = _build_metric_view(
            metric, reading, series, now, window=window, prime=prime
        )

    return views
