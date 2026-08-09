# Device Analytics Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the device page from one chart to eight — a Quick Trends grid for all metrics, energy rendered as arithmetically correct interval bars, and a direction indicator on the snapshot tiles.

**Architecture:** All chart arithmetic lives in `services/monitoring_service.py` as pure functions; components render what they are given and never compute. Chart type is driven solely by `MetricConfig.chart_type`. The existing single body callback keeps owning the device page — no second render path.

**Tech Stack:** Python 3.12, Dash 2.17, Plotly 5.24.1, SQLAlchemy, PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-08-09-device-analytics-expansion-design.md`

## Global Constraints

- Run tests with `.venv/Scripts/python.exe -m pytest`. Pure logic: `-m "not db"`. Full suite needs Docker + seeded DB (`docker compose up -d`).
- UI/page/component code must not execute raw SQL. Repository owns all queries.
- KPI/status/domain calculations live in services, never in callbacks or components.
- Nothing outside `config/metrics.py` may branch on a specific metric key.
- No thresholds, alarm bands, warning colours, R/Y/B phase charts, or derived electrical relationships. `MonitoringCondition` stays `UNKNOWN`.
- Selection styling uses accent/selection tokens only — never the warning or freshness palette.
- All displayed instants are UTC and labelled as such.
- Never expose stack traces, SQL, passwords or connection strings in UI errors.
- Per spec §6.9: where a style is the deliverable, acceptance reads the **computed** value from a running browser. CSS-source assertions are regression guards, never proof.
- Commit after each task. End commit messages with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- On Windows PowerShell, pass multi-line commit messages via `git commit -F <file>`; here-strings break on embedded quotes.

## File Structure

| File | Responsibility |
|---|---|
| `config/metrics.py` | Add `SOURCE_RESOLUTION_MINUTES`; energy `chart_type` → `"bar"` |
| `services/monitoring_service.py` | `choose_bin`, `DeltaStatus`, `DeltaResult`, `period_delta`, `bin_consumption`, `ConsumptionBar`, `MetricView.change` |
| `repositories/plant_monitoring_repository.py` | `get_last_reading_before` |
| `components/metric_chart.py` | Branch once on `chart_type`; `build_delta_figure` |
| `components/metric_snapshot_strip.py` | Tile direction line |
| `components/trend_grid.py` (new) | Eight static cells |
| `components/kpi_card.py` | Render `DeltaStatus` on Period Change |
| `callbacks/device.py` | Switch to `get_device_full_view`; feed grid |
| `pages/device_dashboard.py` | `trend-grid` slot |
| `assets/app.css` | Grid layout, responsive fallback, selection styling |

---

### Task 1: Binning ladder

**Files:**
- Modify: `config/metrics.py`
- Modify: `services/monitoring_service.py`
- Test: `tests/test_energy_binning.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `config.metrics.SOURCE_RESOLUTION_MINUTES: int`; `services.monitoring_service.choose_bin(span: timedelta) -> timedelta`, `BIN_LADDER: tuple[timedelta, ...]`, `TARGET_BARS: int`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_energy_binning.py`:

```python
"""Energy bin selection — duration aware, never finer than the source data."""
from __future__ import annotations

from datetime import timedelta

import pytest

from config.metrics import SOURCE_RESOLUTION_MINUTES
from services.monitoring_service import TARGET_BARS, choose_bin


