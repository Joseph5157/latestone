# HMI / UI UX Specification — Power Plant Monitoring

**Status:** Draft v2 — re-baselined against audited PR branch; implementation contract for remaining UI refinement  
**Primary framework:** Python Dash + Plotly  
**Primary target:** Desktop/laptop operator workstation  
**Current scope:** Fleet Overview + Device Monitoring foundations  

---

## 1. Product Design Goal

Build a professional industrial monitoring interface that lets an operator answer five questions quickly:

1. Is the monitored fleet/data healthy?
2. Which plant/equipment requires attention?
3. What is happening on the selected device now?
4. What changed over the selected time period?
5. Can I trust the data being shown?

The interface follows a **high-performance HMI mindset**: calm normal state, strong information hierarchy, minimal decorative colour, clear freshness/data-quality communication, predictable drill-down, and charts that support diagnosis instead of decoration.

This is not a SCADA mimic. Do not add animated pipes, 3D equipment, glowing gauges, speedometers, decorative gradients, blinking objects, or dense multi-axis charts unless a later client requirement explicitly needs them.

---

## 2. Non-Negotiable Project Constraints

- Keep **Dash + Plotly**. Do not introduce another chart engine for the current scope.
- Preserve URL-driven navigation and state.
- Preserve hierarchy: **Plant → Transformer → Device → Metric**.
- PostgreSQL remains the source of monitoring data.
- Data currently updates approximately every 30 minutes; UI refresh must not imply a faster data acquisition rate.
- Do **not** invent voltage/current/power/temperature/etc. warning or critical thresholds.
- `MonitoringCondition` remains `UNKNOWN` until client-confirmed threshold rules exist.
- Administrative equipment state, data freshness and future monitoring condition are separate concepts.
- Correctness and data trust take priority over visual polish.


## 2.1 Baseline Already Implemented on Current Branch

The following behaviours are **already implemented** and are acceptance invariants, not new UX tasks:

- Device equipment identity already shows Plant · Transformer · Device · administrative Status · Last data.
- Parent breadcrumbs are functional where a parent route exists.
- Entity table navigation preserves identity through sorting/filtering/paging using stable row IDs.
- Capacity remains numeric for correct sorting.
- Metric switching retains the selected period; the period is URL-shareable.
- Period changes intentionally reset the Plotly viewport via chart revision.
- Relative periods are anchored to wall-clock time, so stale devices do not redefine “Last 24h”.
- Database-unavailable states are handled without exposing stack traces.
- Current audited navigation and numeric-sort fixes must not regress during the UI refactor.

Phase UX-0 therefore does **not** re-implement these items; it only verifies them before visual changes.

Sections below carry **[IMPLEMENTED]** against any rule already satisfied on the
branch. Treat those as invariants to preserve, not work to schedule. Everything
unmarked is genuine remaining effort.

The invariants are executable — they are encoded in these test modules, which are
what Phase UX-0 should run rather than inspect by eye:

```text
tests/test_table_navigation.py     row identity under sort/filter/paging
tests/test_period_anchoring.py     relative windows anchored to wall-clock now
tests/test_date_range.py           custom end date covers the whole day
tests/test_device_context.py       equipment identity + linked parent breadcrumbs
tests/test_freshness_slot.py       exactly one freshness badge, correct class
tests/test_equipment_selector.py   callback/layout wiring integrity
tests/test_listing_errors.py       database-unavailable state, no internals leaked
```


## 2.2 Equipment Population Rule

Every aggregate, count, listing and freshness rollup uses **one population: active
equipment**. This is not a per-screen choice.

- Overview counts, plant/transformer/device listings, fleet data-health counts and
  every freshness aggregation filter on `status = 'active'`.
- A screen may include inactive equipment only by asking for it explicitly.
- Inactive equipment remains reachable by direct URL and is marked with an inactive
  notice, so historical readings stay inspectable. **[IMPLEMENTED]**

The failure this prevents: counts computed over all equipment while listings show
only active equipment, so an overview row claims 4 transformers and the page it
opens shows 3. Any new aggregate query must carry the same filter as the listing it
summarises, or the two will disagree the moment real data contains decommissioned
plant.

---

## 3. Operator Mental Model

The database hierarchy and the operator investigation hierarchy are related but not identical.

### Physical hierarchy

```text
Plant
  └── Transformer
        └── Device
              └── Metric
```

### Operator investigation hierarchy

```text
FLEET / PLANTS
    ↓
Where is the issue or stale data?
    ↓
PLANT
    ↓
Which transformer/device?
    ↓
DEVICE
    ↓
What changed over time?
    ↓
METRIC / DIAGNOSTICS
```

Every page should progressively reveal more detail instead of repeating the same information at every level.

---

## 4. Information Architecture

### Current implementation routes retained

```text
/login
/plants
/plants/<plant_id>
/plants/<plant_id>/<transformer_id>
/devices/<device_id>
```

### UX naming

- `/plants` becomes the **Fleet / Plants Overview**.
- Plant page = plant-level equipment overview.
- Transformer page = transformer-level device overview.
- Device page = primary monitoring workspace.

