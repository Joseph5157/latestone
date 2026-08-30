# CC-1 Roadmap

Status: Approved
Date: 2026-08-29

The phase-by-phase build sequence for Command Center, Phase 3 onward. Phases
0-2 (baseline verification, plan, architecture review) are complete —
`docs/context/ACTIVE_GATE.md` covers whichever phase is the current gate in
detail; this file is the map across all of them so that document can stay
short and per-gate instead of accumulating every future phase.

This file is sequence and shape — what to build, in what order, what it
should look like. It is not where the rules live: every rule-bearing bullet
below points at the ADR that owns it. If this file and an ADR ever disagree,
the ADR wins (`docs/context/SOURCE_AUTHORITY.md`).

Reviewed against the repo 2026-08-29 before being recorded — see ADR-008 for
what that review found (two functions confirmed by name/line, one imprecision
in ADR-002 fixed, route policy default confirmed against the pack's own
"Primary users" section).

## Phase 3 — CC-1 foundation — DONE (`cc6b67a`, 2026-08-29)

Route, `ROUTE_POLICY` entry, sidebar item, page, callback layer and the
`command_center_service` facade. Browser-verified 1440/1024; Fleet
Overview unchanged.


- Route: `/command-center` in `routes.py`. Do not change `/`.
- `ROUTE_POLICY["command_center"] = _EVERY_ROLE` in `services/authorization.py` (ADR-008 — matches every other monitoring route).
- Navigation item only after the policy entry exists (existing `routes.py` convention: `NAV_KEY_BY_ROUTE`).
- `pages/command_center.py` — matches the existing one-file-per-page convention.
- `components/command_center/` — first subdirectory under `components/`; fresh presentation only, no imports from `fleet_condition.py`/`needs_attention.py`/other Fleet Overview components (ADR-008).
- `callbacks/command_center.py` — matches the existing one-file-per-domain convention.
- `services/command_center_service.py` — mandatory façade; assembles one presentation-ready snapshot per render by calling `get_fleet_health()` and `list_recent_device_events()` once each (ADR-008), never issuing new SQL (`AGENTS.md` rule 1).

## Phase 4 — Command Center shell — DONE (`cc6b67a`, 2026-08-29)

Six named panel slots, honest not-built-yet placeholders, live scope
indicator.


Visual skeleton first:

```text
COMMAND CENTER
│
├── Header / refresh / scope
│
├── Situation summary
│
├── Exception intelligence
│
├── Recent operational events
│
├── Location concentration
│
├── Selected location / transformer concentration
└── Priority investigation
```

Acceptance for Phase 3+4 together: `/command-center` opens, the façade is
wired end to end, panels may show safe empty/unavailable states.

## Phase 5 — Situation summary — DONE (2026-08-29)

Four real cards over presentation-ready snapshot fields. The Situation
Summary slot became a live region; the other five stayed placeholders.
Includes the mandated partially-reporting-RTL regression test (a device
with two fresh metrics and one that never reported is NO_DATA, its
`device_last_updated` stays present, and it lands in both Communication
and Needs Attention). Verified against the live database: Command Center
and Fleet Overview report identical figures, which is the single-read-path
contract (ADR-008) holding in practice rather than only in tests.


- **Fleet Health** — operational fleet monitoring picture, from `FleetHealth` (ADR-008).
- **Needs Attention** — `Stale + No Data` only (ADR-002).
- **Communication/visibility** — No Data RTL count, share of monitored RTLs, optionally affected Plant count. Copy: "At least one monitored metric has no reading." (ADR-002 — no age buckets, no "never reported").
- **Inventory** — Plants / Transformers / RTL Devices from the monitoring population. Do not mix in Managed RTL administration counts (a different population — see `admin1_administration_summary_implemented` in memory for that distinction if it resurfaces).

## Phase 6 — Electrical event presentation — DONE (2026-08-29)

Critical/Warning visual system built; current state stays `None` /
Unavailable, structurally distinct from zero. Threshold-free by
construction and enforced by two AST guards (a text scan cannot tell
`"< 3.61 V"` legend copy from a classification predicate). Event-window
occurrence counts deliberately deferred to Phase 9.


```text
Electrical Conditions

Critical
Power Down
Current state: Unavailable

Warning
Battery Low
Current state: Unavailable
```

Legend:

```text
Critical = Power Down
Device definition: <3.61 V

Warning = Battery Low
Device definition: <3.75 V
```

