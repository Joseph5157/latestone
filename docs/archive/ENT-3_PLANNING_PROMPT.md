# ENT-3 — RTL Detail Density & Condition Workspace
## Planning Prompt (frozen scope — REVIEW BEFORE IMPLEMENTATION)

---

## 0. Gate status

| Field | Value |
|---|---|
| Tranche | ENT-3 |
| Baseline | `main = d4d23e3e21a7a134e76cdc9f2fd5c151a4d99c69` |
| Predecessors | ENT-2 (`4e6d26c`, approved), DEFECT-1 (`d4d23e3`, committed) |
| Flow | PLAN → **REVIEW GATE (this document)** → IMPLEMENT → TEST/VISUAL VERIFY → IMPLEMENTATION REVIEW → COMMIT → PUSH GATE |
| Rule | Do not implement until this plan is approved. Do not absorb other tranches. |

---

## 1. Problem statement

The RTL detail page presents every metric twice:

```text
Snapshot strip      label · latest value · direction · freshness badge   (8 tiles)
Quick Trends grid   label · latest value · sparkline                     (8 cells)
```

Both surfaces are built from the same `MetricView` objects and navigate through the
identical `device_href(device_id, metric_key, period, start, end)` contract. The page
carries ~2x the vertical height for one fact per metric plus one trend thumbnail per
metric, plus duplicated hint text.

## 2. Evidence base (verified at baseline)

- `components/metric_snapshot_strip.py` — `snapshot_tile` renders label (L60),
  value (L61–64), direction (L68–71), freshness badge (L72), empty condition slot (L73).
- `components/trend_grid.py` — `trend_cell` renders label + value header (L115–129)
  above a 120px figure (`go.Bar` for DELTA/energy, `go.Scatter` lines otherwise,
  L51–87); bars pre-computed by `monitoring_service.quick_trend_bars`.
- `callbacks/device.py` — `refresh_device_dashboard` makes exactly ONE service call
  (`get_device_full_view`, L147) feeding all eight outputs. This invariant is locked
  by `tests/test_device_analytics_wiring.py` and MUST survive ENT-3 unchanged.
- Hint text duplication candidates: `pages/device_dashboard.py` L127, L196, L214;
  empty-state wording differs ("No readings in this period" vs "No readings").
- Heading grammar on this page is eyebrow+H2 (`device-section__eyebrow`), distinct
  from other pages — see §5 exclusion.

## 3. Target shape

Consolidate the two surfaces into ONE operational metric workspace of eight cells
(one per configured metric, display order, exactly one selected):

```text
┌───────────────────────────┐
│ TEMPERATURE        Stale  │   ← label + freshness state (compact badge)
│ 63.4 °C            ▼ 2.1 │   ← latest value + direction vs period start
│ [ sparkline / bars ]      │   ← line for statistics metrics, bar for energy
└───────────────────────────┘
```

Rules:

1. **One cell per metric.** Label, latest value, direction, freshness, and trend
   render together. The separate snapshot strip is removed from the page.
2. **Selection promotes.** The selected metric drives the main chart and KPI row,
   exactly as today. Cell selection still navigates via `device_href(...)` so
   metric-period URL state is preserved byte-for-byte.
3. **Chart semantics unchanged.** Energy = bars, others = lines; quick-trend bins
   remain `quick_trend_bars`; hover remains UTC instants; no modebar on cells.
4. **Freshness vocabulary unchanged**: Fresh / Stale / No Data only. The condition
   slot stays UNKNOWN and may be dropped from markup if nothing renders into it —
   dropping it is preferred if no behaviour depends on it.
5. **One fetch stays one fetch.** No new repository calls, no second telemetry read,
   no N+1 hierarchy reads. `get_device_full_view` remains the single source.
6. **Hint text reduced.** Merge "Select a tile to promote…" and "Select a metric and
   UTC time range." into at most one instruction line per interactive region. Keep
   the UTC wording on the readings table hint.
7. **Empty-state wording unified** within the page: one phrase for "no data in
   period", reused by cells, chart annotation, and KPI secondary context where the
   same condition applies.
8. **Heading grammar**: device-page-local tidy-up ONLY (see §5).

Responsive: the merged workspace keeps the grouped-surface treatment ENT-2
established — desktop ≥1200px multi-column grouped panel, tablet 2-col, mobile
single-column or horizontal scroll (pick one; horizontal scroll-snap already exists
for the strip and is acceptable). Parent/child visual language stays calm, dense,
neutral-palette; freshness tokens are the only colour accents.

