# AUTHENTICATION-REALIGNMENT-01

Status: **CLOSED / PASS — audit and planning only**
Date: 2026-09-30
Repository baseline: `79027e4f49d092d5f399a2c94035707b51a447a8`
Database work: read-only inspection only; no credentials, account state,
assignments, or client SQL Server data were changed.

## 1. Current auth architecture

### Sign-in and identity

The login form accepts `username` and `password`. `services/auth_service.py`
checks the pair against environment configuration: the primary
`DEMO_USERNAME`/`DEMO_PASSWORD` pair plus optional username/password pairs in
the `DEMO_CREDENTIALS` JSON object. Comparison uses `hmac.compare_digest`, with
a sentinel comparison for an unknown username. The application does **not**
store or verify a per-user password hash.

After a configured pair matches, `authenticate()` loads the PostgreSQL
`plant_monitoring.users` row by the typed username. The row—not the credential
configuration—supplies `user_id`, display name, role, and account status. Only
`active` rows with one of `administrator`, `technician`, or `general` may sign
in. Every refusal returns the same UI message: `Invalid username or password.`

On success, the server clears the existing Flask session and stores only the
resolved `user_id` in Flask's signed cookie session. Every protected operation
uses `current_identity()` to reload the current user row; role changes and
disablement therefore take effect on the next protected call. The browser
`dcc.Store` is session-storage presentation state and is reconciled from the
trusted server session; it is not an authorization source. Logout at `/logout`
clears the Flask session and browser auth store.

Production session hardening already requires `FLASK_SECRET_KEY`, sets the
cookie `Secure`, `HttpOnly`, and `SameSite=Lax`, and fails startup if the secret
is missing. Development uses a per-process random secret. No explicit idle or
absolute session timeout is configured.

### Accounts, roles, and administration

`users.username` is the login lookup key. `email_address` is an optional
identifier/contact field and is not a login key. `mobile_number` is optional.
The PostgreSQL `users` row holds `role` and `status`; there is no separate role
provider. User Administration is Administrator-only and persists username,
identifier/email, role, and `active`/`inactive` status. It does not set a
password, link a client person, or send an activation/reset message.
`USER_CREATED` and `USER_UPDATED` are audited atomically with saves. Login,
login failure, logout, password, activation, and explicit link-change events
are not currently written to the audit log.

### Provisioning and unsupported controls

Development identities come from three paths:

- `prototype_users.seed_demo_user()` creates the configured primary demo
  username as an active Administrator on first successful credential use if
  the row is absent.
- `python -m db.seed_demo_personas` explicitly creates the synthetic General
  User identity; `db.seed_admin_demo` creates synthetic Technicians. Neither
  seed creates credentials.
- `python -m scripts.bootstrap_rtl_assignments --apply
  --provision-technicians` explicitly created five login-less Technician users
  to anchor the imported client-RTL assignments.

There is no password setup or reset flow, password policy, password expiry,
MFA, login rate limit, account lockout, recovery-code flow, external identity
provider, OAuth/OIDC, SAML, Entra ID, or Active Directory integration. The
application logs safe diagnostic messages for some login refusals but has no
successful-login audit and no durable failed-login record.

## 2. Current user/person mapping

The client SQL Server was queried read-only. All eight `persons` rows have
blank/null `user_id` and `password_hash` values. These fields cannot
authenticate anyone and the application does not read them for login.

| Client person | Client role | Application user | App role/status | Mapping |
|---|---|---|---|---|
| 1 — Milton Sambo | Administrator | none | — | not linked |
| 2 — Senzo Mpungose | Technician | 117 — `client-person-2` | technician / active | linked |
| 3 — Reginald Tshabalala | Technician | 118 — `client-person-3` | technician / active | linked |
| 4 — Nhlakanipho Ndwandwe | Technician | 119 — `client-person-4` | technician / active | linked |
| 5 — Shawn Papi | Technician | 120 — `client-person-5` | technician / active | linked |
| 6 — Linda Gerotek | Technician | 121 — `client-person-6` | technician / active | linked |
| 7 — Remote Temperature Logger Ad | Administrator | none | — | not linked |
| 8 — Peter Adigun | Administrator | none | — | not linked |