### Future-ready navigation, not required in v1

```text
Overview
Plants
Alarms        [future: when client thresholds/events exist]
System Health [future: database/data-quality operational page]
```

Do not create empty navigation destinations prematurely.

---

## 5. Global Shell

### Header priorities

Left to right:

1. Product identity
2. Breadcrumb / hierarchy context
3. Data freshness state where relevant
4. User/logout

The cross-plant equipment selector is **not mounted inside page-local headers** in the current architecture. It remains a separate component in the global app layout so its callbacks never target components that disappear during route changes. A future redesign may move `app_header()` itself into the global layout, but that is a separate architectural change and must make breadcrumb/freshness route-driven callback outputs.

### Header wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ POWER PLANT MONITORING  Plants / Three Gorges Dam / aa12 / 29017  DATA ● FRESH │
│                                                               Logout        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Rules

- Header height should stay compact, approximately 56–64 px desktop.
- Global shell + selector + equipment context must obey the vertical budget in §6.8; do not stack independent bars simply because each one is individually compact.
- Breadcrumb must be functional where a parent route exists. **[IMPLEMENTED]**
- Current entity is plain text; parent entities are links. **[IMPLEMENTED]**
- Freshness is not shown as a vague green success message. Use explicit text such as `Fresh`, `Stale`, `No data` and optionally `Last reading …` on device pages. **[IMPLEMENTED]**
- Avoid large brand blocks that steal vertical space from monitoring data.

---

## 6. Visual Design System

### 6.1 Design character

Use a neutral, modern industrial interface:

- light neutral background
- white or slightly elevated surfaces
- dark high-contrast text
- restrained brand accent
- borders instead of heavy shadows
- colour reserved primarily for state and selection

### 6.2 Recommended semantic tokens

These are conceptual roles; exact hex values may reuse or evolve the current CSS variables.

```text
Canvas/background     neutral cool grey
Surface/card          white
Primary text          near-black / dark slate
Secondary text        medium grey
Border/divider        light grey
Selection/accent      blue
Fresh/healthy data    restrained green
Stale/attention       amber
Error/unavailable     red
No data/inactive      neutral grey
```

### 6.3 Colour rule

**Normal information should not be coloured aggressively.**

Do not make every normal KPI green. A healthy screen should feel visually calm. Green is best kept to small freshness/status indicators. Amber/red should attract attention only when the underlying state actually warrants it.

Because production electrical thresholds are not yet defined, metric cards must **not** display fabricated Normal/Warning/Critical states.

### 6.4 Typography

Recommended hierarchy:

```text
Page title            22–24 px / semibold
Section heading       16–18 px / semibold
Primary KPI value     24–30 px / bold
Snapshot value        18–22 px / semibold
Body/table            13–14 px
Metadata/labels       11–12 px
```

Use tabular numerals where practical for changing numeric values.

### 6.5 Spacing

Base spacing system:

```text
4 / 8 / 12 / 16 / 20 / 24 / 32 px
```

Cards should be compact. Monitoring screens benefit from density, but never at the cost of scanability.

### 6.6 Radius and shadows

- Radius: 6–8 px.
- Prefer a 1 px border.
- Use subtle shadows only if required to separate major floating controls.

### 6.7 Screens in scope for the design system

The token and component work applies to **every** screen the operator sees, not only
the monitoring pages:

```text
/login                    Login
/plants                   Fleet Overview
/plants/<id>              Plant detail
/plants/<id>/<id>         Transformer detail
/devices/<id>             Device workspace
```

**Login is in scope.** It is the first screen the client sees, it already uses its own
card/input/button styling, and UX-1 token changes will alter it whether or not anyone
checks. Verify Login alongside the monitoring screens for: focus states, contrast,
spacing rhythm, error-message treatment, and responsive behaviour at each breakpoint
in section 24.

Login is also the one screen where the equipment selector must remain hidden — it is
mounted globally and suppressed there. Confirm that after any shell restructuring.

### 6.8 Vertical budget — 1366×768 baseline

The primary chart must begin at **≤ 420 px from the top of the viewport** at 1366×768. This is an explicit acceptance budget, not a style preference.

Measured starting point on the device page at 1366x768:

```text
selector bar        y=0        app header      y=53
equipment context   y=118      snapshot strip  y=193   (212 px, 4x2)
metric controls     y=405      KPI row         y=457
chart               y=561      <- 141 px over budget
```

### Intended path to the budget (in order)

1. **Validate 8 snapshot tiles in one row at 1366 px.** At ~160 px per tile this is
   readable, and it recovers ~106 px — the single largest saving, because the 4x2
   grid is the tallest block on the page. Section 24 already permits 8-across at
   >=1200 px "if validated visually"; this is that validation.
2. **Consolidate vertical chrome.** Three stacked bars (selector, header, equipment
   context) cost 190 px before content.
3. **If still short, integrate the equipment selector visually with the header** —
   but see the constraint below.

### Non-negotiable constraint on step 3