## 4. Frozen invariants (must hold after implementation)

- `svc.get_device_full_view(...)` called exactly once per dashboard refresh.
- No SQL in callbacks/components; services/repositories untouched except… none.
  **No changes to `services/` or `repositories/` at all** unless a defect is proven,
  in which case it becomes its own DEFECT ticket.
- URL contract `metric` / `period` / `start` / `end` unchanged; `device_href`
  signature unchanged; router parse/build untouched.
- Chart revision identity (`chart_revision(metric, period, bounds)`) untouched —
  zoom survival behaviour does not regress.
- No invented thresholds; no Normal/Warning/Critical semantics anywhere.
- Row IDs/navigation stable: `#metric-dropdown`, `#period-radio`,
  `#custom-range-container`, `#kpi-row-container`, `#metric-chart`,
  `#readings-table`, `#header-freshness`, `#equipment-last-data`,
  `#device-refresh-interval` all continue to exist with the same roles.
- Existing error-boundary behaviour preserved (generic UI error, logged detail).

## 5. Explicitly out of scope

- Cross-page section-heading grammar unification → **ENT-6**. Device-page headings
  may adopt clearer wording, but no other page's headings change in this tranche.
- Report UX, notification UX, drawer grammar, Device Management filters/wiring.
- Routing structure, nested device URLs, authorization, scope policy.
- Repository SQL, schema/migrations, seed data.
- Eskom taxonomy, high-temperature/vibration/anomaly semantics.
- Acknowledgement/escalation/suppression/notification lifecycle.
- Data-column custom severity sorting (UXD-2 accepted debt stands).
- New dependencies. Plotly/Dash cover everything required.

## 6. Known test impact (expected, not optional)

| Test file | Why it moves |
|---|---|
| `tests/test_trend_grid.py` | Grid becomes the merged workspace cell contract |
| `tests/test_snapshot_direction.py` | Direction semantics move into merged cells; strip-specific CSS guards rewritten |
| `tests/test_device_presentation.py` | KPI/hint wording contracts touched by §3.7 |
| `tests/test_device_analytics_wiring.py` | Must keep passing UNCHANGED — proves the one-fetch invariant survived |

`test_device_context.py`, `test_chart_types.py`, `test_chart_revision.py`,
`test_chart_presentation.py` are expected green without edits; any edit to them is a
scope smell and needs justification in the implementation review.

New/updated tests must lock:

1. exactly eight merged cells, one per metric, fixed display order;
2. exactly one selected cell; selection styling uses accent only (no warning colours);
3. cell carries value + direction + freshness + sparkline (bar iff DELTA);
4. promotion links preserve `period=` and custom `start`/`end`;
5. snapshot strip absent from `pages/device_dashboard.py` layout;
6. hint-text budget: at most one instruction line per interactive region;
7. CSS source guards for the merged-cell fixed-height/ellipsis contract (DEF-2 style).

## 7. Verification requirements

1. Focused device-page suite:
   `python -m pytest tests/test_trend_grid.py tests/test_snapshot_direction.py tests/test_device_presentation.py tests/test_device_analytics_wiring.py tests/test_device_context.py tests/test_chart_types.py tests/test_chart_revision.py -q`
2. Full suite: `python -m pytest -q` (requires Docker + seeded DB).
3. `git diff --check`; `git status --short`.
4. Visual verification via screenshots: 1366px, 768px, 390px — grouped hierarchy
   readable, no horizontal overflow except the deliberate ≤640px scroll variant.
5. Proof in the review report: single `get_device_full_view` call site; zero diffs
   under `services/` and `repositories/`; URL round-trip demo (select metric +
   custom range, copy URL, reload, state restored).
6. Stop before commit. Wait for review approval. Commit separately. Push separately.

## 8. Suggested commit message (post-approval)

```text
feat(device): consolidate snapshot strip and quick trends into metric workspace (ENT-3)
```

---

## 9. Decision requests for the reviewer

1. **Mobile fallback**: single-column stack vs horizontal scroll-snap for the merged
   8-cell workspace at ≤640px. Plan leans scroll-snap (existing pattern, preserves
   scan order).
2. **Condition slot**: confirm dropping `.snapshot-tile__condition` markup entirely
   (it renders nothing today; `MonitoringCondition` is always UNKNOWN).
3. **Direction line**: keep ▲/▼ vs period start inside merged cells (plan says yes —
   it is the only period-relative fact the cell adds beyond the sparkline).
4. Confirm §5 deferral of cross-page heading unification to ENT-6.
