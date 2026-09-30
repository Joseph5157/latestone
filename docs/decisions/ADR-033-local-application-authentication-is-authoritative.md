# ADR-033: Local application-managed authentication is authoritative

Status: Approved
Date: 2026-09-30
Evidence: `docs/audit/authentication-realignment-01/AUTHENTICATION_REALIGNMENT.md`;
`docs/database/CLIENT_RTL_SQLSERVER_KNOWLEDGE_BASE.md` §18;
`docs/client/CLIENT_DB_CLARIFICATION_01_RESPONSE_TRACKER.md` CDB-04;
`services/auth_service.py`; `services/account_service.py`;
`alembic/versions/017_local_auth_hardening.py`;
`docs/audit/authentication-local-hardening-01/`
Implemented-by: not yet

## Context

The application authenticated with environment-configured plaintext
username/password pairs that merely named a PostgreSQL `users` row. The
realignment audit (AUTHENTICATION-REALIGNMENT-01) found no per-user hash, no
setup/reset, no throttling, no session revocation, no login/logout audit, and a
demo credential that could create an Administrator on first login. The client
SQL Server `persons` table has `user_id` / `password_hash` columns, but every
value is empty. CDB-04 asked whether an external Microsoft/Active Directory
sign-in should be used; the business decision is now final.

## Decision

1. **Local, application-managed authentication is authoritative.** The
   application uses its own username/password sign-in. External
   Microsoft / Active Directory / Entra ID / SSO authentication is **not
   required and is not part of the current architecture.** (CDB-04: ANSWERED.)
2. **The application PostgreSQL `users` table owns credentials.** SQL Server
   `persons` is an identity *reference* only. `persons.user_id` and
   `persons.password_hash` are never read for login and never written; the
   client SQL Server stays `READ_ONLY` (ADR-029). Final production storage of
   these credentials still requires a separately approved ADR-029 SQL Server
   proposal; nothing here authorizes a SQL Server write.
3. **Passwords use a secure per-user hash.** Werkzeug `scrypt` with a random
   per-hash salt, verified only with the framework helper. No plaintext, no
   reversible storage, no password logging or display. Policy: at least 12
   characters, at most 256, passphrases welcome, not blank, not equal to the
   username; no composition rules.
4. **`client_person_id` is an explicit, validated linkage.** An integer link to
   a client `persons` row, unique in both directions, validated read-only
   against the person's client role (Technician ↔ Technician, Administrator ↔
   Administrator; a General User has no client counterpart and cannot be
   linked). People are never matched by name. A Technician must be linked
   before a setup link may be issued.
5. **Account lifecycle.** `pending_activation` → `active` → `disabled`.
   Pending cannot sign in. Active may sign in if the credential is valid.
   Disabled cannot sign in; its sessions die at once; its Technician
   assignments and history are untouched (account state is not assignment
   state). Re-enable returns an account to Active if it already has a password,
   otherwise to Pending. An account becomes Active only by completing password
   setup, never by choosing a status. Usernames are canonical lower case,
   unique, never derived from a display name. Email stays optional and
   non-unique.
6. **Provisioning is an Administrator workflow with one-time tokens.**
   Administrator creates/links an account (Pending), issues a setup link; the
   user chooses the password; the token is spent and the account is Active. A
   reset link is the same mechanism for an Active account. Tokens are 256-bit
   random, time-limited (setup 72 h, reset 60 min by default), single-use,
   stored only as SHA-256, revoked by a newer token and by any security change,
   and answered with one generic message when unusable. **No email or SMS
   exists**: the Administrator sees the link once and hands it over. A later
   notification gate may automate delivery.
7. **Sessions.** Flask's signed cookie carries `uid` plus a `session_version`,
   an issue time and a per-login nonce. Password set/reset, disable, rename,
   role change and client-link change bump the version, so every earlier
   session is refused; a fixed session lifetime from login (8 h,
   `AUTH_SESSION_HOURS`) applies as both cookie lifetime and server-side check;
   a cookie without the metadata is refused. The cookie is deliberately NOT
   refreshed per request: a slow in-flight request that read the cookie before
   a logout would rewrite the old session and undo the logout (found in browser
   acceptance). Cookie flags
   (`HttpOnly`, `SameSite=Lax`, `Secure` in production) and the production
   secret-key requirement are unchanged.
