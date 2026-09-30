"""Client-RTL Technician assignment workflow (TECHNICIAN-REAL-RTL-ACCESS-01, ADR-032).

Application-owned. The client SQL Server is only READ here (the registered
directory and current network context); the assignment itself lives in
PostgreSQL and no client table is ever written.

Rules:

* one OPEN assignment per client RTL UID, many per Technician - enforced by a
  partial unique index, and by a row lock inside one transaction here;
* only an Administrator assigns or reassigns. The service enforces it with the
  authenticated actor (not only the callback), so a future caller cannot skip it;
* the RTL must be currently registered, the target must be an ACTIVE Technician;
* reassignment is atomic: end the old row, open the new one, audit both - one
  commit. The old row is never edited except for its end columns;
* stale UI: a reassignment carries the assignment_id the Administrator saw; if
  the RTL has changed since, nothing is written;
* audit rows are written in the SAME transaction (audit_service), so a failed
  audit rolls the assignment back.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sqlalchemy.exc import IntegrityError

from config import audit as audit_cfg
from config.settings import RTLDatabaseConfigurationError
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import (
    PROVENANCE_APPLICATION,
    PROVENANCE_LEGACY_IMPORT,
    RtlAssignmentRecord,
)
from repositories.rtl_temperature_repository import (
    RTLTemperatureRepository,
    RTLTemperatureRepositoryError,
)
from services import audit_service
from services import rtl_network_service as network
from services.auth_service import AuthenticatedUser
from services.authorization import MANAGE_RTL_ASSIGNMENTS, may_perform_capability

logger = logging.getLogger(__name__)


class AssignmentError(Exception):
    """A refused assignment change. `message` is safe to show to the operator."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotAuthorized(AssignmentError):
    pass


class RtlNotRegistered(AssignmentError):
    pass


class NotATechnician(AssignmentError):
    pass


class AlreadyAssigned(AssignmentError):
    pass


class StaleAssignment(AssignmentError):
    pass


class SameTechnician(AssignmentError):
    pass


class SourceUnavailable(AssignmentError):
    pass


def _require_admin(actor: AuthenticatedUser | None) -> int:
    if actor is None or not may_perform_capability(actor.role, MANAGE_RTL_ASSIGNMENTS):
        raise NotAuthorized("Only an Administrator can change RTL assignments.")
    return actor.user_id


def _registered_uids() -> set[int]:
    try:
        return set(RTLTemperatureRepository().get_registered_device_uids())
    except (RTLTemperatureRepositoryError, RTLDatabaseConfigurationError) as exc:
        logger.warning("Assignment registration check unavailable (%s)", type(exc).__name__)
        raise SourceUnavailable("The client RTL data source is unavailable.") from exc


def _snapshot(record: RtlAssignmentRecord) -> dict:
    """Audit allowlist: identities and provenance only, never contact data."""
    return {
        "assignment_id": record.assignment_id,
        "device_uid": record.device_uid,
        "technician_user_id": record.technician_user_id,
        "technician_username": record.technician_username,
        "provenance": record.provenance,
    }


def _check_target(device_uid, technician_user_id, session, registered_fetch) -> None:
    if isinstance(device_uid, bool) or not isinstance(device_uid, int) or device_uid <= 0:
        raise RtlNotRegistered("That RTL UID is not a registered RTL.")
    if device_uid not in registered_fetch():
        raise RtlNotRegistered("That RTL is not currently registered.")
    if repo.get_active_technician_user_id(technician_user_id, session=session) is None:
        raise NotATechnician("The selected person is not an active Technician.")