class TestChooseBin:
    @pytest.mark.parametrize("span,expected", [
        (timedelta(hours=24), timedelta(minutes=30)),
        (timedelta(days=7), timedelta(hours=6)),
        (timedelta(days=30), timedelta(days=1)),
        (timedelta(days=3), timedelta(hours=2)),
        (timedelta(days=90), timedelta(days=7)),
    ])
    def test_span_selects_its_rung(self, span, expected):
        assert choose_bin(span) == expected

    def test_never_finer_than_the_source_resolution(self):
        """A 5-minute bin would draw mostly-empty bars implying measurement we
        do not have."""
        floor = timedelta(minutes=SOURCE_RESOLUTION_MINUTES)
        for hours in (1, 2, 6, 12, 24):
            assert choose_bin(timedelta(hours=hours)) >= floor

    def test_bar_count_stays_within_target(self):
        for days in (1, 2, 3, 7, 14, 30, 60):
            span = timedelta(days=days)
            assert span / choose_bin(span) <= TARGET_BARS + 1

    def test_duration_aware_not_period_named(self):
        """Two custom ranges of different length must not share a bin."""
        assert choose_bin(timedelta(days=3)) != choose_bin(timedelta(days=90))

    def test_absurdly_long_span_uses_the_coarsest_rung(self):
        assert choose_bin(timedelta(days=3650)) == timedelta(days=7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_energy_binning.py -q`
Expected: FAIL — `ImportError: cannot import name 'SOURCE_RESOLUTION_MINUTES'`

- [ ] **Step 3: Write minimal implementation**

In `config/metrics.py`, after `METRICS`:

```python
#: Approximate cadence of the source data. Client readings arrive roughly every
#: 30 minutes and our seed matches. Energy bins are never finer than this: a
#: 5-minute bar would imply a measurement resolution we do not have.
#: DEVELOPMENT VALUE — replace when the real client cadence is known.
SOURCE_RESOLUTION_MINUTES: int = 30
```

In `services/monitoring_service.py`, after the `Period` enum:

```python
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
```

Add `SOURCE_RESOLUTION_MINUTES` to the existing `from config.metrics import ...` line.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_energy_binning.py -q`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add config/metrics.py services/monitoring_service.py tests/test_energy_binning.py
git commit -m "feat(energy): duration-aware bin ladder with a source-resolution floor"
```

---

### Task 2: Delta result with explicit discontinuity

**Files:**
- Modify: `services/monitoring_service.py`
- Test: `tests/test_delta_status.py` (create)

**Interfaces:**
- Consumes: Task 1.
- Produces: `DeltaStatus` (enum: `OK`, `INSUFFICIENT_DATA`, `DISCONTINUITY`), `DeltaResult(value: float | None, status: DeltaStatus)` with `.is_known`, `period_delta(series: list[Reading], prime: Reading | None = None) -> DeltaResult`. `MetricView` gains `period_change_status: DeltaStatus`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_delta_status.py`:

```python
"""Cumulative meter arithmetic. A decrease is never consumption.

The seeded data is monotonic by construction, so every discontinuity here is
synthesised. That is deliberate: this path will never be exercised by our data
and would otherwise ship untested.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.monitoring_service import (
    DeltaResult, DeltaStatus, Reading, period_delta,
)

T0 = datetime(2026, 8, 9, 0, 0, tzinfo=timezone.utc)


def _series(*values):
    return [Reading(T0 + timedelta(minutes=30 * i), v) for i, v in enumerate(values)]


class TestPeriodDelta:
    def test_monotonic_series_is_last_minus_first(self):
        result = period_delta(_series(100.0, 110.0, 125.0))
        assert result == DeltaResult(25.0, DeltaStatus.OK)

    def test_priming_reading_extends_coverage_backwards(self):
        prime = Reading(T0 - timedelta(minutes=30), 90.0)
        result = period_delta(_series(100.0, 110.0), prime=prime)
        assert result.value == 20.0
        assert result.status is DeltaStatus.OK

    def test_a_decrease_is_a_discontinuity_not_a_negative_number(self):
        """A meter reset must never print as negative consumption."""
        result = period_delta(_series(100.0, 110.0, 5.0, 12.0))
        assert result.status is DeltaStatus.DISCONTINUITY
        assert result.value is None

    def test_single_reading_is_insufficient_data(self):
        result = period_delta(_series(100.0))
        assert result.status is DeltaStatus.INSUFFICIENT_DATA
        assert result.value is None

    def test_empty_series_is_insufficient_data(self):
        assert period_delta([]).status is DeltaStatus.INSUFFICIENT_DATA

    def test_insufficient_data_is_distinguishable_from_discontinuity(self):
        """Today both collapse to None, which hides which one happened."""
        assert (
            period_delta(_series(100.0)).status
            is not period_delta(_series(100.0, 50.0)).status
        )

    def test_flat_meter_reports_zero_not_unknown(self):
        result = period_delta(_series(100.0, 100.0))
        assert result == DeltaResult(0.0, DeltaStatus.OK)

    def test_no_correction_rule_is_applied(self):
        """No abs(), no assumed rollover width, no summing positive segments —
        the register width and reset semantics are unknown."""
        result = period_delta(_series(100.0, 5.0))
        assert result.value is None

    def test_is_known_only_when_ok(self):
        assert period_delta(_series(1.0, 2.0)).is_known
        assert not period_delta(_series(2.0, 1.0)).is_known
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_delta_status.py -q`
Expected: FAIL — `ImportError: cannot import name 'DeltaStatus'`

- [ ] **Step 3: Write minimal implementation**

In `services/monitoring_service.py`, after the `Freshness` enum:

```python
class DeltaStatus(str, Enum):
    """Why a cumulative-meter delta is or is not a number."""

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
```

Replace `_compute_delta` usage in `_build_metric_view`:

```python
    minimum = maximum = average = period_change = None
    period_change_status = DeltaStatus.OK
    if metric.aggregation is Aggregation.DELTA:
        delta = period_delta(series)
        period_change = delta.value
        period_change_status = delta.status
    else:
        minimum, maximum, average = _compute_statistics(series)
```

Add `period_change_status: DeltaStatus` to `MetricView` (after `period_change`) and pass it in the constructor call. Delete `_compute_delta`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_delta_status.py -q`
Then the whole suite: `.venv/Scripts/python.exe -m pytest -m "not db" -q`
Expected: both PASS. If an existing test asserted `_compute_delta` directly, update it to `period_delta` — do not delete coverage.

- [ ] **Step 5: Commit**

```bash
git add services/monitoring_service.py tests/test_delta_status.py
git commit -m "feat(energy): report meter discontinuities instead of negative consumption"
```

---

### Task 3: Priming read

**Files:**
- Modify: `repositories/plant_monitoring_repository.py`
- Test: `tests/test_plant_monitoring_repository.py`

**Interfaces:**
- Consumes: Task 2.
- Produces: `get_last_reading_before(device_id: str, metric: str, ts: datetime) -> RawReading | None`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plant_monitoring_repository.py`:

```python
class TestPrimingRead:
    """The reading that opens the first energy bin. Without it the first bar is
    short by one sampling interval and the bars no longer sum to the KPI."""

    def test_returns_the_reading_immediately_before_the_instant(self):
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "energy")
        with measure_time() as t:
            prime = repo.get_last_reading_before(
                RESERVED_DEVICE_ID, "energy", latest.timestamp
            )
        assert prime is not None
        assert prime.timestamp < latest.timestamp
        t.row_count = 1
        assert_timing(t, BUDGET_LATEST_READING, min_rows=1)

    def test_boundary_is_exclusive(self):
        """`before` means before. Including the instant itself would make the
        first bar cover zero elapsed time."""
        latest = repo.get_latest_reading(RESERVED_DEVICE_ID, "energy")
        prime = repo.get_last_reading_before(
            RESERVED_DEVICE_ID, "energy", latest.timestamp
        )
        assert prime.timestamp != latest.timestamp

    def test_returns_none_before_the_first_reading(self):
        ancient = datetime(2000, 1, 1, tzinfo=timezone.utc)
        assert repo.get_last_reading_before(
            RESERVED_DEVICE_ID, "energy", ancient
        ) is None

    def test_unknown_device_returns_none(self):
        assert repo.get_last_reading_before(
            "no-such-device", "energy", datetime(2026, 1, 1, tzinfo=timezone.utc)
        ) is None
```

Add to that file's imports: `from datetime import datetime, timedelta, timezone`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_plant_monitoring_repository.py::TestPrimingRead -q`
Expected: FAIL — `AttributeError: module has no attribute 'get_last_reading_before'`

Requires Docker: `docker compose up -d` first.

- [ ] **Step 3: Write minimal implementation**

In `repositories/plant_monitoring_repository.py`, next to `get_latest_reading`:

```python
def get_last_reading_before(
    device_id: str, metric: str, ts: datetime
) -> RawReading | None:
    """Newest reading strictly before `ts`, or None if there is none.

    Opens the first energy bin. A bar is consumption *across* its bin, so the
    first one needs the meter value at the window start — a reading that lies
    outside the window. Without it the first bar is short by one sampling
    interval, which is invisible on screen.

    One bounded seek against `ix_readings_device_metric_ts`, the same shape as
    `latest_reading_times`.
    """
    with session_scope() as session:
        row = session.execute(
            text(
                f"""
                SELECT reading_ts, value
                FROM {_SCHEMA}.readings
                WHERE device_id = :device_id
                  AND metric = :metric
                  AND reading_ts < :ts
                ORDER BY reading_ts DESC
                LIMIT 1
                """
            ),
            {"device_id": device_id, "metric": metric, "ts": ts},
        ).first()

    return RawReading(row[0], float(row[1])) if row else None
```

Match the existing `RawReading` construction in `get_latest_reading` — if that function names its fields differently, mirror it exactly.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_plant_monitoring_repository.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/plant_monitoring_repository.py tests/test_plant_monitoring_repository.py
git commit -m "feat(repo): add the priming read that opens the first energy bin"
```

---

### Task 4: Bar arithmetic from boundary values

**Files:**
- Modify: `services/monitoring_service.py`
- Test: `tests/test_energy_binning.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces: `ConsumptionBar(start: datetime, end: datetime, result: DeltaResult)`, `bin_consumption(series, bin_width, start, end, prime=None) -> list[ConsumptionBar]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_energy_binning.py`:

```python
from datetime import datetime, timezone

from services.monitoring_service import (
    DeltaStatus, Reading, bin_consumption, period_delta,
)

DAY = datetime(2026, 8, 9, 0, 0, tzinfo=timezone.utc)


def _meter(start_value, step, count, first_ts=DAY, cadence_minutes=30):
    """A clean monotonic meter at the source cadence."""
    return [
        Reading(first_ts + timedelta(minutes=cadence_minutes * i), start_value + step * i)
        for i in range(count)
    ]


class TestBarArithmetic:
    def test_24h_of_30min_samples_yields_48_non_zero_bars(self):
        """THE regression test for the boundary-value definition.

        A bar is consumption *across* its bin. Computing it as last − first of
        the readings *inside* the bin gives 48 zero-height bars here, because
        each 30-minute bin holds exactly one reading. Nothing else in the suite
        would notice.
        """
        end = DAY + timedelta(hours=24)
        series = _meter(1000.0, 2.0, 48, first_ts=DAY + timedelta(minutes=30))
        prime = Reading(DAY, 1000.0)
        bars = bin_consumption(series, timedelta(minutes=30), DAY, end, prime=prime)
        assert len(bars) == 48
        assert all(b.result.status is DeltaStatus.OK for b in bars)
        assert all(b.result.value == 2.0 for b in bars)

    def test_bars_sum_exactly_to_the_period_delta(self):
        """The load-bearing invariant: the chart and the KPI are the same number."""
        end = DAY + timedelta(hours=24)
        series = _meter(1000.0, 2.0, 48, first_ts=DAY + timedelta(minutes=30))
        prime = Reading(DAY, 1000.0)
        bars = bin_consumption(series, timedelta(hours=6), DAY, end, prime=prime)
        total = sum(b.result.value for b in bars)
        assert total == period_delta(series, prime=prime).value

    def test_sums_to_period_delta_without_a_priming_reading(self):
        end = DAY + timedelta(hours=24)
        series = _meter(1000.0, 2.0, 48, first_ts=DAY)
        bars = bin_consumption(series, timedelta(hours=6), DAY, end)
        known = [b.result.value for b in bars if b.result.is_known]
        assert sum(known) == period_delta(series).value

    def test_bins_align_to_utc_boundaries_not_to_the_first_sample(self):
        start = DAY + timedelta(minutes=17)
        end = start + timedelta(hours=4)
        series = _meter(500.0, 1.0, 10, first_ts=start)
        bars = bin_consumption(series, timedelta(hours=1), start, end)
        assert bars[1].start == DAY + timedelta(hours=1)

    def test_a_bin_containing_a_decrease_is_indeterminate(self):
        end = DAY + timedelta(hours=2)
        series = [
            Reading(DAY + timedelta(minutes=30), 100.0),
            Reading(DAY + timedelta(minutes=60), 110.0),
            Reading(DAY + timedelta(minutes=90), 4.0),
            Reading(DAY + timedelta(minutes=120), 9.0),
        ]
        bars = bin_consumption(series, timedelta(hours=1), DAY, end)
        assert any(b.result.status is DeltaStatus.DISCONTINUITY for b in bars)
        assert all(
            b.result.value is None or b.result.value >= 0 for b in bars
        ), "no bar may render as negative consumption"

    def test_a_bin_with_no_closing_reading_is_insufficient_not_zero(self):
        """Carrying the previous value forward would assert zero consumption,
        which we do not know."""
        end = DAY + timedelta(hours=3)
        series = [Reading(DAY + timedelta(minutes=30), 100.0)]
        prime = Reading(DAY, 99.0)
        bars = bin_consumption(series, timedelta(hours=1), DAY, end, prime=prime)
        assert bars[-1].result.status is DeltaStatus.INSUFFICIENT_DATA

    def test_empty_series_yields_bars_that_are_all_unknown(self):
        end = DAY + timedelta(hours=3)
        bars = bin_consumption([], timedelta(hours=1), DAY, end)
        assert bars
        assert all(not b.result.is_known for b in bars)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_energy_binning.py -q`
Expected: FAIL — `ImportError: cannot import name 'bin_consumption'`

- [ ] **Step 3: Write minimal implementation**

In `services/monitoring_service.py`, after `period_delta`:

```python
@dataclass(frozen=True)
class ConsumptionBar:
    """One bar: consumption across [start, end)."""

    start: datetime
    end: datetime
    result: DeltaResult


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _utc_floor(ts: datetime, bin_width: timedelta) -> datetime:
    """Round down to a UTC wall-clock boundary, so a day bar means that UTC day."""
    return _EPOCH + ((ts - _EPOCH) // bin_width) * bin_width


def bin_edges(start: datetime, end: datetime, bin_width: timedelta) -> list[datetime]:
    """Window bounds plus every UTC boundary between them."""
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
    sampling with 30-minute bins each bin holds one reading, so that definition
    draws only zeros, and at any width it drops the interval between bins.

    A bin whose opening value is unknown, or which no reading closes, is
    INSUFFICIENT_DATA rather than zero — carrying a value forward would assert
    consumption we did not measure.
    """
    pool = [r for r in series if start <= r.timestamp <= end]
    if prime is not None:
        pool = [prime] + pool
    pool.sort(key=lambda r: r.timestamp)

    bars: list[ConsumptionBar] = []
    for t0, t1 in zip(bin_edges(start, end, bin_width), bin_edges(start, end, bin_width)[1:]):
        opening = [r for r in pool if r.timestamp <= t0]
        inside = [r for r in pool if t0 < r.timestamp <= t1]
        if not opening or not inside:
            bars.append(ConsumptionBar(t0, t1, DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)))
            continue
        values = [opening[-1].value] + [r.value for r in inside]
        discontinuous = any(b < a for a, b in zip(values, values[1:]))
        result = (
            DeltaResult(None, DeltaStatus.DISCONTINUITY)
            if discontinuous
            else DeltaResult(values[-1] - values[0], DeltaStatus.OK)
        )
        bars.append(ConsumptionBar(t0, t1, result))
    return bars
```

Compute `bin_edges(...)` once into a local before the loop rather than twice — the doubled call above is shown only to make the pairing obvious.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_energy_binning.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/monitoring_service.py tests/test_energy_binning.py
git commit -m "feat(energy): compute bars from boundary values, not in-bin extremes"
```

---

### Task 5: Bar figure driven by chart_type

**Files:**
- Modify: `config/metrics.py`
- Modify: `components/metric_chart.py`
- Test: `tests/test_chart_types.py` (create)

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: `build_delta_figure(metric, bars, view_revision=None, period_label=None, bin_label="") -> go.Figure`; `build_metric_figure` unchanged for line metrics.

- [ ] **Step 1: Write the failing test**

Create `tests/test_chart_types.py`:

```python
"""Chart type comes from config, never from a metric key."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components.metric_chart import build_delta_figure
from config.metrics import get_metric, ordered_metrics
from services.monitoring_service import (
    ConsumptionBar, DeltaResult, DeltaStatus,
)

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _bar(i, value, status=DeltaStatus.OK):
    return ConsumptionBar(
        T0 + timedelta(hours=i), T0 + timedelta(hours=i + 1),
        DeltaResult(value, status),
    )


class TestChartMatrix:
    def test_energy_is_the_only_bar_chart(self):
        bars = [m.key for m in ordered_metrics() if m.chart_type == "bar"]
        assert bars == ["energy"]

    def test_every_other_metric_is_a_line(self):
        for metric in ordered_metrics():
            if metric.key != "energy":
                assert metric.chart_type == "line"

    def test_energy_is_a_bar_because_it_is_a_delta_metric(self):
        from config.metrics import Aggregation
        energy = get_metric("energy")
        assert energy.aggregation is Aggregation.DELTA
        assert energy.chart_type == "bar"


class TestDeltaFigure:
    def test_draws_one_bar_per_known_bin(self):
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 5.0), _bar(1, 7.0)])
        bar_traces = [t for t in fig.data if t.type == "bar"]
        assert len(bar_traces) == 1
        assert list(bar_traces[0].y) == [5.0, 7.0]

    def test_a_discontinuous_bin_draws_no_bar(self):
        fig = build_delta_figure(
            get_metric("energy"),
            [_bar(0, 5.0), _bar(1, None, DeltaStatus.DISCONTINUITY)],
        )
        bar_trace = next(t for t in fig.data if t.type == "bar")
        assert bar_trace.y[1] is None

    def test_a_discontinuity_is_marked_neutrally_not_as_a_warning(self):
        """Data quality, not an electrical alarm."""
        fig = build_delta_figure(
            get_metric("energy"),
            [_bar(0, None, DeltaStatus.DISCONTINUITY)],
        )
        markers = [t for t in fig.data if t.type == "scatter"]
        assert markers, "a discontinuity must be visible, not merely absent"
        colour = str(markers[0].marker.color).lower()
        assert colour not in ("red", "#ef4444", "#dc2626", "orange", "#f59e0b")

    def test_title_states_the_bin_width(self):
        fig = build_delta_figure(
            get_metric("energy"), [_bar(0, 5.0)], period_label="Last 24 hours",
            bin_label="30 min bars",
        )
        assert "30 min bars" in fig.layout.title.text

    def test_empty_bars_render_an_explanatory_annotation(self):
        fig = build_delta_figure(get_metric("energy"), [])
        assert fig.layout.annotations
        assert "No data" in fig.layout.annotations[0].text

    def test_height_matches_the_frozen_line_chart(self):
        from components.metric_chart import CHART_HEIGHT
        fig = build_delta_figure(get_metric("energy"), [_bar(0, 1.0)])
        assert fig.layout.height == CHART_HEIGHT
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chart_types.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_delta_figure'`

- [ ] **Step 3: Write minimal implementation**

In `config/metrics.py`, change the energy row's `chart_type` from `"line"` to `"bar"`:

```python
    # Cumulative meter: period KPI is last - first, never average/min/max.
    # Bars, not a line: a cumulative meter answers "how much in this interval",
    # which is an interval quantity. The rising meter reading stays available as
    # the Current KPI.
    MetricConfig("energy", "Energy", "MWh", 1, "bar", 8, Aggregation.DELTA),
```

In `components/metric_chart.py`, add:

```python
BAR_COLOR = "#3b82f6"

#: Neutral, deliberately not the warning palette. A meter discontinuity is a
#: data-quality condition, not an electrical alarm (CLAUDE.md keeps the three
#: status concepts separate).
DISCONTINUITY_COLOR = "#9ca3af"


def build_delta_figure(
    metric: MetricConfig,
    bars: list,
    view_revision: str | None = None,
    period_label: str | None = None,
    bin_label: str = "",
) -> go.Figure:
    """Interval consumption for a cumulative meter.

    Bars carry `DeltaResult`s: a bin we could not compute draws no bar and a
    neutral marker, never a zero and never a negative.
    """
    fig = go.Figure()
    if not bars:
        fig.add_annotation(
            text="No data available for the selected period",
            showarrow=False, font=dict(size=14, color="#6b7280"),
        )
    else:
        fig.add_trace(
            go.Bar(
                x=[b.start for b in bars],
                y=[b.result.value if b.result.is_known else None for b in bars],
                marker_color=BAR_COLOR,
                name=metric.label,
                hovertemplate=(
                    "%{x|%Y-%m-%d %H:%M} UTC<br>%{y:."
                    + str(metric.precision) + "f} " + metric.unit
                    + "<extra></extra>"
                ),
            )
        )
        unknown = [b for b in bars if not b.result.is_known]
        if unknown:
            fig.add_trace(
                go.Scatter(
                    x=[b.start for b in unknown],
                    y=[0 for _ in unknown],
                    mode="markers",
                    marker=dict(color=DISCONTINUITY_COLOR, size=6, symbol="x"),
                    hovertext=[b.result.status.value.replace("_", " ") for b in unknown],
                    hovertemplate="%{x|%Y-%m-%d %H:%M} UTC<br>%{hovertext}<extra></extra>",
                    showlegend=False,
                )
            )

    title = _chart_title(metric, period_label)
    if bin_label:
        title = f"{title} &#183; {bin_label}"
    fig.update_layout(
        margin=dict(l=56, r=20, t=44, b=48),
        height=CHART_HEIGHT,
        title=dict(text=title, x=0, xanchor="left", font=dict(size=14)),
        xaxis_title="Time (UTC)",
        yaxis_title=_axis_title(metric),
        template="plotly_white",
        showlegend=False,
        xaxis=dict(showgrid=True, gridcolor="#eef0f3"),
        yaxis=dict(showgrid=True, gridcolor="#eef0f3"),
        uirevision=view_revision or metric.key,
    )
    return fig
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_chart_types.py -q` then `-m "not db" -q`
Expected: PASS. If a frozen contract asserted energy's `chart_type == "line"`, update that assertion deliberately and note why in the commit.

- [ ] **Step 5: Commit**

```bash
git add config/metrics.py components/metric_chart.py tests/test_chart_types.py
git commit -m "feat(chart): render energy as interval bars driven by chart_type"
```

---

### Task 6: Device callback switches to the full view

**Files:**
- Modify: `callbacks/device.py`
- Modify: `components/kpi_card.py`
- Test: `tests/test_device_analytics_wiring.py` (create)

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: device callback calls `svc.get_device_full_view` once per render; `kpi_card` renders `DeltaStatus`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_device_analytics_wiring.py`:

```python
"""The device page fetches once and renders everything from that fetch."""
from __future__ import annotations

from components.kpi_card import kpi_row
from config.metrics import get_metric
from services.monitoring_service import DeltaStatus, MetricView, Freshness, MonitoringCondition
from tests.dash_tree import find_by_class, text_of


def _energy_view(period_change, status):
    return MetricView(
        metric=get_metric("energy"), current=278.2, minimum=None, maximum=None,
        average=None, period_change=period_change, period_change_status=status,
        series=[], last_updated=None, freshness=Freshness.NO_DATA,
        condition=MonitoringCondition.UNKNOWN, has_data=True,
    )


class TestPeriodChangeKpi:
    def test_a_known_delta_shows_the_number(self):
        row = kpi_row(_energy_view(68.6, DeltaStatus.OK))
        values = [text_of(e) for e in find_by_class(row, "kpi-card__value")]
        assert "68.6" in values[1]

    def test_a_discontinuity_shows_a_dash_not_a_negative(self):
        row = kpi_row(_energy_view(None, DeltaStatus.DISCONTINUITY))
        values = [text_of(e) for e in find_by_class(row, "kpi-card__value")]
        assert values[1].strip() == "—"

    def test_a_discontinuity_explains_itself(self):
        row = kpi_row(_energy_view(None, DeltaStatus.DISCONTINUITY))
        secondary = [text_of(e) for e in find_by_class(row, "kpi-card__secondary")]
        assert "meter" in secondary[1].lower()

    def test_insufficient_data_does_not_claim_a_discontinuity(self):
        row = kpi_row(_energy_view(None, DeltaStatus.INSUFFICIENT_DATA))
        secondary = [text_of(e) for e in find_by_class(row, "kpi-card__secondary")]
        assert "meter reset" not in secondary[1].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_device_analytics_wiring.py -q`
Expected: FAIL — `TypeError: MetricView.__init__() got an unexpected keyword argument 'period_change_status'` if Task 2 was skipped, otherwise an assertion failure on the dash text.

- [ ] **Step 3: Write minimal implementation**

In `components/kpi_card.py`, replace the DELTA branch of `kpi_row`:

```python
    if metric.aggregation is Aggregation.DELTA:
        status = view.period_change_status
        if status is DeltaStatus.OK:
            value_text = format_value(metric, view.period_change)
            secondary = period_label or ""
        elif status is DeltaStatus.DISCONTINUITY:
            # Never a negative number: a decrease means the meter reset, was
            # replaced or rolled over, and no correction rule is supported.
            value_text = "—"
            secondary = "Meter discontinuity in this period"
        else:
            value_text = "—"
            secondary = "Not enough readings in this period"
        cards.append(kpi_card("Period Change", value_text, secondary=secondary))
```

Import `DeltaStatus` from `services.monitoring_service`.

In `callbacks/device.py`, inside `refresh_device_dashboard`, replace steps 1 and 4:

```python
            # One fetch serves the strip, the KPIs, the primary chart, the
            # trend grid and the table: two batched queries for all 8 metrics,
            # against three for one metric before.
            period = ...  # unchanged resolution below
            views = svc.get_device_full_view(device_id, period, start, end)
            view = views.get(metric_key)
```

Move the period/custom-date resolution above the fetch so `period`, `start` and `end` are available. Keep the `if view is None: return [no_update] * 7` guard.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add callbacks/device.py components/kpi_card.py tests/test_device_analytics_wiring.py
git commit -m "feat(device): fetch all metrics once and report delta status in the KPI"
```

---

### Task 7: Snapshot tile direction

**Files:**
- Modify: `services/monitoring_service.py`
- Modify: `components/metric_snapshot_strip.py`
- Modify: `callbacks/device.py`
- Test: `tests/test_snapshot_direction.py` (create)

**Interfaces:**
- Consumes: Tasks 2, 6.
- Produces: `MetricView.change: DeltaResult`; `metric_snapshot_strip(views: list[MetricView], active_metric_key, device_id, period=None, custom_start=None, custom_end=None)` — now takes views, not snapshots.

- [ ] **Step 1: Write the failing test**

Create `tests/test_snapshot_direction.py`:

```python
"""Tiles answer "is this rising or falling?", which a bare number cannot."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components.metric_snapshot_strip import direction_text, metric_snapshot_strip
from config.metrics import get_metric
from services.monitoring_service import (
    DeltaResult, DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading,
)
from tests.dash_tree import find_by_class, text_of

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _view(key, change: DeltaResult, series=()):
    metric = get_metric(key)
    return MetricView(
        metric=metric, current=10.0, minimum=None, maximum=None, average=None,
        period_change=None, period_change_status=DeltaStatus.OK, series=list(series),
        last_updated=T0, freshness=Freshness.FRESH,
        condition=MonitoringCondition.UNKNOWN, has_data=True, change=change,
    )


class TestDirectionText:
    def test_a_rise_is_marked_up(self):
        assert direction_text(get_metric("voltage"), DeltaResult(0.31, DeltaStatus.OK)).startswith("▲")

    def test_a_fall_is_marked_down(self):
        assert direction_text(get_metric("voltage"), DeltaResult(-0.31, DeltaStatus.OK)).startswith("▼")

    def test_no_change_is_neither(self):
        text = direction_text(get_metric("voltage"), DeltaResult(0.0, DeltaStatus.OK))
        assert not text.startswith("▲") and not text.startswith("▼")

    def test_unknown_change_shows_a_dash(self):
        assert direction_text(
            get_metric("energy"), DeltaResult(None, DeltaStatus.DISCONTINUITY)
        ) == "—"

    def test_value_carries_the_unit(self):
        assert "kV" in direction_text(get_metric("voltage"), DeltaResult(0.31, DeltaStatus.OK))


class TestStripRendersDirection:
    def test_every_tile_shows_a_direction_line(self):
        views = [_view(k, DeltaResult(1.0, DeltaStatus.OK))
                 for k in ("temperature", "voltage")]
        strip = metric_snapshot_strip(views, "voltage", "dev-1")
        assert len(find_by_class(strip, "snapshot-tile__direction")) == 2

    def test_energy_never_shows_a_negative_direction(self):
        view = _view("energy", DeltaResult(None, DeltaStatus.DISCONTINUITY))
        strip = metric_snapshot_strip([view], "energy", "dev-1")
        text = text_of(find_by_class(strip, "snapshot-tile__direction")[0])
        assert "-" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_snapshot_direction.py -q`
Expected: FAIL — `ImportError: cannot import name 'direction_text'`

- [ ] **Step 3: Write minimal implementation**

In `services/monitoring_service.py`, add `change: DeltaResult` to `MetricView` and compute it in `_build_metric_view`:

```python
    # Direction against the start of the selected period. For a cumulative
    # meter this is the period delta, so a discontinuity propagates here too
    # rather than printing a negative.
    if metric.aggregation is Aggregation.DELTA:
        change = period_delta(series)
    elif len(series) >= 2:
        change = DeltaResult(series[-1].value - series[0].value, DeltaStatus.OK)
    else:
        change = DeltaResult(None, DeltaStatus.INSUFFICIENT_DATA)
```

In `components/metric_snapshot_strip.py`:

```python
def direction_text(metric: MetricConfig, change: DeltaResult) -> str:
    """Signed change against the period start, or an em dash when unknown."""
    if not change.is_known or change.value is None:
        return "—"
    if change.value > 0:
        arrow = "▲ +"
    elif change.value < 0:
        arrow = "▼ "
    else:
        arrow = ""
    return f"{arrow}{format_value(metric, change.value)}"
```

Change `snapshot_tile` to take a `MetricView`, read `view.metric`, `view.current`, `view.freshness`, and insert after the value div:

```python
                    html.Div(
                        direction_text(view.metric, view.change),
                        className="snapshot-tile__direction",
                    ),
```

Update `metric_snapshot_strip` to iterate views. In `callbacks/device.py`, pass `list(views.values())` ordered by `ordered_metrics()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`
Expected: PASS. Existing strip tests that build `MetricSnapshot` need updating to `MetricView` — update them, do not delete them.

- [ ] **Step 5: Commit**

```bash
git add services/monitoring_service.py components/metric_snapshot_strip.py callbacks/device.py tests/test_snapshot_direction.py
git commit -m "feat(strip): show direction against the period start on each tile"
```

---

### Task 8: Trend grid component

**Files:**
- Create: `components/trend_grid.py`
- Test: `tests/test_trend_grid.py` (create)

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `trend_grid(views: dict[str, MetricView], active_metric_key, device_id, period=None, custom_start=None, custom_end=None) -> html.Div`; `TREND_CELL_HEIGHT: int`; `TREND_CHART_CONFIG: dict`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_trend_grid.py`:

```python
"""Eight cells, fixed positions, no modebar."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from components.trend_grid import TREND_CHART_CONFIG, trend_grid
from config.metrics import ordered_metrics
from services.monitoring_service import (
    DeltaResult, DeltaStatus, Freshness, MetricView, MonitoringCondition, Reading,
)
from tests.dash_tree import find_by_class, find_by_exact_class, links, walk

T0 = datetime(2026, 8, 9, tzinfo=timezone.utc)


def _views(with_data=True):
    out = {}
    for m in ordered_metrics():
        series = (
            [Reading(T0 + timedelta(minutes=30 * i), 10.0 + i) for i in range(4)]
            if with_data else []
        )
        out[m.key] = MetricView(
            metric=m, current=10.0, minimum=None, maximum=None, average=None,
            period_change=None, period_change_status=DeltaStatus.OK, series=series,
            last_updated=T0, freshness=Freshness.FRESH,
            condition=MonitoringCondition.UNKNOWN, has_data=with_data,
            change=DeltaResult(1.0, DeltaStatus.OK),
        )
    return out


class TestGridShape:
    def test_renders_one_cell_per_configured_metric(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        assert len(find_by_exact_class(grid, "trend-cell")) == len(ordered_metrics())

    def test_cells_follow_display_order_and_do_not_reflow(self):
        expected = [m.label for m in ordered_metrics()]
        for active in ("temperature", "energy"):
            grid = trend_grid(_views(), active, "dev-1")
            labels = [e.children for e in find_by_class(grid, "trend-cell__label")]
            assert labels == expected

    def test_no_modebar_anywhere(self):
        assert TREND_CHART_CONFIG["displayModeBar"] is False

    def test_selected_cell_uses_selection_styling_not_a_warning_class(self):
        grid = trend_grid(_views(), "voltage", "dev-1")
        selected = [
            e for e in find_by_class(grid, "trend-cell")
            if "trend-cell--selected" in e.className
        ]
        assert len(selected) == 1
        assert "warning" not in selected[0].className
        assert "freshness" not in selected[0].className

    def test_every_cell_links_to_its_metric_preserving_period(self):
        grid = trend_grid(_views(), "temperature", "dev-1", period="7d")
        hrefs = [href for _label, href in links(grid)]
        assert len(hrefs) == len(ordered_metrics())
        assert all("period=7d" in h for h in hrefs)
        assert any("metric=energy" in h for h in hrefs)

    def test_custom_bounds_survive_promotion(self):
        grid = trend_grid(
            _views(), "temperature", "dev-1",
            period="custom", custom_start="2026-08-01", custom_end="2026-08-03",
        )
        hrefs = [href for _label, href in links(grid)]
        assert all("start=2026-08-01" in h and "end=2026-08-03" in h for h in hrefs)

    def test_empty_metric_keeps_full_cell_height(self):
        """A collapsed cell reads as a layout fault rather than absent data."""
        grid = trend_grid(_views(with_data=False), "temperature", "dev-1")
        graphs = [n for n in walk(grid) if getattr(n, "figure", None) is not None]
        assert all(g.figure.layout.height for g in graphs)

    def test_energy_cell_is_a_bar_chart(self):
        grid = trend_grid(_views(), "temperature", "dev-1")
        graphs = [n for n in walk(grid) if getattr(n, "figure", None) is not None]
        energy = graphs[-1]
        assert any(t.type == "bar" for t in energy.figure.data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trend_grid.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'components.trend_grid'`

- [ ] **Step 3: Write minimal implementation**

Create `components/trend_grid.py`:

```python
"""Quick Trends — one small chart per metric, always all eight.

Positions never reflow, so cell location becomes muscle memory. Interaction
lives in the primary chart: these cells carry no modebar, and clicking one
promotes that metric upward via the same `device_href` contract the snapshot
tiles use, so period and custom bounds survive without a new URL parameter.
"""
from __future__ import annotations

from dash import dcc, html
import plotly.graph_objects as go

from components.metric_chart import BAR_COLOR, LINE_COLOR
from config.metrics import Aggregation, MetricConfig, format_value, ordered_metrics
from routes import device_href
from services.monitoring_service import (
    MetricView, bin_consumption, choose_bin,
)

TREND_CELL_HEIGHT = 120

#: No modebar: 8 more toolbars would compete with the primary chart. Dragging is
#: off for the same reason, but hover stays on — §21 requires the absolute UTC
#: instant to be reachable.
TREND_CHART_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "responsive": True,
    "displaylogo": False,
}


def _sparse_layout(metric: MetricConfig) -> dict:
    return dict(
        margin=dict(l=32, r=8, t=4, b=20),
        height=TREND_CELL_HEIGHT,
        template="plotly_white",
        showlegend=False,
        dragmode=False,
        xaxis=dict(showgrid=False, nticks=4, title=None),
        yaxis=dict(showgrid=True, gridcolor="#eef0f3", nticks=3, title=None),
    )


def _cell_figure(view: MetricView) -> go.Figure:
    metric = view.metric
    fig = go.Figure()
    if not view.series:
        fig.add_annotation(text="No readings in this period", showarrow=False,
                           font=dict(size=11, color="#6b7280"))
    elif metric.aggregation is Aggregation.DELTA:
        span = view.series[-1].timestamp - view.series[0].timestamp
        bars = bin_consumption(
            view.series, choose_bin(span),
            view.series[0].timestamp, view.series[-1].timestamp,
        )
        fig.add_trace(go.Bar(
            x=[b.start for b in bars],
            y=[b.result.value if b.result.is_known else None for b in bars],
            marker_color=BAR_COLOR,
            hovertemplate="%{x|%Y-%m-%d %H:%M} UTC<br>%{y} " + metric.unit + "<extra></extra>",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=[r.timestamp for r in view.series],
            y=[r.value for r in view.series],
            mode="lines", line=dict(color=LINE_COLOR, width=1.5),
            hovertemplate="%{x|%Y-%m-%d %H:%M} UTC<br>%{y:."
                          + str(metric.precision) + "f} " + metric.unit + "<extra></extra>",
        ))
    fig.update_layout(**_sparse_layout(metric))
    return fig


def trend_cell(view: MetricView, is_selected: bool, device_id: str,
               period=None, custom_start=None, custom_end=None) -> html.Div:
    metric = view.metric
    # Selection styling only. "The one you are looking at" and "the one with a
    # problem" are different statements and must not share a colour.
    classes = "trend-cell trend-cell--selected" if is_selected else "trend-cell"
    return html.Div(
        className=classes,
        children=[
            dcc.Link(
                href=device_href(device_id, metric_key=metric.key, period=period,
                                 start=custom_start, end=custom_end),
                className="trend-cell__link",
                children=[
                    html.Div(
                        className="trend-cell__header",
                        children=[
                            html.Span(metric.label, className="trend-cell__label"),
                            html.Span(format_value(metric, view.current),
                                      className="trend-cell__value"),
                        ],
                    ),
                    dcc.Graph(figure=_cell_figure(view), config=TREND_CHART_CONFIG,
                              className="trend-cell__chart"),
                ],
            )
        ],
    )


def trend_grid(views: dict, active_metric_key: str, device_id: str,
               period=None, custom_start=None, custom_end=None) -> html.Div:
    """Eight cells in display order. Always eight, always the same order."""
    return html.Div(
        className="trend-grid",
        children=[
            trend_cell(views[m.key], m.key == active_metric_key, device_id,
                       period=period, custom_start=custom_start, custom_end=custom_end)
            for m in ordered_metrics() if m.key in views
        ],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trend_grid.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add components/trend_grid.py tests/test_trend_grid.py
git commit -m "feat(device): add the eight-cell Quick Trends grid"
```

---

### Task 9: Wire the grid into the page

**Files:**
- Modify: `pages/device_dashboard.py`
- Modify: `callbacks/device.py`
- Test: `tests/test_device_analytics_wiring.py`

**Interfaces:**
- Consumes: Tasks 6–8.
- Produces: `trend-grid` output on `refresh_device_dashboard`; `error_outputs()` returns 8 values.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_device_analytics_wiring.py`:

```python
class TestGridWiring:
    def test_layout_provides_the_grid_slot(self):
        from pages import device_dashboard
        from tests.dash_tree import find_by_id
        assert find_by_id(device_dashboard.layout(), "trend-grid") is not None

    def test_grid_sits_below_the_primary_chart(self):
        """§6.8: the grid must not push the primary chart down the page."""
        from pages import device_dashboard
        from tests.dash_tree import walk
        ids = [getattr(n, "id", None) for n in walk(device_dashboard.layout())]
        assert ids.index("metric-chart") < ids.index("trend-grid")

    def test_error_outputs_cover_every_output(self):
        from callbacks.device import error_outputs
        assert len(error_outputs()) == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_device_analytics_wiring.py::TestGridWiring -q`
Expected: FAIL — `assert None is not None`

- [ ] **Step 3: Write minimal implementation**

In `pages/device_dashboard.py`, after `readings_table("readings-table")` insert — no, **before** it and after the chart:

```python
            html.H2("Quick Trends", className="section-heading"),
            html.Div(id="trend-grid"),
```

In `callbacks/device.py`: add `Output("trend-grid", "children")` as the last output, add one more `err` entry to `error_outputs()`, change every `[no_update] * 7` to `* 8`, build the grid and append it to the return tuple:

```python
            grid = trend_grid(
                views, metric_key, device_id,
                period=period_value, custom_start=custom_start, custom_end=custom_end,
            )
            return strip, kpis, fig, table_data, table_columns, freshness, last_data, grid
```

Also switch the primary chart to the bar builder when the metric is cumulative:

```python
            if view.metric.aggregation is Aggregation.DELTA and view.series:
                window_start, window_end = view.series[0].timestamp, view.series[-1].timestamp
                bin_width = svc.choose_bin(window_end - window_start)
                prime = repo_prime  # from svc.get_last_reading_before via the service
                fig = build_delta_figure(
                    view.metric,
                    svc.bin_consumption(view.series, bin_width, window_start, window_end, prime),
                    view_revision=chart_revision(metric_key, period_value, custom_start, custom_end),
                    period_label=label,
                    bin_label=svc.bin_label(bin_width),
                )
            else:
                fig = build_metric_figure(...)  # unchanged
```

Add `bin_label(bin_width: timedelta) -> str` to the service (e.g. `"30 min bars"`, `"6 h bars"`, `"1 d bars"`) and a service helper `energy_prime(device_id, window_start)` that calls `repo.get_last_reading_before(device_id, "energy", window_start)` — the callback must not call the repository directly.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pages/device_dashboard.py callbacks/device.py services/monitoring_service.py tests/test_device_analytics_wiring.py
git commit -m "feat(device): render the trend grid and energy bars on the page"
```

---

### Task 10: Grid styling

**Files:**
- Modify: `assets/app.css`
- Test: `tests/test_trend_grid.py`

**Interfaces:**
- Consumes: Task 8.
- Produces: `.trend-grid`, `.trend-cell`, `.trend-cell--selected`, `.trend-cell__header` styles.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_trend_grid.py`:

```python
import pathlib
import re

CSS_TEXT = (
    pathlib.Path(__file__).resolve().parent.parent / "assets" / "app.css"
).read_text(encoding="utf-8")


class TestGridStyling:
    """Source guards. Computed widths are verified in a browser per §6.9."""

    def test_two_columns_on_desktop(self):
        assert re.search(
            r"\.trend-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,",
            CSS_TEXT, re.S,
        )

    def test_falls_back_to_one_column_when_a_cell_gets_too_narrow(self):
        assert re.search(
            r"@media \(max-width: 1023px\)\s*\{[^}]*\.trend-grid[^}]*repeat\(1,",
            CSS_TEXT, re.S,
        )

    def test_selection_styling_uses_the_accent_token(self):
        match = re.search(r"\.trend-cell--selected\s*\{([^}]*)\}", CSS_TEXT, re.S)
        assert match and "--color-accent" in match.group(1)

    def test_selection_styling_never_borrows_the_warning_palette(self):
        match = re.search(r"\.trend-cell--selected\s*\{([^}]*)\}", CSS_TEXT, re.S)
        for forbidden in ("--color-warning", "--color-danger", "--color-stale"):
            assert forbidden not in match.group(1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_trend_grid.py::TestGridStyling -q`
Expected: FAIL — all four assertions

- [ ] **Step 3: Write minimal implementation**

Append to `assets/app.css`:

```css
/* ---------- Quick Trends ---------- */
/* Two columns on desktop: at the 1200 px content cap a cell is ~570 px, which
   holds 48 energy bars at ~12 px each. Below 1024 px a two-column cell drops
   under the ~280 px a trace needs to stay legible, so it goes single column
   rather than shrinking further. */
.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}

.trend-cell {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
}

.trend-cell__link { text-decoration: none; color: inherit; display: block; }

.trend-cell__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--sp-1) var(--sp-2) 0;
}

