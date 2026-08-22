"""Device visibility scope (ROLE-3).

THE ONLY ANSWER to "may this user see this RTL?". No second predicate exists,
and none is permitted to appear: two tables answering one question each pass
their own tests while contradicting each other. `prototype_access.can_view_device`
was exactly that and was deleted rather than rewritten.

PURITY, STATED ACCURATELY. `DeviceScope` and its predicates are pure and
side-effect free. `scope_for` is NOT — it performs one assignment read per
call. Resolve it once per render and pass the result down; do not call it in
a loop.

`None` IS NOT `frozenset()`. Unrestricted means "no constraint"; EMPTY means
"nothing". A technician with zero assignments resolves to EMPTY and correctly
sees an empty fleet — a bug that produced None there would hand them all 120
devices. Nothing in this module is allowed to collapse the two.

IDENTITY. Scope is keyed on `AuthenticatedUser.user_id`, the persistent
identity key ROLE-1 exists to provide. `username` is login and display
identity and is never the basis of an authorization decision.

ROLE SEMANTICS LIVE HERE. No repository and no callback compares a role string
in the scope path. The repository receives a neutral id-set and never learns
what a technician is.
"""
from __future__ import annotations

from dataclasses import dataclass

from repositories import plant_monitoring_repository as repo
from services.auth_service import AuthenticatedUser, from_session
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN


@dataclass(frozen=True)
class DeviceScope:
    """Which devices a user may see. `None` means unrestricted."""

    device_ids: frozenset[str] | None

    @property
    def is_unrestricted(self) -> bool:
        return self.device_ids is None

    def allows(self, device_id: str) -> bool:
        if self.device_ids is None:
            return True
        return device_id in self.device_ids


#: No constraint. Administrator and General.
UNRESTRICTED = DeviceScope(device_ids=None)

#: A real constraint that matches nothing. Unknown role, no session, or a
#: technician with no active assignments.
EMPTY = DeviceScope(device_ids=frozenset())

#: Roles that see the whole fleet. General is here deliberately: read-only is
#: a constraint on actions, not on sight (ROLE-3 invariant 3).
_UNRESTRICTED_ROLES = frozenset({ADMINISTRATOR, GENERAL})


def scope_for(user: AuthenticatedUser | None) -> DeviceScope:
    """Resolve an authenticated identity to its device scope.

    Performs an assignment read for technicians. Default-deny: an absent user
    or an unrecognised role reaches nothing.
    """
    if user is None or not isinstance(user.role, str):
        return EMPTY
    if user.role in _UNRESTRICTED_ROLES:
        return UNRESTRICTED
    if user.role == TECHNICIAN:
        return DeviceScope(
            device_ids=frozenset(repo.list_active_device_ids_for_user(user.user_id))
        )
    return EMPTY


def scope_from_session(auth_data) -> DeviceScope:
    """Resolve an `auth-store` payload to a scope.

    Goes through `auth_service.from_session` — the same validation the router
    uses — rather than reading the store's raw `role` key. A tampered or
    pre-ROLE-1 payload therefore reaches nothing here for the same reason it
    reaches no policied route.
    """
    return scope_for(from_session(auth_data))
