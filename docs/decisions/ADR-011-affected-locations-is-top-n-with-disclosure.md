# ADR-011: Affected Locations names the worst 8 Plants and discloses the rest

Status: Superseded
Superseded-by: ADR-024 (the panel this governed was removed in SWITCH-OVER-1, 2026-09-19)
Date: 2026-08-30
Evidence: `components/command_center/affected_locations.py` (`TOP_N`,
`visible_locations`); `pages/command_center_locations.py` (the full view,
shipped in Phase 7a); `services/command_center_service.py:_affected_locations`
(still ranks every plant)
Implemented-by: `6aafc4c`
Supersedes: the Phase 7 decision that the cockpit panel lists every affected
Plant

## Context

Phase 7 shipped the panel listing all affected Plants — up to 30 — inside a
bounded scroll region, and recorded an explicit reason for it:

> bounding its HEIGHT is the fix; bounding the DATA is not — hiding affected
> plants behind a "+22 more" cap would remove exactly the concentration
> picture this panel exists to give.

That reasoning is right about the danger and wrong about the remedy, and the
difference only became visible once the surrounding page existed. Thirty
rows in one cell of a fixed-height cockpit means comparing rank 3 against
rank 27 by scrolling a small pane — which is not comparing at all. The panel
had the whole population and gave up the comparison.

Leaving it as-is would also have meant shipping whichever behaviour Phase 7
happened to produce, rather than a decision.

## Decision

The cockpit panel names the worst **8** affected Plants. The rest are
disclosed, never discarded:

- the **service still ranks every Plant** — the cap is a presentation choice,
  made in the component and reversible there;
- the **subtitle still states the true total** ("22 of 23 plants affected"),
  so the scale of the problem never depends on the cap;
- the footer reads **"Show all N affected plants →"** and opens
  `/command-center/locations`, the unbounded view Phase 7a already built.

The number is in the label deliberately. "Show all" alone makes the operator
click to discover how much they were not being shown.

### The selected Plant is retained below the cut

If the operator has selected a Plant that ranks outside the top 8, it stays
visible as a ninth row, with a line saying why:

> `Newcastle is shown because it is selected (rank 12 of 20).`

A selection that vanishes the moment it stops being one of the worst reads
as a bug, and the operator chose that Plant on purpose. The note matters as
much as the row: without it the retained Plant looks like rank 9, which is
the one thing this panel must never misreport.

A selected Plant that is not affected at all retains nothing. This panel
ranks exceptions, and a calm Plant has no exception to rank.

### The scroll region stays, and becomes unconditional

It was previously applied only past a row-count threshold. That threshold is
now unreachable, and leaving it would have silently removed the height bound
the fixed cockpit depends on — inside the cockpit the region's CSS flexes it
to the cell, so even eight rows must live inside it or the panel overflows
its grid area on a short viewport.

It is a HEIGHT bound, not a row-count decision, and it is now written that
way.

## Consequences

- The panel answers "where is this concentrated" at a glance, which was its
  purpose; the full page answers "show me everything", which is its purpose.
- `SCROLL_AFTER_ROWS` is gone from this module rather than left as a dead
  constant.
- Phase 7's tests asserting the panel renders every plant were rewritten
  rather than deleted: they now assert the shared row renderer over the rows
  the panel shows, and the full view over all of them.
