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
