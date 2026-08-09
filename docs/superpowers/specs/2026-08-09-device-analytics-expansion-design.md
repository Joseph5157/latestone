# Device Analytics Expansion — design

**Status:** approved 2026-08-09, amendments incorporated.
**Predecessor:** `2026-08-08-plant-monitoring-architecture-design.md`.
**UX contract:** `HMI_UI_UX_SPEC.md` (sections 6.8, 6.9, 12–18, 21).

The client's stated priority is charting and KPIs. The device page currently
ships one chart. This phase expands the analytics surface on the device page
only, without adding navigation infrastructure.

---

## 1. Scope

**In scope**

- Device page: eight-metric Quick Trends grid, energy as interval bars,
  direction indicator on the snapshot tiles.
- The service functions that make those charts arithmetically defensible.

**Explicitly out of scope**

- Plant and transformer charts. They need different aggregations (fleet totals,
  cross-device comparison) and belong to their own phase. Building three
  charting systems at once is how all three end up half-specified.
- Thresholds, alarm bands and warning colours. No client rules exist;
  `MonitoringCondition` stays `UNKNOWN`.
- R/Y/B phase comparison. No phase fields exist in the schema.
- Derived electrical relationships (apparent power, computed PF, THD). Deriving
  a quantity the client has not defined risks presenting our arithmetic as their
  measurement.

---

## 2. Chart matrix

The matrix is the contract. Chart type is driven solely by
`MetricConfig.chart_type`; nothing outside `config/metrics.py` branches on a
metric key.

| metric | unit | aggregation | chart | series shown | periods |
|---|---|---|---|---|---|
| temperature | °C | STATISTICS | line | raw samples | 24h / 7d / 30d / custom |
| voltage | kV | STATISTICS | line | raw samples | all |
| current | A | STATISTICS | line | raw samples | all |
| active_power | MW | STATISTICS | line | raw samples | all |
| reactive_power | MVAr | STATISTICS | line | raw samples | all |
| power_factor | — | STATISTICS | line | raw samples | all |
| frequency | Hz | STATISTICS | line | raw samples | all |
| **energy** | MWh | **DELTA** | **bar** | **per-bin consumption** | all |

Energy is the only bar chart, and it is a bar chart *because* its configured
aggregation is DELTA — a cumulative meter answers "how much in this interval",
which is an interval quantity. Every other metric is an instantaneous reading
and stays a line.

No metric gets a threshold band, a target line, or a warning colour.

---

## 3. Energy binning — duration aware, resolution respecting

### 3.1 Rules

1. **Never bin below the source sampling resolution.** Readings arrive roughly
   every 30 minutes. A 5-minute bin would draw mostly-empty bars implying
   measurement we do not have. `SOURCE_RESOLUTION = 30 minutes`, stated once in
   config, changed when real client cadence is known.
2. **Choose by duration, not by period name.** A custom range of 3 days and a
   custom range of 90 days must not share a bin width. The rule reads the span,
   so relative and custom periods go through identical logic.
3. **Target a readable bar count.** Pick the *smallest* bin from the ladder whose
   resulting bar count fits the target, so density is as high as legibility
   allows.

**Ladder:** 30 min, 1 h, 2 h, 3 h, 6 h, 12 h, 1 day, 7 days.

**Target: ≤ 48 bars, for the primary chart and the grid cell alike.**

A single target, deliberately. At two columns a cell is ~570 px wide, which
gives ~12 px per bar at 48 — legible. A separate coarser target for cells would
buy little and would mean the same metric showed different bar widths in two
places on one screen, which is the ambiguity we already refused elsewhere.

If even the coarsest rung exceeds the target, the coarsest rung is used —
truncating the range would be worse than a dense chart.

### 3.2 Resulting bins

| span | bin | bars |
|---|---|---|
| 24 h | 30 min | 48 |
| 7 d | 6 h | 28 |
| 30 d | 1 d | 30 |
| custom 3 d | 2 h | 36 |
| custom 90 d | 7 d | 13 |

Each chart labels its bin width ("6 h bars") so the quantity is never ambiguous.

### 3.3 Bin boundaries

Bins are aligned to UTC wall-clock boundaries (hour, day), not to the first
sample. A day bar therefore means that UTC day, which is what an operator
reading a daily figure assumes.

### 3.4 What a bar actually equals — boundary values, not in-bin extremes

A bar is consumption **across** a bin, so it is computed from the meter value at
each boundary:

```
bar(t0, t1) = V(t1) − V(t0),  where V(t) = value of the last reading at or before t
```

