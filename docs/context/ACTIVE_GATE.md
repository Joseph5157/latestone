# Active Gate

Status: Approved
Date: 2026-08-30
Gate: CC-1 Phase 11 — Command Center Theme + Shell Integration
Precondition: Phase 10 complete and committed (`ce5d4ac`, `53a50f0`).
Flow: **HOOK INSPECTION (complete — see below)** → DECIDE (complete) →
IMPLEMENT → TEST → REGRESSION (`/plants`, Reports, Notifications) →
VISUAL VERIFY → COMMIT → **FULL STOP**
Commit/push permission: Commit permitted on `cc-1-command-center-foundation`
once local verification passes. Push NOT GRANTED. **Stop after committing.**

## Task

Dark/light appearance for the Command Center, applied to the whole visible
shell while `/command-center` is active — sidebar, workspace, utility
chrome. Every other route keeps the appearance it has today.

This is architecture, not polish (ADR-006). It is also **not** a licence to
redesign: this gate is passed by a *small* hook, not by a better shell.

## THE OPEN QUESTION, ANSWERED

ADR-006 and `CC1_ROADMAP.md` Phase 11 both require this be settled against
the real files before any edit, and both say to reject a plan that rewrites
`app_shell.py` / `app_sidebar.py` / `app_header.py` to obtain dark mode.

**The hook already exists and is already shipped.** `assets/app.css:5294`
uses `.app-root:has(.page--command-center)` and
`.app-shell:has(.page--command-center)` to give the cockpit its fixed
layout across the *whole shell* — sidebar included — with **zero Python
changes to any of the three shell files** (commit `d0d9f3a`). The class is
emitted by the Command Center page itself; the shell reacts to it.

Theming needs that same hook, carrying a theme class rather than only a
route class. Measured, not assumed:

| Surface | Colour literals outside `:root` | Consequence |
|---|---|---|
| Command Center rules | **0** | themes purely by token override |
| `.app-shell*` / `.app-sidebar*` | 9 | all `#ffffff` / `rgba(255,255,255,a)` |
| `:root` token definitions | 19 | the palette itself |

The sidebar is *already* a dark navy surface (`--color-brand: #1f3a5f`)
carrying white text at alpha. Those nine literals are alpha-on-brand and
survive both appearances unchanged.

`app_header.py` is **not in the Command Center render path at all** — the
page deliberately renders no `app_header` (`pages/command_center.py`), so
one of the three files at issue is not even reachable from this gate.

**Therefore: no shell file is rewritten. No shell file is edited.**

## Decisions this gate makes

- **D1 — The hook.** The Command Center page root carries its theme class
  alongside `page--command-center`. Shell surfaces react via the existing
  `:has()` technique. Scoped token overrides only; no global palette edit.
- **D2 — Theme state is explicit.** A `Dark | Light` toggle inside Command
  Center. NOT inferred from `prefers-color-scheme`: the frozen spec
  (`command center/components/CC11_THEME_TOGGLE.md`) does not ask for it,
  and a control room's ambient choice is not the operating system's to
  make.
- **D3 — Persistence is session-scoped.** A `dcc.Store` with
  `storage_type="session"` — the lifetime ADR-006 named and the one
  `auth-store` already uses. No account preference system, no cookie.
- **D4 — The semantic palette is CC-SCOPED, and that is forced.** Two of
  the required colours differ from what the app renders today:
  - **No Data -> purple.** Today `--state-none-*` is grey and Fleet
    Overview renders it. Redefining that token globally would change
    `/plants`.
  - **Warning -> amber, Stale -> ochre/gold.** Today they are the *same
    token*: `--state-stale-text` backs both `.command-center__tone--warning`
    and `.command-center__tone--stale`. The spec requires them
    distinguishable.

  Both therefore land as overrides inside the Command Center scope, in
  both appearances, never in `:root`.
- **D5 — Unavailable stays neutral.** It is the absence of a derivable
  count (ADR-001), not a severity. Giving it a severity colour would
  assert a state the model cannot support.

## Constraints

- IBM Plex Sans remains the face (`--font-ui`); no type change.
- Telemetry/numeric values keep `font-variant-numeric: tabular-nums`.
- Normal/fresh stays quiet and neutral — it is the majority state, and a
  fleet that is fine should not glow.
- Colour never carries meaning alone: every coloured state keeps its word.
  Already true of the Phase 6/9/10 panels; it must survive the repaint.

## Required tests

- the theme class reaches the page root, and only there
- toggling changes it; the choice survives a re-render
- every dark rule is scoped — no dark token override at `:root` or on a
  bare element selector
- `--state-none-*` and `--state-stale-*` are unchanged in `:root`, so Fleet
  Overview is untouched by construction
- the semantic vocabulary keeps its labels (colour never alone)
- Phase 5-10 panels render identically in structure under both appearances

## Regression surface

`/plants`, Reports and Notifications must be visually unchanged — the
frozen spec names exactly these three. Fleet Overview is frozen.

## Non-goals

- **auto-refresh** — ADR-005, with its own semantics (cadence, preserving
  Plant selection, last-good snapshot on failure) and its own gate. The
  roadmap does not group it with theming, so this gate does not adopt it.
- global dark mode for other routes; shell refactor; type/scale changes;
  Asset Navigator behaviour changes; a new component library; any
  `/` landing-route change; no push.

## Carried forward, not in this gate

- EVT-D5 non-admin browser verification -> final acceptance checklist.
- Recent Events footer wording -> "Open Notification Center ->", polish gate.
- Mixed Fresh/STALE/NO_DATA browser verification -> blocked on SEED-RESET-1
  (`docs/context/KNOWN_DEFECTS.md`), before Phase 12 acceptance.
