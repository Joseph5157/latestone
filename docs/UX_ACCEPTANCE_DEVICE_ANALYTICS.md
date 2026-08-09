# Device Analytics — acceptance pass

**Date:** 2026-08-09. **Viewport:** 1366×768. **Device:** `plant-01-t1-d1`.
**Plan:** `docs/superpowers/plans/2026-08-09-device-analytics-expansion.md`.
**Spec:** `docs/superpowers/specs/2026-08-09-device-analytics-expansion-design.md`.

Every number below is a **computed** value read from a running browser, per spec
§6.9. Stylesheet-source assertions are regression guards and appear in the test
suite; they are not evidence and are not recorded as such here.

---

## 1. Vertical budget (§6.8, ≤ 420 px)

Measured after the DEF-2 fix, at all three relative periods:

| period | chart top | tile height | direction line | within budget |
|---|---|---|---|---|
| 24h | 406 px | 93 px | 16 px | yes |
| 7d | 406 px | 93 px | 16 px | yes |
| 30d | 406 px | 93 px | 16 px | yes |

The chart top is now **independent of the data**, which is the property that
matters more than the number. Headroom is 14 px, up from the 10 px measured
immediately after Task 7.

For reference, the progression across this slice: 390 px before the direction
line → 410 px with it → 430 px when a long value wrapped (breach) → **406 px**
after the fix.

## 2. Energy bars are real

The load-bearing check. A bar is consumption across its bin; the naive in-bin
`last − first` yields all-zero bars and looks entirely plausible.

| period | bin chosen | bars | zero-height | bar sum | Period Change KPI |
|---|---|---|---|---|---|
| 24h | 30 min | 49 | **0** | 9.85 | 9.8 MWh |
| 7d | 6 h | 29 | **0** | 428.03 | 428.0 MWh |
| 30d | 1 d | 31 | **0** | 2030.00 | 2030.0 MWh |

Bins match the ladder the spec predicted for each span. The bars sum to the KPI
beside them at every period, so the chart and the KPI are one number rather than
two that happen to be close.

Chart titles carry the bin width: `Energy (MWh) · Last 7 days · 6 h bars`.

Independently confirmed the guard has teeth rather than assuming it: on the same
fixture the naive in-bin definition produces **48 of 48 zero-height bars**, the
boundary-value definition **none**.

## 3. Quick Trends grid

| check | result |
|---|---|
| plots on page | 9 (1 primary + 8 cells) |
| cells | 8, in `ordered_metrics()` order |
| modebars in cells | 0 |
| selected cells | exactly 1 |
| grid columns at 1366 | 2 × 576 px |
| grid columns at 1000 | 1 × 945 px |
| horizontal overflow | none at either width |
| cell link underline | none |

The 576 px column matches the ~570 px the 48-bar target was sized against, so
bars land at roughly 12 px each.

## 4. Promotion — the plan's contingency was not needed

The plan anticipated that Plotly might swallow a click inside the cell's
`dcc.Link` and specified a fallback of shrinking the link to the header only.
**It is not needed.** Clicking the *chart area* of a cell navigates:

- Clicked Voltage cell's trace → `?metric=voltage`
- Set period 7d, clicked Energy cell's trace → `?metric=energy&period=7d`

The period survives promotion, and no new URL parameter or callback was
introduced — promotion reuses the `device_href` contract the snapshot tiles
already use. Hover is retained, so `staticPlot` was never required.

## 5. Defect found and fixed

### DEF-2 — the direction line wrapped and breached the chart-top budget

**Severity:** high — it broke a binding acceptance budget.

`.snapshot-tile__direction` was added in Task 7 with **no CSS rule at all**, so
it inherited `white-space: normal`. On a 7-day energy delta the value read
`▲ +428.0 MWh`, wrapped to two lines, and measured 40 px against 20 px for every
other tile. The strip is a CSS grid, so that one wrapped tile stretched all eight
from 97 px to 117 px and pushed the primary chart from 410 px to **430 px** —
past the 420 px budget.

**Why it survived the task that introduced it.** The Task 7 check ran at the
default 24h period, where the same tile reads `+9.8 MWh` and fits on one line.
The defect is *value-dependent*, so a single-period check could not see it. This
is the second time in this project a defect has been value- or state-dependent
and invisible to a single spot check.

**Fix.** An explicit rule matching `.kpi-card__secondary`: fixed 16 px height,
`nowrap`, and `text-overflow: ellipsis` so truncation stays visible. Re-verified
across all three periods; the chart top is now constant at 406 px regardless of
the values displayed.

## 6. Observations, not defects

**OBS-3 — the 30d energy series is bin-limited, not data-limited.** 30 days at
1-day bins gives 31 bars, one more than the nominal 30 because the window opens
mid-day. Correct, and the partial first bar is labelled by its own timestamp.

**OBS-4 — the seeded data ends ~21 h in the past**, so a wall-clock-anchored 24h
window legitimately contains only ~6 readings for some metrics. That is the
period-anchoring behaviour fixed earlier in the project working as intended, not
a defect of this slice.

**OBS-5 — payload was not a problem.** The spec flagged ~11,520 points at 30d as
a risk requiring possible downsampling. Nine plots render without a measurable
stall at every period tested, so no decimator was added — which is the right
outcome, since a decimator that drops a spike lies quietly and would have needed
its own correctness tests.

## 7. Suite

578 tests green, including the DB suite. One cold-cache timing test in the
repository suite flaked once during Task 9 and passed in isolation and on two
consecutive full runs — the known `tests/timing.py` no-warm-up behaviour that
spec §9 already documents, not a regression from this work.