8. **Throttling.** Failed sign-ins are counted per hashed login name (real or
   not, so there is no username oracle) with a bounded, doubling back-off (5
   failures, 60 s doubling to 15 min, forgotten after 30 min, cleared on
   success). No permanent lockout. Every refusal shows the same generic
   message; a throttled name shows a separate generic "wait" message that
   reveals no counter or duration.
9. **Demo authentication is prohibited in production.** The
   `DEMO_USERNAME` / `DEMO_PASSWORD` / `DEMO_CREDENTIALS` pairs survive only as
   a development/test fixture: they need `AUTH_DEMO_LOGIN_ENABLED`, apply only
   to an account with no password hash, and a production process
   (`APP_ENV=production`) refuses to start while any of the four is set.
   `seed_demo_user()` (auto-provisioning) never runs in production.
10. **Production preflight and bootstrap.** `python -m scripts.auth_preflight`
    (wired in front of the production start command) fails closed when demo
    configuration or the secret is missing, or when no active, non-demo
    Administrator with a password exists. The initial Administrator is created
    only by the explicit `python -m scripts.bootstrap_admin` operator command
    (Pending, one-time link, idempotent, refuses if an Administrator already
    exists unless `--allow-additional`), never at start-up or login.
11. **Audit.** Sign-in and lifecycle events are recorded in the existing audit
    log (`LOGIN_SUCCEEDED`, `LOGIN_FAILED`, `LOGIN_THROTTLED`, `LOGOUT`,
    `USER_CREATED`, `CLIENT_PERSON_LINK_CHANGED`, `USER_ROLE_CHANGED`,
    `PASSWORD_SETUP_ISSUED`, `PASSWORD_SETUP_COMPLETED`, `ACCOUNT_ACTIVATED`,
    `PASSWORD_RESET_INITIATED`, `PASSWORD_RESET_COMPLETED`, `ACCOUNT_DISABLED`,
    `ACCOUNT_REENABLED`, `ADMIN_BOOTSTRAPPED`). Only `LOGIN_FAILED`,
    `LOGIN_THROTTLED` and `ADMIN_BOOTSTRAPPED` are system-originated (no
    signed-in actor). Rows never carry a password, hash, raw token or cookie,
    and never the typed text of a failed login.
12. **Assignment authorization remains downstream of authentication.**
    Authentication proves the application user only:
    credential → account status → role → `client_person_id` → ADR-032
    assignment scope → allowed RTL UIDs. A valid password is not sufficient if
    the account is not Active or the scope denies the resource. ADR-032 is
    unchanged.
13. **External SSO is not part of the current architecture.** If the client
    later asks for it, that is a new gate: an immutable provider subject would
    resolve to the same application user and could not supply a role or bypass
    scope. The authentication seam (`check_credentials`) stays replaceable.

## Consequences

- Migration 017 adds `users.password_hash`, `password_changed_at`,
  `session_version`, `last_login_at`; a status vocabulary CHECK; a lower-case
  username CHECK; `auth_tokens`; `auth_login_throttle`. Existing `inactive`
  rows become `disabled`; active rows linked to a client person (the five
  login-less Technician anchors, users 117–121) become `pending_activation`;
  other existing active rows keep `active` with no hash (usable only through
  the explicit development fixture; in production they cannot sign in until an
  Administrator issues a reset link). No row, id, role, link or assignment is
  deleted or changed otherwise.
- `check_credentials` now reads the user row before verifying (it must, to find
  the hash); every refusal spends the same verification work.
- Pending Technicians cannot yet be assigned NEW RTLs (assignment targets must
  be Active); their existing assignments remain and are inherited on
  activation without any rewrite.
- Known limits, recorded as debt: a signed cookie cannot be revoked
  individually (logout clears it; theft after logout is bounded by the fixed lifetime and by
  any security-version bump); there is no idle timeout; throttling is per login name, not per
  source address; no self-service password change, no MFA, no password expiry;
  delivery of setup/reset links is manual until a notification gate exists.
