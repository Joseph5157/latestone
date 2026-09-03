# Active Gate

Status: Accepted — held at human review, no code change proposed
Date: 2026-09-03
Gate: ROLE-4D — three-persona browser acceptance
Branch: `main`, baseline `ca01576`
Commit/push permission: **NOT APPLICABLE.** Nothing was changed. This file is
the only edit in the working tree, left uncommitted for review as the gate
instructed ("do not commit, do not push").

## Purpose

Prove, side by side and through the real credentialed login form, that
Administrator, Technician and General User each receive the correct
navigation, data scope, routes, controls and denials — closing the loop ROLE-
4A (authentication), ROLE-4B (Technician reachability) and ROLE-4C (General
User audit) opened separately.

## Finding: no defect found

**All three personas accepted. No product code, test, or configuration file
was changed.**

Every persona was exercised through the normal login form (Playwright,
Chromium, 1440×900, `http://127.0.0.1:8073` against the local development
database with `DEMO_CREDENTIALS` configured for `demo.tech01`/
`demo.general01`) — never by editing `dcc.Store`, injecting session state, or
bypassing `authenticate()`.

### Two scope coincidences worth recording as evidence, not narration

- Technician's Overview read "Showing 5 of **24** affected RTLs" — matching
  `demo.tech01`'s live assignment count (`user_device_assignments`, re-queried
  at gate open) exactly, and its Notifications summary's ">24h No Data 24"
  matched the same number again from an independent code path
  (`current_notifications` vs the Overview's admin-summary query).
- Administrator's Notification Center showed **133** notifications including
  one `Unregistered UID`; General User's showed exactly **132** — the same set
  minus that one row. This is `callbacks/notifications.py`'s
  `include_unregistered=is_admin` gate, observed live rather than only read in
  source.

### Administrator

Sidebar: Overview, Command Center, Devices, Assignments (disabled
placeholder), Registration, Notifications, Reports, Users — the full
authorized surface. `/admin/devices` showed all 120 devices with the
technician column and Assign/Manage actions. `/admin/devices/new` and
`/admin/users` both reachable (7 users listed, `Administrator`/`Technician`
display labels correct — not the lowercase persisted values). On an arbitrary
device not assigned to any relationship with the admin account, the manage
drawer offered Program RTL, Message Forwarding and Deactivate RTL — proving
"any device", not merely "a device". Command Center and Reports both render.

### Technician (`demo.tech01`)

Sidebar: Overview, Command Center, Notifications, Reports only — Devices,
Registration, Users, Operations section and Assignments all absent, and none
leaked from the prior Administrator session (verified empty before login). On
an assigned RTL (`plant-03-t3-d2`, device 29018), the operational surface
rendered with all three actions and no assignment control. A known
out-of-scope RTL (`plant-20-t1-d1`) returned "No access" by direct URL. All
three admin routes (`/admin/devices`, `/admin/devices/new`, `/admin/users`)
returned "No access". Notifications scoped to 26 entries with no
`Unregistered UID` row. Reports reachable; `callbacks/report_center.py`
threads `scope_from_session` through report generation, so export inherits
the same device-scope semantics as everything else.

### General User (`demo.general01`)

Sidebar identical in shape to Technician's (Overview, Command Center,
Notifications, Reports) but scope is unrestricted: Overview read "5 of **120**
affected RTLs" — full fleet, not 24. Viewing the SAME device Technician had
just operated on (29018) showed full telemetry with `#device-operations`
provably empty (`innerHTML` checked, not just visually absent) — proving no
control leaked across the session boundary. All three admin routes denied.
Notifications: 132, `Unregistered UID` correctly absent. Reports/export were
exercised end to end in ROLE-4C (a real 7-row RTL Alarms report, Download CSV
enabled) and reconfirmed reachable here.

### Cross-persona session cleanliness

Administrator → logout → Technician → logout → General User, each transition
checked before the next login: after each logout the login form was present
and the sidebar `<nav>` was mounted but empty (`innerText === ""`) — the
"hidden, not unmounted" architecture (`components/app_sidebar.py`) holding
under an actual transition, not just in its own docstring claim. No prior
persona's sidebar items, selected-device context, or operational controls
persisted into the next login.

