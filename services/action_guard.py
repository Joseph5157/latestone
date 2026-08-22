"""The one place a device action is authorized (ROLE-3).

WHERE ENFORCEMENT ACTUALLY IS. This guard runs at the CALLBACK boundary. It is
not domain-service enforcement and this module does not pretend to be: the
mutation services remain callable without an authorization context, and three
of the four gated actions (Program RTL, message forwarding, deactivate) have
no domain service at all — the manage drawer is prototype-only and changes no
state, so there is currently nothing below the callback to enforce in.

Enforcement moves down when the mutation services take an authenticated actor.
That is the same change `assigned_by` needs, and ROLE-1 deferred it
deliberately; doing it here would scatter it.

WHY THIS IS NOT IN authorization.py. That module is pure — no database, no
Dash — and the assignment condition needs a read. Composing the two here keeps
the policy tables testable without a runtime.

CALLBACKS DO NOT CONTAIN THE RULE. A callback gathers the authenticated
identity and the target device and calls this. It never compares a role and
never decides assignment ownership itself.

CURRENT ASSIGNMENTS ONLY. The assignment condition comes from `scope_for`,
which reads the ACTIVE assignment row. A technician who held a device
yesterday and was reassigned away today has a history row and no active one,
and is refused. History records what was true; it never grants.
"""
from __future__ import annotations

import logging

from services.auth_service import AuthenticatedUser
from services.authorization import AuthorizationError, may_perform_action
from services.device_scope import scope_for

logger = logging.getLogger(__name__)


def require_action(
    user: AuthenticatedUser | None, action: str, *, device_id: str
) -> None:
    """Return normally if `user` may perform `action` on `device_id`.

    Raises `AuthorizationError` otherwise — explicitly, never as a silent
    no-op, per the ROLE-1 decision that an authenticated user reaching for
    something they are not entitled to must fail visibly at the application
    layer. That exception is deliberately not a `ValueError`, so a caller
    handling a malformed identifier cannot swallow a refusal.

    THE ASSIGNMENT READ IS CONDITIONAL. The role is tested against the
    any-device set first, so an action the role may perform universally
    resolves without touching the database. Only an action that could still
    be permitted by assignment pays for the lookup, and the answer is
    identical either way: `role in any_device or (is_assigned and role in
    assigned_only)`.
    """
    if user is None:
        raise AuthorizationError(f"No identity may perform {action!r}")

    # `is_assigned=False` tests the any-device set alone. Passing here means
    # assignment is irrelevant to this role/action pair.
    if may_perform_action(user.role, action, is_assigned=False):
        return

    is_assigned = scope_for(user).allows(device_id)
    if may_perform_action(user.role, action, is_assigned=is_assigned):
        return

    logger.warning(
        "Action %r refused on device %r for role %r (assigned=%s)",
        action,
        device_id,
        user.role,
        is_assigned,
    )
    raise AuthorizationError(
        f"Role {user.role!r} may not perform {action!r} on this device"
    )
