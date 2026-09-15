"""Scoped, read-only RTL programming activity.

This service deliberately exposes the existing request/command history; it
does not dispatch a command, select a transport, or claim that a physical RTL
received anything.  Authorization belongs at the callback boundary, where the
trusted session identity is available.  The supplied ``DeviceScope`` then
constrains this reader in both Python and SQL.
"""
from __future__ import annotations

import logging

from repositories import plant_monitoring_repository as repo
from repositories.plant_monitoring_repository import (
    DeviceAuditHistoryRecord,
    ProgrammingActivityRecord,
)
from services.device_scope import DeviceScope

logger = logging.getLogger(__name__)

DEFAULT_ACTIVITY_LIMIT = 10


class ProgrammingActivityError(Exception):
    """A safe failure to load programming activity for presentation."""


def recent_activity(
    device_id: str,
    *,
    scope: DeviceScope,
    limit: int = DEFAULT_ACTIVITY_LIMIT,
) -> list[ProgrammingActivityRecord]:
    """Return recent-first activity for one RTL only when it is in scope.

    The early return is intentional: a device identifier supplied by a URL or
    Dash component state must never cause a query outside the resolved scope.
    The repository repeats the same scope in SQL, so a future multi-device
    caller can reuse this contract without introducing post-query filtering.
    """
    if not isinstance(device_id, str) or not device_id or not scope.allows(device_id):
        return []

    try:
        return repo.list_programming_activity(
            [device_id],
            allowed_device_ids=scope.device_ids,
            limit_per_device=limit,
        )
    except Exception as exc:
        logger.exception("Failed to load programming activity for device %s", device_id)
        raise ProgrammingActivityError(
            "Programming activity could not be loaded. Please try again."
        ) from exc


def recent_audit_history(
    device_id: str,
    *,
    scope: DeviceScope,
    limit: int = DEFAULT_ACTIVITY_LIMIT,
) -> list[DeviceAuditHistoryRecord]:
    """Return an authorized RTL's persisted audit entries, newest first.

    This is a read-only companion to ``recent_activity``.  Its duplicate
    early scope check is intentional: an unassigned URL/device id cannot
    cause even an audit query, while the repository repeats the constraint in
    SQL for defence in depth and future batched callers.
    """
    if not isinstance(device_id, str) or not device_id or not scope.allows(device_id):
        return []

    try:
        return repo.list_device_audit_history(
            [device_id],
            allowed_device_ids=scope.device_ids,
            limit_per_device=limit,
        )
    except Exception as exc:
        logger.exception("Failed to load device audit history for device %s", device_id)
        raise ProgrammingActivityError(
            "Command and audit history could not be loaded. Please try again."
        ) from exc


__all__ = [
    "DEFAULT_ACTIVITY_LIMIT",
    "ProgrammingActivityError",
    "recent_audit_history",
    "recent_activity",
]
