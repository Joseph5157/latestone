# UX Acceptance — Fleet Overview Visual Slice v2

Verification pass for `docs/superpowers/specs/2026-08-09-fleet-overview-visual-v2-design.md`
and `docs/superpowers/plans/2026-08-09-fleet-overview-visual-v2.md` (Tasks 1–8,
commits `1a7c9f5`..`cefe947`). Measured in real browsers, not inferred from
source — per this project's own rule: a stylesheet-source assertion has passed
twice in this codebase while the browser rendered something different (DEF-1's
focus ring, the `.dash-cell-value` `text-overflow: inherit` finding).

**Environment note.** The sandboxed Chrome instance available via
`claude-in-chrome` runs on a fixed physical display and could not be resized
below ~1920 px CSS width (`resize_window` reported success but `window.
outerWidth` never changed). All width-sensitive measurements below were taken
with **Playwright**, which manages its own viewport independent of physical
screen size (`page.setViewportSize`) and gave genuine 1366×768 and 1920×1080
CSS-pixel viewports. `claude-in-chrome` was used for one confirmatory
screenshot at its native ~1568 CSS-px width (device-pixel-ratio artifact of
that environment), included for visual reference alongside the Playwright
screenshots.

Data: the seeded dataset (30 plants, 71 transformers, 120 devices), all stale
(0 fresh / 120 stale) — the documented, deliberate "not debt" state. DB
container `plant_monitoring_postgres` (already running, already seeded — not
created for this pass), app run on port **8077** (8050 was occupied by two
pre-existing, unrelated `python.exe app.py` processes not started by this
session and not stopped, to avoid touching work that isn't this session's).

---

## 1. Measurements at 1366×768

| Metric | Measured | Target |
|---|---|---|
| `window.innerWidth` | 1366px | 1366px (real viewport, confirmed) |
| `.page--monitoring` content width | 1351px | fills viewport minus scrollbar (no cap engaged — 1550 > 1366) |
| `.page--monitoring` padding | 24px / 24px | 24px per spec §4.3 |
| `.page--monitoring` `max-width` (computed) | 1550px | `var(--w-monitoring)` |
| KPI cards (Plants/Transformers/Devices) | 282×85px each | `1fr` of `repeat(3,1fr) 1.5fr` |
| KPI card (Data Health) | 422×85px | `1.5fr` — ≈ 1.5× the others (282×1.5=423, ✓) |
| KPI value font-size | 30px | `var(--fs-fleet-kpi)` = 30px |
| `.page--monitoring h1` font-size | 24px | `var(--fs-fleet-title)` = 24px |
| Table data row height | 39px | 40–44px target — a target, not a guarantee, and within 1px |

The three structural KPI cards do **not** read as empty slabs at this width —
282px comfortably holds a label, a two-digit/three-digit value, and "active".

Screenshot: `docs/ux-baseline/acceptance-fleet-1366.png` (viewport),
`acceptance-fleet-1366-full.png` (full scrollable page) — Playwright, genuine
1366×768 CSS-pixel viewport.

## 2. Measurements at 1920×1080

| Metric | Measured | Target |
|---|---|---|
| `window.innerWidth` | 1920px | 1920px (real viewport, confirmed) |
| `.page--monitoring` content width | **1550px** | capped at `--w-monitoring` |
| Outer whitespace (left / right) | 178px / 193px | present, roughly centered — not glued to the viewport edge |
| KPI cards (structural) | 326×85px each | scales with the wider container |
| KPI card (Data Health) | 489×85px | 326×1.5=489 ✓ |

