# Active Gate

Status: Accepted at human review — closing
Date: 2026-09-03
Gate: ROLE-4B — Technician operational surface
Branch: `main`, baseline `f102573`
Commit/push permission: GRANTED at ROLE-4B-CLOSE, after review, for the
reviewed ROLE-4B file set onto `main`. The gate was implemented under an
explicit "do not commit, do not push" and held for that review.

## Purpose

Make the Technician's already-authorized assigned-device actions reachable
through normal Technician navigation, without opening an Administrator route
and without changing any policy.

## The gap this closes

ROLE-3 gave a technician `program_rtl`, `toggle_message_forwarding` and
`deactivate_rtl` on an assigned device, and `require_action` has enforced it
since. But the only surface rendering those three was
`device_manage_drawer()`, mounted once, at `pages/device_admin.py:135` — the
`/admin/devices` page, which `ROUTE_POLICY` reserves for `_ADMIN_ONLY`.

A permission with nowhere to happen. It is why CC-1 acceptance verified the
non-administrator side by substituting the authorization identity in the
session store (`CC1_ACCEPTANCE.md`, "Deferred, explicitly", item 1).

## Decision — ADR-016

**A device's operational actions are a shared surface; fleet administration is
not.**

The device page mounts the **same** drawer the admin page mounts — not a copy,
not a technician variant. `assign_device_drawer()` is deliberately not mounted
there: assignment is what *grants* technician authority, so a technician who
could manage it could grant it to themselves.

`/admin/devices` was **not** opened to technicians. That would have collapsed
"operate the equipment I am responsible for" into "administer the fleet".

`action_guard.may_action` was added and `require_action` now calls it — one
decision, two presentations. A component deciding visibility by comparing roles
would be a second permission table beside `ACTION_POLICY` that no policy test
would catch drifting.

**New route: NO.** **Policy change: NONE.**

## In scope

- `services/action_guard.py` — `may_action`, the non-raising sibling;
  `require_action` delegates to it.
- `components/device_operations.py` — new; markup only, no policy.
- `pages/device_dashboard.py` — the operations container and the shared drawer.
- `callbacks/device_manage.py` — `device_operations_children` (decides),
  `render_device_operations` and `open_manage_drawer_from_device` (wire it).
- `assets/app.css` — the section's styling, joining the existing shared
  accent-fill button rule rather than redeclaring it.
- `components/status_panels.py` — `inactive_notice` gains
  `equipment-inactive-notice`; see "Found while implementing" below.
- `tests/test_technician_operations.py` (new), `tests/test_inactive_policy.py`,
  `tests/test_equipment_selector.py`.

## Found while implementing

Two existing tests caught real problems, and both fixes are in scope:

1. **`test_inactive_policy.py`** — `inactive_notice()` marked inactive
   equipment with `status-panel--inactive`, which is a **shared muted-panel
   style** used in ~20 places, including the manage drawer's own honesty
   notices. Mounting the drawer on the device page made "is this equipment
   inactive?" unanswerable by looking for the style. The notice now carries a
   semantic `equipment-inactive-notice` class beside the style class, the test
   asks the semantic question, and the other call sites were not touched.
2. **`test_equipment_selector.py::test_every_callback_id_exists_in_some_layout`**
   — the new button is rendered by a callback, so no static layout declared it.
   The panel's factory was added to that test's mountable set, which is what
   `assign_device_drawer()` and `device_manage_drawer()` already do. The guard
   still fails on a genuinely orphaned id.

## Explicitly out of scope — and not touched

- **ROLE-4C** — broader General/Viewer persona work.
- **ROLE-4D** — the full three-role browser acceptance matrix.
- `ROUTE_POLICY`, `ACTION_POLICY`, `CAPABILITY_POLICY`, device scope, the
  report/export policy — none edited.
- `pages/device_admin.py` and `components/assign_device_drawer.py` — unchanged.
- S-4/S-5, which remain open.
- The untracked `debug.log`.

## Relevant files

- `services/action_guard.py`
- `services/authorization.py` (read only — the policy this obeys)
- `components/device_operations.py`
- `callbacks/device_manage.py`
- `docs/decisions/ADR-016-operational-actions-are-shared-administration-is-not.md`

## Verification

Regression seen failing first, for the right reason: **19 failed, 5 passed** —
the 5 passing were `TestTheAuthorityAlreadyExists`, so the suite proved the
permission existed while the reachability assertions failed with
"device_manage_drawer() is not mounted on the device page". After: 38 passed.

- `tests/test_technician_operations.py` — 38 passed.
- Focused UI/device/routing modules — 204 passed.
- Programming / forwarding / deactivation — 133 passed.
- Authorization, action guard, route scope, scope repository, route
  enforcement — 322 passed.
- ROLE-4A authentication regression — 152 passed.
- DB-marked suite — **496 passed**.
- Full suite — **3,097 passed**.

### Browser, credentialed, no session substitution

Playwright, Chromium, 1440×900, real login form.

| Persona | Result |
|---|---|
| `demo.tech01` | Technician sidebar only (Overview, Command Center, Notifications, Reports — no Devices/Registration/Users/Assignments); "24 affected RTLs" = the technician's scope |
| assigned RTL `plant-11-t2-d1` | Operational controls section present, naming the RTL; **Manage RTL** opened the drawer showing Device 29045 / ku02 / Az Zour South CCGT with **Program RTL**, **Message Forwarding** and **Deactivate RTL** (red), and no assignment control |
| out-of-scope RTL `plant-14-t1-d1` | **"No access"** — the route refuses before any surface renders |
| `/admin/devices` as technician | **"No access"** |
| `admin` | `/admin/devices` renders Device Management, 120 devices, technician column and the Assign/Manage actions — unchanged |
| `demo.general01` | device page renders full telemetry; `#device-operations` is **empty** |

No `dcc.Store` identity substitution was used at any point. Evidence
screenshots were kept outside the repository.

## What this does not claim

S-4/S-5 are unchanged: the session is still browser-held and the data callbacks
still do not verify it. This gate makes an authorized action reachable; it does
not make the UI the security boundary. `require_action` still refuses in every
confirm callback, and route scope refuses earlier.

This is also not ROLE-4D. The browser check was focused on Technician
reachability plus one Administrator and one General smoke.

## Next queued gate — do not start

**ROLE-4C — broader General/Viewer persona**, then **ROLE-4D — browser
acceptance for all three roles**. PCB remains paused at `PCB-9-CLOSE`.