It is **not** `last − first` of the readings inside the bin. That definition is
wrong twice over: at 30-minute sampling with 30-minute bins each bin holds a
single reading and every bar would be **zero**; and at any bin width it drops the
consumption between the last reading of one bin and the first of the next, so
every bar is short by one sampling interval. The error is invisible — the chart
looks entirely plausible.

**Priming.** The first bin needs `V(window_start)`, which is a reading *before*
the window. The repository therefore gains
`get_last_reading_before(device_id, metric, ts)`.

- Prime found → the first bar covers the full bin, and the bars sum exactly to
  `V(last) − V(prime)`.
- No prime (the device began reporting inside the window) → the first bar opens
  at the first reading in the window, the bars still sum exactly to the period
  total, and the Period Change KPI states "from first reading" so the partial
  coverage is disclosed rather than hidden.

In both cases **the bars sum exactly to the Period Change KPI**, which is what
makes the load-bearing test in section 9 an equality rather than an
approximation.

---

## 4. Cumulative meter discontinuities

A meter's period consumption is `last − first`. That identity holds **only while
the meter is monotonic**. It breaks on a reset, a replacement, a rollover, or a
backfill correction.

### 4.1 What we will not do

- **Not** treat a negative delta as consumption. It would print a negative
  MWh figure and read as generation.
- **Not** apply `abs()`.
- **Not** assume a rollover width and add it back. The meter's register width is
  unknown; a wrong constant produces a plausible number that is wrong, which is
  worse than a gap.
- **Not** silently sum only the positive segments. That invents a reading for
  the discarded interval.

No correction rule is invented, because none is supported by domain evidence.
**Open question for the client:** do these meters reset, roll over, or get
replaced, and what should a discontinuity mean operationally?

### 4.2 What we will do

Detection: within a bin (or period), a discontinuity exists if any consecutive
pair of readings decreases, `v[i+1] < v[i]`.

Result type, replacing a bare float:

```
DeltaResult(value: float | None, status: OK | INSUFFICIENT_DATA | DISCONTINUITY)
```

`INSUFFICIENT_DATA` means fewer than two readings — today's `None` case, which
is currently indistinguishable from a discontinuity and must not stay that way.

Presentation:

- A bin with `DISCONTINUITY` draws **no bar** and a neutral gap marker, with
  hover text naming the reason. The marker uses neutral styling, never the
  warning palette — this is a data-quality condition, not an electrical alarm.
- The Period Change KPI shows `—` with the reason as its secondary line, rather
  than a number.
- Discontinuous bins are excluded from any total, and a total computed over a
  range containing one is itself reported as indeterminate.

The seeded dataset is monotonic by construction, so tests synthesise resets.
That is deliberate: this path will never be exercised by our data and would
otherwise ship untested.

---

## 5. Layout

```text
context bar                                     y=118
SNAPSHOT / OPERATIONAL KPIs — 8 tiles + direction   y=193
metric + period controls                        y=~300
selected-metric KPIs — 4 cards                  y=~330
PRIMARY CHART                                   y=390   (§6.8 budget 420)
— fold —
QUICK TRENDS — 8 cells, 4 rows × 2 columns
readings table
```

The snapshot strip **is** the operational KPI row; there is no second one. It
already carries all eight metrics with value and freshness, and a second row
would restate it while pushing the primary chart past its budget.

### 5.1 Quick Trends grid

- **Eight cells, fixed positions**, in `ordered_metrics()` order. Positions never
  reflow, so cell location becomes muscle memory.
- **4 rows × 2 columns** on desktop. Falls back to **1 column** below 1024 px,
  where a two-column cell drops under the ~280 px needed for a legible trace.
- **No modebar.** Interaction lives in the primary chart.
- Sparse axis ticks; **UTC-aware hover** carrying the absolute instant, matching
  §21's rule that an unlabelled instant is ambiguous across ~30 countries.
- Each cell shows metric label, latest value with unit, and the trace.

### 5.2 Selection and promotion

Clicking a cell promotes that metric to the primary chart by setting
`metric-dropdown.value`. The existing sync callback then updates `url.search`,
so period, custom bounds and deep-link shareability are preserved unchanged.
**No new URL parameters.**

The selected cell is marked with **selection styling only** — border and
background weight drawn from the accent/selection tokens. It must not use the
warning or freshness palette: "this is the one you are looking at" and "this one
has a problem" are different statements and must not share a colour.

### 5.3 Snapshot tile direction

Each tile gains one compact line: the change against the start of the selected
period, with direction. It reuses series already fetched and fits the existing
tile height, so the 390 px chart top is unaffected.

For energy, the tile's direction line obeys section 4 — a discontinuity shows
`—`, never a negative.

---

## 6. Architecture