def assign(
    device_uid: int,
    technician_user_id: int,
    *,
    actor: AuthenticatedUser | None,
    registered_fetch: Callable[[], set[int]] = _registered_uids,
) -> int:
    """Assign an UNASSIGNED RTL to a Technician. Returns the new assignment_id."""
    actor_id = _require_admin(actor)
    try:
        with session_scope() as session:
            _check_target(device_uid, technician_user_id, session, registered_fetch)
            if repo.get_current_rtl_assignment(device_uid, session=session, lock=True):
                raise AlreadyAssigned(
                    "That RTL is already assigned. Reassign it instead, or refresh the page."
                )
            new_id = repo.insert_rtl_assignment(
                session=session, device_uid=device_uid,
                technician_user_id=technician_user_id,
                provenance=PROVENANCE_APPLICATION, assigned_by=actor_id,
            )
            audit_service.record(
                session,
                operation=audit_cfg.RTL_ASSIGNMENT_CREATED,
                entity_type=audit_cfg.ENTITY_RTL_ASSIGNMENT,
                entity_id=str(device_uid),
                old_values=None,
                new_values={"assignment_id": new_id, "device_uid": device_uid,
                            "technician_user_id": technician_user_id,
                            "provenance": PROVENANCE_APPLICATION},
                actor_user_id=actor_id,
            )
            return new_id
    except IntegrityError as exc:
        # Two concurrent assigns: the partial unique index let only one win.
        raise AlreadyAssigned(
            "That RTL was just assigned by someone else. Refresh the page."
        ) from exc


def reassign(
    device_uid: int,
    new_technician_user_id: int,
    *,
    expected_assignment_id: int,
    actor: AuthenticatedUser | None,
    registered_fetch: Callable[[], set[int]] = _registered_uids,
) -> int:
    """Atomically move an assigned RTL to another Technician. Returns the new id.

    ``expected_assignment_id`` is the current assignment the operator saw. If
    the RTL has since been reassigned or unassigned, nothing is written.
    """
    actor_id = _require_admin(actor)
    try:
        with session_scope() as session:
            _check_target(device_uid, new_technician_user_id, session, registered_fetch)
            current = repo.get_current_rtl_assignment(device_uid, session=session, lock=True)
            if current is None or current.assignment_id != expected_assignment_id:
                raise StaleAssignment(
                    "This RTL's assignment has changed since the page was loaded. "
                    "Refresh and try again."
                )
            if current.technician_user_id == new_technician_user_id:
                raise SameTechnician("That RTL is already assigned to this Technician.")
            if not repo.end_rtl_assignment(
                session=session, assignment_id=current.assignment_id, ended_by=actor_id
            ):
                raise StaleAssignment("This RTL's assignment has already been ended. Refresh.")
            new_id = repo.insert_rtl_assignment(
                session=session, device_uid=device_uid,
                technician_user_id=new_technician_user_id,
                provenance=PROVENANCE_APPLICATION, assigned_by=actor_id,
            )
            old = _snapshot(current)
            audit_service.record(
                session, operation=audit_cfg.RTL_ASSIGNMENT_ENDED,
                entity_type=audit_cfg.ENTITY_RTL_ASSIGNMENT, entity_id=str(device_uid),
                old_values=old, new_values={"reason": "reassigned"}, actor_user_id=actor_id,
            )
            audit_service.record(
                session, operation=audit_cfg.RTL_ASSIGNMENT_REASSIGNED,
                entity_type=audit_cfg.ENTITY_RTL_ASSIGNMENT, entity_id=str(device_uid),
                old_values=old,
                new_values={"assignment_id": new_id, "device_uid": device_uid,
                            "technician_user_id": new_technician_user_id,
                            "provenance": PROVENANCE_APPLICATION},
                actor_user_id=actor_id,
            )
            return new_id
    except IntegrityError as exc:
        raise StaleAssignment(
            "This RTL was just changed by someone else. Refresh and try again."
        ) from exc


def end_assignment(
    device_uid: int, *, expected_assignment_id: int, actor: AuthenticatedUser | None
) -> None:
    """End an assignment, leaving the RTL unassigned. History is retained."""
    actor_id = _require_admin(actor)
    with session_scope() as session:
        current = repo.get_current_rtl_assignment(device_uid, session=session, lock=True)
        if current is None or current.assignment_id != expected_assignment_id:
            raise StaleAssignment("This RTL's assignment has changed. Refresh and try again.")
        repo.end_rtl_assignment(session=session, assignment_id=current.assignment_id,
                                ended_by=actor_id)
        audit_service.record(
            session, operation=audit_cfg.RTL_ASSIGNMENT_ENDED,
            entity_type=audit_cfg.ENTITY_RTL_ASSIGNMENT, entity_id=str(device_uid),
            old_values=_snapshot(current), new_values={"reason": "unassigned"},
            actor_user_id=actor_id,
        )


