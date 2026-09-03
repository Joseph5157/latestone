# Active Gate

Status: CLOSED — committed to `main` in this closure commit
Date: 2026-09-03
Gate: AUTH-HARDEN-1 (+ AUTH-HARDEN-1R, AUTH-HARDEN-1R2) — server-trusted
authorization
Branch: `main`, baseline `0c40478a458b619f1f28751f7697aea3e48e7128`
Commit/push permission: **COMMIT GRANTED, PUSH NOT GRANTED.** This gate's own
closure instruction is "commit the completed tranche; do not push." See `git
log -1` for the resulting commit; `origin/main` is unchanged.

## Purpose

Close S-4/S-5 (`docs/CODE_AUDIT.md`, "Security posture") — the gap ROLE-4D
explicitly declined to claim closed: "the session is still a browser-side
`dcc.Store`, and the data callbacks still do not independently verify it."
Replace that with a real server-trusted session so role-based authorization
stops being an application-level affordance and becomes an actual boundary.

## What changed

**A Flask signed session, not the browser-side `auth-store`, is now the
identity source.** `server.secret_key` (`app.py`, `config.settings.
flask_session`) signs the cookie. `services.auth_service.
start_trusted_session(user_id)` is called once, from `callbacks.auth.
handle_login`, after a real credential has already resolved a real `users`
row in that same call — nothing browser-supplied is read first.
`end_trusted_session()` clears it on logout.

**`current_identity()` re-reads the database on every call — no caching.**
The signed session carries nothing but a `user_id`; role, status and full
name come from the CURRENT `users` row every time. A demotion or
deactivation an administrator performs while the affected user's tab stays
open takes effect on that user's very next protected request, not on their
next login — verified directly (see Verification below).
`services.device_scope.current_device_scope()` applies the same rule to
`DeviceScope`.

**`auth-store` is now presentation-only.** It still carries the identity for
the four callbacks that branch on its `authenticated` flag (pre-login
cosmetics: hiding the equipment selector, etc.) and for whatever the UI
renders from it, but no authorization decision reads it. Every previously
independently-invokable callback that used to answer whoever asked now calls
`current_identity()`/`current_device_scope()` first: device telemetry
refresh, the device-admin and user-admin tables, the user-save mutation,
device assignment, message forwarding, RTL programming, RTL deactivation,
device registration's loaders and review step, plant/transformer detail, and
report scope labels.

**The router's existence oracle is closed (AUTH-HARDEN-1R2).** For a
restricted Technician, `callbacks/routing.py` now checks `entity_in_scope`
*before* any unrestricted existence lookup for plant, transformer and device
routes — a nonexistent id and a real-but-out-of-scope id both resolve to the
identical Forbidden response, with no unrestricted query ever run to tell
them apart. Administrator/General are unaffected (`entity_in_scope`
short-circuits `True` with no query for an unrestricted scope).

Full narrative, including the three read-path defects AUTH-HARDEN-1R found
and fixed (registration loaders, plant/transformer detail, report labels) and
the exact reordering AUTH-HARDEN-1R2 made, is recorded in
`docs/CODE_AUDIT.md`'s "AUTH-HARDEN-1 (+ 1R, 1R2) closes S-4 and S-5" entry —
this file summarizes; that one is the detailed record.

## Why no ADR

This is architecture the module docstrings (`services/auth_service.py`,
`services/authorization.py`, `services/device_scope.py`,
`services/hierarchy_service.py::entity_in_scope`) already state and justify
inline, and `docs/CODE_AUDIT.md` already tracks S-4/S-5 as a running,
append-only security log — adding a fourth parallel record would duplicate
rather than clarify. Follow the reasoning at its source.

## In scope

- Server-trusted Flask session (identity + scope resolution).
- Closing S-4/S-5 for every previously browser-trusting protected callback.
- The router existence-oracle fix and its test coverage.
- Report/export scope-label metadata protection and its test coverage.
- Tests: `tests/auth_test_support.py`, `tests/test_auth_harden.py`,
  `tests/test_auth_harden_repair.py` (new), plus corrections to
  `tests/test_route_scope.py` / `tests/test_route_scope_db.py` where their
  prior assertions described the disclosure this closure fixes.
