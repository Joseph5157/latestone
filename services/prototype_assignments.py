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
"""
from __future__ import annotations

import logging

from repositories import plant_monitoring_repository as repo

logger = logging.getLogger(__name__)


def get_assigned_technician(device_id: str) -> str | None:
    """Return the username of the device's active technician, or None."""
    assignment = repo.get_active_device_assignment(device_id)
    return assignment.username if assignment else None


def assign_technician(
    device_id: str, technician_username: str, assigned_by_username: str | None = None
) -> None:
    """Assign (or reassign) a device to a technician.

    Raises ValueError if technician_username does not name an active
    technician — callers should treat that as an unexpected/prototype-only
    edge case, since the UI dropdown only ever offers valid technicians.
    """
    repo.assign_device_to_user(device_id, technician_username, assigned_by_username)


def unassign_technician(device_id: str) -> None:
    """Clear the device's active technician assignment, if any (no-op otherwise)."""
    repo.end_active_device_assignment(device_id)


def list_devices_for_technician(username: str) -> list[str]:
    """Device ids currently assigned to a technician."""
    return repo.list_devices_for_technician(username)


def clear_all_assignments() -> None:
    """Reset the assignment store (for testing)."""
    repo.delete_all_assignments()
