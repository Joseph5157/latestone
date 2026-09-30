"""
Application-local authentication and the session identity contract (ADR-033).

Intentionally isolated so a different credential mechanism could be swapped in
without touching UI code — callbacks should only ever call the sign-in service
(`services.login_service`), `authenticate()`/`check_credentials()` below, and
the session helpers.

Two separable jobs live here, in this order:

1. `check_credentials()` proves a credential AND resolves who it belongs to,
   from the application-owned `users` row. Identity is never derived from what
   was typed: the row decides the user_id, the name, the role and whether the
   account may sign in at all. Deriving the role from the typed username would
   make it a client-supplied value.
2. The server-trusted session (`start_trusted_session` / `current_identity`)
   remembers the answer.

**The credential is a per-user password hash.** AUTHENTICATION-LOCAL-HARDENING-01
replaced environment-configured plaintext username/password pairs with a scrypt
hash stored on the account (`users.password_hash`). The old configured pairs
survive ONLY as an explicit development/test fixture (`verify_credentials`),
consulted only for an account that has no hash, only when
`AUTH_DEMO_LOGIN_ENABLED` is set, and never in production.

**AUTH-HARDEN-1 closed the trust boundary this docstring used to describe as
open.** `to_session()`/`from_session()` still exist and the identity still
rides in the browser-side `auth-store` — but protected callbacks no longer
read that payload for authorization. `current_identity()` below is what they
call instead: it re-derives who is signed in from Flask's own signed session
cookie (set at login by `start_trusted_session()`, cleared at logout by
`end_trusted_session()`) and reloads the CURRENT `users` row on every call, so
a browser-edited `role` or `user_id` in `auth-store` no longer has anywhere to
land. `auth-store` remains presentation state — the four callbacks branching
on its `authenticated` flag are unaffected — never a permission.

FAILS CLOSED, always to the same `None`. Bad credentials, a credential naming
no user, a Pending or Disabled account and a role outside the confirmed
vocabulary are indistinguishable to the caller, so the login form cannot leak
which one happened. A partially-built identity is never returned: downstream
code would treat it as real.
"""
from __future__ import annotations

import hmac
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any, Mapping

from flask import session as _flask_session

