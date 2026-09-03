# Active Gate

Status: Audited — held at human review, no code change proposed
Date: 2026-09-03
Gate: ROLE-4C — General User persona completion
Branch: `main`, baseline `576b7cc`
Commit/push permission: **NOT APPLICABLE.** Nothing was changed. This file is
the only edit in the working tree, left uncommitted for review as the gate
instructed ("do not commit, do not push").

## Purpose

Determine whether the existing `general` persona already satisfies the
client's third runtime role, and identify the smallest real gap if not — audit
first, code only if the audit finds a defect.

## Finding: no defect found

**Classification: A — COMPLETE AS-IS.**

The client Functional Specification (`docs/RTL_FUNCTIONAL_SPEC_EXTRACT.md:206-
212`) states the General User requirement in full:

> Eskom employee not assigned as Administrator or Technician. Can log on. Can
> view transformer data. Can export data only. Message forwarding/programming
> options should not be available.

Every clause is implemented and was re-verified against live `HEAD` — both by
reading the policy tables (`ROUTE_POLICY`, `CAPABILITY_POLICY`, `ACTION_POLICY`,
`device_scope._UNRESTRICTED_ROLES`) and by a live credentialed browser session
as `demo.general01` (no session-store substitution): sidebar limited to
Overview/Command Center/Notifications/Reports; Overview, Command Center, the
full Plant→Transformer→Device hierarchy and Notifications all render
completely with no admin residue; Report Center generated a real 7-row RTL
Alarms report and enabled Download CSV; `/admin/devices` returned "No access";
the device page's operational-controls slot (ROLE-4B) stayed empty. 636
targeted tests plus the 3,097-test full suite pass unchanged.

**No UI led to a workflow that reaches a denial.** No dead CTA, no empty
container with a dangling heading, no Admin terminology surfaced to the
General user themselves was found anywhere in the audited pages.

### A note on this gate's own premise

The gate specification's §2 asserted "the client documentation uses
terminology such as: Client, Viewer." That is not supported by the repository.
Every client-facing source (`RTL_FUNCTIONAL_SPEC_EXTRACT.md`,
`RTL_CLIENT_REVIEW_GATE.md`) uses **General / General User** exclusively, and
no ADR or planning document introduces "Viewer" or "Client" as a role label.
The one place "General/Viewer" appears in this repository is this file's own
prior shorthand, written at ROLE-4B's closure — an informal aside, not client
evidence. No terminology change was made or is warranted; `"General User"`
remains correct wherever it already appears (only in the Administrator's own
user-management screens — `components/user_form_drawer.py`,
`callbacks/user_admin.py` — never shown to the General persona about
themselves, since no header/sidebar surface displays the signed-in user's own
name or role at all).

**Two distinct things, not to be conflated going forward:** the client persona
name is **General User** (used in prose, UI copy, and gate/ADR text); the
persisted application role value stored in `plant_monitoring.users.role` and
compared throughout `services/authorization.py`/`device_scope.py` is the
lowercase string `general`, and that value is unchanged and not renamed by
this gate. From this closure onward, the three client personas are named
**Administrator / Technician / General User** — not Viewer, not Client.

## Why no ADR

ROLE-4C changed no durable rule. ADR-004 (device scope), ADR-008 (Command
Center route policy) and ADR-013 (EXPORT_DATA as a capability) already state
and justify every property this audit confirmed. Writing ADR-017 to restate
them would be documentation churn, which the gate itself warned against.

## In scope

- This file only. No application source, test, or configuration file was
  edited.

## Explicitly out of scope — and not touched

- Any product code, test, or documentation beyond this record.
- **ROLE-4D** — the full three-persona comparative browser acceptance matrix.
  What ran here was a focused General-only pass, per this gate's own scope.
- Authorization policy of any kind.
- S-4/S-5, which remain open.
- The untracked `debug.log`.

## Verification

- Existing General-relevant suites — **636 passed** (authorization, action
  guard ×3, route enforcement, route scope ×2, device scope, scope repository,
  report export ×2, technician operations, credentialed personas, persona
  seed, admin overview, admin summary wiring, app sidebar).
- ROLE-4A regression — **133 passed**. ROLE-4B regression — **38 passed**.
- DB-marked suite — **496 passed**. Full suite — **3,097 passed** (unchanged
  from ROLE-4B's closing total — expected, since nothing changed).
- `git diff --check` / `git status --short` / `git diff --stat` — no
  application diff exists to check; only this file is modified.
- Context pack — CLEAN before and after.

### Live credentialed General browser pass (Playwright, 1440×900, real login)

| Surface | Result |
|---|---|
| Sidebar | Overview, Command Center, Notifications, Reports only |
| Overview | Full fleet summary; no Administration block, no residue |
| Command Center | Fully functional, read-only |
| Plant → Transformer → Device | Full hierarchy and telemetry render; device page ends after Recent Readings — no operational-controls section |
| Notifications | 132 formal notifications render; no admin-only content |
| Reports | Generate Preview produced a real 7-row RTL Alarms (30 Days) report; Download CSV enabled |
| `/admin/devices` | "No access" |

No `dcc.Store` identity substitution was used. Evidence screenshots kept
outside the repository.

## What this does not claim

This is not ROLE-4D. Only the General persona was exercised end to end here;
Administrator and Technician were confirmed unchanged by policy/test evidence,
not re-walked in the browser during this gate. S-4/S-5 remain open and this
gate makes no claim about session security.

## Next queued gate — do not start

**ROLE-4D — full browser acceptance for Administrator, Technician and General
User.** PCB remains paused at `PCB-9-CLOSE`.
