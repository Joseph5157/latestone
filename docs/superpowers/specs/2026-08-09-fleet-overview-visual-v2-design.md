# Fleet Overview Visual Slice v2 — design

**Date:** 2026-08-09
**Status:** approved, ready for an implementation plan
**Scope:** Phase 1 of the UI modernisation plan. Fleet Overview only.

---

## 1. Purpose

Raise the Fleet page from "KPI cards above a long administration table" to a
portfolio monitoring overview, reusing the frozen Device Monitoring design
system. Visual and presentational work only.

This slice invents no alarms, no thresholds, no charts, no maps, and no new
monitoring vocabulary. `MonitoringCondition` stays `UNKNOWN`.

---

## 2. Invariants

These must hold when the slice lands. Each is asserted, not assumed.

| Invariant | How it is held |
|---|---|
| URL contracts `/plants`, `/plants/<pid>`, `/plants/<pid>/<tid>`, device routes | unchanged; existing routing tests |
| Equipment selector stays globally mounted (UXD-1 remains accepted debt) | `app.layout` untouched |
| One `FleetHealth` per render feeds both the cards and the rows | callback shape unchanged |
| Freshness chain: metric → device → plant → fleet, worst-of | `aggregate_freshness` untouched |
| Active-equipment population rule (`d.status` **and** `t.status`) | existing per-plant assertion |
| No thresholds, alarms or electrical conditions | no new state vocabulary |
| Device-consumed tokens `--fs-kpi`, `--fs-page-title`, `--fs-body`, `--fs-meta` | values byte-for-byte unchanged |
| Device chart top and KPI row height | re-measured in the browser (§9.4) |

**Not in this slice:** Phase 1F's exception-first panel. At the current 120/120
stale it would reproduce the plant table verbatim. Excluded as a decision, not
an oversight; revisit when fleet state is mixed enough for an exception list to
be shorter than the table.

---

## 3. The five locked decisions

1. **Naming.** Page title `FLEET OVERVIEW`; breadcrumb root `Fleet` at all four
   levels. Route stays `/plants`. Domain names, table names and identifiers are
   unchanged — this is a label change only.
2. **Data Health wording.** Exception-led when exceptions exist, health-led when
   they do not, kept in the **shared** `_health_summary()` so Fleet, Plant and
   Transformer speak one sentence.
3. **Width.** The entire Fleet surface sits at monitoring width. Header, KPI
   cards and plant table share one left/right edge.
4. **Overflow.** The Plant identity column wraps and never truncates. Secondary
   text columns ellipsise with an accessible reveal.
5. **Type scale.** Fleet-specific additive tokens. State styling joins on
   semantic identity, never on rendered text and never on a bare rank number.

---

## 4. Tokens and containers

### 4.1 New tokens

```css
--w-monitoring:   1550px;
--w-reading:      1200px;
--fs-fleet-title:   24px;   /* Device keeps --fs-page-title: 22px */
--fs-fleet-kpi:     30px;   /* Device keeps --fs-kpi: 26px       */
--fs-fleet-body:    14px;
```

### 4.2 Tokens deliberately NOT added

`--fs-micro: 11px` and `--fs-table: 13px` appeared in the phase sketch. Both are
omitted: they duplicate the values *and* the roles of the existing `--fs-meta`
and `--fs-body`. A design system grows by adding semantic roles, not by adding a
second name for a role that already exists — two names for one role is precisely
the drift the token layer exists to prevent.

Fleet's *primary body* text is a genuinely new role and does get a token
(`--fs-fleet-body: 14px`). The table stays on `--fs-body`, micro labels on
`--fs-meta`.

### 4.3 Containers

```css
.page             { max-width: var(--w-reading); }      /* was a literal 1200px */
.page--monitoring { max-width: var(--w-monitoring); }
```

`.page` remains the default reading-width container, so Device, Plant and
Transformer are untouched. Fleet alone opts in with
`className="page page--monitoring"`.