Visual integration must not move the selector into the page-local header component.
Its callbacks fire on every route; mounting it in a component that only some routes
render reintroduces the nonexistent-Output defect recorded as finding 2 in
`docs/CODE_AUDIT.md`. Achieve the appearance with layout/CSS while the component
stays in the global layout, or globalise `app_header()` deliberately as described in
section 5.

**The budget must be met without breaking callback/layout invariants.** If those two
goals ever conflict, the invariant wins and the budget is renegotiated.

- KPI/snapshot controls must not consume enough height to push the primary chart below the fold.
- Reserve approximately 300 px of visible chart height above the fold at 768 px viewport height where practical.

---

# PART A — FLEET / PLANTS OVERVIEW

## 7. Purpose

The Fleet Overview is the first operational screen after login. It should answer:

- How many plants/equipment objects are available?
- Which data feeds are fresh/stale/no-data?
- Which plant should I inspect first?
- How quickly can I drill into a plant?

Until client thresholds/alarm rules exist, this page must be **data-health first**, not alarm first.

---

## 8. Fleet Overview — Desktop Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ POWER PLANT MONITORING                         Fleet / Plants        Logout │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ Plants                                                   Page refreshed 08:21 UTC │
│ Monitor plant hierarchy and data availability                                  │
│                                                                              │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│ │ PLANTS       │ │ TRANSFORMERS │ │ DEVICES      │ │ DATA HEALTH  │        │
│ │ 30           │ │ 71           │ │ 120          │ │ 118 fresh    │        │
│ │ total        │ │ total        │ │ total        │ │ 2 stale      │        │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                                              │
│ Needs attention                                                             │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ STALE DATA  Three Gorges Dam  Device 29017  2h 08m ago · 05:43 UTC     → │ │
│ │ NO DATA     Bang Pakong        1 device      No readings received      → │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ All plants                                                      Search [  ] │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Plant       Country   Fuel    Capacity   Transformers   Devices   Data   │ │
│ │ Three Gorges Dam China  Hydro    22,500        4            7      Stale → │ │
│ │ Grand Coulee     USA    Hydro      6,809        1            1      Fresh → │ │
│ │ Bang Pakong      Thai   Gas        4,384        2            3    No data→ │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Important current-scope distinction

The `Needs attention` block may initially contain **only freshness/data availability exceptions**. Do not label a plant electrically `Critical` or `Warning` without client rules.

Wireframe identities are real rows from the development dataset:
`Three Gorges Dam` (`plant-01`, China, transformer `aa12`, device `29017` — the
client-known reserved identifier), `Grand Coulee` (`plant-07`, USA) and
`Bang Pakong` (`plant-19`, Thailand). Do not pair a plant name with another plant's
transformer/device codes, and do not invent plant names — mockups must exercise real
strings, including long names and diacritics such as `Bełchatów`.

---

## 9. Fleet KPI Cards

### Required initial cards

1. **Plants** — total visible/active plants according to agreed repository semantics.
2. **Transformers** — total relevant transformers.
3. **Devices** — total relevant devices.
4. **Data Health** — fresh/stale/no-data device summary.

### Card anatomy

```text
┌────────────────────┐
│ DEVICES            │
│ 120                │
│ 118 fresh · 2 stale│
└────────────────────┘
```

### Rules

- Use numbers that support decisions, not vanity metrics.
- Do not add sparklines to fleet KPI cards unless the underlying KPI is genuinely time-dependent.
- Card click behaviour is optional; if clickable, it must have an obvious destination/filter.
- If data-health counts cannot be queried efficiently in v1, ship the first three counts and a simple overall freshness summary rather than expensive per-row computations.
- For latest-reading freshness across the fleet, drive lookups from the small
  `devices`/metric set and use indexed
  `LEFT JOIN LATERAL (... ORDER BY reading_ts DESC LIMIT 1)` seeks. Do **not** use a
  whole-table `DISTINCT ON (device_id, metric)` scan over `readings`; it scales with
  historical table size, not with device count.

### Fleet latest-reading query contract

```sql
SELECT t.plant_id, latest.device_id, latest.metric, latest.reading_ts
FROM devices d
JOIN transformers t ON t.transformer_id = d.transformer_id
CROSS JOIN (VALUES ('temperature'), ...) AS m(metric)
LEFT JOIN LATERAL (
    SELECT rr.device_id, rr.metric, rr.reading_ts
    FROM readings rr
    WHERE rr.device_id = d.device_id AND rr.metric = m.metric
    ORDER BY rr.reading_ts DESC LIMIT 1
) latest ON TRUE
WHERE d.status = 'active'
```

**One query serves both** the Data Health card (count the rows) and the plant
freshness column (group by `plant_id`). Do not issue two near-identical queries per
page load.

Measured on the current 1,383,360-row dataset:

| shape | rows | time |
|---|---|---|
| `DISTINCT ON` over `readings` | 960 | 3332 ms — `Index Only Scan ... rows=1383360` |
| lateral seeks, cold cache | 960 | ~86 ms |
| lateral seeks, warm | 960 | ~14 ms |

### Performance budget policy

**≤ 80 ms is a warm/steady-state engineering target, not a cold-cache CI assertion.**

- Performance tests must warm the query first, or take repeated measurements and
  assert on the best/median — never on a single cold run.
