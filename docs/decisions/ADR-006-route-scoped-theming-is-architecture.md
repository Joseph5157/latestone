# ADR-006: Route-scoped dark/light theming is CC-1 architecture, not later polish

Status: Approved — not yet implemented
Date: 2026-08-28
Evidence: `assets/app.css` has zero `data-theme` or `prefers-color-scheme` rules today (verified by grep — no theme system exists in this application at all); `assets/app.css:7` (`--color-bg: #f4f6f8`, the light token Command Center light mode must reuse); `command center/05_VISUAL_DESIGN_SYSTEM.md` §"Theme architecture"
Implemented-by: not yet — this ADR is the pre-commitment; implementation is CC-1 Phase 1
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

## The open implementation question this ADR does not resolve

Whether the shell hook stays minimal (a single class/attribute toggled at the
shell root) or ends up pulling `app_shell`/`app_sidebar`/`app_header` into a
combined edit is an implementation-time judgment call, not a planning-time
one — it depends on how those files are actually structured when Phase 1
lands. Flagged here so it is not lost: verify at implementation time that the
hook is genuinely minimal before accepting a plan that touches all three.

## Affected areas

- `assets/app.css` — net-new dark token block; light block is additive only
- Shared shell files (exact set to be named at Phase 1 implementation,
  approved-shared-modify per `command center/07_IMPLEMENTATION_PLAN.md`)
- `command center/components/CC11_THEME_TOGGLE.md` — the control this ADR
  backs
- `/plants` and every other existing route — must be regression-tested
  visually unchanged (`command center/07_IMPLEMENTATION_PLAN.md` gate
  principle)