**`--w-monitoring` is a maximum, never a target.** At 1920 it caps; at 1366 the
page fills the viewport minus gutters. No rule may set an explicit `width`.

**Gutters are explicit.** `.page--monitoring` states its own
`padding: 0 24px 40px` rather than relying on inheritance from `.page`, so
widening the container can never leave content glued to the viewport edge.

**The page title override is scoped, not global.** `app.css` currently sets
`.page h1 { font-size: 22px }` for every page. Fleet's 24 px comes from a more
specific rule on the modifier:

```css
.page--monitoring h1 { font-size: var(--fs-fleet-title); }
```

The global `.page h1` rule keeps its value, so Device, Plant and Transformer
titles are unchanged. No `!important` — if the cascade needs forcing, the
selector is wrong.

### 4.4 Consequence to verify

Fleet's layout changes at **1366 as well as 1920**. Today `.page` caps at 1200,
leaving ~166 px of margin at 1366; at monitoring width the page fills to ~1318
(1366 − 48 gutters). 1366 is a changed layout, not a control.

---

## 5. Header

```
FLEET OVERVIEW                                   24px / 600
30 monitored plants across the active fleet      14px, muted
Page refreshed 09 Aug 2026 11:24 UTC             11px, muted
```

**The refresh line is an absolute UTC stamp, not a relative time.** There is no
`dcc.Interval` on the Fleet page — only `pages/device_dashboard.py` has one —
so a relative "1 min ago" would freeze at render and quietly lie. Adding an
interval is a callback-architecture change, which is out of scope. An absolute
stamp is honest about being a render time.

`Page refreshed` and `Last data` remain different concepts. The word `updated`
appears nowhere on this page: it reads as sensor freshness.

The plant count is read from the same hierarchy counts that feed the Plants
card, never a literal.

**One timestamp per render.** The stamp is generated once in the listing
callback and passed to both the header and the rows, so the cards and the table
can never report different instants.

---

## 6. KPI cards

```
┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌────────────────────┐
│ PLANTS   │ │ TRANSFORMERS │ │ DEVICES  │ │ DATA HEALTH        │
│ 30       │ │ 71           │ │ 120      │ │ ● 120 stale        │
│ active   │ │ active       │ │ active   │ │ 0 fresh            │
└──────────┘ └──────────────┘ └──────────┘ └────────────────────┘
```

`.kpi-row--fleet` already exists in the markup with no CSS rule behind it. It
gains:

```css
.kpi-row--fleet { grid-template-columns: repeat(3, minmax(0, 1fr)) 1.5fr; }
.kpi-row--fleet .kpi-card__value { font-size: var(--fs-fleet-kpi); }
```

Device's `.kpi-row` is untouched.

### 6.1 Data Health loses `accent=True`

`--color-accent` is documented in `app.css` as **selection** colour. A
permanently accented health card spends the selection signal on something that
is never selected. The card becomes a neutral surface carrying one small state
dot in the state's text colour — restrained treatment, not a bright panel.

This lands on the Plant and Transformer cards too, via the shared component.
That is the shared component working as intended, and both pages are verified
(§9.4).

### 6.2 Exception-led headline

The headline names the **worst state present**, derived by walking `Freshness`
in canonical severity order and taking the first state with a non-zero count.
The dot takes its colour from that same state. Severity order is
`NO_DATA > STALE > FRESH`, the same rule as worst-of aggregation — not a second
ordering maintained by the presentation layer.

| Population | Value | Secondary |
|---|---|---|
| 120 stale, 0 fresh | `120 stale` | `0 fresh` |
| 102 fresh, 15 stale, 3 no data | `3 no data` | `102 fresh · 15 stale` |
| 120 fresh | `120 fresh` | `No stale or missing feeds` |
| empty (total 0) | `No active devices` | `No data available` |