- A cold ~86 ms / warm ~14 ms result is **acceptable** and must not fail the build.
  Normal cache and environment variance is not a regression.
- A genuine regression must still fail: a shape change back to a history-wide scan
  moves this into seconds, which any of the above will catch.

This policy exists because `tests/timing.py` currently has no warm-up and has already
produced a spurious failure at 84.5 ms against an 80 ms budget. Copying that pattern
here would make the Data Health card permanently flaky in CI.

- If the budget cannot be met once shaped correctly, defer the Data Health card
  rather than ship an expensive implementation.


---

## 10. Exception-First Ordering

Professional monitoring interfaces surface exceptions before normal rows.

For our current scope, exception priority should be:

```text
NO DATA
↓
STALE
↓
FRESH
```

This ordering applies only to **data freshness**, not electrical condition.

Potential implementation:

- Small `Needs attention` panel above the complete table.
- Or default table sort by freshness severity, then plant name.

The full list must remain accessible regardless of exception state.

---

## 11. Plant Table

Retain the current table concept but improve scanability.

Recommended columns:

```text
Plant | Country | Fuel | Capacity MW | Transformers | Devices | Data freshness
```

### Plant freshness semantics

Plant freshness is the **worst-of child device freshness** with an affected count.
See section 21 for the full metric → device → plant → fleet chain, which is the
canonical definition; this section must not diverge from it.

```text
Fresh
Stale (2 of 8 devices)
No data (1 of 6 devices)
```


### Table rules

- Plant name is the primary interactive link. **[IMPLEMENTED]**
- Capacity remains numeric in the backing data so sorting is numeric. **[IMPLEMENTED]**
- Right-align numeric columns.
- Status/freshness uses compact text + dot/badge, not full-cell colour fills.
- Row hover indicates clickability.
- Preserve row identity through sorting/filtering/paging. **[IMPLEMENTED]** — navigation
  reads `active_cell["row_id"]`. Any new table must do the same; indexing `data` by
  `active_cell["row"]` sends the operator to the wrong entity as soon as a column is
  sorted.
- Search/filter can be added once table navigation remains ID-safe.
- Rows show the active-equipment population only (section 2.2).

---

# PART B — DEVICE MONITORING WORKSPACE

## 12. Purpose

The device page is the primary analytical workspace. It should answer:

- What equipment am I looking at?
- How fresh is the data?
- What are the latest values across available metrics?
- How did the selected metric behave over the chosen period?
- What are its min/max/average or energy delta?
- What raw readings support the chart?

---

## 13. Device Page — Desktop Wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ POWER PLANT MONITORING  Plants / Three Gorges Dam / aa12 / 29017  DATA ● FRESH │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ Device 29017                                        Last reading 08:00 UTC   │
│ Plant Three Gorges Dam · Transformer aa12 · Admin status Active             │
│                                                                              │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│ │ Temp     │ │ Voltage  │ │ Current  │ │ Act Power│                         │
│ │ 67.2 °C  │ │ 11.02 kV │ │ 82.7 A   │ │ 1.82 MW  │                         │
│ │ Fresh    │ │ Fresh    │ │ Fresh    │ │ Fresh    │                         │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘                         │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                         │
│ │ Re Power │ │ PF       │ │ Frequency│ │ Energy   │                         │
│ │ 0.31MVAr │ │ 0.943    │ │ 50.01 Hz │ │278.2MWh │                         │
│ │ Fresh    │ │ Fresh    │ │ Fresh    │ │ Fresh    │                         │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘                         │
│                                                                              │
│ Voltage ▼        [24H] [7D] [30D] [CUSTOM]                  ↻ Refresh       │
│                                                                              │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐                 │
│ │ CURRENT    │ │ MINIMUM    │ │ MAXIMUM    │ │ AVERAGE    │                 │
│ │ 11.02 kV   │ │ 10.94 kV   │ │ 11.08 kV   │ │ 11.01 kV   │                 │
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘                 │
│                                                                              │
│ Voltage (kV)                                                   Last 24 hours │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ 11.1 ┤                           ╭────                                  │ │
│ │ 11.0 ┤──────╮        ╭──────────╯    ╰────────────                     │ │
│ │ 10.9 ┤      ╰────────╯                                                 │ │
│ │      └──────────────────────────────────────────────────────────────     │ │
│ │        08:00        14:00        20:00        02:00        08:00         │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Recent readings                                               View: newest  │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Timestamp                    Voltage                                     │ │
│ │ 2026-08-09 08:00            11.02 kV                                    │ │
│ │ 2026-08-09 07:30            11.01 kV                                    │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Device Context Header

**[IMPLEMENTED]** — see section 2.1. The minimal `Last data:` bar has already been
replaced by an equipment identity area showing
`Plant | Transformer | Device | Status | Last data (UTC)`, and the device breadcrumb
links its plant and transformer parents.

Remaining work here is **visual only**: refinement and the vertical consolidation
required by section 6.7. Do not rebuild the identity area.

### Required information

```text
Device <device_code>
Plant <plant_name> · Transformer <transformer_code> · Status <administrative_status>
Last reading <absolute or relative time>
Freshness <fresh/stale/no data>
```

