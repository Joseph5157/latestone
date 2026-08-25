"""Technician-to-device assignment store — backed by
plant_monitoring.user_device_assignments (DB-3).

Replaces callbacks/device_assign.py's in-memory
``_mock_technician_assignments`` dict. Technician identity at this boundary
(and above) stays a plain username string; the repository resolves that to
``users.user_id`` internally, matching the pattern already established for
identifier/email_address in services/prototype_users.py.

Only technician-device assignment is wired here. The asset (device ->
transformer) mock in callbacks/device_assign.py is a separate, deliberately
unchanged concept — see that module's docstring.

AUD-1: assignment and unassignment write audit rows in the SAME transaction
as the mutation. Entity id is the stable device_id (review decision), with
assignment ids and technician details inside old/new values. A genuine
no-op (assigning the technician who already holds the device) writes NO
audit row (decision D1) — this is an activity/state-change audit, not an
attempted-action log.
"""
from __future__ import annotations

import logging

from config import audit as audit_cfg
from db.engine import session_scope
from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import AssignmentRecord
from services import audit_service

logger = logging.getLogger(__name__)


def _snapshot(record: AssignmentRecord) -> dict:
    """Audit allowlist for an assignment row (never dump the dataclass)."""
    return {
        "assignment_id": record.assignment_id,
        "technician_user_id": record.user_id,
        "technician_username": record.username,
    }


def get_assigned_technician(device_id: str) -> str | None:
    """Return the username of the device's active technician, or None."""
    assignment = repo.get_active_device_assignment(device_id)
    return assignment.username if assignment else None


def assign_technician(
    device_id: str,
    technician_username: str,
    *,
    actor_user_id: int,
) -> None:
    """Assign (or reassign) a device to a technician, auditing the change.

    Raises ValueError if technician_username does not name an active
    technician — callers should treat that as an unexpected/prototype-only
    edge case, since the UI dropdown only ever offers valid technicians.
    """
    try:
        with session_scope() as session:
            change = repo.assign_device_to_user(
                device_id,
                technician_username,
                assigned_by_user_id=actor_user_id,
                session=session,
                with_change_info=True,
            )
            if not change.changed:
                return  # genuine no-op: no state change, no audit row (D1)
            audit_service.record(
                session,
                operation=audit_cfg.DEVICE_ASSIGNED,
                entity_type=audit_cfg.ENTITY_ASSIGNMENT,
                entity_id=device_id,
                old_values=_snapshot(change.previous)
                if change.previous is not None
                else None,
                new_values=_snapshot(change.current),
                actor_user_id=actor_user_id,
            )
    except audit_service.AuditError as exc:
        logger.error(
            "Audit failure blocked technician assignment: device=%s "
            "technician=%s actor=%s",
            device_id,
            technician_username,
            actor_user_id,
        )
        raise ValueError(str(exc)) from exc


def unassign_technician(device_id: str, *, actor_user_id: int) -> None:
    """Clear the device's active technician assignment, if any.

    Nothing assigned means nothing changed: silent no-op, no audit row.
    """
    try:
        with session_scope() as session:
            closed = repo.end_active_device_assignment(device_id, session=session)
            if not closed:
                return
            # Partial unique index guarantees at most one active row; if
            # that invariant ever yields more, audit each closed row rather
            # than silently dropping history.
            for record in closed:
                audit_service.record(
                    session,
                    operation=audit_cfg.DEVICE_UNASSIGNED,
                    entity_type=audit_cfg.ENTITY_ASSIGNMENT,
                    entity_id=device_id,
                    old_values=_snapshot(record),
                    new_values=None,
                    actor_user_id=actor_user_id,
                )
    except audit_service.AuditError as exc:
        logger.error(
            "Audit failure blocked technician unassignment: device=%s actor=%s",
            device_id,
            actor_user_id,
        )
        raise ValueError(str(exc)) from exc


def list_devices_for_technician(username: str) -> list[str]:
    """Device ids currently assigned to a technician."""
    return repo.list_devices_for_technician(username)


def clear_all_assignments() -> None:
    """Reset the assignment store (for testing)."""
    repo.delete_all_assignments()
