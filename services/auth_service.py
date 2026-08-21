"""
Placeholder authentication and the session identity contract.

Intentionally isolated so it can be swapped for the client's real
authentication (API/session/SSO) without touching UI code — callbacks should
only ever call `authenticate()` and the session helpers below.

Two separable jobs live here, in this order:

1. `verify_credentials()` proves a credential *pair*. That is all it has ever
   done and all it does now.
2. `authenticate()` answers who that pair **is**, by loading the persistent
   `users` row (DB-2). Identity is never derived from what was typed: the
   credential proves *a* login, the row decides the user_id, the name and the
   role. Deriving the role from the typed username would make it a
   client-supplied value.

**This is not an authorization boundary.** The result is held in a
browser-side `dcc.Store`, and the data callbacks do not independently verify a
session, so anyone able to set that store can reach the data callbacks.
ROLE-1 makes identity *consistent and contracted*; it does not make it
*unforgeable*. Route and navigation enforcement built on this session is an
application-level affordance until a server-verifiable session mechanism
exists. Replacing this module is necessary but not sufficient — see
docs/CODE_AUDIT.md, "Security posture".

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


def verify_credentials(username: str, password: str) -> bool:
    """Check the configured credential pair. Fails closed when unconfigured.

    There is no fallback credential: if `DEMO_USERNAME`/`DEMO_PASSWORD` are not
    set, every login is refused rather than silently accepting a well-known
    default that is published in `.env.example`.
    """
    if not username or not password:
        return False

    if not demo_auth.is_configured:
        logger.error(
            "Login refused: DEMO_USERNAME/DEMO_PASSWORD are not configured. "
            "Set them in .env (see .env.example)."
        )
        return False

    # Compared with compare_digest so the check does not leak length or a
    # matching prefix through timing. Cheap here, and the habit matters more
    # once this is swapped for something real.
    return hmac.compare_digest(username, demo_auth.username) and hmac.compare_digest(
        password, demo_auth.password
    )


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