`users.client_person_id` is nullable and has a partial unique index, so a
client person can link to at most one app user. The current store has exactly
five non-null links, no duplicate link, and no role mismatch. Every other app
user has no client-person link. Names were used only during the one-time legacy
evidence bootstrap; runtime authorization uses the stored integer link and
stable app `user_id`.

## 3. Five Technician account status

| App user ID | `client_person_id` | Username | Role | Email | Status | Password/credential | Can sign in? | Purpose now |
|---:|---:|---|---|---|---|---|---|---|
| 117 | 2 | `client-person-2` | technician | blank | active | none | no | anchors Senzo's 19 open assignments |
| 118 | 3 | `client-person-3` | technician | blank | active | none | no | anchors Reginald's 16 open assignments |
| 119 | 4 | `client-person-4` | technician | blank | active | none | no | anchors Nhlakanipho's 25 open assignments |
| 120 | 5 | `client-person-5` | technician | blank | active | none | no | anchors Shawn's 3 open assignments |
| 121 | 6 | `client-person-6` | technician | blank | active | none | no | anchors Linda's 1 open assignment |

The configured login names at audit time are `admin`, `demo.tech01`, and
`demo.general01`; none of the five usernames is present. The `users` table has
no password column. These rows are therefore not accidentally usable accounts.
They were created solely so imported assignment scope could reference stable
application users. Their `active` label describes the current schema default,
not completed activation; the implementation gate should move them to a
Pending state until setup completes.

## 4. Security gaps

- Passwords are plaintext deployment configuration, shared with the process,
  rather than per-account modern hashes.
- A matching primary demo credential can create an Administrator row on first
  login, including in a production-mode process if demo variables are supplied.
- No password setup/reset, expiry of setup tokens, MFA, rate limiting, lockout,
  or durable login/logout audit exists.
- User Administration can create an identity but cannot create a credential or
  explicitly link `client_person_id`.
- The account lifecycle has only `active` and `inactive`; the five bootstrap
  identities appear active although setup is incomplete.
- Session transport flags are sound, but no idle/absolute timeout or session
  revocation/version is defined.
- Demo example passwords exist in `.env.example`. They are not hard-coded
  fallbacks, but production must reject all demo credential configuration.
- Existing UI/module comments still call persisted User Administration a
  frontend prototype; the code, not those stale comments, is authoritative.

## 5. Options comparison

| Option | Codebase fit | Client dependency | Security / maintenance | Reset and lifecycle | `client_person_id` / roles | Deployment |
|---|---|---|---|---|---|---|
| A. Application-local username/password | High. Keeps the current form, `authenticate()` seam, app user, trusted session, and guards. | None for an initial safe implementation; final SQL Server persistence still needs an ADR-029-approved target. | Application owns hashing, reset tokens, throttling, session policy, and support. Manageable with Werkzeug scrypt and a small explicit lifecycle. | Application supplies setup/reset and Active/Disabled/Pending. | Direct explicit app-user link; app row remains role authority for all three roles. | Lowest immediate complexity; works without enterprise infrastructure. |
| B. Email/password | Medium. Email is currently optional/non-unique and not the login key. | Requires verified unique email for every user; five Technicians have none and SQL Server has no General Users. | Same password burden as A plus email verification/delivery and address lifecycle. | Reset is convenient only after trustworthy email delivery exists. | Same explicit link and app role model. | More moving parts with no current evidence that email is complete or authoritative. |
| C. Microsoft Entra ID / AD / SSO | Good through the existing authentication seam; credential verification changes while app identity/authorization stays. | High: tenant, app registration, OIDC/SAML choice, identifiers/claims, groups, conditional access, and owners must be confirmed by the client. | Preferred enterprise posture when available: the client owns passwords, MFA, recovery, and joiner/mover/leaver policy. The app still owns account/link/role authorization and audit. | Disable either by enterprise identity or app account; define precedence. No app password resets. | Store immutable provider subject/tenant on the app user; never match runtime names. `client_person_id` stays a separate business link. | Highest coordination and configuration complexity; cannot be selected from current evidence alone. |
| D. Other identity provider | No evidence of one in source, configuration, dependencies, or client data. | Unknown. | Cannot assess responsibly. | Unknown. | Must still resolve to an explicit app user. | Do not build without new evidence. |

