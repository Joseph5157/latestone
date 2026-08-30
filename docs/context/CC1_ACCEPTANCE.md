# CC-1 Command Center — Acceptance Record

Status: Approved
Date: 2026-08-30
Branch: `cc-1-command-center-foundation` @ `6aafc4c` (21 commits ahead of
`main`, unpushed)

Evidence for the CC-1 push decision. Every PASS below was observed, not
inferred; where something was verified indirectly it says so.

## Result

| Item | Result |
|---|---|
| ADRs | **11/11** implemented (001-011) |
| Automated suite (`-m "not db"`) | **PASS** — 2,459 tests |
| DB suite (`-m db`) | **PASS** — 487 tests |
| Mixed freshness browser | **PASS** |
| Freshness capture/restore | **PASS** — 1,515/1,515 exact |
| EVT-D5 role verification | **PASS** — both roles rendered |
| Dark/light | **PASS** — 6 matrix cells, 0 contrast failures |
| Polling + failure + recovery | **PASS** |
| Plant selection persistence | **PASS** |
| Theme persistence | **PASS** (after a defect fix, below) |
| Asset drill-through | **PASS** |
| Fleet Overview regression | **PASS** — no presentation file touched |
| Reports / Notification Center | **PASS** — unaffected |
| Desktop matrix 1440/1366/1024 | **PASS** — no horizontal overflow |
| **Blocking defects** | **None** |

## The semantic proof (Section A)

Ran through the reversible workflow: capture → apply → verify → restore →
prove. Fixture and screen agreed exactly.

| RTL | State | Panel row | `oldest_metric` | `device_last_updated` |
|---|---|---|---|---|
| plant-02 | FRESH | absent from Needs Attention and Priority | 11:00 | 11:00 |
| plant-03 | STALE | "Oldest monitored metric last reported 4h 05m ago" | 07:30 | 07:30 |
| **plant-04** | **STALE** | **"…9h 35m ago"** | **02:00** | **11:00** |
| plant-05 | NO_DATA | "At least one monitored metric has no reading." — **no age** | `None` | 11:00 |

`plant-04` is the proof the whole phase was built for. Its two timestamps
are nine hours apart; a row reading `device_last_updated` would have claimed
**35 minutes**. It reported **9h 35m**.

`plant-05` holds `None`, so any age at all would have been fabricated. None
appeared.

Ordering held: NO_DATA first, then STALE oldest-first (9h35m before 4h05m).
Fleet Health read 117/2/1, matching `get_fleet_health` exactly; Needs
Attention 3 = Stale + No Data; Communication 1 No Data across 1 plant.

**Restore proved exact**: 1,515 of 1,515 rows returned, readings back to
1,383,360, fleet back to 120/0/0. No demo state left in the database.

## EVT-D5, both sides rendered (Section B)

| Identity | Unregistered-UID row |
|---|---|
| administrator | present — `UID 99000042 · Unregistered UID` |
| technician (24 RTLs in scope) | **absent from the DOM entirely** |

Not merely hidden: the string `99000042` appears nowhere in
`document.documentElement.outerHTML`, with zero hidden/disabled placeholders
and no link revealing it indirectly.

**Method, stated plainly:** the non-administrator side was verified by
substituting the authorization identity in the session store, not by a
credentialed sign-in. EVT-D5 is an authorization rule and that is the input
it keys on, so the rendered result is the real one — but this exercised
authorization, not authentication. A credentialed technician login remains
unverified.

## The defect acceptance found

**Selecting a Plant silently reset the appearance to dark.** Dash re-applies
a `dcc.Store`'s declared `data=` on every component MOUNT, and this page
remounts on every in-app navigation — so the declared default overwrote the
operator's stored choice, store and all. It survived a full page reload
(where the store loads first) and died on a client-side one, which is why
Phase 11's own navigation check missed it.

Fixed by declaring no initial data. Re-verified across both cases: selecting
a Plant, and a round trip to `/plants` and back. A regression test asserts
the store declares no initial data.

## Polling (Section E)

Two cycles observed at the configured 60s cadence with the DOM sampled every
300 ms. Card count never dropped below 9; theme and `?plant=` never changed.

Database stopped mid-session: banner appeared, `Last updated` froze at
11:41:09, all nine cards kept real data, no error panel (correct — that path
is first-load only). Database restarted: banner cleared on its own and
`Last updated` advanced to 11:43:09.

## Containment

`/plants`, `/reports` and `/notifications` all carry no `cc-theme--` class
in the DOM, resolve `--cc-*` to nothing, and keep `--state-none-text:
#495057` / `--state-stale-text: #713f12` unchanged.

No shell Python file was edited to obtain theming — verified against the
commit (`267b11a` touches none) and enforced by a live test. `app_sidebar.py`
and `app_header.py` do appear in the branch, in `fb6fae2`, a separate and
explicitly-titled commit moving Logout to the sidebar.

## Branch hygiene

- `git diff --check` — clean
- 72 files, +11,915 / −231
- No images, binaries, seed data, or scratch scripts committed
- No Fleet Overview presentation file touched
- Every non-Command-Center file has a CC-1 reason: routing and route policy,
  the batched `list_device_paths` read, `device_oldest_metric_updated`,
  `format_age`/`NO_DATA_EXPLANATION` moved to services for the one-way
  dependency rule, the seeds, and the Logout shell commit.

## Deferred, explicitly

1. **Credentialed non-administrator sign-in** — EVT-D5 verified by identity
   substitution; a real technician login has no demo credential.
2. **Login-form React warning** — pre-existing, reproducible on `/login`
   before Command Center exists. Not a CC-1 blocker.
3. **"State update on an unmounted component" warning** — pre-existing Dash
   `Suspense` behaviour; reproduced navigating `/plants` ↔ `/reports` with
   Command Center never involved.
4. **Live simulator drift** — `db/live_simulator.py` grows `readings` beyond
   the seeded 1,383,360 and will fail `test_seed_integrity` again. Cleared
   by `--reset`; not a defect in either.
5. **`--purge` executed end to end** — its refusal path and ordering are
   tested, and the ordering is checked against the live schema, but the
   destructive branch has never been run against a real database.

## Not verified

Mobile and tablet widths. The matrix is desktop only (1440/1366/1024), which
is what the cockpit is designed for.