from config import settings as _settings
from config.settings import auth_settings, demo_auth
from repositories import plant_monitoring_repository as repo
from services import credentials as credentials_mod
from services import prototype_users

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Who is signed in. Frozen: a session identity that callbacks can edit in
    place is not an identity.

    Deliberately carries no credential material, no email address and no
    status — only what a screen or a later authorization phase needs to name
    the user and reason about what they may do. `status` is absent because an
    `AuthenticatedUser` only ever exists for an active account.
    """

    user_id: int
    username: str
    full_name: str
    role: str


#: The session keys `to_session` writes and `from_session` requires.
#: `authenticated` is first because four existing callbacks (`routing`,
#: `navigation`, `equipment_selector` x2) branch on it and nothing else;
#: widening the store must not move it.
_IDENTITY_FIELDS = ("user_id", "username", "full_name", "role")


#: Compared against when a login names no configured demo credential, so an
#: unknown name costs the same as a wrong password. Carries no security weight:
#: the result is discarded and the branch returns False regardless.
_ABSENT = "absent-credential-sentinel"


def _demo_login_permitted() -> bool:
    """Whether the development demo-credential fixture may be consulted at all.

    ADR-033. False in production regardless of any configuration (the settings
    layer already refuses to start a production process that carries demo
    variables; this is the second, independent gate), and false unless demo
    credentials are explicitly enabled and configured.
    """
    if _settings.IS_PRODUCTION:
        return False
    return bool(demo_auth.credentials)


def verify_credentials(username: str, password: str) -> bool:
    """Check the typed pair against the DEVELOPMENT demo credentials only.

    This is the only place a password is compared directly, and it is
    unreachable in production (`_demo_login_permitted`). It is used solely for
    an account that has NO password hash of its own: once a user has a hash,
    the hash is the only accepted credential (`check_credentials`).

    Fails closed: unset, malformed or not-explicitly-enabled configuration
    refuses every login.
    """
    if not username or not password:
        return False
    if not _demo_login_permitted():
        if not _settings.IS_PRODUCTION:
            error = demo_auth.config_error
            if error:
                logger.error("Demo login refused: credential configuration rejected. %s", error)
            else:
                logger.error(
                    "Demo login refused: demo credentials are not configured "
                    "or not enabled (AUTH_DEMO_LOGIN_ENABLED)."
                )
        return False

    configured = {
        name.strip().lower(): secret for name, secret in demo_auth.credentials.items()
    }
    expected = configured.get(username.strip().lower())
    if expected is None:
        hmac.compare_digest(password, _ABSENT)
        return False
    return hmac.compare_digest(password, expected)


@dataclass(frozen=True)
class CredentialCheck:
    """The verdict on one typed credential pair.

    ``reason`` exists for the audit log only and is never shown to the user:
    the sign-in form answers every failure with the same message.
    """

    user: AuthenticatedUser | None
    reason: str  # ok | invalid | unknown | pending | disabled | role
    user_id: int | None = None


def check_credentials(username: str, password: str) -> CredentialCheck:
    """Who a credential pair belongs to, and why not if it does not.

    ADR-033. The application-owned `users` row decides everything: its status
    gates login, its per-user scrypt hash is the credential, its role is the
    role. Every refusal — unknown name, wrong password, Pending, Disabled, a
    role outside the confirmed vocabulary — spends the same verification work
    and returns the same `user=None`, so timing and the return value do not say
    which one happened.

    Side-effect free apart from database READS. Throttling and audit live in
    `services.login_service`, around this function.
    """
    name = credentials_mod.normalize_username(username)
    if not name or not password:
        credentials_mod.burn_verification_time(password or "")
        return CredentialCheck(None, "invalid")

    row = repo.get_user_by_username(name)

    if row is None and verify_credentials(name, password):
        # Development fixture only (`verify_credentials` is False in
        # production): provisions the configured primary demo login on first
        # use. Never runs in production, never for a wrong password.
        prototype_users.seed_demo_user()
        row = repo.get_user_by_username(name)

    if row is None:
        credentials_mod.burn_verification_time(password)
        return CredentialCheck(None, "unknown")

    if row.role not in prototype_users.CONFIRMED_ROLES:
        logger.error(
            "Login refused: user_id=%s holds role %r, outside the confirmed "
            "vocabulary %r.", row.user_id, row.role, prototype_users.CONFIRMED_ROLES,
        )
        credentials_mod.burn_verification_time(password)
        return CredentialCheck(None, "role", row.user_id)

    if row.status != "active":
        credentials_mod.burn_verification_time(password)
        reason = "pending" if row.status == "pending_activation" else "disabled"
        return CredentialCheck(None, reason, row.user_id)

    if row.has_password:
        stored = repo.get_password_hash(row.user_id)
        verified = bool(stored) and credentials_mod.verify_password(stored, password)
    elif _demo_login_permitted():
        verified = verify_credentials(name, password)
    else:
        credentials_mod.burn_verification_time(password)
        verified = False

    if not verified:
        return CredentialCheck(None, "invalid", row.user_id)

    return CredentialCheck(
        AuthenticatedUser(
            user_id=row.user_id,
            username=row.username,
            full_name=row.full_name,
            role=row.role,
        ),
        "ok",
        row.user_id,
    )


def authenticate(username: str, password: str) -> AuthenticatedUser | None:
    """The signed-in identity behind a credential pair, or None.

    The bare verdict, with no throttling and no audit — see
    `services.login_service.attempt_login` for the full sign-in path the login
    form uses. Every failure is the same `None`.
    """
    return check_credentials(username, password).user


def to_session(user: AuthenticatedUser) -> dict:
    """The `auth-store` payload for a signed-in user.

    Keeps `authenticated` exactly where it was, so the four callbacks already
    reading that key keep working unchanged, and adds the identity beside it.
    Nothing else goes in: this dict is sent to the browser, and it holds an
    identity, never a credential.
    """
    return {
        "authenticated": True,
        "user_id": user.user_id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
    }


def from_session(data: Any) -> AuthenticatedUser | None:
    """Read an `auth-store` payload back as an identity, or None.

    Validates STRUCTURE ONLY, and deliberately does not query anything. Every
    UI callback that reads the store would otherwise become an identity
    database lookup. Revalidating a persisted role or status against the
    `users` table is a real requirement, but it belongs to the authorization
    phase as a deliberate decision — not as a side effect of reading a
    session.

    Rejects the pre-ROLE-1 payload `{"authenticated": True}`: a valid flag and
    an invalid identity. This function is the one place that says so, which is
    also the seam a later phase closes when `authenticated` alone stops being
    enough for the routing callbacks.

    Unknown keys are tolerated so a session written by a later phase is not
    invalidated by this one.
    """
    if not isinstance(data, Mapping):
        return None
    if data.get("authenticated") is not True:
        return None
    if any(field not in data for field in _IDENTITY_FIELDS):
        return None

    user_id = data["user_id"]
    # `bool` is an `int` in Python: without this an identity carrying True
    # would silently address user 1.
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        return None

    username = data["username"]
    full_name = data["full_name"]
    role = data["role"]
    if not isinstance(username, str) or not username:
        return None
    if not isinstance(full_name, str):
        return None
    if role not in prototype_users.CONFIRMED_ROLES:
        return None

    return AuthenticatedUser(
        user_id=user_id, username=username, full_name=full_name, role=role
    )


# ---------------------------------------------------------------------------
# AUTH-HARDEN-1 — the server-trusted session
#
# Everything above this line answers "what does the browser's auth-store
# claim". Everything below answers "who does the SERVER believe is signed in,
# right now, according to the CURRENT database row" — the only question a
# protected operation may act on.
# ---------------------------------------------------------------------------

#: The identity Flask's signed session carries: a user_id. Never a role,
#: never a name — those are re-read from `users` on every call so a role
#: change or a deactivation takes effect on the NEXT request rather than
#: requiring logout/login. A browser can read this cookie but cannot alter it
#: without invalidating Flask's signature (server.secret_key), which is what
#: makes it trustworthy where `auth-store`'s plain JSON is not.
_SESSION_USER_ID_KEY = "uid"

#: ADR-033. The user's `session_version` at login. A password change/reset, a
#: disable, or any role/link/rename change bumps the stored version, so every
#: cookie minted before it stops matching and is refused — the revocation
#: mechanism for a signed-cookie session.
_SESSION_VERSION_KEY = "sv"

#: Epoch seconds of login: the base of the absolute session lifetime.
_SESSION_ISSUED_KEY = "iat"

#: A fresh random value per login. It authorises nothing; it makes each
#: login's cookie a distinct, newly signed payload (session rotation).
_SESSION_NONCE_KEY = "sid"


def start_trusted_session(user_id: int, session_version: int | None = None) -> None:
    """Record `user_id` as the server-trusted signed-in identity.

    Called exactly once, from `callbacks.auth.handle_login`, after the sign-in
    service has already resolved a real `users` row in the SAME callback
    invocation — nothing browser-supplied has been read yet at that point, so
    binding to it here is safe. `clear()` first: a login on a tab that already
    held a different trusted session must not merge the two, and the new cookie
    carries a new nonce and issue time (session rotation).

    `session_version` defaults to the row's CURRENT version, read here.
    """
    if session_version is None:
        row = repo.get_user_by_id(user_id)
        session_version = row.session_version if row is not None else 1
    _flask_session.clear()
    _flask_session[_SESSION_USER_ID_KEY] = user_id
    _flask_session[_SESSION_VERSION_KEY] = session_version
    _flask_session[_SESSION_ISSUED_KEY] = int(time.time())
    _flask_session[_SESSION_NONCE_KEY] = secrets.token_hex(8)
    # Permanent = Flask applies PERMANENT_SESSION_LIFETIME (the sliding idle
    # window configured in app.py) instead of a browser-session cookie.
    _flask_session.permanent = True


def end_trusted_session() -> None:
    """Clear the server-trusted session. Called on logout.

    Idempotent — clearing an already-empty session is a no-op, so callers
    never need to check whether one existed first.
    """
    _flask_session.clear()


def _session_expired() -> bool:
    """True when the absolute lifetime has passed, or the cookie carries no
    issue time (a pre-ADR-033 cookie is refused rather than trusted forever)."""
    issued = _flask_session.get(_SESSION_ISSUED_KEY)
    if not isinstance(issued, int) or isinstance(issued, bool):
        return True
    return (time.time() - issued) > auth_settings.session_absolute_hours * 3600


def current_identity() -> AuthenticatedUser | None:
    """Who is CURRENTLY signed in, reloaded from the database every call.

    This is the one function every protected operation must call instead of
    `from_session(auth_data)`. It never trusts the browser: the only input is
    Flask's signed session cookie, and even that supplies nothing but a
    user_id and the session's security metadata — role, status and name are
    read fresh from `users` here, so a demotion or deactivation the operator
    performs while the affected user's tab stays open takes effect on that
    user's NEXT protected call, not on their next login.

    Fails closed exactly like `from_session`: no session, an expired session, a
    session whose security version no longer matches the account's (password
    change/reset, disable, role/link change), no such user, a non-Active
    account, or a role outside the confirmed vocabulary all return None rather
    than a partial identity.
    """
    user_id = _flask_session.get(_SESSION_USER_ID_KEY)
    if user_id is None:
        return None
    if _session_expired():
        return None

    row = repo.get_user_by_id(user_id)
    if row is None:
        return None
    if row.status != "active":
        return None
    if _flask_session.get(_SESSION_VERSION_KEY) != row.session_version:
        return None
    if row.role not in prototype_users.CONFIRMED_ROLES:
        return None

    return AuthenticatedUser(
        user_id=row.user_id,
        username=row.username,
        full_name=row.full_name,
        role=row.role,
    )


def current_role() -> str | None:
    """`current_identity().role`, or None. A thin convenience — the identity
    itself remains the thing every guard actually takes."""
    user = current_identity()
    return user.role if user else None