## 6. Recommended production model

Use **application-local username/password as the safest implementable default
now**, behind the existing credential-verification seam, for Administrator,
Technician, and General User alike. Store a modern per-user hash in the
application-owned account store; do not reuse or update SQL Server
`persons.password_hash`. Keep the app `users` row as the authorization identity
and role source, and keep `client_person_id` as an explicit, unique business
link.

If the client confirms company Microsoft/Active Directory sign-in is available
for this application, **Entra ID/AD SSO is the preferred enterprise option**.
Implement it as a provider adapter resolving an immutable provider subject to
the same app user. It must not replace app roles, assignment scope, or the
person link with group/name guessing. Unknown SSO availability does not block
the local-auth implementation.

ADR-029 still governs persistence: PostgreSQL may hold the transitional
application account capability during implementation, but final production
storage needs a separately approved SQL Server schema/migration proposal.
This audit authorizes neither SQL Server writes nor a schema change.

## 7. Account lifecycle and linking

Minimum states:

- **Pending activation** — identity and optional person link exist, but no
  completed credential setup; login refused.
- **Active** — credential/provider identity is ready; login may proceed.
- **Disabled** — login and existing trusted sessions are refused immediately.

Administrator creation/link flow:

1. Create or select an application user.
2. For a real Technician, select a client person by stable `person_id` from a
   read-only list; never type/match a name at runtime.
3. Validate that the client role and requested app role agree where a client
   role exists. A Technician link requires a client Technician.
4. Set the app role explicitly.
5. Set a unique username (and verified email only if email is used).
6. Initiate credential setup or bind an enterprise provider subject.
7. Activate only after setup succeeds.

Rules:

- Client person with no app account: create Pending, link explicitly, then set
  up authentication. No automatic production account creation.
- App account with no client person: valid for app-only Administrator or
  General User where policy allows. A Technician must be linked before being
  assigned or activated for real RTL work.
- Wrong-role link: refuse save/activation; require an audited role or link
  correction. Do not silently copy either role over the other.
- Deactivated client person: no such source state was verified, so do not
  invent automatic behavior. The app account's Disabled state controls access;
  add synchronization only if a future authoritative client lifecycle source
  is confirmed.
- Duplicate link: refuse. Preserve the existing unique database constraint and
  show which account already owns the link only to an authorized Administrator.
- Disablement never ends or deletes RTL assignments. Assignment history/current
  responsibility remains attached to stable IDs for reassignment or later
  reactivation.

The five current Technician identities should remain linked to persons 2–6 and
retain user IDs 117–121. An Administrator should either (a) set the intended
username/email, initiate setup, and activate after completion, or (b) disable
access if the person should not sign in. No password is invented, displayed,
shared, or assigned by this audit.

## 8. Password and session policy

For local authentication:

- Use Werkzeug's available `generate_password_hash` / `check_password_hash`
  with its modern `scrypt` default; store only the encoded salted hash.
- Minimum password length: 12 characters; allow long passphrases (at least 64
  characters), spaces, and password-manager output. Do not impose composition
  rules that encourage predictable substitutions.
- Never store/log plaintext, display an existing password, email a password,
  or ship a shared/default production credential.
- Setup/reset uses a single-use, random, short-lived token stored hashed, with
  generic responses that do not reveal account existence. Completion revokes
  the token and existing sessions.
- Add rate limiting per account and source, with bounded backoff. Prefer
  throttling over permanent lockout/denial-of-service; make Administrator
  recovery explicit and audited.
- Retain `Secure`, `HttpOnly`, `SameSite=Lax`, and the production secret-key
  startup requirement. Add defined idle and absolute timeouts and rotate the
  session on login and privilege/credential change. The current login already
  clears the old session before setting `uid`.
- Do not add MFA locally in Phase A. If SSO is adopted, use the client's MFA
  and conditional-access policy. Local MFA would be a later explicit need.