# --------------------------------------------------------------------------
# Reads for the Administrator page
# --------------------------------------------------------------------------

class AssignmentView(str, Enum):
    ALL = "all"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"


@dataclass(frozen=True)
class AssignmentRow:
    """One registered RTL and, if any, its current Technician."""

    device_uid: int
    transformer_codes: tuple[str, ...]
    assignment_id: int | None
    technician_user_id: int | None
    technician_name: str | None
    provenance: str | None
    since: datetime | None  # assigned_at (APPLICATION) or imported_at (LEGACY_IMPORT)
    since_is_import: bool

    @property
    def is_assigned(self) -> bool:
        return self.assignment_id is not None


@dataclass(frozen=True)
class AssignmentOverview:
    available: bool
    rows: tuple[AssignmentRow, ...] = ()

    @property
    def assigned_count(self) -> int:
        return sum(r.is_assigned for r in self.rows)

    @property
    def unassigned_count(self) -> int:
        return len(self.rows) - self.assigned_count


def get_assignment_overview(
    *, network_fetch=network.get_current_network,
    assignments_fetch=repo.list_current_rtl_assignments,
) -> AssignmentOverview:
    """Every registered RTL joined to its open assignment (one read of each)."""
    current = network_fetch()
    if current.status is not network.NetworkStatus.DATA:
        return AssignmentOverview(available=False)
    by_uid = {a.device_uid: a for a in assignments_fetch()}
    rows = []
    for net_row in sorted(current.rows, key=lambda r: r.device_uid):
        a = by_uid.get(net_row.device_uid)
        legacy = a is not None and a.provenance == PROVENANCE_LEGACY_IMPORT
        rows.append(AssignmentRow(
            device_uid=net_row.device_uid,
            transformer_codes=tuple(net_row.mapping_codes),
            assignment_id=a.assignment_id if a else None,
            technician_user_id=a.technician_user_id if a else None,
            technician_name=a.technician_name if a else None,
            provenance=a.provenance if a else None,
            since=(a.imported_at if legacy else a.assigned_at) if a else None,
            since_is_import=legacy,
        ))
    return AssignmentOverview(True, tuple(rows))


def filter_rows(
    rows, *, view: str = AssignmentView.ALL.value, technician_user_id: int | None = None,
    uid_text: str | None = None,
) -> tuple[AssignmentRow, ...]:
    """Pure filter. A UID search is a substring match on the digits."""
    out = tuple(rows)
    if view == AssignmentView.ASSIGNED.value:
        out = tuple(r for r in out if r.is_assigned)
    elif view == AssignmentView.UNASSIGNED.value:
        out = tuple(r for r in out if not r.is_assigned)
    if technician_user_id is not None:
        out = tuple(r for r in out if r.technician_user_id == technician_user_id)
    needle = (uid_text or "").strip()
    if needle:
        out = tuple(r for r in out if needle in str(r.device_uid))
    return out


def get_assignment_history(device_uid: int) -> list[RtlAssignmentRecord]:
    return repo.list_rtl_assignment_history(device_uid)


def list_technician_options() -> list[tuple[int, str]]:
    """(user_id, label) for every active Technician."""
    return [(uid, name) for uid, _username, name, _pid in repo.list_active_technician_users()]


def to_payload(rows) -> list[dict]:
    """JSON-safe rows for a dcc.Store (filtering then needs no further reads)."""
    return [
        {"uid": r.device_uid, "codes": list(r.transformer_codes),
         "assignment_id": r.assignment_id, "tech_id": r.technician_user_id,
         "tech": r.technician_name, "prov": r.provenance,
         "since": r.since.isoformat() if r.since else None, "import": r.since_is_import}
        for r in rows
    ]


def from_payload(payload) -> tuple[AssignmentRow, ...]:
    return tuple(
        AssignmentRow(
            device_uid=int(p["uid"]), transformer_codes=tuple(p["codes"]),
            assignment_id=p["assignment_id"], technician_user_id=p["tech_id"],
            technician_name=p["tech"], provenance=p["prov"],
            since=datetime.fromisoformat(p["since"]) if p["since"] else None,
            since_is_import=bool(p["import"]),
        )
        for p in (payload or [])
    )