### Rule

Administrative status (`active/inactive`) must not be visually conflated with data freshness (`fresh/stale/no_data`).

Example:

```text
Device 29017                                      ● Data fresh
Plant Three Gorges Dam · Transformer aa12 · Status Active
Last reading: 09 Aug 2026, 08:00 UTC
```

---

## 15. Metric Snapshot Strip

The current eight-tile concept is retained.

### Improved tile anatomy

```text
┌──────────────────┐
│ VOLTAGE          │
│ 11.02 kV         │
│ ● Fresh          │
└──────────────────┘
```

### Selected state

Selected metric uses:

- accent border
- subtle tinted background
- optional 2 px selection indicator

Do not use status colour to indicate selection.

### Rules

- Metric label
- formatted latest value + unit
- metric freshness
- no fabricated condition state
- clicking changes the selected metric while preserving active period/custom range
- 8 tiles desktop: preferably 4 × 2 unless screen width comfortably supports 8 across

---

## 16. Time Controls

### Current controls retained

```text
24h | 7d | 30d | Custom
```

### Future enhancement

Add `1h` or `6h` only if actual source granularity/operational usage makes those windows meaningful. With approximately 30-minute source updates, a 1-hour chart may contain too little information.

### Rules

- Selected period must be visually obvious.
- Custom range displays the chosen dates after selection. **[IMPLEMENTED]**
- Period selection is URL-shareable, including custom bounds. **[IMPLEMENTED]**
- Changing metric retains period. **[IMPLEMENTED]**
- Changing period resets chart viewport intentionally. **[IMPLEMENTED]** — `uirevision`
  keys on metric + period + custom bounds, so zoom survives the refresh interval but
  resets on any view change.
- Refresh must not silently change the selected period. **[IMPLEMENTED]**
- A custom end date means the **end** of that day. **[IMPLEMENTED]** — treating the
  picker's calendar date as an instant silently drops the whole final day. Any new
  date control must preserve this.
- Custom bounds are timezone-aware UTC before they reach the database. **[IMPLEMENTED]**

---

## 17. KPI Cards — Selected Metric

The existing aggregation-aware architecture is correct and should be retained.

### Statistics metric

```text
Current | Minimum | Maximum | Average
```

### Energy / delta metric

```text
Current meter value | Period change
```

### Card anatomy

```text
┌───────────────────┐
│ AVERAGE           │
│ 11.01 kV          │
└───────────────────┘
```

### Future contextual layer

When the client supplies validated operating ranges/thresholds, KPI cards may add:

- condition label
- distance from normal range
- threshold context

Until then, do not display `Normal` simply because a value looks plausible.

---

## 18. Main Metric Chart

Plotly remains the standard charting engine.

### Required behaviour

- one primary metric per chart
- line chart for current eight metrics
- clear Y-axis metric + unit
- timestamp X-axis
- unified X hover
- responsive width
- zoom/pan
- no legend for a single-series chart
- visible no-data state
- loading state that does not collapse layout

### Recommended visual refinements

- chart surface integrated into a bordered panel/card
- subtle gridlines
- slightly stronger zero/reference line only where semantically useful
- do not force Y-axis to zero for metrics where it destroys useful variation
- title/header row includes metric and period
- keep the toolbar minimal, configured through `modeBarButtonsToRemove` so it is
  testable. Validated against the installed **Plotly 5.24.1** default 2D cartesian
  modebar — only buttons that actually appear are listed:

  ```python
  config={
      "displayModeBar": True,
      "scrollZoom": True,
      "responsive": True,
      "displaylogo": False,
      "modeBarButtonsToRemove": [
          "select2d", "lasso2d",                              # meaningless on a time series
          "zoomIn2d", "zoomOut2d", "autoScale2d",             # drag-zoom + reset cover these
          "toggleSpikelines",                                 # unified hover already does this
          "hoverClosestCartesian", "hoverCompareCartesian",   # hovermode is fixed by us
      ],
  }
  ```

  **`resetScale2d` must remain available.** Zoom and pan are supported behaviour, so
  the operator needs a discoverable way back to the full period. Double-click also
  resets, but an undiscoverable gesture is not an acceptable sole escape route in an
  HMI. `toImage`, `zoom2d` and `pan2d` are also retained.

  `sendDataToCloud` is **not** in the default modebar and we do not set
  `showSendToCloud`, so it must not appear in the removal list — listing buttons that
  are never rendered signals an unvalidated config.

### Chart wireframe

```text
┌───────────────────────────────────────────────────────────────┐
│ Voltage (kV)                                  Last 24 hours   │
│                                                               │
│ 11.1 ┤                    ╭────                               │
│ 11.0 ┤────╮     ╭────────╯    ╰────────────                  │
│ 10.9 ┤    ╰─────╯                                            │
│      └──────────────────────────────────────────────────      │
│        08        12        16        20        00        08    │
└───────────────────────────────────────────────────────────────┘
```

### Threshold bands

Architect the chart so threshold/reference bands can be added later from configuration, but **do not add them now**.

---

