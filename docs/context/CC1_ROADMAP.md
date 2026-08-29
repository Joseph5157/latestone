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

## Phase 6 — Electrical event presentation

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

## Phase 7 — Affected Locations

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

## Phase 8 — Selected Location / Transformer concentration

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

## Phase 9 — Recent Operational Events

Large panel. Persisted events only, via `list_recent_device_events()`
(ADR-008):

```text
14:02  RTL-081  Startup
13:41  RTL-017  Invalid UID
13:12  RTL-104  Power Down
12:56  RTL-220  Battery Low
```

"Open asset →" where an entity resolves; plain text where it doesn't. No
acknowledge button, no fake delivery state, no pretending events are
persistent alarms (events have no closure contract — ADR-001).

## Phase 10 — Priority investigation

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

## Phase 11 — Whole-shell dark/light theme

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
