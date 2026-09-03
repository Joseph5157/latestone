# ADR-016: Operational actions are a shared surface; fleet administration is not

Status: Approved
Date: 2026-09-03
Evidence: `services/authorization.py` (`ACTION_POLICY` — the three operational
actions carry a technician in their assigned-only set, `MANAGE_ASSIGNMENT`
carries none); `services/action_guard.py` (`may_action` / `require_action`);
`components/device_operations.py`; `pages/device_dashboard.py`;
`callbacks/device_manage.py` (`render_device_operations`,
`open_manage_drawer_from_device`); `pages/device_admin.py` (unchanged, still
mounts both drawers); `docs/context/CC1_ACCEPTANCE.md` ("Deferred, explicitly")
Implemented-by: `08e44af` (`feat(roles): expose technician device
operations`; full sha 08e44af75c344533ccca50ce3d72de27c45e1243 — the commit
carries this ADR too, so the sha is recorded here afterwards, as ADR-014 and
ADR-015 were)
Supersedes: nothing. It gives the reachability half of ROLE-3's authorization
model a home, and changes no policy ROLE-3 set.

## Context

ROLE-3 gave a technician `program_rtl`, `toggle_message_forwarding` and
`deactivate_rtl` on an assigned device, and `require_action` has enforced that
since. But the only surface that rendered those three was
`device_manage_drawer()`, mounted once, on `/admin/devices` — a route
`ROUTE_POLICY` reserves for administrators.

So the permission existed and could not be exercised. Not a policy bug: a
policy with nowhere to happen. It is why CC-1 acceptance verified the
non-administrator side by substituting the authorization identity in the
session store rather than by using the application.

## Decision

**A device's operational actions are a shared surface. Fleet administration is
not.**

Concretely, two things that were bundled by *location* are now separated by
*meaning*:

| | Who | Where |
|---|---|---|
| Operational actions on a device | administrator (any device), technician (assigned) | device page **and** `/admin/devices` |
| Assignment, registration, the fleet table | administrator only | `/admin/devices` only |

The device page mounts the **same** `device_manage_drawer()` the admin page
mounts — not a copy, not a technician variant. `assign_device_drawer()` is not
mounted there, and that is the whole boundary: assignment is what *grants*
technician authority, so a technician who could manage it could grant it to
themselves. `ACTION_POLICY` already says so by giving `MANAGE_ASSIGNMENT` an
empty assigned-only set; this ADR is the UI obeying it.

`/admin/devices` was NOT opened to technicians. Doing so would have been the
easy fix and the wrong one: it would collapse "operate the equipment I am
responsible for" into "administer the fleet", which are different jobs held by
different people.

## The rendering question and the enforcement question are one question

`action_guard.may_action` was added and `require_action` now calls it. Same
decision, two presentations — one returns a bool for a renderer, the other
raises for a callback.

That matters more than it looks. A component deciding visibility with
`if role == "technician"` would be a **second permission table**, beside
`ACTION_POLICY`, that no test of `ACTION_POLICY` would catch drifting. The
failure would be silent and asymmetric: a UI offering what the guard refuses
(confusing), or hiding what the guard allows (invisible). A test asserts the
two functions agree across every role × action × scope combination.

**Visibility is not authority, and this ADR does not make it so.** The section
is absent for a general user and for a technician on an unassigned RTL, but
that is a courtesy. `require_action` runs in every confirm callback regardless,
so a fabricated click on a control that was never rendered is still refused.
Route scope refuses earlier still: `callbacks/routing.py` returns the forbidden
panel for an out-of-scope device, so a hand-typed URL never reaches the page
that would host the surface.

## Two openers, one drawer

`open_manage_drawer` is driven by the admin table's `active_cell` and reads the
clicked row, which does not exist on a device page. Rather than widen it,
`open_manage_drawer_from_device` writes the same twelve outputs from
`page-context`. They are `allow_duplicate` and cannot fire together, because
the router renders exactly one page per request — which is also what makes the
drawer's fixed (non-pattern-matched) ids safe on two pages.

## An ambiguity this surfaced, and closed

`inactive_notice()` marked inactive equipment with `status-panel--inactive`.
That class is a **shared muted-panel style**, used in about twenty places for
notices unrelated to equipment state — including the manage drawer's own
"requests are recorded, not sent" honesty notices. Mounting the drawer on the
device page therefore made "is this equipment inactive?" unanswerable by
looking for the style, and `test_inactive_policy.py` caught it.

The notice now carries `equipment-inactive-notice` alongside the style class,
and the test asks the semantic question. Presentation is unchanged everywhere,
and the other twenty call sites were not touched.

## What this does not claim

S-4 and S-5 are unchanged. The session is still browser-held and the data
callbacks still do not verify it. ROLE-4B makes an authorized action reachable
through the UI; it does not make the UI the security boundary, and
`require_action` is still where refusal actually happens.

Nor is this the full role acceptance. A focused technician browser check was
run at 1440×900 with a real credentialed login; the complete three-role matrix
is ROLE-4D.