## 19. Multi-Metric Correlation — Later Phase

Do not immediately put all eight metrics onto one chart.

If correlation becomes a client requirement, prefer **small multiples with a shared time window**:

```text
┌ Voltage ────────────────┐   ┌ Current ────────────────┐
│ ~~~~~~~~~~~~            │   │ ~~~~~~~~~~~~            │
└─────────────────────────┘   └─────────────────────────┘

┌ Active Power ───────────┐   ┌ Power Factor ───────────┐
│ ~~~~~~~~~~~~            │   │ ~~~~~~~~~~~~            │
└─────────────────────────┘   └─────────────────────────┘
```

This is preferred over incompatible multi-axis “spaghetti” charts.

---

## 20. Readings Table

Retain the table below the chart as an evidence layer.

### Recommended columns

```text
Timestamp | Selected metric value
```

### Rules

- newest first
- units visible in heading or values, but avoid unnecessary repetition if heading is explicit
- use exact timestamps
- empty state explains that no readings exist for the selected period
- table should not dominate the page; chart remains primary

Future: CSV export only if requested by client.

---

## 21. Freshness and Data Trust

Freshness is a first-class monitoring concept.

### States

```text
FRESH
STALE
NO DATA
```

### Device presentation

Show both state and last-reading time.

Pair relative with absolute wherever the exact instant matters — relative alone
drifts, absolute alone is hard to scan:

```text
● Fresh       8 min ago · 09 Aug 2026 05:43 UTC
⚠ Stale       2h 17m ago · 09 Aug 2026 03:26 UTC
○ No data     No readings available
```

UTC remains the explicit application timezone. Plant-local time is a future product
decision and must not be introduced implicitly.

### Freshness aggregation chain (canonical definition)

Freshness is measured per **(device, metric)**. Every level above that is a
**worst-of** rollup carrying the affected count, so an aggregate never hides a
single dead feed behind healthy siblings. Severity order throughout:

```text
NO DATA  >  STALE  >  FRESH
```

| level | rule | display |
|---|---|---|
| metric | measured directly from the latest reading | `Fresh` |
| metric → **device** | worst-of its metrics, + count of affected metrics | `STALE · 1 of 8 metrics` |
| device → **plant** | worst-of its devices, + count of affected devices | `STALE · 2 of 8 devices` |
| plant → **fleet** | same exception-first aggregation, + counts per state | `118 fresh · 2 stale` |

**A device with 7 fresh metrics and 1 stale metric is STALE**, displayed as
`STALE · 1 of 8 metrics`. It is never shown as Fresh, and never as "mostly fresh".
An average or majority rule at any level is forbidden — it is precisely how a single
failed sensor disappears.

If a level has both stale and no-data children, display the worst state and carry
both counts in supporting text or tooltip.

Every level uses the active-equipment population defined in section 2.2.

### Important behaviour

A period such as `Last 24h` should describe the intended requested time window, not hide that the latest underlying data is old. If data is stale, the UI must still say so prominently.

**[IMPLEMENTED]** Relative windows anchor to wall-clock now, not to the newest
reading, so a device that stopped reporting days ago no longer answers "Last 24h"
with a full chart of old data.

### Relative-time refresh rule

Relative labels such as `2h 17m ago` are only valid until the next refresh. They must either:

- update from the existing ~60 s page/freshness interval, or
- be rendered client-side from an absolute timestamp.

Do not render a server-side relative string with no refresh mechanism.

### Timezone rule

Current application timestamps are presented in **UTC**. Every absolute timestamp visible to the operator must include `UTC` (or a clear page-level timezone label). Plant-local time is a future product decision and must not be introduced implicitly.


---

## 22. Data Completeness — Recommended Next Data Feature

Once repository support exists, add a compact data-quality indicator:

```text
DATA QUALITY
Completed intervals 47
Received             46
Completeness         97.9%
Missing intervals    1
```

Expected/completed interval count must include **only intervals whose expected arrival time has elapsed**. For a 30-minute cadence, a wall-clock 24-hour window must not permanently penalise the still-open final interval.

This should be presented as data quality, not an electrical alarm.

It is especially valuable in a government/industrial monitoring context because operators need to distinguish "equipment changed" from "data did not arrive".

---

## 23. Loading, Empty and Error States

Every data component should support explicit states.

### Loading

```text
Skeleton/placeholder preserving component height
```

Reserved-height loading states are required for:

- metric snapshot strip
- selected-metric KPI row
- primary chart
- readings table
- fleet summary cards when refreshed asynchronously

Avoid flashing an empty chart/table before data arrives, and do not let snapshot/KPI rows collapse to zero height and cause layout shift.

### Empty selected period

```text
No readings available for this device and period.
Try another period.
```

### Database/service unavailable

```text
Monitoring data is temporarily unavailable.
The page could not retrieve readings.
[Retry]
```

Do not present a database exception or stack trace in the UI.

### Stale

Do not replace existing historical data with an error panel. Show the chart plus a strong stale-data notice.

---

## 23.1 Accessibility and government-client usability

Accessibility is a functional requirement for this UI refactor. Minimum rules:

