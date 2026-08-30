# ADR-006: Route-scoped dark/light theming is CC-1 architecture, not later polish

Status: Approved — implemented at CC-1 Phase 11
Date: 2026-08-28
Evidence: `assets/app.css` has zero `data-theme` or `prefers-color-scheme` rules today (verified by grep — no theme system exists in this application at all); `assets/app.css:7` (`--color-bg: #f4f6f8`, the light token Command Center light mode must reuse); `command center/05_VISUAL_DESIGN_SYSTEM.md` §"Theme architecture"
Implemented-by: not yet (Phase 11 lands it; sha recorded in the follow-up)
Amended: 2026-08-30 — the open implementation question below is now ANSWERED
against the real files, and the semantic-palette scoping it did not anticipate
is recorded
Supersedes: treating theming as a Phase-9 cosmetic pass

## Decision

This application has no theme system today — not a dark mode users can miss,
an *absence of the concept*. Command Center introduces the first one, and
because nothing exists to extend, this is routing/shell architecture, not a
CSS pass added at the end. It ships in Phase 1 alongside routing and
authorization, not deferred to polish.

**Scope of effect.** While `/command-center` is the active route, the
appearance choice covers the *whole visible shell* — sidebar, content, and
utility/Asset Navigator chrome — via one minimal route-scoped root/shell
class or data attribute. Every other route is unaffected; a user leaving
Command Center returns to the application's one existing appearance
unchanged. This requires touching shared shell files, which is why it's
listed as an approved shared-modify exception rather than something CC-1
could do inside its own page module alone.

**Light mode** reuses existing tokens — `--color-bg: #f4f6f8`
(`assets/app.css:7`) and the rest of the current light family. Command
Center-local tokens may extend that system; they must not fork identical
values under new names.

**Dark mode** is new: canvas `#121820`, panels slightly lighter than canvas,
cool muted gray/blue borders, near-white (not pure white) primary text, muted
gray secondary text.

**Persistence** is session-scoped, the same lifetime as other session state
in this app — not a cookie, not `localStorage` reaching outside the session.

## The open implementation question — ANSWERED 2026-08-30

The question was whether the shell hook stays minimal or ends up pulling
`app_shell`/`app_sidebar`/`app_header` into a combined edit. Answered against
the real files at Phase 11, and the answer is smaller than the question
feared: **the hook already existed.**

`assets/app.css:5294` already scopes whole-shell layout to this route with
`.app-root:has(.page--command-center)` / `.app-shell:has(.page--command-center)`,
shipped for the fixed cockpit in `d0d9f3a` — and it reached the sidebar with
**zero Python changes to any of the three files**. The Command Center page
emits the class; the shell reacts. Theming reuses that hook, carrying a theme
class beside the route class.

Three measurements made the risk concrete rather than assumed:

- Command Center rules contain **zero** colour literals outside `:root`, so
  the workspace themes purely by redefining tokens.
- `.app-shell*` / `.app-sidebar*` contain nine, every one of them
  `#ffffff` or `rgba(255,255,255,alpha)`. The sidebar is already a dark navy
  surface (`--color-brand`) with white text at alpha, so those nine survive
  both appearances untouched.
- `app_header.py` is not in this route's render path at all — the Command
  Center page deliberately renders no header.

**No shell file is edited.** A future gate that finds itself needing to is
looking at a different problem and should say so rather than absorbing it
into theming.

## What this ADR did NOT anticipate: the semantic palette is CC-scoped

The frozen palette asks for two colours the application does not currently
render, and neither can be applied by editing `:root`:

- **No Data is purple.** `--state-none-*` is grey today and Fleet Overview
  renders it. Redefining it globally would restyle `/plants`, which this
  ADR's own regression rule forbids.
- **Warning and Stale must be distinguishable.** They are currently the
  SAME token — `--state-stale-text` backs both
  `.command-center__tone--warning` and `.command-center__tone--stale`.

So the semantic overrides live inside the Command Center scope in BOTH
appearances, not only in dark. That is a wider scoping rule than "dark mode
adds a dark block", and it is the rule that keeps every other route
unchanged by construction rather than by re-inspection.

Unavailable stays neutral in both appearances. It is the absence of a
derivable count (ADR-001), not a severity, and colouring it would assert a
state the model cannot support.

## Affected areas

- `assets/app.css` — net-new dark token block; light block is additive only
- Shared shell files (exact set to be named at Phase 1 implementation,
  approved-shared-modify per `command center/07_IMPLEMENTATION_PLAN.md`)
- `command center/components/CC11_THEME_TOGGLE.md` — the control this ADR
  backs
- `/plants` and every other existing route — must be regression-tested
  visually unchanged (`command center/07_IMPLEMENTATION_PLAN.md` gate
  principle)