- This closure's own documentation (`docs/CODE_AUDIT.md`, this file).

## Explicitly out of scope — and not touched

- Microsoft Entra ID / any real SSO — `DEMO_CREDENTIALS` remains the
  authentication mechanism.
- Physical RTL programming, SMS forwarding, the 18:30 forwarding scheduler,
  the Maximum Temperature report — none of these are implemented by this
  gate; do not read anything above as claiming otherwise.
- New alarms, UI redesign, new roles, an audit UI.
- Production cookie/deployment hardening (`SESSION_COOKIE_SECURE`, explicit
  `SameSite`, HTTPS enforcement, a production `FLASK_SECRET_KEY` that fails
  closed rather than falling back to a per-process random key) — recorded as
  a non-blocking follow-up below, not part of S-4/S-5's closure.
- `services.device_scope.scope_from_session()` — kept, unused by any
  protected path, per the repository's "remove only what is demonstrably
  unused everywhere" convention.
- `callbacks/listings.py::hierarchy_code_index()` — recorded as a
  non-blocking follow-up below.
- `debug.log` — untracked, untouched throughout.

## Non-blocking follow-ups (not implemented here)

1. `callbacks/listings.py::hierarchy_code_index()` runs a broader-than-
   strictly-necessary fleet-wide `list_all_devices()` read when at least one
   plant is non-fresh. No demonstrated disclosure — its output only labels
   entries the caller's own scope-filtered `health`/`plants` already
   restricted to. Defense-in-depth follow-up only.
2. `services/device_scope.py::scope_from_session()` remains a legacy
   compatibility helper with no protected production caller.
3. Production cookie/deployment hardening (see "Explicitly out of scope"
   above) remains future work.

## Verification

Three independent verification passes, each starting from a fresh read of
the actual code and re-running the tests rather than trusting the prior
pass's narrative:

- **AUTH-HARDEN-1** — 3112 passed (baseline 3097), 15 named AUTH-HARDEN
  tests, manual security recheck matrix (role forgery, user_id forgery,
  mid-session revocation, out-of-scope device denial).
- **AUTH-HARDEN-1R** — found and fixed 3 blockers (registration loaders,
  plant/transformer detail, report labels) independent verification
  surfaced; 27 new AUTH-HARDEN-R tests, each invoking a REAL registered
  callback against a REAL (fake- or DB-backed) trusted session — never a
  hand-built identity. 3139 passed.
- **AUTH-HARDEN-1R2** — found and fixed the router existence oracle plus an
  ineffective export test (checked the status message, not the actual
  downloadable payload); 22 new/corrected tests, including a deliberate
  revert-and-rerun proof that the new router tests actually fail against the
  old existence-first ordering. 3161 passed.
- **Final independent re-verification** (read-only, no code changes) —
  re-ran the full matrix cold, confirmed the router order, the export
  payload flow, and a residual search for the same defect class elsewhere in
  `callbacks/`; verdict **AUTH-HARDEN-1 VERIFIED WITH NON-BLOCKING
  FOLLOW-UPS — SAFE TO COMMIT**.

Final numbers for this closure commit:

- Route R2 tests: 42 passed
- Export/report-label R2 tests: 16 passed
- Full AUTH-HARDEN (`test_auth_harden.py` + `test_auth_harden_repair.py`):
  61 passed
- Route/report/listing regression (14 files): 436 passed
- DB-marked suite: 510 passed, 2651 deselected
- Full suite: 3161 passed (from a 3097 pre-AUTH-HARDEN baseline — zero
  existing tests deleted, skipped, or weakened across all three tranches;
  two tests were corrected because their prior assertions described the
  existence-oracle disclosure this closure fixes, not weakened to obtain
  green)

## Next queued gate

None queued. The operator decides what comes next.