- All interactive snapshot tiles, table links, period controls, breadcrumbs and buttons are keyboard reachable.
- Visible focus indicators must not be removed.
- Status is never communicated by colour alone; pair colour with text/icon/state label.
- Text/background and meaningful UI component contrast should meet WCAG AA where applicable.
- Interactive targets should be large enough for reliable pointer use on laptop displays.
- Charts need a text/data-table evidence path; do not make the graph the only way to access a value.
- Screen-reader labels should describe metric name, value, unit, selection state and freshness where applicable.

---

## 24. Responsive Behaviour

Primary design target is desktop at approximately 1366–1920 px widths.

### ≥ 1200 px

- full header
- 4×2 metric snapshot grid or 8 across if validated visually
- four KPI cards in one row
- chart full width

### 768–1199 px

- 2×4 snapshot grid
- 2×2 KPI grid
- breadcrumbs may wrap

### < 768 px

Mobile is a fallback, not the primary operator workflow.

- hide/condense non-critical selector controls
- snapshot strip becomes horizontal scroll or 2-column grid
- KPI cards single/2-column depending width
- table horizontally scrolls
- chart remains readable

Do not compromise desktop operator efficiency to achieve an overly elaborate mobile layout.

---

# PART C — COMPONENT SYSTEM

## 25. Existing Components to Evolve

The current architecture already contains reusable pieces. Evolve them rather than duplicating new UI fragments.

### `components/app_header.py`

Evolve to support:

- compact product title
- fully linked parent breadcrumb
- reliable freshness presentation

Do not re-mount the cross-plant selector inside this page-local header under the current layout architecture. Keep the selector in the global layout unless `app_header()` itself is deliberately globalised.

### `components/metric_snapshot_strip.py`

Retain. Improve:

- hierarchy/spacing
- freshness placement
- selected state
- accessible interaction

### `components/kpi_card.py`

Retain aggregation logic. Improve generic visual anatomy so future subtext/context can be added without metric-specific branching.

Suggested future API concept:

```python
kpi_card(
    label="Average",
    value="11.01 kV",
    secondary=None,
    state=None,
    accent=False,
)
```

`state` must not be populated with fabricated electrical condition values.

### `components/metric_chart.py`

Retain Plotly. Refine:

- chart container/header
- toolbar
- grid typography
- intentional viewport reset behaviour on period change
- hooks for future validated reference ranges/annotations

### `components/entity_table.py`

Retain, but standardise:

- numeric alignment
- hover/focus state
- stable ID navigation after sort/filter
- optional freshness cells

---

## 26. New Reusable Components Recommended

Do not implement all at once; these are target abstractions.

```text
page_heading.py
  title + subtitle + optional right-side actions

summary_card.py
  fleet/plant count card

equipment_identity.py
  device + plant + transformer + admin status + freshness

section_header.py
  compact heading + metadata/actions

data_health_summary.py
  fresh/stale/no-data counts

exception_list.py
  data freshness exceptions in priority order
```

Avoid building a component abstraction unless it is used in at least two places or materially simplifies a complex page.

---

# PART D — IMPLEMENTATION SEQUENCE

## 27. Phase UX-0 — Freeze Functional Baseline

Before UI changes:

- treat the audited PR branch as the functional baseline
- verify the already-implemented invariants in §2.1 remain green
- tests green
- screenshot/reference of existing pages captured
- no DB/schema changes mixed into visual refactor unless required

This phase is verification only; do not recreate fixes already present on the branch.

## 28. Phase UX-1 — Design Tokens + Global Shell

Files likely affected:

```text
assets/app.css
components/app_header.py
components/breadcrumb.py
pages/login.py
```

Deliverables:

- updated semantic CSS tokens
- compact header
- consistent typography/spacing
- page/section heading conventions
- status/freshness badge rules
- **Login verified against the new tokens** — focus states, contrast, spacing and
  responsive behaviour, per section 6.7
- accessibility pass on every token-affected screen: keyboard reachability, visible
  focus, contrast, and no status conveyed by colour alone (section 23.1)

## 29. Phase UX-2 — Fleet Overview

Files likely affected:

```text
pages/plants_overview.py
callbacks/listings.py
components/entity_table.py
services/hierarchy_service.py or monitoring service as appropriate
repositories/plant_monitoring_repository.py if aggregate queries are needed
```

Deliverables:

- summary cards
- data-health summary where performant
- optional freshness exceptions
- enhanced plant table

Do not make N+1 application-layer reading queries across 30 plants/devices. Use one repository query shaped as indexed lateral seeks driven from the small equipment relation.

Existing debt to remove while touching this layer: `populate_plant_detail` currently calls `list_devices()` once per transformer. Replace with a bulk device fetch/grouping path rather than preserving that N+1 pattern.

## 30. Phase UX-3 — Device Workspace

Files likely affected:

```text
pages/device_dashboard.py
components/metric_snapshot_strip.py
components/kpi_card.py
components/metric_chart.py
components/readings_table.py
callbacks/device.py
assets/app.css
```

Deliverables:

- equipment identity header
- revised snapshot tiles
- improved period controls
- refined KPI cards
- chart container and styling
- explicit freshness and empty/error states