.trend-cell__label {
  font-size: 11px;
  color: var(--color-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.trend-cell__value { font-size: 14px; font-weight: 600; }

/* Selection only. A selected cell must never look like a cell in trouble —
   freshness and warning colours stay out of this rule entirely. */
.trend-cell--selected {
  border-color: var(--color-accent);
  box-shadow: inset 0 0 0 1px var(--color-accent);
}

@media (max-width: 1023px) {
  .trend-grid { grid-template-columns: repeat(1, minmax(0, 1fr)); }
}
```

If `--color-surface` does not exist in the token block, use the token the other card components use — check `.kpi-card` and match it.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest -m "not db" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add assets/app.css tests/test_trend_grid.py
git commit -m "style(device): lay out the Quick Trends grid with selection-only highlighting"
```

---

### Task 11: Browser acceptance

**Files:**
- Create: `docs/UX_ACCEPTANCE_DEVICE_ANALYTICS.md`
- Modify: `tests/test_frozen_contracts.py`

**Interfaces:**
- Consumes: Tasks 1–10.
- Produces: a written acceptance record with measured values.

- [ ] **Step 1: Start the stack and load the device page**

```bash
docker compose up -d
.venv/Scripts/python.exe app.py
```

Log in (`admin` / `demo1234`), navigate to a device, set the viewport to 1366×768.

- [ ] **Step 2: Measure the vertical budget — computed, not from CSS**

In the browser console, confirm the primary chart still starts at or above 420 px and the tile height is unchanged:

```js
Math.round(document.querySelector('.js-plotly-plot').getBoundingClientRect().top)
Math.round(document.querySelector('.snapshot-tile').getBoundingClientRect().height)
```

Expected: chart top ≤ 420 (was 390 before the direction line); tile height unchanged from the pre-change value. If the direction line pushed the chart past 420, reduce the tile's line-height rather than renegotiating §6.8.

- [ ] **Step 3: Confirm the energy bars are real**

Select Energy, period 24h. In the console:

```js
const y = document.querySelectorAll('.js-plotly-plot')[0].data[0].y;
[y.length, y.filter(v => v === 0).length, y.filter(v => v > 0).length]
```

Expected: ~48 bars, **zero** of them exactly 0. All-zero output means the in-bin `last − first` definition crept back in.

- [ ] **Step 4: Confirm the grid**

```js
document.querySelectorAll('.trend-cell').length            // 8
document.querySelectorAll('.trend-cell .modebar').length   // 0
document.documentElement.scrollWidth > document.documentElement.clientWidth  // false
```

Click a cell's trace and confirm it promotes that metric to the primary chart with the period preserved. **Contingency:** if Plotly swallows the click inside the `dcc.Link`, move the link to wrap only `.trend-cell__header` and record that in the acceptance doc — do not add `staticPlot`, which would kill the hover §21 requires.

- [ ] **Step 5: Write the acceptance record and commit**

Create `docs/UX_ACCEPTANCE_DEVICE_ANALYTICS.md` with the measured numbers from steps 2–4, following the format of `docs/UX_ACCEPTANCE_DEVICE.md`. Record any defect found and whether it was fixed or deferred.

```bash
git add docs/UX_ACCEPTANCE_DEVICE_ANALYTICS.md tests/test_frozen_contracts.py
git commit -m "test(ux): device analytics acceptance pass"
```

---

## Self-Review

**Spec coverage:** §2 chart matrix → Tasks 1, 5. §3 binning → Tasks 1, 4. §4 discontinuities → Tasks 2, 4, 6. §5 layout → Tasks 7, 9, 10. §6 architecture → Tasks 1–10. §7 data flow → Tasks 3, 6. §8 error/empty → Tasks 8, 9. §9 testing → every task. §10 risks → Task 11.

**Known follow-up:** the spec's payload risk (~11,520 points at 30d) is measured in Task 11 but no downsampling task exists, deliberately — per the spec, downsampling is added only if a measured budget is missed, and it would need its own tests proving the decimator cannot drop a spike.

**Type consistency:** `DeltaResult`/`DeltaStatus` (Task 2) are consumed by Tasks 4–8 under the same names. `ConsumptionBar.result` is a `DeltaResult` everywhere. `MetricView` gains `period_change_status` (Task 2) and `change` (Task 7); every constructor call in tests and services must pass both.