## Why no ADR

ROLE-4D is acceptance evidence for decisions ROLE-2/3/ADR-004/ADR-008/ADR-013/
ADR-015/ADR-016 already made and justified. It establishes no new rule.

## In scope

- This file only. No application source, test, or configuration file was
  edited.

## Explicitly out of scope — and not touched

- Any product code, test, or documentation beyond this record.
- Authorization policy of any kind.
- S-4/S-5, which remain open.
- The untracked `debug.log`.

## Verification

- ROLE-4A regression — **133 passed**. ROLE-4B regression — **38 passed**.
- ROLE-4C / general-relevant suites (authorization, action guard ×3, route
  enforcement, route scope ×2, device scope, scope repository, report export
  ×2, admin overview, admin summary wiring, app sidebar) — **532 passed**.
- DB-marked suite — **496 passed**. Full suite — **3,097 passed** (unchanged
  from ROLE-4C's closing total — expected, since nothing changed).
- `git diff --check` / `git status --short` / `git diff --stat` — no
  application diff exists to check; only this file is modified.
- Context pack — CLEAN before and after.

### Comparative matrices, browser-observed

**Sidebar**

| Navigation item | Administrator | Technician | General User |
|---|---|---|---|
| Overview | yes | yes | yes |
| Command Center | yes | yes | yes |
| Devices | yes | absent | absent |
| Registration | yes | absent | absent |
| Notifications | yes | yes | yes |
| Reports | yes | yes | yes |
| Users | yes | absent | absent |
| Assignments (disabled placeholder) | yes | absent | absent |

**Routes**

| Route | Administrator | Technician | General User |
|---|---|---|---|
| Overview | 200 | 200 | 200 |
| Command Center | 200 | 200 | 200 |
| Plant / Transformer | 200 | 200 | 200 |
| Assigned device (29018) | 200 | 200 | 200 (read-only) |
| Out-of-scope device (plant-20-t1-d1) | N/A | No access | N/A |
| Notifications | 200 (133) | 200 (26) | 200 (132) |
| Reports | 200 | 200 | 200 |
| Admin Devices | 200 | No access | No access |
| Registration | 200 | No access | No access |
| Users | 200 | No access | No access |

**Actions**

| Capability | Administrator | Technician | General User |
|---|---|---|---|
| Program RTL | any device | assigned only | denied |
| Message Forwarding | any device | assigned only | denied |
| Deactivate RTL | any device | assigned only | denied |
| Manage Assignment | any device | denied | denied |
| Register Device | allowed | denied | denied |
| User Administration | allowed | denied | denied |
| Report Export | allowed | allowed, scoped | allowed, full-fleet (proven in ROLE-4C) |

### Data scope

- Administrator: unrestricted (`device_scope._UNRESTRICTED_ROLES`).
- Technician: 24 active assignments for `demo.tech01`, re-queried live against
  `user_device_assignments` at gate open — unchanged since ROLE-4B/4C.
- General User: unrestricted, same set as Administrator
  (`_UNRESTRICTED_ROLES` includes `GENERAL`) — confirmed by the 120-vs-24
  Overview contrast and the identical-device telemetry-vs-controls split
  against Technician.

## What this does not claim

**S-4/S-5 remain open.** The session is still a browser-side `dcc.Store`, and
the data callbacks still do not independently verify it. This gate proves
intended application behaviour under *normal* credentialed use through the
real UI; it does not establish a server-trusted session boundary, and no part
of this record should be read as claiming otherwise. Direct-URL denial was
proven for every admin route and the out-of-scope device; browser-store
forgery was explicitly not attempted, per this gate's own scope.

## Final persona classification

```text
Administrator — IMPLEMENTED AND UI-ACCEPTED
Technician     — IMPLEMENTED AND UI-ACCEPTED
General User   — IMPLEMENTED AND UI-ACCEPTED
```

This supersedes the original live-role-audit's "Technician/General partial"
classification. ROLE-4A/4B/4C/4D closed that gap; the earlier finding is
historical record, not current status.

## Next queued gate

None queued. ROLE-4A/4B/4C/4D are all closed. PCB remains paused at
`PCB-9-CLOSE`; the next move is for the operator to decide.