## 31. Phase UX-4 — Plant + Transformer Consistency

After the two key screens are approved, propagate the design language to:

```text
pages/plant_detail.py
pages/transformer_detail.py
```

Do not redesign these pages independently.

## 32. Phase UX-5 — Advanced Monitoring Features

Only after client requirements exist:

- electrical warning/critical thresholds
- alarms/events
- chart annotations
- condition bands
- cross-device comparison
- small-multiple diagnostics
- export/reporting

---

# PART E — ACCEPTANCE CRITERIA

## 33. Fleet Overview Acceptance

- Operator can identify total plants/transformers/devices quickly.
- Stale/no-data feeds are distinguishable from fresh feeds.
- No fabricated electrical condition/alarm status appears.
- Plant navigation remains correct after sorting/filtering.
- Table numeric columns sort numerically.
- Page remains usable at 1366×768 without excessive vertical waste.
- Plant freshness uses the worst-of + count semantics defined in section 21.
- Counts and listings use the same active-equipment population (section 2.2); an
  overview count never disagrees with the page it opens.
- Fleet data-health uses the lateral query contract and meets the warm-cache target,
  or the card is deferred. Its timing test warms first and does not fail on cold-cache
  variance.
- Wireframe/mockup identities are real dataset rows, never invented names.
- Keyboard reachable, visible focus, no status by colour alone (section 23.1).

## 34. Device Workspace Acceptance

- Plant, transformer and device context are visible without relying only on breadcrumb.
- Primary chart top is ≤ 420 px at 1366×768.
- Freshness + last-reading time are visible and timestamp timezone is explicit (UTC in current scope).
- Eight latest metric values are scannable.
- Selected metric and period are unmistakable.
- KPI semantics remain correct for statistics vs delta metrics.
- Chart unit/time context is explicit.
- Metric switches preserve period/custom range.
- Period switches intentionally reset/retain viewport according to defined behaviour.
- Stale data is not presented as current data.
- Empty/error/loading states do not break page layout or cause large vertical jumps.
- No client-unconfirmed threshold is displayed.
- A device with any stale metric reads STALE with its affected-metric count, never Fresh.
- Relative times are paired with an absolute UTC instant where the exact time matters.
- `resetScale2d` is present in the chart toolbar.
- Keyboard reachable, visible focus, no status by colour alone (section 23.1).
- Login renders correctly under the same tokens, with the equipment selector hidden.

---

# PART F — DESIGN DECISIONS LOCKED BY THIS SPEC

## 35. Locked for Current UI Refactor

1. **Charting:** Plotly.
2. **Frontend:** Dash/Python.
3. **Style philosophy:** modern high-performance industrial monitoring.
4. **Navigation hierarchy:** Plants → Plant → Transformer → Device.
5. **Primary device visualization:** one selected metric time-series at a time.
6. **Fleet priority:** data-health exceptions before decorative analytics.
7. **Colour:** restrained; status/selection have semantic roles.
8. **KPI semantics:** aggregation-aware; no fabricated conditions.
9. **Freshness:** first-class and independent from equipment administrative status.
10. **Thresholds/alarms:** future-ready but not implemented until client values/rules are confirmed.
11. **Desktop:** primary operational target.
12. **Component strategy:** evolve existing reusable components; avoid page-specific duplication.
13. **Selector placement:** global-layout selector remains separate from page-local header unless the whole header is globalised. Visual integration must not relocate the component.
14. **Timezone:** UTC is explicit in current scope; relative times pair with an absolute UTC instant where precision matters.
15. **Freshness aggregation:** worst-of with affected counts at every level — metric → device → plant → fleet. No averaging or majority rules.
16. **Fleet latest-reading query:** indexed lateral seeks from equipment; no history-wide DISTINCT ON scan. One query serves both the card and the plant column.
17. **Accessibility:** keyboard, focus, contrast and non-colour-only status are required.
18. **Equipment population:** all aggregates, listings and rollups use active equipment; inactive stays reachable by URL with a notice.
19. **Performance budgets:** warm/steady-state targets, measured with warm-up or repeated runs. Cache variance must not fail CI; a shape regression must.
20. **Baseline:** items marked [IMPLEMENTED] are invariants to preserve, verified by the named test modules in section 2.1 — not work to redo.
21. **Design system scope:** includes Login, not only monitoring screens.

---

## 36. Next Design Deliverables

Use a **real Dash vertical slice first**, because Dash/Plotly sizing, `dcc.Dropdown`, DataTable and modebar behaviour are part of the visual constraint:

1. Implement **Device Monitoring — desktop vertical slice** using real tokens and current data.
2. Approve it at 1366×768 and 1920×1080, including the ≤420 px chart-top budget.
3. Capture the proven component/state sheet: Fresh / Stale / No Data / Loading / Error; snapshot tile / KPI card / period selector / freshness badge.
4. Produce the Fleet Overview mockup/implementation using those validated constraints.
5. Propagate the proven component system to Plant and Transformer pages.

Static mockups remain useful for communication, but they are not a gate before the first real Dash screen.