The voltage figures are device-definition legend copy, never a value CC code
evaluates (ADR-001). Current Critical/Warning counts are `Unavailable`, never
`0` (ADR-001 — no clear/resolve/closure contract exists yet). A separate,
explicitly time-bounded event-count field (e.g. "Power Down events · last
24h") may be shown, but must never be named or treated as `critical_count`/
`warning_count` (ADR-001).

## Phase 7 — Affected Locations — DONE (2026-08-29)

Ranked plant bars from the same FleetHealth already fetched; no SQL
added for ranking. ADR-008 amended to record a third read path
(`hierarchy_service.list_plants`) supplying plant NAMES only — every
number and the order still come from FleetHealth. Bar widths are
relative to the worst plant, so the chart reads comparatively.


Location = Plant (ADR-003). Ranked, horizontal:

```text
Affected Locations

Plant A    ███████████████  18
Plant B    ██████████       12
Plant C    ███████           8
Plant D    ████              5
Plant E    ██                3
```

Prefer Stale/No Data composition where visually useful. Clicking a Plant
selects it. No GIS, no Zone, no Feeder entity (ADR-003 — the schema doesn't
have one; reopens only on new client evidence).

## Phase 8 — Selected Location / Transformer concentration — DONE (2026-08-29)

Selection travels in the URL (`?plant=`), mirroring the `?assign=`
precedent: it survives a refresh by construction, is bookmarkable, and
no callback can clear what it does not own. Transformer counts come from
`FleetHealth.transformers_for_plant()`; only codes are fetched, for the
one selected plant. ADR-008's entry points restated as three read
CATEGORIES so reading another level of the same hierarchy does not
re-open the decision.


```text
KZN NORTH
12 affected RTLs

Transformer concentration

TRF-04  █████████  5
TRF-07  █████      3
TRF-11  ███        2
TRF-16  ███        2
```

Selection survives a routine polling refresh (ADR-005). Actions deep-link to
the existing Plant/Transformer/RTL routes — flattening investigation without
duplicating the hierarchy.

## Phase 9 — Recent Operational Events — DONE (2026-08-29)

Persisted events only, via `list_recent_device_events()` (ADR-008), newest
first, at the repository's own order. Severity presentation is DERIVED from
Phase 6's `ELECTRICAL_CONDITIONS` rather than restated, so the current-state
card and the event rows cannot disagree about `power_down -> Critical`.
Event type NAMES moved into `services/event_semantics.py` (`display_label`)
so no consumer spells them out.

ADR-008 amended a third time, before the code, for three things: a batched
`list_device_paths` label lookup (one query for the visible rows, not one
per plant and one per transformer — a ~20-query-per-render N+1 on a page
meant to auto-refresh), the events failure boundary, and the EVT-D5
administrator gate on unregistered-UID rows.

```text
● CRITICAL                    14:02
Power Down            29017
Three Gorges Dam / aa12    Open asset →
Battery voltage · 3.54 V
```

"Open asset →" ONLY where the asset resolved; plain text where it didn't,
including every unregistered UID. No acknowledge / clear / resolve /
silence / escalate control, no fake delivery state, no pretending events
are persistent alarms (events have no closure contract — ADR-001).

Three outcomes kept structurally apart: rows, "no recent operational events
are available", and "could not be loaded". The third is why the events read
has its own boundary in the façade — an event query failing must not blank
the freshness truth beside it.

### Blocking debt CLEARED: the operational-event seed

`db/seed_events_demo.py` (opt-in, `python -m db.seed_events_demo`) ingests a
13-event batch through `ingest_event()` — never `insert_device_event()` —
so a demo `invalid_uid` row is quarantined by the real resolution rather
than declared, and a demo `startup` really does activate its RTL and write
its system-originated audit row. No `--reset`: event persistence is
append-only (INGEST-D3), so a second run is refused rather than silently
doubling.

The FRESHNESS demo seed (Fresh / Stale / mixed-metric NO_DATA) is a
different gap and is still open — see Phase 12 below.

## Phase 10 — Priority Investigation — IMPLEMENTED (2026-08-30)

The last question in the chain: which exact RTLs to open first. A ranked
per-RTL list over the SAME attention population as Needs Attention — Stale
+ No Data, freshness only (ADR-002/ADR-009). No event affects membership or
order, and a test fires a storm of Power Down events to prove it.

```text
● NO DATA
29017        Three Gorges Dam / aa12
At least one monitored metric has no reading.
Open asset →

● STALE
18442        Grand Coulee / tx07
Oldest monitored metric last reported 3h 41m ago
Open asset →
```

The load-bearing correction is ADR-009 D3. `device_last_updated` is a MAX
across metrics, so on an RTL that is Stale because one metric of eight
stopped it holds the FRESHEST metric's time. `FleetHealth` gained
`device_oldest_metric_updated` (the min), populated only when every metric
has a timestamp — so a NO_DATA RTL structurally has no number from which a
duration could be fabricated. Both the displayed age and the ranking key
read that one field, so they cannot drift.

No footer link: `/command-center/locations` is the ranked PLANT list
(ADR-003), and an approximate destination is worse than none.

### Visual verification DEFERRED — not a phase failure

> Phase 10 implementation and semantic verification complete. Mixed
> Fresh/STALE/NO_DATA browser verification deferred because the available
> freshness seed is destructive and lacks a safe rollback path.

`db/seed_freshness_demo.py` is built and tested but NOT applied: staleness
cannot be inserted, only carved out by deleting readings, and
`seed_plant_monitoring --reset` is itself broken (SEED-RESET-1,
`docs/context/KNOWN_DEFECTS.md`). Fix that before the Phase 12 acceptance
pass, then apply the seed and complete this verification.

## Phase 10 — Priority investigation (original plan)

Fresh component, not a reuse of Needs Attention's tree (ADR-008):

```text
RTL-104
NO DATA
Plant A / TRF-04
Open →

RTL-081
STALE
Plant B / TRF-22
3h 42m since latest available data
Open →
```

Answers "which RTL should I inspect next." Ranking comes from existing
freshness/event data only — no invented electrical severity precedence
unless a future domain contract supports one (ADR-001 principle extended).

## Phase 11 — Whole-shell dark/light theme — DONE (2026-08-30)

Dark/light for the Command Center, applied to the whole visible shell while
`/command-center` is active. Dark is the default; the choice persists for
the session in a `dcc.Store`, and is never inferred from
`prefers-color-scheme` — a day shift and a night shift on one machine want
different answers from the same OS setting.

### ADR-006's open question, answered: the hook already existed

`.app-root:has(.page--command-center)` / `.app-shell:has(...)` has scoped
whole-shell LAYOUT to this route since `d0d9f3a`, reaching the sidebar with
zero Python changes to `app_shell.py`, `app_sidebar.py` or `app_header.py`.
Theming carries a theme class on the same element and reuses it. **No shell
file was edited**, and `app_header.py` is not even in this route's render
path. A test asserts no theme class ever appears in those three files: if
one does, the hook stopped being minimal and the gate re-opens.

Measured before deciding: Command Center rules held **zero** colour
literals outside `:root` (so it themes purely by token override), the shell
held nine, all white-on-navy alpha that survive both appearances.

### The scoping rule ADR-006 did not anticipate

The semantic palette is route-scoped in BOTH appearances, not only dark.
No Data is purple here while `--state-none-*` stays grey for Fleet
Overview, and Warning/Stale had to be separated because they were the SAME
token. Neither could be expressed by editing `:root` without restyling
`/plants`.

### Two contrast defects the browser found and the tests had not

- The page `<h1>` had no colour rule at all, so it inherited `body`'s
  hardcoded light `#1f2937`: **1.22:1** on the dark canvas. Fixed at the
  source — the route scope now sets `color`, so every un-ruled descendant
  follows the appearance rather than only the elements someone styled.
- The active sidebar item paired `--color-brand` text on a `--color-surface`
  pill, which inverts in dark: **1.18:1**. Re-expressed with the accent pair.
- Separately, `.command-center__unavailable` had **never** applied: at
  0,1,0 it lost to `.command-center__condition-facts dd` at 0,1,1, so the
  Unavailable value always rendered in primary text colour. Pre-existing and
  invisible on a light canvas. The test now asserts the rule out-specifies
  its competitor rather than merely existing.

Verified in the browser: every measured pair clears WCAG AA in both
appearances; `/plants`, Reports and Notifications carry no theme class and
resolve `--cc-*` to nothing; the stored choice survives navigating away and
back; 1440/1366/1024 all clean with no horizontal scroll; no new console
errors.

## Phase 11 — Whole-shell dark/light theme (original plan)

Architecture, decided at Phase 1, not late polish (ADR-006). Dark canvas
≈`#121820` (not pure black); light reuses the existing token foundation.

Semantic colours: normal/fresh → quiet neutral; stale → ochre/gold; No Data
→ purple; Warning/Battery Low → amber; Critical/Power Down → red;
success/connected/completed → green. Color never carries meaning alone —
labels/icons are mandatory alongside every color-coded state (accessibility
principle, consistent with this repo's existing a11y work; not yet its own
ADR — fold into ADR-006 if it needs one before Phase 11 lands).

ADR-006's open question — is the shell hook genuinely minimal, or does it
drag `app_shell.py`/`app_sidebar.py`/`app_header.py` in wholesale — gets
answered here, at implementation time, against the real structure of those
three files (confirmed to exist, unread in detail as of this review).
Reject a plan/diff that rewrites all three just to obtain dark mode.

## Phase 12 — Browser verification

Widths: 1440 (primary), 1366 (normal enterprise desktop), 1024 (reduced-width
usability), 768 (regression only — desktop-first). Check: no horizontal
overflow; charts readable; dark shell coherent; Asset Navigator and sidebar
work; theme toggle works; refresh doesn't clear the page; selected Plant
persists; errors don't masquerade as zeros; `Unavailable` stays visually
distinct from `0`; existing Fleet Overview unchanged.

### Visual debt: Affected Locations needs Top-N disclosure (raised 2026-08-29, Phase 8)

The Affected Locations default presentation needs Top-N disclosure /
expansion before final Command Center polish. **Candidate: Top 8 + "Show
all 30 affected locations".**

Eight rather than five: five looks right in a mockup, but eight gives an
operator substantially more situational coverage while still keeping the
panel compact at 1440/1366.

Deliberately NOT implemented in Phase 8. Introducing Top-N while the
Selected Location behaviour was still being settled would have created a
selection-interaction problem — the selected plant can fall outside the
visible N. When this lands, the compact list should keep the currently
selected plant visible even if it ranks below the cut.

Phase 7 shipped an internal scroll region plus a "View all" page
(`/command-center/locations`) instead. That bounds the panel's HEIGHT
without hiding any row, so it does not have the selection problem and is
compatible with adding Top-N later — the scroll region would simply have
fewer rows to hold.

### Blocking debt: the freshness demo seed (raised 2026-08-29, Phase 5)

The local seed is **entirely stale** — 120 Stale, 0 Fresh, 0 No Data — so
the two most semantically delicate states have never been seen rendered
with real data. Phase 5's Communication card shows an honest `0`, but an
honest zero is not a verification of the No Data path.

Before this phase's visual pass, add a **deterministic demo case** as its
own controlled seed change (never smuggled into a feature gate):

- one genuinely **Fresh** RTL
- one **Stale** RTL
- one RTL with a **mixed metric state that rolls up to `NO_DATA`** — some
  metrics reporting fresh, at least one never reporting

The third is the important one: it is the exact shape ADR-002 exists to
protect, it is covered by unit tests
(`tests/test_command_center_service.py::TestPartiallyReportingDeviceRegression`),
and it has never been looked at on screen. Follow the
`db/seed_admin_demo.py` precedent — opt-in, separate from the core seed,
never implicit in production (the same constraint ADR-007 puts on the
event demo seed).

Recorded here rather than in `docs/UX_DEBT.md` because that file is
gitignored, so a note there would carry no history and be invisible to a
fresh clone.

## Phase 13 — Test gate

Targeted: routes, route authorization, navigation, Command Center service,
monitoring semantics, No Data regression, recent-event reads, event
ingestion/seed, theme state, auto-refresh, selected Plant, empty/loading/
error states, existing Fleet Overview regression. Then the broadest safe
suite (`python -m pytest -m "not db" -v`, plus the DB-marked suite where
Docker is available). No commit if tests fail.

## Phase 14 — Review gate

Existing Fleet Overview (hierarchy/inventory monitoring workspace) vs. new
Command Center (exception-first operational cockpit) — side by side. Do not
decide yet that Command Center replaces `/`; that is its own future gate
(below). Questions: faster to spot abnormal concentration? matches the
research-led industrial-HMI feel? dense enough? too much color? does Recent
Events help? is Transformer concentration clear? does light mode hold up?
are all labels semantically truthful?

## Phase 15 — Commit gate

Only after Phase 14 approval: `git diff --check`, tests, browser
verification, `git status`, then one commit for CC-1 (matching this repo's
existing per-tranche commit granularity). Still stop before push — the
normal review gate applies same as every other tranche this session
(`docs/context/ACTIVE_GATE.md`'s `Commit/push permission` field governs
exactly when).

## After Command Center

Only once CC-1 is stable and reviewed:

1. **CC-2 / ENT-next — Transformer Operational Workspace**
2. **Field Operations Console**
3. **Reports & Audit evolution**
4. **Landing-page decision: does `/` become Command Center?** — explicitly
   its own gate, decided after side-by-side validation (Phase 14), never
   folded into CC-1 itself.

## The one sentence to keep pinned through all of it

> Command Center is a fresh presentation system over existing RTL domain
> truth: redesign the operator experience aggressively, but never redesign
> the meaning of the data to make the UI more impressive.
