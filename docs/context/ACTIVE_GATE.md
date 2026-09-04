# Active Gate

Status: **CLOSED**
Date: 2026-09-04
Gate: AUTH-PROD-HARDEN-1 — production session/cookie hardening
Branch: `main`, baseline `4c91b190589d754cd11419951873de6231a6f79c`
Commit: `667e3fc`
Commit/push permission: **GRANTED.** Tranche verified, tests green, context
pack clean. Committed as part of this gate closure.

## Purpose

Close the non-blocking follow-up AUTH-HARDEN-1 explicitly left open:
"Production cookie/deployment hardening (`SESSION_COOKIE_SECURE`, explicit
`SameSite`, HTTPS enforcement, a production `FLASK_SECRET_KEY` that fails
closed rather than falling back to a per-process random key)" — recorded in
`docs/CODE_AUDIT.md`'s AUTH-HARDEN-1 entry and this file's own prior
"Non-blocking follow-ups" list.

## What changed

**`APP_ENV` is the one environment/deployment-mode concept this app now
has** (`config/settings.py::resolve_app_environment`). No such setting
existed before this gate — nothing was reused because nothing was there to
reuse. Blank/unset resolves to `development`, so an existing local `.env`
that has never heard of `APP_ENV` behaves exactly as before. `production` is
the only other recognised value; anything else raises immediately.

**`FLASK_SECRET_KEY` now fails closed in production**
(`config/settings.py::resolve_flask_secret_key`). Non-production behaviour is
unchanged from AUTH-HARDEN-1: a configured key if set, else a fresh random
key generated once per process start. With `APP_ENV=production`, a missing
or blank key raises `RuntimeError` at import/startup time — `gunicorn
app:server` will not start — naming exactly what is missing, rather than
silently signing sessions with a key that changes on every
restart/redeploy or differs across replicas.

**The session cookie carries an explicit transport policy**
(`config.settings.FlaskSessionSettings.cookie_secure/cookie_httponly/
cookie_samesite`, wired into `server.config` in `app.py`):
- `Secure` — `True` only when `APP_ENV=production`. `False` outside
  production so the cookie still reaches the browser over plain local HTTP;
  a `Secure` cookie set from an `http://` origin is silently dropped by the
  browser, which looks exactly like a broken login.
- `HttpOnly` — `True` unconditionally, in every environment.
- `SameSite` — `"Lax"` unconditionally. This is a single-origin Dash app
  with no cross-site POST target the session cookie needs to accompany.

**HTTPS enforcement is documented as the deployment platform's
responsibility, not implemented in-app.** This process is reached only
through Railway's own HTTPS edge (`railway.json` runs `gunicorn app:server`
bound to a Railway-assigned port on its private network; there is no public
listener this app owns to terminate TLS on or redirect from). Nothing in the
codebase reads an `X-Forwarded-*` header to make a security decision, so
there was no proxy chain to interpret and no bounded hop count to trust one
against — adding `ProxyFix`-style header trust without that would let a
client spoof its own scheme. `app.py` documents this inline beside the
cookie-config wiring, and `tests/test_prod_session_hardening.py::
TestHttpsProxyBoundaryIsThePlatforms` pins the absence of any such trust
rather than inventing middleware to enforce it here.

## Why no ADR

This closes a follow-up already tracked as a running, append-only entry in
`docs/CODE_AUDIT.md` (the same reasoning AUTH-HARDEN-1 itself gave for not
adding a fourth parallel record) and does not introduce a new architectural
concept beyond `APP_ENV`, which is documented at its own definition in
`config/settings.py`.

## In scope

- `APP_ENV` environment/deployment-mode setting.
- `FLASK_SECRET_KEY` fail-closed requirement in production.
- Explicit `SESSION_COOKIE_SECURE` / `SESSION_COOKIE_HTTPONLY` /
  `SESSION_COOKIE_SAMESITE` policy.
- Documenting (and testing the absence of an alternative to) the HTTPS/proxy
  boundary.
- `tests/test_prod_session_hardening.py` (new).
- `.env.example` documentation for `APP_ENV`.
- This closure's own documentation (`docs/CODE_AUDIT.md`, this file,
  `docs/context/PROJECT_LEDGER.md`).

## Explicitly out of scope — and not touched

- Microsoft Entra ID / any real SSO, or any other production authentication
  source (C-06). `DEMO_CREDENTIALS` remains the authentication mechanism.
  **Production authentication is not COMPLETE** — only the session/cookie
  transport around it is hardened.
- Any Railway service configuration (setting `APP_ENV=production` /
  `FLASK_SECRET_KEY` on the actual deployed service). This gate changes only
  what the application *does* with those variables; setting them on the real
  Railway service is a separate, external action for whoever deploys next —
  see Follow-ups below.
- `ProxyFix` or any other forwarded-header trust middleware — deliberately
  not added; see "What changed" above.
- AUTH-HARDEN-1's identity/authorization behaviour — untouched, all of its
  tests still pass unmodified.
- `debug.log` — untracked, untouched throughout.

## Non-blocking follow-ups (not implemented here)

1. Whether the real Railway `dashboard` service already has `APP_ENV` and
   `FLASK_SECRET_KEY` set was not checked as part of this gate (no Railway
   service configuration was read or changed here). This gate's fail-closed
   check only engages once `APP_ENV=production` is actually set there — until
   then, production keeps running under the pre-existing (safe but
   restart-fragile) fallback behaviour. Confirm and set both before relying
   on this hardening in the deployed environment.
2. `callbacks/listings.py::hierarchy_code_index()` broader-than-necessary
   read (carried over from AUTH-HARDEN-1, still unaddressed).
3. `services/device_scope.py::scope_from_session()` remains a legacy
   compatibility helper with no protected production caller (carried over).

## Verification

- Focused: `tests/test_prod_session_hardening.py` — 21 passed.
- AUTH-HARDEN regression: `test_auth_harden.py`, `test_auth_harden_repair.py`,
  `test_auth_hardening.py`, `test_auth_identity.py`, `test_authorization.py`
  — 227 passed, none weakened.
- Non-DB suite: `python -m pytest -m "not db"` — 2690 passed, 510 deselected
  (2669 pre-gate baseline + 21 new).
- DB suite: `python -m pytest -m "db"` — 510 passed (local PostgreSQL was
  available).
- Full suite: `python -m pytest` — 3200 passed.
- `python scripts/build_context_pack.py --check` — CLEAN (open run).
- `git diff --check` — clean, no whitespace errors.

## Next queued gate

None queued. The operator decides what comes next — likely candidates:
setting `APP_ENV=production`/`FLASK_SECRET_KEY` on the real Railway service,
or resuming `CLIENT-CLARIFICATION-PACK-1`'s blocked-work queue.