**This is the direct confirmation that `--w-monitoring` behaves as a maximum,
not a target**: the container grows from 1351px (1366 viewport) to the 1550px
cap (1920 viewport) and stops — it does not keep growing to fill 1920. The
remaining ~371px becomes outer whitespace, matching the design intent ("the
dashboard should no longer look like a tiny application floating in a huge
empty canvas" while "tables must remain comfortably readable").

Screenshot: `docs/ux-baseline/acceptance-fleet-wide.jpg` (`claude-in-chrome`
capture at this environment's native wide layout, ~1568 CSS-px due to that
environment's own devicePixelRatio; visual reference only — precise numbers
above are from Playwright's genuine 1920×1080 viewport).

## 3. Computed-style verification — OBS-2 reveal

Selector branch taken (per plan Task 7 Step 5's ordered fallback): **primary
branch** — `td[data-dash-column="..."]` confirmed present in the live DOM
(`class="dash-cell column-6" data-dash-column="freshness"`, etc.), so no
fallback to the `column-N` index class or to plain wrapping was needed.

| Check | Result |
|---|---|
| `country`/`fuel`/`freshness` cell at rest | `white-space: nowrap; overflow: hidden; text-overflow: ellipsis` ✓ |
| Same cell under real Playwright `:hover` | `white-space: normal` (reveal fires) ✓ |
| Same cell under `:focus-within` (programmatic focus) | `white-space: normal` (reveal fires) ✓ |
| Reveal scoped to only `country`/`fuel`/`freshness` | Confirmed — selector is column-scoped, not a generic `.dash-cell` rule |
| Overlap with neighbouring cell | None observed: `white-space: normal` wraps *within* the cell's own box rather than overflowing horizontally (`overflow: hidden` — inert per Task 7's own finding, but harmless: the `td` has auto height, so wrapped content grows the row instead of spilling sideways) |
| Focus ring (DEF-1) | Not independently re-measured this pass — architecturally out of risk, since Task 7's CSS rule sets only `white-space`/`overflow`, never `outline`/`box-shadow`; DEF-1's ring rule is untouched and pre-existing |

## 4. Plant identity column — never truncates

`td[data-dash-column="plant"]` containing "Itaipu Binacional Dam (Paraguay
part)": `white-space: normal` confirmed, cell height **56px** (taller than the
39px baseline row — exactly the documented trade-off: "rows whose plant name
wraps are taller by design").

### New finding — not part of this slice, logged not fixed

`components/entity_table.py`'s link-column styling sets `overflowWrap:
"anywhere"` inline (pre-existing code, predates every task in this plan). The
live DOM's `element.style.cssText` does **not** contain `overflow-wrap` at
all — only `white-space: normal` actually lands; `dash_table` silently drops
the `overflowWrap` key when converting the style dict to inline CSS. This is
the same class of defect this project has hit twice before (source says one
thing, the browser does another).

**Why this isn't a current problem:** `white-space: normal` alone already
wraps on the natural word-break points (spaces), and every plant name in the
current 30-plant dataset contains spaces. **Why it's still worth recording:**
a single unbroken long token (no spaces — a URL, an ID, a name in a script
without word-breaking spaces) would not wrap and could overflow the column,
which is exactly the silent-truncation failure mode OBS-2 was written to
prevent. Not fixed here — it is pre-existing code no task in this plan
touched, and the rule "never opportunistically fix things outside the slice"
applies. Recorded as **OBS-3** for `docs/UX_DEBT.md` (not yet added there;
flagging for the next pass that touches that file, per this document being
the acceptance record rather than the debt ledger).

## 5. Unusual data

| Case | Result |
|---|---|
| `Itaipu Binacional Dam (Paraguay part)` | Wraps correctly, no truncation, renders and sorts correctly |
| `MONTALTO (Alessandro Volta)` | Renders correctly |
| `Niederaussem power station` | Renders correctly |
| `Bełchatów` (diacritic) | Renders correctly; sorts into correct alphabetical position (B-e-ł... between Bang Pakong and DOEL 4) |
| Sorting (Plant column, ascending) | Confirmed via real click on the sort control — alphabetical order including the diacritic name |
| Filtering | **Not conclusively re-verified this pass** — the filter input's exact index among `dash_table`'s rendered `<input>` elements could not be reliably targeted via automation in the time available. Not a risk specific to this slice: `filter_action="native"` is untouched by every task in Tasks 1–8 |
| Keyboard-only navigation | `:focus-within`-driven reveal confirmed (§3); full keyboard-only traversal of the whole page not separately walked this pass |
| Database-error path | Not exercised this pass (would require deliberately breaking the DB connection) |

## 6. Cross-page regression — the shared `_health_summary` change

Because Task 1 changed a function shared across four card call sites, all four
were checked, not assumed:

| Page | Breadcrumb | Data Health | Accent class |
|---|---|---|---|
| Fleet (`/plants`) | `Fleet` | `120 stale` / `0 fresh` | none (confirmed absent) |
| Plant (`/plants/plant-11`) | `Fleet › Az Zour South CCGT` | `7 stale` / `0 fresh` | none |
| Transformer (`/plants/plant-11/plant-11-t1`) | `Fleet › Az Zour South CCGT › ku01` | `1 stale` / `0 fresh` | none |
| Device (`/devices/plant-11-t1-d1`) | `Fleet › Az Zour South CCGT › ku01 › 29044` | n/a (Device has no Data Health card) | n/a |

Every level's Data Health wording is exception-led and unaccented, exactly as
the shared function change requires. Breadcrumb root reads `Fleet` at every
depth, confirming Task 4's rename reached all four layouts.

## 7. Device baseline — settled by measurement

The plan required resolving a documented disagreement: `docs/UX_DEBT.md` cited
**390px**, the device-analytics acceptance pass (`docs/
UX_ACCEPTANCE_DEVICE_ANALYTICS.md`) left it at **406px**.

**Measured live in this pass:**

| Metric | Measured |
|---|---|
| Chart top (`.metric-chart`'s `getBoundingClientRect().top`) | **406px** |
| KPI row height (`.kpi-row`) | **80px** |
| `.page` `max-width` | **1200px** (unchanged — `var(--w-reading)` now resolves to the same literal value `.page` always had) |
| `.page h1` | Device has **no `<h1>` element at all** — it uses a different heading structure, so the `.page h1` rule (restored in Task 6's fix round) never applied to Device in either direction. No regression is possible on that axis. |

**406px is the correct, current baseline.** `docs/UX_DEBT.md` has been
corrected in this pass (see diff) to stop citing 390px as if it were still
true — it was true only at the time that entry was written, before the
device-analytics expansion moved the figure.

## 8. Suite

Full suite (all tests, DB included, run against the seeded, already-running
Postgres container): **607 passed**. Non-db suite alone: **554 passed, 53
deselected** (matches the ledger's running count through Task 8).

## 9. Observations logged, not fixed

- **OBS-3** (§4 above): `overflowWrap: "anywhere"` is silently dropped by
  `dash_table`'s inline-style conversion; harmless today (all current names
  have spaces), latent risk for a future unbroken long token. Pre-existing,
  outside this slice.
- Filtering was not re-verified this pass (§5) — recommend a follow-up
  browser check if filter behavior is ever touched by a future task.
- Two pre-existing, unrelated `python.exe app.py` processes were found
  already bound to port 8050 when this pass began. Not started by this
  session, not stopped by this session — this pass ran on port 8077 instead
  to avoid touching another session's work.
