"""The one server-side client-RTL UID scope (ADR-032).

Answers one question: **which client RTL UIDs may this caller access?** It is
the ONLY place a Technician's assignment set is turned into a UID filter.
Fleet, RTL Detail, Network, Historical Events and the Technician dashboard all
take their scope from `current_rtl_scope()` and apply it with `RtlScope`
helpers; none of them may query assignments or invent its own filter.
`tests/test_rtl_scope_guard.py` fails if one tries.

`None` IS NOT `frozenset()`. ``uids=None`` means unrestricted (Administrator,
General User); an EMPTY set means "nothing" - a Technician with no assignments
correctly sees an empty list. The two are never collapsed.

`permitted` is separate from the set: an unknown role, no session or a
malformed identity is DENIED outright (not merely empty), so a route callback
that re-checks `may_view_real_rtls` refuses it instead of rendering an
empty-looking page.

The scope holds only UIDs assigned NOW (open assignments). It is intersected
with the registered directory by `restrict`, so a UID that is no longer
registered can never surface, and history never grants access.

Identity: keyed on `AuthenticatedUser.user_id`, never on a display name.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from repositories import plant_monitoring_repository as repo
from services.auth_service import AuthenticatedUser, current_identity
from services.authorization import ADMINISTRATOR, GENERAL, TECHNICIAN


@dataclass(frozen=True)
class RtlScope:
    """Which client RTL UIDs a caller may access. ``uids is None`` = all."""

    uids: frozenset[int] | None
    permitted: bool = True

    @property
    def is_unrestricted(self) -> bool:
        return self.permitted and self.uids is None

    def allows(self, device_uid: int) -> bool:
        if not self.permitted:
            return False
        return self.uids is None or device_uid in self.uids

    def restrict(self, registered: Iterable[int]) -> list[int]:
        """The registered UIDs this scope may see, ascending."""
        if not self.permitted:
            return []
        return sorted(u for u in registered if self.uids is None or u in self.uids)

    def filter_rows(self, rows: Iterable, key=lambda row: row.device_uid) -> tuple:
        """Rows whose UID is in scope. The single row-filtering primitive."""
        return tuple(r for r in rows if self.allows(key(r)))


#: No constraint: Administrator and General User (existing behaviour).
UNRESTRICTED = RtlScope(uids=None)
#: Refused outright: no session, unknown role.
DENIED = RtlScope(uids=frozenset(), permitted=False)


def scope_for(user: AuthenticatedUser | None) -> RtlScope:
    """Resolve an identity to its UID scope (one assignment read for a Technician)."""
    if user is None or not isinstance(user.role, str):
        return DENIED
    if user.role in (ADMINISTRATOR, GENERAL):
        return UNRESTRICTED
    if user.role == TECHNICIAN:
        return RtlScope(uids=frozenset(repo.list_current_rtl_assignment_uids(user.user_id)))
    return DENIED


def current_rtl_scope() -> RtlScope:
    """The CURRENT trusted caller's scope (identity re-read from the users row)."""
    return scope_for(current_identity())


def may_view_real_rtls(scope: RtlScope | None) -> bool:
    """Whether the caller may see client RTL facts at all (possibly none)."""
    return scope is not None and scope.permitted


def is_assigned_only(scope: RtlScope | None) -> bool:
    """True for a restricted (Technician) scope - drives labels, never access."""
    return scope is not None and scope.permitted and scope.uids is not None