The empty-population wording is specified here **deliberately**, so the test
encodes an intended sentence rather than whatever the implementation happens to
return. Zero devices is not zero problems: a population with nothing in it must
not read as healthy.

### 6.3 No separate health summary panel

Phase 1E sketched a panel below the cards. With the card now reading
`● 120 stale / 0 fresh`, a panel restating that in prose duplicates it. The
card's secondary line already carries the breakdown when the fleet goes mixed.

---

## 7. Plant table

### 7.1 Columns — unchanged

The live `PLANT_COLUMNS` already matches the target column set: Plant, Country,
Fuel, Capacity (MW), Transformers, Devices, Data. Nothing added or removed.

**Cleanup in scope:** `pages/plants_overview.py` carries a second, stale column
spec (`plant_id`, `"Primary Fuel"`) that the callback overwrites on first fire.
It is dead, it contradicts the live spec, and it is the first thing a reader
finds. The layout imports `PLANT_COLUMNS` instead — *provided* `pages →
callbacks` introduces no import cycle. If it does, correct the literal in place;
do not invent a new module purely to de-duplicate.

### 7.2 Numeric alignment

Right alignment is derived from the column spec's existing `type: "numeric"`
declaration, applied to cell and header. Capacity, Transformers and Devices
already declare it. No Fleet-specific column list to drift.

### 7.3 Row density

`style_cell` padding `8px 12px` → `11px 12px`, giving ~40 px against a 40–44 px
target. A target, not a guarantee: rows whose plant name wraps are taller by
design (§7.5).

### 7.4 State styling — the `_state` join

Rows gain `"_state": rollup.state.value` beside the existing `_severity`. The
model is:

```
_severity      → ordering / rank
_state         → semantic identity
rendered text  → presentation only
```

```python
_STATE_TEXT_TOKEN = {           # one named mapping, beside the enum
    Freshness.FRESH:   "--state-fresh-text",
    Freshness.STALE:   "--state-stale-text",
    Freshness.NO_DATA: "--state-none-text",
}

def freshness_style_rules(column_id: str) -> list[dict]:
    return [
        {"if": {"filter_query": f'{{_state}} eq "{s.value}"', "column_id": column_id},
         "color": f"var({_STATE_TEXT_TOKEN[s]})"}
        for s in Freshness       # iterated, never enumerated by hand
    ]
```

Neither a bare `0/1/2` nor a display string such as `"Stale"` appears in any
style rule. `_state` values come from the canonical `Freshness` enum, not a
second handwritten vocabulary.

Cell renders as `● Stale · 7 of 7 devices` in the state's text colour, with
**no background tint**: thirty tinted cells would put more colour on this screen
than the entire Device page, and colour marks exceptions rather than filling a
column.

Adding `_state` does **not** fix UXD-2. Sorting the Data column still orders by
display text; wiring it to `_severity` remains logged debt.

### 7.5 OBS-2 — overflow

**Contract: never silently clip identity or metadata text.**

| Column | Behaviour |
|---|---|
| Plant | wraps, never truncates (already set) |
| Country, Fuel, Data | ellipsis on the `td` (already set) + full text on hover **and** keyboard focus |

The reveal is CSS, because inline `style_cell_conditional` cannot carry
pseudo-classes. It is **column-scoped**, not applied to every `.dash-cell`: a
generic rule would let numeric and status cells change height on focus and make
the table jump.

Selector preference, in order:

1. `td[data-dash-column="country"]` — semantic and order-independent. Verify the
   attribute exists in the rendered DOM.
2. `td.dash-cell.column-N` — index-based fallback. Take only with a comment
   noting it breaks silently if columns are reordered.
3. Wrap those columns as well.

**Falling back to wrapping is preferred over shipping a rule that reads correctly
in the stylesheet and computes to nothing.** That was DEF-1's exact failure mode,
and the `text-overflow: inherit` finding was the same shape.