## 9. Demo/production separation

- Under `APP_ENV=production`, reject `DEMO_USERNAME`, `DEMO_PASSWORD`, and
  `DEMO_CREDENTIALS`; never call `seed_demo_user()` and never run demo seeds.
- Keep `db.seed_demo_personas`, `db.seed_admin_demo`, and their `.invalid`
  identities available for explicit development/test use only.
- Production bootstrap must be a separate, explicit, one-time operator command
  that creates a Pending Administrator or binds an approved SSO subject. It
  must not create a password or account at application startup.
- Production preflight must fail closed if no enabled Administrator exists,
  with a safe operator instruction and no secret in logs. It must also refuse
  synthetic `.invalid`/`demo.*` accounts as the only Administrator population.
- Current working demo access stays unchanged until the implementation gate;
  none of these recommendations silently removes a developer login.

## 10. Authorization integration

The required boundary remains:

```text
credential or SSO assertion
  -> explicit application user
  -> current app role/status
  -> client_person_id where relevant
  -> ADR-032 current assignment scope
  -> allowed RTL UIDs
```

Authentication proves the app user only. It does not grant a route, capability,
or RTL. `current_identity()` continues to re-read status/role; real RTL routes
must continue through `services/rtl_scope.py` and assignment-aware guards. An
identity provider group, email, display name, or successful password must never
bypass or expand ADR-032 scope. An active Technician with no current
assignments receives an empty scope, not unrestricted access.

## 11. CDB-04 revision

The remaining client question is intentionally business-readable:

> Do users already sign in to other Eskom systems using a company
> Microsoft/Active Directory account that this application should use?

If yes, the project requests the appropriate client identity-team contact and
integration onboarding later. If unknown or no, engineering can safely proceed
with local username/password accounts; the answer does not block Phase A.

## 12. Implementation plan

### Phase A — `AUTHENTICATION-LOCAL-HARDENING-01`

1. Add application-owned credential and Pending/Active/Disabled lifecycle
   storage through Alembic; preserve stable existing user IDs and links.
2. Replace environment-password verification with per-user scrypt hashes while
   retaining the existing `authenticate()` and trusted-session boundary.
3. Add Administrator account creation/linking, explicit activation/disablement,
   username/email editing, setup/reset initiation, and role/link validation.
4. Convert the five linked Technicians to Pending without changing assignments;
   allow an Administrator to complete or disable them without inventing a
   password.
5. Add throttling, setup/reset tokens, session timeout/revocation rules, and
   safe account-recovery behavior.
6. Add audit events: `LOGIN_SUCCEEDED`, safe `LOGIN_FAILED`, `LOGOUT`,
   `USER_CREATED`, `ACCOUNT_ACTIVATED`, `ACCOUNT_DISABLED`, `USER_ROLE_CHANGED`,
   `CLIENT_PERSON_LINK_CHANGED`, `PASSWORD_RESET_INITIATED`, and
   `PASSWORD_RESET_COMPLETED`. Never record passwords, reset tokens, session
   cookies, hashes, or secrets. Anonymous failure storage needs an explicit
   audit-model extension because current audit rows require a recognized actor.
7. Enforce production/demo separation and explicit Administrator bootstrap.
8. Test every role through the same mechanism and prove ADR-032 scope is
   unchanged.

### Phase B — optional enterprise SSO adapter

Only after client confirmation: add Entra ID/AD integration, immutable
tenant/subject mapping, callback/state/nonce validation, and client-approved
logout/session behavior. Keep local auth as an explicitly controlled fallback
only if the client approves it; otherwise disable it after SSO acceptance. No
role or RTL scope comes directly from an unapproved identity-provider claim.

## 13. Next implementation gate

Open **`AUTHENTICATION-LOCAL-HARDENING-01`** against this artifact. Its non-goals
must include SQL Server writes, automatic production account creation, changes
to client `persons`, invented Technician passwords, assignment mutation, and
SSO implementation. If the client confirms enterprise sign-in before Phase A
closes, record the answer and open a separately bounded SSO design gate; do not
expand Phase A into an unreviewed enterprise integration.
