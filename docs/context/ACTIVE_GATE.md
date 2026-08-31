# Active Gate

Status: Complete — closed, committed and pushed
Date: 2026-08-31
Gate: FIX-1 Callback Regression Hardening
Branch: `cc-1-command-center-foundation`. Opened at `5de9a03`; implemented
by `723dd0b`, closed by the commit containing this file.

## Outcome

**FIX-1 PASSED. Five verified defects repaired, and the boundary they all
sat on now has tests.**

Every defect was confirmed against the source before being accepted — one
reproduced live, one proven by AST, three by execution — rather than taken
from the report that raised them. Every fix was preceded by a regression
test observed to fail.

| # | Defect | Failure before the fix | Now proven by |
|---|---|---|---|
| 1 | Add User raised `NameError` | `NameError: name 'user' is not defined` at `user_admin.py:270` | `test_add_user_persists_with_the_actor_from_the_session` |
| 2 | An unchanged username read as a duplicate on edit | `assert 'Username already exists.' == ''` | `test_editing_a_user_under_their_own_unchanged_username_is_allowed` |
| 3 | Inactive filter and inactive summary were dead | `assert ['d-active'] == ['d-active', 'd-inactive']` | `test_inactive_filter_returns_inactive_devices`, `test_summary_counts_inactive_devices` |
| 4 | CSV export raised `TypeError` | `TypeError: require_action() missing 1 required keyword-only argument: 'device_id'` | `test_download_does_not_raise_type_error`, `test_permitted_roles_reach_export_generation` |
| 5 | Assign and Manage shared one cell | `clicking 'actions' opened both drawers` — `assert not (True and True)` | `test_no_single_click_ever_opens_both_drawers[actions]` |

## The finding that mattered more than the five

All five sat in Dash callbacks, and the callback layer had no tests. That is
not a coincidence — it is why they survived a green suite. At gate open,
every one of these had **zero** test files referencing it. Now:

| callback | covering test file |
|---|---|
| `confirm_user_form` | `tests/test_user_admin_callbacks.py` |
| `populate_device_admin` | `tests/test_device_admin_inactive_filter.py` |
| `download_report_csv` | `tests/test_report_export_authorization.py` |
| `open_assign_drawer` | `tests/test_device_admin_action_routing.py` |
| `open_manage_drawer` | `tests/test_device_admin_action_routing.py` |

2,464 tests passed while Add User raised `NameError` on every save. That
cannot happen the same way again for these five paths.

## Decisions recorded

- **ADR-013 — `EXPORT_DATA` is a capability, not a device action.** Moved
  from `ACTION_POLICY` to `CAPABILITY_POLICY` with the same role set; the
  callback calls `require_capability`. **Supersedes R4-D3**, whose text in
  `services/report_export.py` was corrected in the same change per the
  supersession rule. No role gained or lost export. Scope was never this
  guard's job and still is not: `DeviceScope` reaches the repository's
  `allowed_device_ids` filter untouched.
- **FIX-1C — one column per action.** The shared `actions` cell became
  `assign` and `manage`. `column_id` was already the routing key both
  callbacks used; the defect was one cell carrying two actions. Chosen over
  pattern-matching ids because it needs no new convention, keeps
  `active_cell["row_id"]` as device identity, and leaves the responsive
  DataTable intact. Not recorded as an ADR: it changes a table's column
  layout, not an architectural rule.

## Also fixed, found while fixing the five

- `open_manage_drawer` declared 12 Outputs and every early return built an
  11-tuple. Dormant only because the dead markdown check made declines
  nearly unreachable — and a Dash output-count error the moment routing by
  column made declining routine. Now one named `_DECLINED`, sized once.
- `pages/device_admin.py` carries a duplicate column spec for first paint.
  `test_columns_match_layout_spec` caught the drift when only one was
  updated. Both are correct now; the duplication remains (see below).

## Verification

- Full non-DB: **2,504 passed** (2,464 at gate open + 40 added: 38 in the
  four new files, 2 in existing ones — the dedicated four-file selector runs
  38, and the two figures are not interchangeable).
- Full DB-marked: **487 passed**.
- FIX-1 regression tests alone: 38 passed.
- Context pack CLEAN before the close and after it.

Seven existing tests were migrated, none deleted. Each kept its original
claim and changed only the API asserting it — including
`test_export_is_open_to_every_confirmed_role`, which moved from the action
matrix to the capability matrix over the same role set, so a silent widening
during the migration would have failed it.

## Queued follow-ups — explicitly OUTSIDE FIX-1

Order is deliberate: **defect repair → upstream integration → client
synchronization.** Pulling any of these into FIX-1 would make a later
regression ambiguous between the two.

- **INT-1 — merge the Command Center branch to `main`.** The branch is
  ahead of `main` by the whole CC-1/CC-2 body of work with `main` 0 behind
  (clean fast-forward); local `main` is also 7 commits ahead of
  `origin/main` and unpushed.
- **CLIENT-SYNC-1 — bring the client readers onto the accepted work.**
  `client/cc-1-command-center-progress` still carries the pre-CC-2 CSS, and
  the client repo now has three read-only collaborators.
- **DB test-order sensitivity.** During FIX-1B a full DB run reported
  `test_batched_latest_returns_all_eight_metrics` failing. Investigated, not
  waved through: it passed in isolation, a clean worktree at unmodified
  `5de9a03` passed 487/487, and a re-run of the working tree passed 487/487.
  It reproduced only immediately after a targeted DB subset had run, so a
  green DB suite is currently order-dependent. Not caused by FIX-1 and
  deliberately not repaired inside it.
- **Device Administration duplicated column spec.** The page and the
  callback each declare the column list. They agree today and a test
  enforces it; deduplicating is a separate change.
- **Discoverability of View.** The explicit `[View](#)` link is gone, so a
  device opens by clicking its name, which renders as plain text.
  Navigation is unchanged and this was the gate's direction; whether the
  affordance needs restating is a UI decision, not a defect.

## Required tests

`python -m pytest -m "not db" -v`, plus `-m db` for the authorization and
report suites.

## Commit/push permission

GRANTED by the user on 2026-08-31, after the closure evidence was reviewed.
Landed as two commits, deliberately: an ADR cannot cite the sha of the commit
that contains that citation, because adding it changes the hash. So `723dd0b`
carries the implementation, ADR-013's decision text and the R4-D3
supersession, and this commit records the provenance and closes the gate.
