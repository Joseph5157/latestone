# Active Gate

Status: Open
Date: 2026-08-31
Gate: FIX-1 Callback Regression Hardening
Branch: `cc-1-command-center-foundation` @ `5ec3862`, in sync with `origin`.

The previous gate, CC-2, is complete. Its record is
`docs/decisions/ADR-012-rank-bars-are-capped-and-route-themed.md`, which
carries the outcome, both implementing shas, and the two items deliberately
carried forward. Do not look for it here.

## Task

Repair five verified callback-layer defects and establish regression coverage
at the boundary where they occurred.

**The finding is bigger than the five defects.** Every one of them is in a
Dash callback, and the callback layer has no direct tests:

| callback | test files referencing it |
|---|---|
| `download_report_csv` | 0 |
| `confirm_user_form` | 0 |
| `open_assign_drawer` | 0 |
| `open_manage_drawer` | 0 |
| `populate_device_admin` | 0 |

2,464 tests pass while Add User raises `NameError` on **every** save. A green
suite currently proves nothing about whether these workflows run. Regression
coverage at the callback boundary is therefore part of this gate, not
optional cleanup afterwards — the fixes are the occasion, the coverage is the
point.

**Work test-first.** Add a failing regression test BEFORE each production
change, and report the failure evidence before fixing. A fix landed without a
test that was first seen to fail has not been verified, it has been asserted.

### The five verified defects

Each was confirmed against the source, not taken from a report.

1. **`callbacks/report_center.py:720` — export raises `TypeError`.**
   `download_report_csv` calls `require_action(user, EXPORT_DATA)`, but
   `require_action(user, action, *, device_id: str)` takes `device_id` as
   keyword-only with no default. Reproduced live:
   `TypeError: require_action() missing 1 required keyword-only argument: 'device_id'`.
   The surrounding `except AuthorizationError` cannot catch it.

2. **`callbacks/user_admin.py:270` — save raises `NameError`.**
   `confirm_user_form` reads `user.user_id`, but line 250 discards the return
   of `from_session(auth_data)` and `user` is bound nowhere in that scope
   (AST-verified: read = True, bound = False).

3. **`callbacks/user_admin.py:38-45` — an unchanged username reads as a
   duplicate.** `_validate_user_form(username)` rejects when `get_user()`
   finds any record, including the one being edited. It never receives
   `existing_username`.

4. **`callbacks/device_assign.py:145` and `callbacks/device_manage.py:73` —
   Assign and Manage cannot be told apart.** Both fire on the DataTable
   `active_cell` with `column_id == "actions"`, an identical condition.
   `active_cell` identifies the cell, never which markdown link inside it was
   clicked.

5. **`callbacks/device_admin.py:189` — the Inactive filter is dead.**
   `pages/device_admin.py:75` offers an `Inactive` option, but
   `list_all_devices()` is called with its `include_inactive=False` default,
   so inactive devices never enter the table for the filter to match.

## The three review points

This gate does NOT run start to finish unattended. Stop and report at each
boundary; the next stage is not authorized until the previous one is
reviewed.

### FIX-1A — Users add/edit, then the inactive-device filter

Defects 2 and 3 are **one coherent change**: they live in the same save path,
and 3 returns first, so an edit with an unchanged username never reaches the
`NameError`. Fixing 3 alone widens 2's blast radius.

Required cases, failing first: add user as an authenticated administrator
reaches persistence with the actor id derived from `from_session`; edit with
an unchanged username validates; edit onto **another** user's username is
still refused; an invalid or absent session fails closed.

Then, separately, the inactive filter. Do **not** change
`list_all_devices()`'s default globally — `db/live_simulator.py`,
`db/seed_admin_demo.py`, `db/seed_events_demo.py` and `callbacks/listings.py`
all rely on it. Device Administration should explicitly request the
population its advertised filter needs.

**STOP AND REPORT.**

### FIX-1B — Export authorization, decided before it is implemented

Do not pass a fabricated `device_id` to satisfy the signature. Do not swap in
`require_capability` blindly either: `EXPORT_DATA` is currently in
`ACTION_POLICY`, not `CAPABILITY_POLICY`, and `may_perform_capability`
default-denies an unknown capability — so a naive swap refuses every role.