**`config/metrics.py`** — `energy.chart_type` becomes `"bar"`. Add
`SOURCE_RESOLUTION_MINUTES = 30` with a comment that it is a development value
pending real client cadence.

**`services/monitoring_service.py`** — new pure functions:

- `choose_bin(span) -> timedelta` — the ladder of section 3.
- `bin_consumption(series, bin, start, end, prime) -> list[DeltaResult]` —
  UTC-aligned boundaries, each bar computed from boundary values per §3.4, each
  carrying the discontinuity check of section 4.
- `period_delta(series, prime) -> DeltaResult` — replaces the current
  `_compute_delta`, which returns a bare float and treats a negative as
  ordinary consumption.

**`repositories/plant_monitoring_repository.py`** — adds
`get_last_reading_before(device_id, metric, ts)`, the priming read of §3.4. One
indexed seek against `ix_readings_device_metric_ts`, the same shape already
proven by `latest_reading_times`; it is issued only when the selected metric is
a DELTA metric.

**`components/trend_grid.py`** (new) — builds eight figures. Presentation only,
reads `MetricConfig`, never queries.

**`components/metric_chart.py`** — `build_metric_figure` branches once on
`chart_type` (line vs bar). This mirrors the existing rule that `kpi_card` is the
only component branching on `aggregation`.

**`components/metric_snapshot_strip.py`** — tile gains the direction line.

**`callbacks/device.py`** — switches from `get_device_snapshot` +
`get_metric_view` to the existing, already-tested `get_device_full_view`.

---

## 7. Data flow

Today the device callback issues about three queries and receives one metric's
series. `get_device_full_view` issues two batched queries — one latest per
metric, one range across all eight — and returns everything the page needs, plus
one indexed priming seek when the selected metric is cumulative.

**Query count goes 3 → 2 (3 for energy) while the data returned goes from 1
series to 8.**

Payload grows: 30 days × 8 metrics at 30-minute cadence is ~11,520 rows in one
round trip, against ~1,440 today. One callback still owns the whole body, so
there is no second render path to keep in sync.

---

## 8. Error and empty states

`error_outputs()` gains one entry for the grid, keeping the existing
one-fallback-per-output contract.

A metric with no data in the window renders a cell of **identical height** to a
populated one, carrying "No readings in this period" — the fixed-height
empty-state rule already frozen at 89/80/340 px. A cell must never collapse,
because a shorter cell reads as a layout fault rather than as absent data.

---

## 9. Testing

Tests are written before implementation.

**Binning**

- Each ladder rung selected for the span that should select it.
- Never returns a bin below `SOURCE_RESOLUTION`.
- Bars align to UTC hour/day boundaries, not to the first sample.

**Bar arithmetic**

- **A 24 h window at 30-minute sampling produces 48 non-zero bars.** This is the
  regression test for the boundary-value definition: the naive in-bin
  `last − first` yields 48 zeros here, and nothing else in the suite would
  notice.
- A bar equals `V(t1) − V(t0)` from boundary values, not from in-bin extremes.
- With a priming reading, the first bar covers its whole bin.
- Without one, the first bar opens at the first in-window reading and the KPI
  discloses "from first reading".

**Deltas and discontinuities**

- A decreasing pair yields `DISCONTINUITY`, not a negative number.
- Fewer than two readings yields `INSUFFICIENT_DATA`, distinct from
  `DISCONTINUITY`.
- A total spanning a discontinuous bin is itself indeterminate.
- **The load-bearing test: the rendered energy bars sum *exactly* to the Period
  Change KPI** for a clean period, with and without a priming reading. This is
  what catches a chart drawn from cumulative values instead of deltas — a
  mistake that produces a confident, wrong, plausible-looking chart.

**Grid**

- Eight cells, `ordered_metrics()` order, positions stable across metric changes.
- Selected cell carries selection styling and **no** warning/freshness class.
- Clicking a cell sets the metric and preserves period and custom bounds.
- Empty metric renders a full-height cell with an explanatory string.

**Contracts**

- Chart top still ≤ 420 px and tile height unchanged, measured from
  `getComputedStyle`/`getBoundingClientRect` in a browser per §6.9 — not from
  the stylesheet.
- No modebar present in any cell.

---

## 10. Risks

**Payload.** ~11,520 points at 30d. Measure render in the acceptance pass.
Downsample only if a measured budget is missed, and only with tests proving the
decimator cannot drop a spike — a decimator that hides an excursion lies
quietly.

**Bin arithmetic.** The sum-to-KPI test is the guard; without it a wrong chart
looks right.

**Vertical growth.** Eight cells below the fold do not threaten §6.8, but the
tile direction line sits above it. Its height is asserted.
