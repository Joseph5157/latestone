# Accepted UX debt

Deliberate, time-boxed compromises made during the UI work. Each entry records
what is wrong, why it was not fixed now, and what fixing it would require.

An item belongs here only when the decision was made explicitly. Anything found
by accident is a bug, not debt, and goes through the normal fix path.

---

## UXD-1 — The equipment selector bar renders above the brand header

**Status:** Accepted for the Device Monitoring vertical slice. Revisit only after
the slice is approved.

**What it looks like.** On every authenticated route the "Jump to equipment" bar
sits at the very top of the page, above the "Powerplant Dashboard" brand and the
breadcrumb. It reads backwards: a secondary navigation control appears more
prominent than the product identity and the operator's current location.

**Why.** DOM order. The selector is mounted once in `app.layout`, before
`page-content`, while `app_header()` is rendered *inside* each page layout. The
visual order is a direct consequence of the callback-safety decision recorded as
finding 2 in `docs/CODE_AUDIT.md`: the selector's callbacks fire on every route,
so the component has to exist on every route, which a page-local header cannot
guarantee.

**Why it was not "temporarily" fixed.** Reordering with CSS (`order`, flex
direction, negative margins) or moving the node in the DOM would make the
appearance right while leaving the architecture unchanged — hiding the real
choice behind a cosmetic fix, and risking exactly the layout/callback mismatch
the current structure prevents. A visual fix that makes the underlying problem
harder to see is worse than the visible oddity.

**What a real fix requires.** Globalising `app_header()` into `app.layout`
alongside the selector, which turns breadcrumb and freshness from layout
arguments into route-driven callback outputs. Spec section 5 already names this
as a separate architectural change. It is not vertical-slice work.

**Not blocking.** The §6.8 chart-top budget was met at 390 px without touching
this, so there is no performance or layout argument forcing the change now.

**Cost of waiting.** Cosmetic only. No functional, accessibility or data-trust
impact — the breadcrumb still communicates location, and the selector still
works from every route.

---

## UXD-2 — The Data column sorts alphabetically, not by severity

**Status:** Accepted. Logged 2026-08-09 with the Fleet Overview slice.

**What it looks like.** The plant table's default order is exception-first and
operationally correct: `NO DATA > STALE > FRESH`, then plant name. But the `Data`
column holds display strings, so an operator who clicks its sort control gets
`Fresh` → `No data` → `Stale` — alphabetical, and close enough to a severity
order to be believed.

**Why it was not fixed now.** The default ordering already answers "which plant
needs attention first", which is the operational question. Rewriting the sort
also touches the shape of the row data, and doing that opportunistically inside
the Fleet slice would have shipped an untested change to the one contract that
row-click navigation depends on.

**What a real fix requires.** Sort on a hidden numeric rank rather than the
displayed text. The rank already exists on every row as `_severity`
(`services.monitoring_service.severity_rank`) — the work is wiring dash_table to
sort the visible column by that key, which currently means either a
`sort_action="custom"` callback or exposing the rank as a hidden column.

**Cost of waiting.** An operator who sorts by `Data` sees a plausible but wrong
ordering. Nothing is hidden — every row and its exact state text stays on screen.

---

## UXD-3 — React "uncontrolled to controlled input" warning on login

**Status:** Accepted. Logged 2026-08-09. Pre-existing; surfaced during Fleet
browser verification, not caused by it.

**What it looks like.** Typing into the login form emits a React console error:
a component is changing an uncontrolled input to be controlled. Console only —
login works correctly, including the wrong-credentials path.

**Why.** The login inputs are rendered without a `value` prop and acquire one
once a callback writes to them, so React sees the input change category
mid-lifetime.

**Why it is not being fixed now.** It is a console-only warning on a screen that
is already verified working, and the fix touches authentication input handling.
It must not be folded into Plant/Transformer UI work.

**What a real fix requires.** Give both login inputs an explicit initial `value`
so they are controlled for their whole lifetime, and re-verify both login paths.

**Cost of waiting.** Console noise that makes real errors harder to spot during
browser verification.

---

## UXD-4 — dash_table "state update on unmounted component" warning on navigation

**Status:** Accepted. Logged 2026-08-09. Pre-existing; surfaced during Fleet
browser verification.

**What it looks like.** Navigating away from any page containing a `dash_table`
emits a React console error about a state update on an unmounted component. The
stack is entirely inside minified dash_table internals (`in t (created by t)`,
under a `Suspense` boundary). Navigation itself is correct.

**Why it is not being fixed now.** The warning originates in a third-party
component's own lifecycle, not in this application's code, so there is no local
fix that is not a workaround. It is a dev-build warning; React strips this class
of message in production builds.

**What a real fix requires.** Confirming against a current dash/dash_table
release whether it still occurs, and upgrading if it is fixed upstream. Do not
restructure this application's routing to silence a vendor warning.

**Cost of waiting.** Console noise only.

---

## Not debt: seed freshness

The seeded dataset is old enough that every device reads `Stale` (0 fresh / 120
stale). This is **correct behaviour on old data**, not a defect and not debt, so
it is recorded here only to stop it being "fixed" by accident.

Keep the stale dataset as-is — it is the state most worth testing against. If a
green screen is ever needed for a demonstration, add a deliberate reseed mode or
a recent-timestamp fixture. Never hand-edit timestamps in the development data to
make a screen look healthy: the whole point of the freshness chain is that the UI
reports what the data actually says.