Verify the reveal does not overlap neighbouring cell content in a misleading
way. If horizontal overflow overlaps, use wrap-on-focus instead.

---

## 8. Files touched

| File | Change |
|---|---|
| `assets/app.css` | tokens, containers, gutters, Fleet type scale, `.kpi-row--fleet`, table density, reveal rule |
| `pages/plants_overview.py` | title, subtitle, refresh slot, container class, dead column spec |
| `components/fleet_summary.py` | exception-led `_health_summary`, accent removal |
| `components/entity_table.py` | numeric alignment, freshness style rules, per-column overflow |
| `callbacks/listings.py` | `_state` on rows, render timestamp output |
| breadcrumb call sites (×3) | root label `Fleet` |
| tests | §9 |

---

## 9. Testing

### 9.1 Pure logic (no Docker)

- `_health_summary` headline follows worst-of: `NO_DATA` leads over `STALE`,
  `STALE` over `FRESH`
- all four §6.2 rows asserted, including the **specified** empty-population
  wording
- `freshness_style_rules` emits exactly `len(Freshness)` rules, so a fourth
  state can never ship unstyled
- every plant row carries `_state` equal to its rollup's state value
- `_severity` and the exception-first default order are **unchanged** —
  regression guard on the contract row-click navigation depends on
- right alignment is derived from `type: "numeric"`
- breadcrumb root reads `Fleet` at all four levels
- **one render timestamp** reaches both header and rows, tested by injecting a
  single frozen timestamp and asserting both consumers carry that exact value —
  never by generating two timestamps and comparing them for proximity
- the layout's column spec and `PLANT_COLUMNS` agree

### 9.2 Browser, measured at 1366×768 and 1920×1080

- page width and gutters at both sizes; 1550 caps at 1920, fills at 1366
- KPI card widths reflect `3 × 1fr + 1.5fr`; row height; value renders at 30 px
- table row height against the 40–44 px target
- `getComputedStyle` on `white-space`, `overflow` and `text-overflow` for Plant
  vs Country/Fuel/Data, **at rest and under focus**. Stylesheet source is not
  evidence
- Tab to a truncated cell: the reveal fires, and the focus ring is still the
  single tight ring DEF-1 established, not a doubled one
- revealed text does not overlap the neighbouring cell
- long and diacritic names: `Itaipu Binacional Dam (Paraguay part)`,
  `MONTALTO (Alessandro Volta)`, `Niederaussem power station`, `Bełchatów`

### 9.3 Unusual data

Long names, Unicode/diacritics, stale, fresh, no data, missing rows, database
error, sorting and filtering, keyboard-only navigation.

### 9.4 Cross-page regression

The shared `_health_summary` reaches beyond Fleet, so:

- **Device** — re-measure chart top and KPI row height; confirm unchanged
- **Plant** and **Transformer** — Data Health is exception-led there too and the
  accent is gone; both verified, not assumed

**The Device baseline is settled by measurement.** `UX_DEBT.md` records a
390 px chart top; the device-analytics acceptance pass left it at 406 px. The
measured value wins, is recorded in `docs/UX_ACCEPTANCE_FLEET.md`, and the
stale figure in the older document is corrected in the same pass so the
ambiguity is not carried forward again.

### 9.5 Suite

Baseline is the measured **526 passing** under `-m "not db"`. The db-marked
tests require Docker; if it is not running, say so plainly rather than report a
partial run as green. No net reduction without a written reason.

---

## 10. Output

- before/after screenshots at both widths into `docs/ux-baseline/`
- `docs/UX_ACCEPTANCE_FLEET.md` carrying the measurements and the settled Device
  baseline
- anything found outside this slice is **logged** as an observation or a
  `UX_DEBT.md` entry — never opportunistically fixed

---

## 11. Commit sequence

```
design decision  →  implementation  →  acceptance
```

This document is the first commit, made before any implementation, so the audit
trail separates what was decided from what was built.