Produce a read-only decision note first: is export a device action or an
application capability; does a report span zero, one, or many devices; what
scope enforcement already happens when rows are built; would moving the
constant change any existing authorization outcome; which roles keep export;
what test proves no scope widening. If the answer is to move it, that is an
ADR-level change (it would be ADR-013) and the ADR lands before the code.

**STOP AND REPORT THE DECISION BEFORE TOUCHING THE POLICY TABLES.**

### FIX-1C — Assign vs Manage, redesigned not patched

No string parsing of cell contents, no click-position heuristics. The
interaction contract is wrong, not the parsing. Compare separate
columns/buttons against pattern-matching per-row ids on callback simplicity,
accessibility, visual impact, and testability, and propose the smallest
robust contract.

Tests must prove that Assign opens only the assignment drawer, Manage only
the management drawer, the device id is correct, an unauthorized action is
still refused, and the existing `?assign=<device_id>` deep link from the
Overview still works.

**STOP AFTER DESIGN AND FAILING-TEST EVIDENCE. Do not implement until
reviewed.**

## Non-goals (explicit)

- Authorization is never weakened to make a test pass. A refusal that becomes
  a pass is a defect, not a fix.
- No fabricated device identifiers to satisfy an API signature.
- No route, schema, or public-behaviour change beyond what a verified defect
  requires.
- Not in scope, and explicitly not bugs: absent SMS/email transport,
  Maximum Temperature as prototype, demo authentication, polling rather than
  streaming, programming requests not reaching hardware. These are known
  scope and integration limits.
- No Command Center work. ADR-011 and ADR-012 stand.

## Known ambiguities

- Whether `EXPORT_DATA` is an action or a capability is the open question of
  FIX-1B, not a settled premise. ADR-004 fixed that device scope is
  authorization-derived and never user-selectable; it did not decide how a
  multi-device export expresses that.
- `pages/device_admin.py` advertises Active/Inactive as though the underlying
  read supports it. Whether "All" is also intended is not stated anywhere and
  should be settled from the page, not assumed.

## After this gate — queued, and deliberately not merged into it

Recorded here so the sequence survives a lost conversation. Neither is in
scope, and pulling either forward would make FIX-1 harder to review: a
regression found afterwards must be attributable to FIX-1 alone, not to
integration work that landed in the same window.

- **INT-1 — merge the Command Center branch to `main`.**
  `cc-1-command-center-foundation` is 31 commits ahead of `main` and 0
  behind, a clean fast-forward; local `main` is also 7 commits ahead of
  `origin/main` and unpushed. No open PRs. Upstream integration, not defect
  repair.
- **CLIENT-SYNC-1 — bring the client readers onto the accepted
  Command Center.** `client/cc-1-command-center-progress` still carries the
  pre-CC-2 CSS (`minmax(0, 10rem) 1fr auto`, `--state-stale-text`), and the
  client repo now has three read-only collaborators. Client synchronization,
  a third concern again.

The order is deliberate: **defect repair → upstream integration → client
synchronization.**

## Relevant files

- `callbacks/report_center.py` — defect 1, `download_report_csv`
- `callbacks/user_admin.py` — defects 2 and 3, one change
- `callbacks/device_admin.py` — defect 5, `populate_device_admin`
- `callbacks/device_assign.py` — defect 4, `open_assign_drawer`
- `callbacks/device_manage.py` — defect 4, `open_manage_drawer`
- `pages/device_admin.py` — the advertised Active/Inactive filter
- `components/entity_table.py` — the shared actions cell
- `services/action_guard.py` — `require_action` / `require_capability`
- `services/authorization.py` — `ACTION_POLICY`, `CAPABILITY_POLICY`
- `services/report_export.py` — where export scope is enforced today
- `services/hierarchy_service.py` — `list_all_devices`
- `repositories/plant_monitoring_repository.py` — `include_inactive`

## Required tests

`python -m pytest -m "not db" -v`

Plus the new callback regression tests, each demonstrated failing before its
fix. Tests must never write to the real `plant_monitoring` schema — use the
`isolated_schema` fixture — and unmarked tests may not open a DB connection.

## Commit/push permission

NOT GRANTED until the final review. Work through FIX-1A, FIX-1B and FIX-1C
stopping at each review point, then report: files changed, tests added, proof
each failed first, the `EXPORT_DATA` decision, the Assign/Manage decision,
targeted and full non-DB results, remaining risks, `git diff --check`, and
`git status --short`.
