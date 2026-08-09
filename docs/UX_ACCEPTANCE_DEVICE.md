# Device Monitoring vertical slice — acceptance record

**Date:** 2026-08-09
**Scope:** spec deliverables 8–10, run as a strict acceptance pass. No design
changes were made during it except one defect fix, recorded below.
**Result:** all criteria pass. One accessibility defect found and fixed; one
observation deferred; one latent risk noted.

Screenshots: `docs/ux-baseline/`.

---

## Progression

| stage | chart top | KPI card | chart visibility |
|---|---|---|---|
| baseline | 561 px | 104 px | ~207 px of 380 visible |
| after shell compaction | 402 px | 104 px | partly below fold |
| after component work | **390 px** | **80 px** | **fully visible, 390–730 px** |

Budget is 420 px. The chart is no longer merely higher up — it is entirely
inside a 768 px viewport, axis title included.

---

## Criteria

| criterion | result |
|---|---|
| Keyboard reachability | **Pass** — 29 focusable elements: selector dropdowns, breadcrumbs, logout, all 8 snapshot tiles (real `<a>`, not click-divs), metric dropdown, 4 period radios, table pagination, and all 4 modebar buttons |
| Visible focus everywhere | **Pass after fix** — see DEF-1 |
| No status by colour alone | **Pass** — all 9 freshness badges carry a text label; verified programmatically, not by eye |
| No horizontal overflow at 1366×768 | **Pass** — `scrollWidth == clientWidth == 1351`; zero elements extend past the viewport |
| Chart usable at 1366×768 | **Pass** — 390–730 px, title/axis/labels all in view |
| Chart usable at 1920×1080 | **Pass** — 1160 px wide, 7 d of 30-minute data readable, 10 table rows visible without scrolling |
| Long names / diacritics | **Pass** — 310 px column; `Bełchatów` and `Itaipu Binacional Dam (Paraguay part)` both fit with no clipping across all 30 rows |
| Stale state | **Pass** — every tile and the header read `Stale` with paired age; data still shown, not replaced by an error |
| No-data state holds layout | **Pass** — future custom range yields identical heights (strip 89, KPI 80, chart 340), `—` values, no invented context, chart shows "No data available for the selected period" |
| Error state | **Pass** — verified earlier by stopping PostgreSQL: generic panel in the UI, full `OperationalError` in the log, no internals leaked |
| Custom range preserves contract | **Pass** — `?period=custom&start=…&end=…` survives, title reads `2026-09-01 to 2026-09-02 UTC` |
| Metric switch preserves period | **Pass** — `?metric=voltage&period=30d`, chart and axis follow |
| Deep-linked period restores | **Pass** — `?period=30d` selects the right radio on load |
| Regression suite | **Pass** — 364 tests, green on consecutive runs |

---

## DEF-1 — focus ring silently absent (found, fixed)

**Severity: high — accessibility.** The focus rule was written as
`:where(a, button, input, …):focus-visible`. `:where()` contributes **zero
specificity**, so Dash's react-select and Plotly's own `outline: none` overrode
it. Keyboard users got no focus indicator anywhere.

It was invisible to every other check: the element still matched
`:focus-visible`, the rule was present in the stylesheet, and a screenshot of an
unfocused page looks identical either way. Only reading the *computed* style of
`document.activeElement` after a real Tab keypress exposed it —
`outlineWidth: 0px, boxShadow: none`.

Fixed by dropping `:where()` and marking the outline `!important`, since the
resets being overridden live in third-party stylesheets a version bump could
change. Re-verified across the selector input, breadcrumb links and snapshot
tiles: `2px solid` on all.

---

## OBS-1 — 1200 px content cap at 1920 px width

**Classification: UX improvement candidate.** Not a defect; do not act during
this slice.

At 1920×1080 the content is capped at 1200 px, leaving 720 px unused (360 px per
side). Assessed against the test "does the screen suffer, or is it merely
spacious":

- Nothing is cramped. Snapshot tiles sit at the validated 138 px, KPI cards at
  281 px, and 10 readings rows are visible without scrolling.
- The readings table is the opposite of cramped — two columns spread across
  1160 px, so the eye travels a long way between timestamp and value. **Widening
  the container would make that worse, not better.**
- The one component that would genuinely benefit is the chart: more horizontal
  resolution helps 7 d and 30 d ranges.

So the improvement, if taken later, is "let the chart use more width", not
"remove the max-width globally". Removing the cap wholesale would degrade the
table it is currently protecting.

Screenshot: `docs/ux-baseline/acceptance-device-1920.png`.

---

## OBS-2 — table cells clip without an ellipsis

**Classification: latent risk, not a current defect.**

Plant name cells compute to `overflow: hidden; text-overflow: clip;
white-space: nowrap`. No name in the current 30-plant dataset is long enough to
truncate, so the acceptance criterion passes.

But the failure mode is silent: a longer name in real client data would be cut
mid-word with nothing to indicate it. `text-overflow: ellipsis` would make the
truncation visible. Left alone here because this is an acceptance pass, and it
belongs with the Fleet Overview table work.

---

## Freshness advances — verified over wall-clock time

The paired freshness line is dynamic, so a screenshot cannot prove it is not
frozen. Sampled on a page left untouched:

| time (UTC) | rendered | navigation between samples? |
|---|---|---|
| 04:23:37 | `14h 53m ago · 08 Aug 2026 13:30 UTC` | — |
| 04:28:30 | `14h 58m ago · 08 Aug 2026 13:30 UTC` | yes (route change) |
| 04:29:28 | `14h 59m ago · 08 Aug 2026 13:30 UTC` | **no** |

The last interval is the meaningful one: 58 seconds elapsed with no navigation
and only passive DOM reads, and the relative half advanced by a minute while the
absolute half stayed identical. The `dcc.Interval` (60 s) drives it through the
same callback that renders everything else, so the relative time cannot drift
away from the data it describes.

---

## Not changed during acceptance

- **UXD-1** (selector bar above the brand header) remains accepted debt. See
  `docs/UX_DEBT.md`.
- **OBS-1** and **OBS-2** deferred as above.
- No design or architecture changes. DEF-1 was a defect fix, not a redesign.
