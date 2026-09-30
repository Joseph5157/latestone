# AUTHENTICATION-LOCAL-HARDENING-01 — acceptance record

Date: 2026-09-30. Baseline `b166557255a5210e8c0500371fa2904ae71557fe`. ADR-033.
Browser run: Playwright, 1366x768, the app on `127.0.0.1:8050` against the
development PostgreSQL (migration 017 applied) and the local read-only client
SQL Server copy. **No plaintext password, hash or token is recorded here;** the
acceptance passphrases were typed into password fields only, and every setup
link was consumed during the run.

## Migration (development database, before -> after)

`pg_before.json` / `pg_after_migration.json` / `pg_after.json`:

- Alembic `016_rtl_technician_assignments` -> `017_local_auth_hardening`.
- 13 users, none deleted, ids unchanged. Users 117-121 (linked, login-less
  Technicians) `active` -> `pending_activation`; links `client_person_id` 2-6
  untouched. The other eight (`admin`, `demo.tech01-05`, `demo.general01`,
  `cvbncv`) stay `active` with no hash (usable only through the explicit
  development fixture).
- `rtl_technician_assignments`: 68 rows / 64 open, and the row-level fingerprint
  is identical before and after (assignments neither altered nor rewritten).
  Readings, devices, plants, transformers, `user_device_assignments` counts
  identical.

## Administrator

1. `python -m scripts.bootstrap_admin` created one Pending Administrator and
   printed a one-time link (`ADMIN_BOOTSTRAPPED`, system-originated).
2. Set-password page: a 5-character password was refused with the policy
   message and did not consume the link (`01_setup_weak_password.png`); a valid
   passphrase activated the account (`02_admin_setup_done.png`). Re-opening the
   used link shows "Link not valid" (single use).
3. Login with a wrong password showed only "Invalid username or password."
   (audited `LOGIN_FAILED`); the correct passphrase signed in.
4. User Administration (`03_admin_user_management.png`): new columns Name,
   Status (Pending activation / Active / Disabled), Client person; summary line
   "14 users total — 9 active, 5 pending activation, 0 disabled".
5. Technician provisioning (`04_technician_pending_drawer.png`; the one-time link panel sits below the fold and is deliberately not screenshotted): user 121 opened
   in the drawer (read-only status "Pending activation", Client person 6);
   renamed to a real username (audited `USER_UPDATED`); *Issue setup link*
   rendered the one-time link with the handover note ("no email or SMS was
   sent ... shown once ... closing this panel discards it"). Closing and
   reopening the drawer left no link and no token anywhere in the DOM.
6. Disable then re-enable of the Technician from the drawer: status text, table
   row and buttons updated; sessions ended; assignments untouched.
7. Audit log page listed `ADMIN_BOOTSTRAPPED`, `PASSWORD_SETUP_ISSUED/COMPLETED`,
   `ACCOUNT_ACTIVATED`, `LOGIN_SUCCEEDED/FAILED`, `USER_CREATED`, `USER_UPDATED`,
   `ACCOUNT_DISABLED/REENABLED` with no hash or token text (`09_audit_log.png`).

## Technician (client person 6, one assigned RTL)

- Completed first-time setup from the link, signed in, landed on
  **Assigned RTLs** with exactly one RTL, no administration navigation
  (`06_technician_landing.png`).
- `/rtls/<assigned UID>` rendered; `/rtls/<another Technician's UID>` and
  `/rtls/<unassigned UID>` both answered "No access" (no existence oracle).
- `/events` listed only the assigned UID. `/admin/users` -> "No access".
- Logout, then a protected route showed the login form
  (`07_protected_route_requires_login.png`).

## General User

Account created in User Administration, link issued, password set; sign-in
with different letter case of the username worked; full Registered RTLs
(339, unrestricted) with the General User navigation (`08_general_user_login.png`).

## Defect found by this run and fixed

Permanent sessions with per-request cookie refresh let a slow in-flight request
that had read the cookie before a logout write the old session straight back,
so *Logout* appeared to do nothing. Fixed: the session lifetime is fixed from
login (`AUTH_SESSION_HOURS`, default 8) and `SESSION_REFRESH_EACH_REQUEST` is
off; a test pins it. Console: 0 errors caused by this gate (the only errors were
"server did not respond" during a deliberate app restart).

## SQL Server safety

`sqlserver_before.json` and `sqlserver_after.json` are byte-identical: persons 8,
roles 3, device_list 339, techmician_device_list 68, technician_assignments 0,
no `persons` credential values, and the read-only login holds no
db_datawriter/UPDATE/INSERT/DELETE rights. No authentication code path writes it.

## Acceptance clean-up (development database)

`accept.general` and `accept.admin` were disabled through the audited service
(actor: the seeded demo administrator). User 121 was returned to its exact
pre-acceptance state by direct SQL (there is deliberately no service path back
to Pending): original username `client-person-6`, no password, pending,
sessions invalidated, open tokens revoked. The two `accept.*` accounts remain as
disabled rows; the audit rows from the run remain (34 -> 62).
