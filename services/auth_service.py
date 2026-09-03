"""
Placeholder authentication and the session identity contract.

Intentionally isolated so it can be swapped for the client's real
authentication (API/session/SSO) without touching UI code — callbacks should
only ever call `authenticate()` and the session helpers below.

Two separable jobs live here, in this order:

1. `verify_credentials()` proves a credential. That is all it has ever done and
   all it does now — ROLE-4A widened the configuration from one pair to a map
   of them, which changes how many people can sign in and nothing about what
   any of them may do.
2. `authenticate()` answers who that credential **is**, by loading the
   persistent `users` row (DB-2). Identity is never derived from what was
   typed: the credential proves *a* login, the row decides the user_id, the
   name and the role. Deriving the role from the typed username would make it a
   client-supplied value.

**Credential configuration names logins, never roles** (ROLE-4A). There is no
field in it that could say "administrator", so adding a credential can never
grant a permission — it can only let an existing `users` row be reached. A
Technician credential yields a Technician session because the row says so.

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
no user, a deactivated account and a role outside the confirmed vocabulary are
indistinguishable to the caller, so the login form cannot leak which one
happened. A partially-built identity is never returned: downstream code would
treat it as real.
"""
from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass
from typing import Any, Mapping

from flask import session as _flask_session

from config.settings import demo_auth
from repositories import plant_monitoring_repository as repo
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


#: Compared against when no credential is configured for the typed username, so
#: an unknown name and a wrong password cost the same work rather than the
#: unknown name answering first — that difference is a username oracle. Its
#: value carries no security weight: the result is discarded and the branch
#: returns False regardless of what the comparison says.
_ABSENT = "absent-credential-sentinel"


def verify_credentials(username: str, password: str) -> bool:
    """Check the typed pair against the configured credentials. Fails closed.

    ROLE-4A: the configuration is a map, so Technician and General personas
    reach this same path instead of Administrator being the only login. What it
    still is NOT is an identity: this function answers "is this a valid
    credential", never "who is this" and never "what may they do".
    `authenticate()` below loads both from the `users` row.

    There is no fallback credential. Unset means unset, and so does malformed —
    an ambiguous credential configuration refuses every login rather than
    letting some through (`parse_demo_credentials`).
    """
    if not username or not password:
        return False

    credentials = demo_auth.credentials
    if not credentials:
        error = demo_auth.config_error
        if error:
            logger.error("Login refused: credential configuration rejected. %s", error)
        else:
            logger.error(
                "Login refused: DEMO_USERNAME/DEMO_PASSWORD are not configured. "
                "Set them in .env (see .env.example)."
            )
        return False

    # compare_digest so the check leaks neither length nor a matching prefix
    # through timing, and the `_ABSENT` branch so an unknown username does not
    # answer faster than a wrong password — that difference is a username
    # oracle. The habit matters more once this is swapped for something real.
    expected = credentials.get(username)
    if expected is None:
        hmac.compare_digest(password, _ABSENT)
        return False
    return hmac.compare_digest(password, expected)


def authenticate(username: str, password: str) -> AuthenticatedUser | None:
    """The signed-in identity behind a credential pair, or None.

    The credential is checked FIRST and the user store is not touched unless it
    passes: looking up a user on a failed password would let a wrong guess
    probe which usernames exist.

    `seed_demo_user()` runs before the lookup for the same reason
    `prototype_users.get_user()` calls it — a freshly provisioned database has
    no rows yet, and the configured demo credential must resolve to a real
    user on first login rather than on second.

    Reads `repo.UserRecord` directly rather than going through
    `prototype_users.get_user()`: that function's dict contract is lossy (no
    `user_id`, no `full_name`), and an identity assembled from a lossy view is
    exactly the kind of half-built object this module refuses to produce.
    """
    if not verify_credentials(username, password):
        return None

    prototype_users.seed_demo_user()
    row = repo.get_user_by_username(username)

    if row is None:
        logger.error(
            "Login refused: credentials verified but no user row exists for %r. "
            "The configured demo credential does not name a user in this "
            "database.",
            username,
        )
        return None

    if row.status != "active":
        logger.warning("Login refused: user %r is %s.", username, row.status)
        return None

    if row.role not in prototype_users.CONFIRMED_ROLES:
        logger.error(
            "Login refused: user %r holds role %r, which is outside the "
            "confirmed vocabulary %r and cannot be reasoned about.",
            username, row.role, prototype_users.CONFIRMED_ROLES,
        )
        return None

    return AuthenticatedUser(
        user_id=row.user_id,
        username=row.username,
        full_name=row.full_name,
        role=row.role,
    )


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

#: The one thing Flask's signed session carries: a user_id. Never a role,
#: never a name — those are re-read from `users` on every call so a role
#: change or a deactivation takes effect on the NEXT request rather than
#: requiring logout/login. A browser can read this cookie but cannot alter it
#: without invalidating Flask's signature (server.secret_key), which is what
#: makes it trustworthy where `auth-store`'s plain JSON is not.
_SESSION_USER_ID_KEY = "uid"


def start_trusted_session(user_id: int) -> None:
    """Record `user_id` as the server-trusted signed-in identity.

    Called exactly once, from `callbacks.auth.handle_login`, after
    `authenticate()` has already resolved a real `users` row in the SAME
    callback invocation — nothing browser-supplied has been read yet at that
    point, so binding to it here is safe. `clear()` first: a login on a tab
    that already held a different trusted session must not merge the two.
    """
    _flask_session.clear()
    _flask_session[_SESSION_USER_ID_KEY] = user_id


def end_trusted_session() -> None:
    """Clear the server-trusted session. Called on logout.

    Idempotent — clearing an already-empty session is a no-op, so callers
    never need to check whether one existed first.
    """
    _flask_session.clear()


def current_identity() -> AuthenticatedUser | None:
    """Who is CURRENTLY signed in, reloaded from the database every call.

    This is the one function every protected operation must call instead of
    `from_session(auth_data)`. It never trusts the browser: the only input is
    Flask's signed session cookie, and even that supplies nothing but a
    user_id — role, status and name are read fresh from `users` here, so a
    demotion or deactivation the operator performs while the affected user's
    tab stays open takes effect on that user's NEXT protected call, not on
    their next login.

    Fails closed exactly like `from_session`: no session, no such user, an
    inactive account, or a role outside the confirmed vocabulary all return
    None rather than a partial identity.
    """
    user_id = _flask_session.get(_SESSION_USER_ID_KEY)
    if user_id is None:
        return None

    row = repo.get_user_by_id(user_id)
    if row is None:
        return None
    if row.status != "active":
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
