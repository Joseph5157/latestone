"""The one place an action is authorized (ROLE-3).

TWO PRESENTATIONS, ONE DECISION. `may_action` answers the question and
`require_action` enforces the answer — the guard calls the predicate, so a
rendered control and an honoured click can never disagree about policy
(ROLE-4B). Components ask the predicate; they never compare roles themselves.

TWO GUARDS, ONE DIMENSION APART. `require_action` authorizes an action on a
device and may resolve an assignment to do it. `require_capability`
authorizes one where no device is involved — page content, or a mutation
whose target does not exist yet — and never reads anything. They are
separate functions rather than one with an optional device_id because a
placeholder id would make "no device" indistinguishable from "some device",
which is the same conflation ACTION_POLICY's two sets exist to avoid.

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
from services.authorization import (
    AuthorizationError,
    may_perform_action,
    may_perform_capability,
)
from services.device_scope import DeviceScope, scope_for

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
    if may_action(user, action, device_id=device_id):
        return

    logger.warning(
        "Action %r refused on device %r for role %r",
        action,
        device_id,
        user.role if user else None,
    )
    raise AuthorizationError(
        f"Role {user.role!r} may not perform {action!r} on this device"
        if user
        else f"No identity may perform {action!r}"
    )


def may_action(
    user: AuthenticatedUser | None,
    action: str,
    *,
    device_id: str,
    scope: DeviceScope | None = None,
) -> bool:
    """Whether `user` may perform `action` on `device_id`. Never raises.

    THE SAME DECISION `require_action` ENFORCES, asked without raising — it is
    literally the function `require_action` now calls, so the two cannot drift.
    That matters because they answer different audiences: this one decides
    whether to *render* a control, and the guard decides whether to *honour*
    the click. A UI that offered what the guard refuses would be a lie, and one
    that hid what the guard allows would be a bug nobody could see.

    ROLE-4B added it so a component can ask the policy instead of carrying a
    copy of it. Rendering code must not compare roles: `if role == technician`
    in a template is a second permission table that no test of
    `ACTION_POLICY` would ever catch drifting.

    **Visibility is not authority.** A false here hides a control; it does not
    protect anything. `require_action` at the callback boundary is what
    actually refuses, and it still runs whether or not this was ever consulted.
    """
    if user is None:
        return False

    # `is_assigned=False` tests the any-device set alone. Passing here means
    # assignment is irrelevant to this role/action pair, so the read below is
    # never paid for.
    if may_perform_action(user.role, action, is_assigned=False):
        return True

    # A protected read callback may already have resolved the CURRENT trusted
    # scope once for its repository call.  Reusing that object prevents a
    # duplicate assignment lookup while preserving this guard as the sole
    # policy decision.  Callers must never supply browser-derived scope data.
    resolved_scope = scope if scope is not None else scope_for(user)
    is_assigned = resolved_scope.allows(device_id)
    return may_perform_action(user.role, action, is_assigned=is_assigned)


def require_capability(user: AuthenticatedUser | None, capability: str) -> None:
    """Return normally if `user` may exercise `capability`.

    The DEVICE-LESS counterpart to `require_action`, for a permission with no
    device to name — either page content, or a mutation whose target does not
    exist yet. `require_action` cannot express those: it takes a device_id and
    resolves an assignment against it, and inventing a placeholder id to
    satisfy that signature would both lie about the dimension and pay for an
    assignment read whose answer could not matter.

    NO DATABASE READ, EVER. There is no assignment condition to resolve, so
    unlike `require_action` this is pure. It lives here rather than in the
    pure policy module so that every "raise on refusal" guard is in one place
    and a callback imports its enforcement from a single import.

    Refuses with `AuthorizationError`, the same explicit failure
    `require_action` raises and deliberately not a `ValueError`, so a caller
    handling a malformed identifier cannot swallow a refusal.
    """
    if user is None:
        raise AuthorizationError(f"No identity may exercise {capability!r}")

    if may_perform_capability(user.role, capability):
        return

    logger.warning(
        "Capability %r refused for role %r", capability, user.role
    )
    raise AuthorizationError(
        f"Role {user.role!r} may not exercise {capability!r}"
    )
